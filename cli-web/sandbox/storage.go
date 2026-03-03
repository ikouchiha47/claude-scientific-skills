package sandbox

import (
	"context"
	"io"
	"time"
)

// SessionStorage persists session state. Implementations are swappable via DI.
type SessionStorage interface {
	Save(ctx context.Context, sessionID string) error
	Load(ctx context.Context, sessionID string) error
	Export(ctx context.Context, sessionID string, w io.Writer) error
	Import(ctx context.Context, sessionID string, r io.Reader) error
	List(ctx context.Context) ([]StoredSession, error)
	Delete(ctx context.Context, sessionID string) error
}

// StoredSession is metadata about a persisted session.
type StoredSession struct {
	ID             string
	Tool           string
	Size           int64
	CreatedAt      time.Time
	UpdatedAt      time.Time
	LastActivityAt time.Time
}
