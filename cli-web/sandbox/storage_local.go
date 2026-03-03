package sandbox

import (
	"archive/tar"
	"compress/gzip"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// LocalStorage implements SessionStorage using the local filesystem.
type LocalStorage struct {
	BaseDir string // e.g. "./sessions"
}

type sessionMeta struct {
	ID             string    `json:"id"`
	Tool           string    `json:"tool"`
	CreatedAt      time.Time `json:"created_at"`
	UpdatedAt      time.Time `json:"updated_at"`
	LastActivityAt time.Time `json:"last_activity_at"`
}

func NewLocalStorage(baseDir string) *LocalStorage {
	return &LocalStorage{BaseDir: baseDir}
}

func (s *LocalStorage) sessionDir(id string) string {
	return filepath.Join(s.BaseDir, id)
}

func (s *LocalStorage) metaPath(id string) string {
	return filepath.Join(s.sessionDir(id), ".meta.json")
}

func (s *LocalStorage) Save(ctx context.Context, sessionID string) error {
	dir := s.sessionDir(sessionID)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return fmt.Errorf("create session dir: %w", err)
	}
	meta := sessionMeta{
		ID:        sessionID,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}
	data, err := json.Marshal(meta)
	if err != nil {
		return fmt.Errorf("marshal meta: %w", err)
	}
	return os.WriteFile(s.metaPath(sessionID), data, 0o644)
}

func (s *LocalStorage) Load(_ context.Context, sessionID string) error {
	if _, err := os.Stat(s.sessionDir(sessionID)); err != nil {
		return fmt.Errorf("session %s not found: %w", sessionID, err)
	}
	return nil
}

func (s *LocalStorage) Export(_ context.Context, sessionID string, w io.Writer) error {
	dir := s.sessionDir(sessionID)
	gz := gzip.NewWriter(w)
	defer gz.Close()
	tw := tar.NewWriter(gz)
	defer tw.Close()

	return filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(dir, path)
		header, err := tar.FileInfoHeader(info, "")
		if err != nil {
			return err
		}
		header.Name = rel
		if err := tw.WriteHeader(header); err != nil {
			return err
		}
		if info.IsDir() {
			return nil
		}
		f, err := os.Open(path)
		if err != nil {
			return err
		}
		defer f.Close()
		_, err = io.Copy(tw, f)
		return err
	})
}

func (s *LocalStorage) Import(_ context.Context, sessionID string, r io.Reader) error {
	dir := s.sessionDir(sessionID)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	gz, err := gzip.NewReader(r)
	if err != nil {
		return err
	}
	defer gz.Close()
	tr := tar.NewReader(gz)

	for {
		header, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return err
		}
		target := filepath.Join(dir, filepath.Clean(header.Name))
		// Prevent path traversal
		rel, err := filepath.Rel(dir, target)
		if err != nil || strings.HasPrefix(rel, "..") {
			continue
		}
		if header.Typeflag == tar.TypeDir {
			if err := os.MkdirAll(target, 0o755); err != nil {
				return fmt.Errorf("mkdir %s: %w", target, err)
			}
			continue
		}
		f, err := os.Create(target)
		if err != nil {
			return fmt.Errorf("create %s: %w", target, err)
		}
		if _, err := io.Copy(f, tr); err != nil {
			f.Close()
			return fmt.Errorf("write %s: %w", target, err)
		}
		f.Close()
	}
	return nil
}

func (s *LocalStorage) List(_ context.Context) ([]StoredSession, error) {
	entries, err := os.ReadDir(s.BaseDir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	var sessions []StoredSession
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		meta := StoredSession{ID: e.Name()}
		metaPath := s.metaPath(e.Name())
		if data, err := os.ReadFile(metaPath); err == nil {
			var m sessionMeta
			if json.Unmarshal(data, &m) == nil {
				meta.Tool = m.Tool
				meta.CreatedAt = m.CreatedAt
				meta.UpdatedAt = m.UpdatedAt
				meta.LastActivityAt = m.LastActivityAt
			}
		}
		info, _ := e.Info()
		if info != nil {
			meta.Size = info.Size()
		}
		sessions = append(sessions, meta)
	}
	return sessions, nil
}

func (s *LocalStorage) Touch(_ context.Context, sessionID string) error {
	metaPath := s.metaPath(sessionID)
	data, err := os.ReadFile(metaPath)
	if err != nil {
		return err
	}
	var m sessionMeta
	if err := json.Unmarshal(data, &m); err != nil {
		return err
	}
	now := time.Now()
	m.LastActivityAt = now
	m.UpdatedAt = now
	out, err := json.Marshal(m)
	if err != nil {
		return err
	}
	return os.WriteFile(metaPath, out, 0o644)
}

func (s *LocalStorage) GetMeta(_ context.Context, sessionID string) (*StoredSession, error) {
	data, err := os.ReadFile(s.metaPath(sessionID))
	if err != nil {
		return nil, err
	}
	var m sessionMeta
	if err := json.Unmarshal(data, &m); err != nil {
		return nil, err
	}
	return &StoredSession{
		ID:             m.ID,
		Tool:           m.Tool,
		CreatedAt:      m.CreatedAt,
		UpdatedAt:      m.UpdatedAt,
		LastActivityAt: m.LastActivityAt,
	}, nil
}

func (s *LocalStorage) Delete(_ context.Context, sessionID string) error {
	return os.RemoveAll(s.sessionDir(sessionID))
}
