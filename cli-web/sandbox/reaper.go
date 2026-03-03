package sandbox

import (
	"context"
	"log"
	"time"
)

const (
	DefaultIdleTimeout = 15 * time.Minute
	ReapInterval       = 1 * time.Minute
)

// Reaper periodically checks for idle containers and stops them.
type Reaper struct {
	sandbox    *DockerSandbox
	storage    *LocalStorage
	idleAfter  time.Duration
	stopCh     chan struct{}
}

func NewReaper(sb *DockerSandbox, storage *LocalStorage, idleAfter time.Duration) *Reaper {
	if idleAfter == 0 {
		idleAfter = DefaultIdleTimeout
	}
	return &Reaper{
		sandbox:   sb,
		storage:   storage,
		idleAfter: idleAfter,
		stopCh:    make(chan struct{}),
	}
}

func (r *Reaper) Start() {
	go r.loop()
}

func (r *Reaper) Stop() {
	close(r.stopCh)
}

func (r *Reaper) loop() {
	ticker := time.NewTicker(ReapInterval)
	defer ticker.Stop()

	for {
		select {
		case <-r.stopCh:
			return
		case <-ticker.C:
			r.reap()
		}
	}
}

func (r *Reaper) reap() {
	ctx := context.Background()
	sessions, err := r.sandbox.List(ctx)
	if err != nil {
		return
	}

	now := time.Now()
	for _, s := range sessions {
		if s.Status != "running" {
			continue
		}
		meta, err := r.storage.GetMeta(ctx, s.ID)
		if err != nil {
			continue
		}

		lastActive := meta.LastActivityAt
		if lastActive.IsZero() {
			lastActive = meta.CreatedAt
		}

		if now.Sub(lastActive) > r.idleAfter {
			log.Printf("reaper: stopping idle session %s (idle %s)", s.ID[:8], now.Sub(lastActive).Round(time.Second))
			r.sandbox.Stop(ctx, s.ID)
		}
	}
}
