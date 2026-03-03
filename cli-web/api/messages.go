package api

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// MessageStore is a JSON-file backed implementation of MessageStorage (fallback).
type MessageStore struct {
	mu      sync.RWMutex
	cache   map[string][]Message
	baseDir string
}

func NewMessageStore(baseDir string) *MessageStore {
	return &MessageStore{
		cache:   make(map[string][]Message),
		baseDir: baseDir,
	}
}

func (s *MessageStore) messagesPath(sessionID string) string {
	return filepath.Join(s.baseDir, sessionID, "messages.json")
}

func (s *MessageStore) List(_ context.Context, sessionID string) ([]Message, error) {
	s.mu.RLock()
	if msgs, ok := s.cache[sessionID]; ok {
		s.mu.RUnlock()
		return msgs, nil
	}
	s.mu.RUnlock()

	data, err := os.ReadFile(s.messagesPath(sessionID))
	if err != nil {
		return []Message{}, nil
	}
	var msgs []Message
	if err := json.Unmarshal(data, &msgs); err != nil {
		return []Message{}, nil
	}

	s.mu.Lock()
	s.cache[sessionID] = msgs
	s.mu.Unlock()
	return msgs, nil
}

func (s *MessageStore) Append(_ context.Context, msg Message) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if msg.Timestamp.IsZero() {
		msg.Timestamp = time.Now()
	}
	if msg.ContentType == "" {
		msg.ContentType = "text"
	}

	msgs := s.cache[msg.SessionID]
	msgs = append(msgs, msg)
	s.cache[msg.SessionID] = msgs

	return s.writeLocked(msg.SessionID, msgs)
}

func (s *MessageStore) UpdateLast(_ context.Context, sessionID, content string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	msgs := s.cache[sessionID]
	if len(msgs) == 0 {
		return fmt.Errorf("no messages to update")
	}
	msgs[len(msgs)-1].Content = content
	s.cache[sessionID] = msgs

	return s.writeLocked(sessionID, msgs)
}

func (s *MessageStore) Delete(_ context.Context, sessionID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.cache, sessionID)
	return nil
}

func (s *MessageStore) writeLocked(sessionID string, msgs []Message) error {
	data, err := json.Marshal(msgs)
	if err != nil {
		return fmt.Errorf("marshal messages: %w", err)
	}
	return os.WriteFile(s.messagesPath(sessionID), data, 0o644)
}
