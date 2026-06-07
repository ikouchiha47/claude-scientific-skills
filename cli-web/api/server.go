package api

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"sync"
	"time"

	"github.com/aibusiness/cli-web/cli"
	"github.com/aibusiness/cli-web/sandbox"
	"github.com/docker/docker/pkg/stdcopy"
	"github.com/google/uuid"
)

// Server is the HTTP API for managing sandbox sessions.
type Server struct {
	mux            *http.ServeMux
	sandbox        *sandbox.DockerSandbox
	storage        *sandbox.LocalStorage
	jobs           *JobManager
	messages       MessageStorage
	chroma         *ChromaClient  // semantic search (also implements MessageStorage)
	defaultModel     string         // e.g. "xai/grok-4-1-fast-non-reasoning"
	defaultWorkspace string         // project root for containers
	openCodeConfig map[string]any // loaded opencode.json (model catalog, served to UI)
	creds          CredsFile      // loaded opencode.creds.json (default API keys)
}

// ServerConfig holds all configuration for the API server.
type ServerConfig struct {
	OpenCodeConfigPath string
	CredsPath          string
	DefaultModel       string
	DefaultWorkspace   string
	ChromaDir          string
	OllamaURL          string
	EmbeddingModel     string
}

func NewServer(sb *sandbox.DockerSandbox, storage *sandbox.LocalStorage, cfg ServerConfig) *Server {
	s := &Server{
		mux:              http.NewServeMux(),
		sandbox:          sb,
		storage:          storage,
		jobs:             NewJobManager(sb),
		defaultModel:     cfg.DefaultModel,
		defaultWorkspace: cfg.DefaultWorkspace,
	}

	// SQLite for all message storage
	dbPath := filepath.Join(storage.BaseDir, "messages.db")
	sqliteStore, err := NewSQLiteMessageStore(dbPath)
	if err != nil {
		log.Printf("warning: sqlite message store failed: %v, falling back to JSON", err)
		s.messages = NewMessageStore(storage.BaseDir)
	} else {
		s.messages = sqliteStore
		log.Printf("SQLite message store enabled (%s)", dbPath)
	}

	// ChromaDB for semantic search only (not message storage)
	if cfg.ChromaDir != "" {
		s.chroma = NewChromaClient(cfg.ChromaDir, cfg.OllamaURL, cfg.EmbeddingModel)
		if s.chroma != nil {
			log.Printf("ChromaDB enabled for semantic search (persist=%s, ollama=%s, model=%s)", cfg.ChromaDir, cfg.OllamaURL, cfg.EmbeddingModel)
		}
	}

	if ocCfg, err := LoadOpenCodeConfig(cfg.OpenCodeConfigPath); err != nil {
		log.Printf("warning: %v", err)
	} else {
		s.openCodeConfig = ocCfg
	}
	if creds, err := LoadCreds(cfg.CredsPath); err != nil {
		log.Printf("warning: %v", err)
	} else {
		s.creds = creds
	}

	s.routes()
	return s
}

func (s *Server) routes() {
	s.mux.HandleFunc("POST /sessions", s.handleCreate)
	s.mux.HandleFunc("GET /sessions", s.handleList)
	s.mux.HandleFunc("POST /sessions/{id}/exec", s.handleExec)
	s.mux.HandleFunc("POST /sessions/{id}/stop", s.handleStop)
	s.mux.HandleFunc("DELETE /sessions/{id}", s.handleRemove)
	s.mux.HandleFunc("GET /sessions/{id}/export", s.handleExport)

	// Messages
	s.mux.HandleFunc("GET /sessions/{id}/messages", s.handleGetMessages)
	s.mux.HandleFunc("POST /sessions/{id}/messages", s.handlePostMessage)

	// Semantic search across messages
	s.mux.HandleFunc("POST /search", s.handleSearch)

	// Config — UI reads this for model picker
	s.mux.HandleFunc("GET /config/models", s.handleGetModels)

	// File browser — list and read files from container
	s.mux.HandleFunc("GET /sessions/{id}/files", s.handleFileList)
	s.mux.HandleFunc("GET /sessions/{id}/files/content", s.handleFileContent)
	s.mux.HandleFunc("GET /sessions/{id}/files/raw", s.handleFileRaw)

	// Long-running jobs with SSE streaming
	s.mux.HandleFunc("GET /sessions/{id}/jobs", s.handleSessionJobs)
	s.mux.HandleFunc("POST /sessions/{id}/jobs", s.handleJobCreate)
	s.mux.HandleFunc("GET /sessions/{id}/jobs/{jobID}", s.handleJobStatus)
	s.mux.HandleFunc("GET /sessions/{id}/jobs/{jobID}/stream", s.handleJobStream)
	s.mux.HandleFunc("GET /jobs", s.handleJobList)
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}
	s.mux.ServeHTTP(w, r)
}

