package sandbox

import (
	"context"
	"io"
	"time"
)

// Sandbox manages isolated container sessions for AI coding tools.
type Sandbox interface {
	Create(ctx context.Context, opts CreateOpts) (*Session, error)
	Exec(ctx context.Context, sessionID string, cmd []string) (io.ReadCloser, error)
	Stop(ctx context.Context, sessionID string) error
	Remove(ctx context.Context, sessionID string) error
	List(ctx context.Context) ([]Session, error)
}

// CreateOpts configures a new sandbox session.
type CreateOpts struct {
	Tool      string            // "claude", "opencode", "codex", "bash"
	Workspace string            // host project dir to mount
	Env       map[string]string // merged env: API keys + tool-specific vars
	SessionID string            // our generated ID
}


// Session represents a running or stopped sandbox.
type Session struct {
	ID          string
	ContainerID string
	Tool        string
	Status      string // "running", "stopped", "exited"
	CreatedAt   time.Time
}
