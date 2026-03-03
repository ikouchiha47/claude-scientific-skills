package api

import (
	"context"
	"time"
)

// Message represents a chat message.
type Message struct {
	Role        string    `json:"role"`         // "user", "assistant"
	Content     string    `json:"content"`
	ContentType string    `json:"content_type"` // "text", "file", "image", "code", "stderr"
	SessionID   string    `json:"session_id,omitempty"`
	Timestamp   time.Time `json:"timestamp"`
}

// MessageStorage is the DI interface for message persistence.
type MessageStorage interface {
	Append(ctx context.Context, msg Message) error
	List(ctx context.Context, sessionID string) ([]Message, error)
	Delete(ctx context.Context, sessionID string) error
}