func (s *Server) ListenAndServe(addr string) error {
	log.Printf("API server listening on %s", addr)
	return http.ListenAndServe(addr, s)
}

// --- Handlers ---

type createReq struct {
	Tool      string            `json:"tool"`
	Workspace string            `json:"workspace"`
	Model     string            `json:"model,omitempty"`     // e.g. "anthropic/claude-haiku-4-5"
	Config    cli.ToolConfig    `json:"config"`
	BYOKeys   map[string]string `json:"byo_keys,omitempty"` // provider → user's own key
}

func (s *Server) handleCreate(w http.ResponseWriter, r *http.Request) {
	var req createReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		httpErr(w, http.StatusBadRequest, err.Error())
		return
	}
	if req.Tool == "" {
		req.Tool = "bash"
	}

	tool, ok := cli.Get(req.Tool)
	if !ok {
		httpErr(w, http.StatusBadRequest, "unknown tool: "+req.Tool)
		return
	}

	sessionID := uuid.New().String()
	if err := s.storage.Save(r.Context(), sessionID); err != nil {
		httpErr(w, http.StatusInternalServerError, err.Error())
		return
	}

	sessDir := filepath.Join(s.storage.BaseDir, sessionID)

	// If no explicit opencode_config, use the default opencode.json
	if req.Config.OpenCodeConfig == nil && s.openCodeConfig != nil {
		req.Config.OpenCodeConfig = s.openCodeConfig
	}

	// Override model if provided at top level
	if req.Model != "" {
		req.Config.Model = req.Model
	}

	// Apply default model (provider/model format, e.g. "xai/grok-4-1-fast-non-reasoning")
	if req.Config.Model == "" && s.defaultModel != "" {
		req.Config.Model = s.defaultModel
	}

	// Write tool config files into session dir
	for relPath, content := range tool.ConfigFiles(req.Config) {
		absPath := filepath.Join(sessDir, relPath)
		if err := os.MkdirAll(filepath.Dir(absPath), 0o755); err != nil {
			httpErr(w, http.StatusInternalServerError, "mkdir config: "+err.Error())
			return
		}
		if err := os.WriteFile(absPath, []byte(content), 0o644); err != nil {
			httpErr(w, http.StatusInternalServerError, "write config: "+err.Error())
			return
		}
	}

	// Resolve API keys: defaults from creds file, overridden by BYOK
	apiKeys := ResolveAPIKeys(s.creds, req.BYOKeys)

	// Merge into tool config so BuildEnv can use them
	if req.Config.APIKeys == nil {
		req.Config.APIKeys = map[string]string{}
	}
	for k, v := range apiKeys {
		// BYOK / default — only set if not already explicitly in config
		if _, exists := req.Config.APIKeys[k]; !exists {
			req.Config.APIKeys[k] = v
		}
	}

	// Build env
	env := map[string]string{
		"HOME":       "/session",
		"MEMORY_DIR": "/workspace/.memory",
	}
	for k, v := range tool.BuildEnv(req.Config) {
		env[k] = v
	}

	workspace := req.Workspace
	if workspace == "" {
		workspace = s.defaultWorkspace
	}
	if workspace == "" {
		workspace, _ = os.Getwd()
	}

	sess, err := s.sandbox.Create(r.Context(), sandbox.CreateOpts{
		Tool:      req.Tool,
		Workspace: workspace,
		Env:       env,
		SessionID: sessionID,
	})
	if err != nil {
		httpErr(w, http.StatusInternalServerError, err.Error())
		return
	}

	jsonResp(w, http.StatusCreated, sess)
}

func (s *Server) handleGetModels(w http.ResponseWriter, _ *http.Request) {
	resp := map[string]any{
		"default_model": s.defaultModel,
	}
	if s.openCodeConfig != nil {
		if providers, ok := s.openCodeConfig["provider"]; ok {
			resp["providers"] = providers
		}
	}
	jsonResp(w, http.StatusOK, resp)
}

