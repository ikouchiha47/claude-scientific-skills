package api

import (
	"bufio"
	"context"
	"io"
	"sync"
	"time"

	"github.com/aibusiness/cli-web/sandbox"
	"github.com/docker/docker/pkg/stdcopy"
	"github.com/google/uuid"
)

// JobEvent is a typed line from a running job.
type JobEvent struct {
	Stream string `json:"stream"` // "stdout" or "stderr"
	Data   string `json:"data"`
}

// Job represents a long-running command inside a session container.
type Job struct {
	ID          string    `json:"id"`
	SessionID   string    `json:"session_id"`
	Cmd         []string  `json:"cmd"`
	Description string    `json:"description"`
	Status      string    `json:"status"` // "running", "completed", "failed"
	StartedAt   time.Time `json:"started_at"`
	FinishedAt  time.Time `json:"finished_at,omitempty"`
	Error       string    `json:"error,omitempty"`

	mu          sync.RWMutex
	output      []JobEvent
	subscribers map[chan JobEvent]struct{}
}

// JobInfo is the serializable view of a Job.
type JobInfo struct {
	ID          string    `json:"id"`
	SessionID   string    `json:"session_id"`
	Cmd         []string  `json:"cmd"`
	Description string    `json:"description"`
	Status      string    `json:"status"`
	StartedAt   time.Time `json:"started_at"`
	FinishedAt  time.Time `json:"finished_at,omitempty"`
	Error       string    `json:"error,omitempty"`
	OutputLines int       `json:"output_lines"`
}

func (j *Job) Info() JobInfo {
	j.mu.RLock()
	defer j.mu.RUnlock()
	return JobInfo{
		ID:          j.ID,
		SessionID:   j.SessionID,
		Cmd:         j.Cmd,
		Description: j.Description,
		Status:      j.Status,
		StartedAt:   j.StartedAt,
		FinishedAt:  j.FinishedAt,
		Error:       j.Error,
		OutputLines: len(j.output),
	}
}

func (j *Job) Subscribe() chan JobEvent {
	j.mu.Lock()
	defer j.mu.Unlock()

	ch := make(chan JobEvent, 128)

	// Send buffered output first
	for _, ev := range j.output {
		ch <- ev
	}

	// If already done, close immediately
	if j.Status != "running" {
		close(ch)
		return ch
	}

	j.subscribers[ch] = struct{}{}
	return ch
}

func (j *Job) Unsubscribe(ch chan JobEvent) {
	j.mu.Lock()
	defer j.mu.Unlock()
	delete(j.subscribers, ch)
}

func (j *Job) emit(ev JobEvent) {
	j.mu.Lock()
	defer j.mu.Unlock()
	j.output = append(j.output, ev)
	for ch := range j.subscribers {
		select {
		case ch <- ev:
		default:
			// Slow subscriber — drop
		}
	}
}

func (j *Job) finish(status string, err error) {
	j.mu.Lock()
	defer j.mu.Unlock()
	j.Status = status
	j.FinishedAt = time.Now()
	if err != nil {
		j.Error = err.Error()
	}
	for ch := range j.subscribers {
		close(ch)
	}
	j.subscribers = nil
}

// JobManager tracks all running and completed jobs.
type JobManager struct {
	mu      sync.RWMutex
	jobs    map[string]*Job
	sandbox *sandbox.DockerSandbox
}

func NewJobManager(sb *sandbox.DockerSandbox) *JobManager {
	return &JobManager{
		jobs:    make(map[string]*Job),
		sandbox: sb,
	}
}

func (m *JobManager) Start(sessionID string, cmd []string, description string) *Job {
	job := &Job{
		ID:          uuid.New().String(),
		SessionID:   sessionID,
		Cmd:         cmd,
		Description: description,
		Status:      "running",
		StartedAt:   time.Now(),
		subscribers: make(map[chan JobEvent]struct{}),
	}

	m.mu.Lock()
	m.jobs[job.ID] = job
	m.mu.Unlock()

	go m.run(job)
	return job
}

func (m *JobManager) run(job *Job) {
	ctx := context.Background()
	rawReader, err := m.sandbox.Exec(ctx, job.SessionID, job.Cmd)
	if err != nil {
		job.finish("failed", err)
		return
	}
	defer rawReader.Close()

	// Demux Docker multiplexed stream into separate stdout/stderr pipes
	stdoutPR, stdoutPW := io.Pipe()
	stderrPR, stderrPW := io.Pipe()

	go func() {
		_, err := stdcopy.StdCopy(stdoutPW, stderrPW, rawReader)
		if err != nil {
			stdoutPW.CloseWithError(err)
			stderrPW.CloseWithError(err)
		} else {
			stdoutPW.Close()
			stderrPW.Close()
		}
	}()

	// Scan both streams concurrently, emit typed events
	var wg sync.WaitGroup
	wg.Add(2)

	scanStream := func(r io.Reader, stream string) {
		defer wg.Done()
		scanner := bufio.NewScanner(r)
		scanner.Buffer(make([]byte, 256*1024), 256*1024) // 256KB line buffer
		for scanner.Scan() {
			job.emit(JobEvent{Stream: stream, Data: scanner.Text()})
		}
	}

	go scanStream(stdoutPR, "stdout")
	go scanStream(stderrPR, "stderr")

	wg.Wait()
	job.finish("completed", nil)
}

func (m *JobManager) Get(id string) (*Job, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	j, ok := m.jobs[id]
	return j, ok
}

func (m *JobManager) List() []JobInfo {
	m.mu.RLock()
	defer m.mu.RUnlock()
	infos := make([]JobInfo, 0, len(m.jobs))
	for _, j := range m.jobs {
		infos = append(infos, j.Info())
	}
	return infos
}
