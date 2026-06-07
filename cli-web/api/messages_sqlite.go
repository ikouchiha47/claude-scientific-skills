package api

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

// SQLiteMessageStore implements MessageStorage backed by SQLite with
// separate read/write connections, WAL mode, and mmap.
type SQLiteMessageStore struct {
	writer *sql.DB
	reader *sql.DB
}

func NewSQLiteMessageStore(dbPath string) (*SQLiteMessageStore, error) {
	// Writer connection: single conn, WAL, mmap 256MB
	writer, err := sql.Open("sqlite3", dbPath+"?_journal_mode=WAL&_busy_timeout=5000&_mmap_size=268435456&_synchronous=NORMAL")
	if err != nil {
		return nil, fmt.Errorf("open writer: %w", err)
	}
	writer.SetMaxOpenConns(1)

	// Reader connection: multiple conns, read-only
	reader, err := sql.Open("sqlite3", dbPath+"?_journal_mode=WAL&_busy_timeout=5000&_mmap_size=268435456&mode=ro")
	if err != nil {
		writer.Close()
		return nil, fmt.Errorf("open reader: %w", err)
	}

	// Create schema on writer
	_, err = writer.Exec(`CREATE TABLE IF NOT EXISTS messages (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		session_id TEXT NOT NULL,
		role TEXT NOT NULL,
		content TEXT NOT NULL,
		content_type TEXT NOT NULL DEFAULT 'text',
		timestamp TEXT NOT NULL
	)`)
	if err != nil {
		writer.Close()
		reader.Close()
		return nil, fmt.Errorf("create table: %w", err)
	}

	_, err = writer.Exec(`CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)`)
	if err != nil {
		writer.Close()
		reader.Close()
		return nil, fmt.Errorf("create index: %w", err)
	}

	return &SQLiteMessageStore{writer: writer, reader: reader}, nil
}

func (s *SQLiteMessageStore) Close() error {
	s.reader.Close()
	return s.writer.Close()
}

func (s *SQLiteMessageStore) Append(_ context.Context, msg Message) error {
	if msg.Content == "" {
		return nil
	}
	if msg.ContentType == "" {
		msg.ContentType = "text"
	}
	if msg.Timestamp.IsZero() {
		msg.Timestamp = time.Now()
	}

	_, err := s.writer.Exec(
		`INSERT INTO messages (session_id, role, content, content_type, timestamp) VALUES (?, ?, ?, ?, ?)`,
		msg.SessionID, msg.Role, msg.Content, msg.ContentType, msg.Timestamp.Format(time.RFC3339),
	)
	return err
}

func (s *SQLiteMessageStore) List(_ context.Context, sessionID string) ([]Message, error) {
	rows, err := s.reader.Query(
		`SELECT role, content, content_type, timestamp FROM messages WHERE session_id = ? ORDER BY id ASC`,
		sessionID,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var msgs []Message
	for rows.Next() {
		var m Message
		var ts string
		if err := rows.Scan(&m.Role, &m.Content, &m.ContentType, &ts); err != nil {
			return nil, err
		}
		m.SessionID = sessionID
		m.Timestamp, _ = time.Parse(time.RFC3339, ts)
		msgs = append(msgs, m)
	}
	if msgs == nil {
		msgs = []Message{}
	}
	return msgs, rows.Err()
}

// Upsert inserts a new row or updates content for an existing row by ID.
// Returns the row ID (for subsequent updates).
func (s *SQLiteMessageStore) Upsert(_ context.Context, rowID int64, msg Message) (int64, error) {
	if msg.Timestamp.IsZero() {
		msg.Timestamp = time.Now()
	}
	if msg.ContentType == "" {
		msg.ContentType = "text"
	}

	if rowID == 0 {
		res, err := s.writer.Exec(
			`INSERT INTO messages (session_id, role, content, content_type, timestamp) VALUES (?, ?, ?, ?, ?)`,
			msg.SessionID, msg.Role, msg.Content, msg.ContentType, msg.Timestamp.Format(time.RFC3339),
		)
		if err != nil {
			return 0, err
		}
		return res.LastInsertId()
	}

	_, err := s.writer.Exec(`UPDATE messages SET content = ? WHERE id = ?`, msg.Content, rowID)
	return rowID, err
}

func (s *SQLiteMessageStore) Delete(_ context.Context, sessionID string) error {
	_, err := s.writer.Exec(`DELETE FROM messages WHERE session_id = ?`, sessionID)
	return err
}