func (s *Server) handleGetMessages(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	msgs, err := s.messages.List(r.Context(), id)
	if err != nil {
		httpErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	jsonResp(w, http.StatusOK, msgs)
}

type sendMessageReq struct {
	Content string   `json:"content"`
	Cmd     []string `json:"cmd"` // pre-built command, or we build from content + tool
	Model   string   `json:"model,omitempty"`
}

func (s *Server) handlePostMessage(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("id")
	var req sendMessageReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		httpErr(w, http.StatusBadRequest, err.Error())
		return
	}

	// Touch session activity
	s.storage.Touch(r.Context(), sessionID)

	// Save user message
	userMsg := Message{Role: "user", Content: req.Content, ContentType: "text", SessionID: sessionID}
	if err := s.messages.Append(r.Context(), userMsg); err != nil {
		httpErr(w, http.StatusInternalServerError, "save message: "+err.Error())
		return
	}
	if s.chroma != nil {
		s.chroma.Append(r.Context(), userMsg) // index for search, ignore error
	}

	// Build command if not provided
	cmd := req.Cmd
	if len(cmd) == 0 {
		// Find the session's tool
		sessions, _ := s.sandbox.List(r.Context())
		tool := "opencode"
		for _, sess := range sessions {
			if sess.ID == sessionID {
				tool = sess.Tool
				break
			}
		}
		model := req.Model
		if model == "" {
			model = s.defaultModel
		}

		switch tool {
		case "bash":
			cmd = []string{"bash", "-c", req.Content}
		case "claude":
			cmd = []string{"claude", "-p", req.Content}
			if model != "" {
				// Claude uses just the model name, not provider/model
				parts := splitModel(model)
				cmd = append(cmd, "--model", parts[1])
			}
		default: // opencode
			cmd = []string{"opencode"}
			if model != "" {
				cmd = append(cmd, "-m", model)
			}
			cmd = append(cmd, "run", req.Content)
		}
	}

	// Ensure container is running (auto-restart if stopped/exited)
	if err := s.sandbox.EnsureRunning(r.Context(), sessionID); err != nil {
		httpErr(w, http.StatusInternalServerError, "restart container: "+err.Error())
		return
	}

	// Start job — tee output to SQLite periodically
	msgStore := s.messages
	sqliteStore, hasSqlite := s.messages.(*SQLiteMessageStore)
	chromaStore := s.chroma
	sessionStorage := s.storage
	job := s.jobs.Start(sessionID, cmd, req.Content)
	go func() {
		ch := job.Subscribe()
		defer job.Unsubscribe(ch)

		var mu sync.Mutex
		var stdout, stderr string
		var stdoutRowID, stderrRowID int64
		dirty := false
		ctx := context.Background()
		ts := time.Now()

		flush := func() {
			mu.Lock()
			curOut, curErr := stdout, stderr
			wasDirty := dirty
			dirty = false
			mu.Unlock()

			if !wasDirty || sqliteStore == nil {
				return
			}

			if curOut != "" {
				id, err := sqliteStore.Upsert(ctx, stdoutRowID, Message{
					Role: "assistant", Content: curOut, ContentType: "text",
					SessionID: sessionID, Timestamp: ts,
				})
				if err != nil {
					log.Printf("ERROR: flush stdout: %v", err)
				} else {
					stdoutRowID = id
				}
			}
			if curErr != "" {
				id, err := sqliteStore.Upsert(ctx, stderrRowID, Message{
					Role: "assistant", Content: curErr, ContentType: "stderr",
					SessionID: sessionID, Timestamp: ts,
				})
				if err != nil {
					log.Printf("ERROR: flush stderr: %v", err)
				} else {
					stderrRowID = id
				}
			}
		}

		ticker := time.NewTicker(3 * time.Second)
		defer ticker.Stop()

		done := false
		for !done {
			select {
			case ev, ok := <-ch:
				if !ok {
					done = true
					break
				}
				mu.Lock()
				if ev.Stream == "stderr" {
					stderr += ev.Data + "\n"
				} else {
					stdout += ev.Data + "\n"
				}
				dirty = true
				mu.Unlock()
			case <-ticker.C:
				flush()
				sessionStorage.Touch(ctx, sessionID)
			}
		}

		// Final flush
		flush()

		// Fallback: if not SQLite, use Append for final write
		mu.Lock()
		finalStdout, finalStderr := stdout, stderr
		mu.Unlock()
		if !hasSqlite {
			if finalStdout != "" {
				msgStore.Append(ctx, Message{Role: "assistant", Content: finalStdout, ContentType: "text", SessionID: sessionID, Timestamp: ts})
			}
			if finalStderr != "" {
				msgStore.Append(ctx, Message{Role: "assistant", Content: finalStderr, ContentType: "stderr", SessionID: sessionID, Timestamp: ts})
			}
		}
		// Index stdout in ChromaDB for semantic search (skip stderr)
		if finalStdout != "" && chromaStore != nil {
			if err := chromaStore.Append(ctx, Message{
				Role: "assistant", Content: finalStdout, ContentType: "text",
				SessionID: sessionID, Timestamp: ts,
			}); err != nil {
				log.Printf("WARNING: chroma index failed: %v", err)
			}
		}
	}()

	jsonResp(w, http.StatusCreated, map[string]string{
		"job_id":     job.ID,
		"session_id": sessionID,
	})
}

func splitModel(model string) [2]string {
	for i, c := range model {
		if c == '/' {
			return [2]string{model[:i], model[i+1:]}
		}
	}
	return [2]string{"", model}
}

func (s *Server) handleList(w http.ResponseWriter, r *http.Request) {
	sessions, err := s.sandbox.List(r.Context())
	if err != nil {
		httpErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	jsonResp(w, http.StatusOK, sessions)
}

type execReq struct {
	Cmd []string `json:"cmd"`
}

type execResp struct {
	Output string `json:"output"`
}

func (s *Server) handleExec(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	var req execReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		httpErr(w, http.StatusBadRequest, err.Error())
		return
	}
	if len(req.Cmd) == 0 {
		httpErr(w, http.StatusBadRequest, "cmd required")
		return
	}

	reader, err := s.sandbox.Exec(r.Context(), id, req.Cmd)
	if err != nil {
		httpErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	output, err := sandbox.ReadAll(reader)
	if err != nil {
		httpErr(w, http.StatusInternalServerError, "reading exec output: "+err.Error())
		return
	}
	jsonResp(w, http.StatusOK, execResp{Output: output})
}

func (s *Server) handleStop(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	if err := s.sandbox.Stop(r.Context(), id); err != nil {
		httpErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	jsonResp(w, http.StatusOK, map[string]string{"status": "stopped"})
}

func (s *Server) handleRemove(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	s.sandbox.Remove(r.Context(), id)
	s.messages.Delete(r.Context(), id)
	s.storage.Delete(r.Context(), id)
	jsonResp(w, http.StatusOK, map[string]string{"status": "removed"})
}

type searchReq struct {
	Query     string `json:"query"`
	SessionID string `json:"session_id,omitempty"`
	K         int    `json:"k,omitempty"`
}

func (s *Server) handleSearch(w http.ResponseWriter, r *http.Request) {
	if s.chroma == nil {
		httpErr(w, http.StatusServiceUnavailable, "semantic search not available (ChromaDB not connected)")
		return
	}

	var req searchReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		httpErr(w, http.StatusBadRequest, err.Error())
		return
	}
	if req.K == 0 {
		req.K = 10
	}

	results, err := s.chroma.Search(r.Context(), req.Query, req.SessionID, req.K)
	if err != nil {
		httpErr(w, http.StatusInternalServerError, "search: "+err.Error())
		return
	}
	jsonResp(w, http.StatusOK, map[string]any{"results": results})
}

func (s *Server) handleExport(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	w.Header().Set("Content-Type", "application/gzip")
	w.Header().Set("Content-Disposition", "attachment; filename="+id+".tar.gz")
	if err := s.storage.Export(r.Context(), id, w); err != nil {
		httpErr(w, http.StatusInternalServerError, err.Error())
	}
}

// --- Job handlers ---

type jobCreateReq struct {
	Cmd         []string `json:"cmd"`
	Description string   `json:"description"`
}

func (s *Server) handleJobCreate(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("id")
	var req jobCreateReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		httpErr(w, http.StatusBadRequest, err.Error())
		return
	}
	if len(req.Cmd) == 0 {
		httpErr(w, http.StatusBadRequest, "cmd required")
		return
	}

	job := s.jobs.Start(sessionID, req.Cmd, req.Description)
	jsonResp(w, http.StatusCreated, job.Info())
}

func (s *Server) handleJobStatus(w http.ResponseWriter, r *http.Request) {
	jobID := r.PathValue("jobID")
	job, ok := s.jobs.Get(jobID)
	if !ok {
		httpErr(w, http.StatusNotFound, "job not found")
		return
	}
	jsonResp(w, http.StatusOK, job.Info())
}

func (s *Server) handleJobStream(w http.ResponseWriter, r *http.Request) {
	jobID := r.PathValue("jobID")
	job, ok := s.jobs.Get(jobID)
	if !ok {
		httpErr(w, http.StatusNotFound, "job not found")
		return
	}

	flusher, ok := w.(http.Flusher)
	if !ok {
		httpErr(w, http.StatusInternalServerError, "streaming not supported")
		return
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	ch := job.Subscribe()
	defer job.Unsubscribe(ch)

	for {
		select {
		case ev, ok := <-ch:
			if !ok {
				data, _ := json.Marshal(map[string]string{"event": "done", "status": job.Status})
				w.Write([]byte("data: " + string(data) + "\n\n"))
				flusher.Flush()
				return
			}
			data, _ := json.Marshal(map[string]string{"event": "output", "stream": ev.Stream, "data": ev.Data})
			w.Write([]byte("data: " + string(data) + "\n\n"))
			flusher.Flush()
		case <-r.Context().Done():
			return
		}
	}
}

func (s *Server) handleSessionJobs(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("id")
	all := s.jobs.List()
	var filtered []JobInfo
	for _, j := range all {
		if j.SessionID == sessionID {
			filtered = append(filtered, j)
		}
	}
	if filtered == nil {
		filtered = []JobInfo{}
	}
	jsonResp(w, http.StatusOK, filtered)
}

func (s *Server) handleJobList(w http.ResponseWriter, r *http.Request) {
	jsonResp(w, http.StatusOK, s.jobs.List())
}

// --- File browser handlers ---

type fileEntry struct {
	Path  string `json:"path"`
	Name  string `json:"name"`
	IsDir bool   `json:"is_dir"`
	Size  int64  `json:"size"`
}

func (s *Server) handleFileList(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("id")
	dir := r.URL.Query().Get("path")
	if dir == "" {
		dir = "/workspace/output"
	}

	// Ensure container is running
	if err := s.sandbox.EnsureRunning(r.Context(), sessionID); err != nil {
		httpErr(w, http.StatusInternalServerError, "container not available: "+err.Error())
		return
	}

	// Use find to list files, excluding .claude, .opencode, .codex, __pycache__, .git
	cmd := []string{"find", dir, "-maxdepth", "4",
		"-not", "-path", "*/.claude/*",
		"-not", "-path", "*/.opencode/*",
		"-not", "-path", "*/.codex/*",
		"-not", "-path", "*/__pycache__/*",
		"-not", "-path", "*/.git/*",
		"-not", "-path", "*/.venv/*",
		"-not", "-path", "*/.ruff_cache/*",
		"-printf", "%y %s %P\n"}

	reader, err := s.sandbox.Exec(r.Context(), sessionID, cmd)
	if err != nil {
		httpErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	output, err := sandbox.ReadAll(reader)
	if err != nil {
		httpErr(w, http.StatusInternalServerError, err.Error())
		return
	}

	var entries []fileEntry
	for _, line := range splitLines(output) {
		if len(line) < 3 || line[1] != ' ' {
			continue
		}
		typeByte := line[0]
		rest := line[2:]
		// Parse "size path"
		spaceIdx := -1
		for i, c := range rest {
			if c == ' ' {
				spaceIdx = i
				break
			}
		}
		if spaceIdx < 0 {
			continue
		}
		sizeStr := rest[:spaceIdx]
		relPath := rest[spaceIdx+1:]
		if relPath == "" {
			continue
		}
		size, _ := strconv.ParseInt(sizeStr, 10, 64)

		name := relPath
		for i := len(relPath) - 1; i >= 0; i-- {
			if relPath[i] == '/' {
				name = relPath[i+1:]
				break
			}
		}

		entries = append(entries, fileEntry{
			Path:  relPath,
			Name:  name,
			IsDir: typeByte == 'd',
			Size:  size,
		})
	}
	if entries == nil {
		entries = []fileEntry{}
	}
	jsonResp(w, http.StatusOK, entries)
}

func (s *Server) handleFileContent(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("id")
	filePath := r.URL.Query().Get("path")
	if filePath == "" {
		httpErr(w, http.StatusBadRequest, "path required")
		return
	}

	// Security: prevent path traversal
	if containsDotDot(filePath) {
		httpErr(w, http.StatusBadRequest, "invalid path")
		return
	}

	// Ensure container is running
	if err := s.sandbox.EnsureRunning(r.Context(), sessionID); err != nil {
		httpErr(w, http.StatusInternalServerError, "container not available: "+err.Error())
		return
	}

	// Read file from container
	cmd := []string{"cat", filePath}
	reader, err := s.sandbox.Exec(r.Context(), sessionID, cmd)
	if err != nil {
		httpErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	output, err := sandbox.ReadAll(reader)
	if err != nil {
		httpErr(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Detect content type from extension
	contentType := "text/plain"
	if len(filePath) > 3 {
		switch {
		case hasSuffix(filePath, ".md"):
			contentType = "text/markdown"
		case hasSuffix(filePath, ".csv"):
			contentType = "text/csv"
		case hasSuffix(filePath, ".json"):
			contentType = "application/json"
		case hasSuffix(filePath, ".py"):
			contentType = "text/x-python"
		case hasSuffix(filePath, ".png"), hasSuffix(filePath, ".jpg"), hasSuffix(filePath, ".jpeg"):
			contentType = "application/octet-stream"
		}
	}

	jsonResp(w, http.StatusOK, map[string]string{
		"content":      output,
		"content_type": contentType,
		"path":         filePath,
	})
}

func (s *Server) handleFileRaw(w http.ResponseWriter, r *http.Request) {
	sessionID := r.PathValue("id")
	filePath := r.URL.Query().Get("path")
	if filePath == "" {
		httpErr(w, http.StatusBadRequest, "path required")
		return
	}
	if containsDotDot(filePath) {
		httpErr(w, http.StatusBadRequest, "invalid path")
		return
	}
	if err := s.sandbox.EnsureRunning(r.Context(), sessionID); err != nil {
		httpErr(w, http.StatusInternalServerError, "container not available: "+err.Error())
		return
	}

	reader, err := s.sandbox.Exec(r.Context(), sessionID, []string{"cat", filePath})
	if err != nil {
		httpErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	defer reader.Close()

	// Detect content type from extension
	ct := "application/octet-stream"
	if hasSuffix(filePath, ".png") {
		ct = "image/png"
	} else if hasSuffix(filePath, ".jpg") || hasSuffix(filePath, ".jpeg") {
		ct = "image/jpeg"
	} else if hasSuffix(filePath, ".svg") {
		ct = "image/svg+xml"
	} else if hasSuffix(filePath, ".gif") {
		ct = "image/gif"
	} else if hasSuffix(filePath, ".pdf") {
		ct = "application/pdf"
	}

	w.Header().Set("Content-Type", ct)
	// Docker multiplexed stream — demux stdout
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	_, copyErr := stdcopy.StdCopy(&stdout, &stderr, reader)
	if copyErr != nil {
		// Fallback: raw stream
		io.Copy(w, reader)
		return
	}
	w.Write(stdout.Bytes())
}

func splitLines(s string) []string {
	var lines []string
	start := 0
	for i := 0; i < len(s); i++ {
		if s[i] == '\n' {
			lines = append(lines, s[start:i])
			start = i + 1
		}
	}
	if start < len(s) {
		lines = append(lines, s[start:])
	}
	return lines
}

func containsDotDot(s string) bool {
	for i := 0; i < len(s)-1; i++ {
		if s[i] == '.' && s[i+1] == '.' {
			return true
		}
	}
	return false
}

func hasSuffix(s, suffix string) bool {
	return len(s) >= len(suffix) && s[len(s)-len(suffix):] == suffix
}

// --- Helpers ---

func jsonResp(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(v)
}

func httpErr(w http.ResponseWriter, code int, msg string) {
	jsonResp(w, code, map[string]string{"error": msg})
}
