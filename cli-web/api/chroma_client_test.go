package api

import (
	"context"
	"os"
	"testing"
)

func TestChromaStoreAndSearch(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "chroma-test-*")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	c := NewChromaClient(tmpDir, "http://localhost:11434", "qllama/bge-large-en-v1.5")
	if c == nil {
		t.Fatal("failed to create chroma client")
	}
	defer c.Close()

	ctx := context.Background()

	// Store messages
	if err := c.Store(ctx, "sess-001", "user", "How do earthquakes affect mining stocks in India?"); err != nil {
		t.Fatalf("store user msg: %v", err)
	}
	if err := c.Store(ctx, "sess-001", "assistant", "Earthquakes near Jharkhand and Odisha disrupt Coal India and NMDC, causing 2-5% temporary drops."); err != nil {
		t.Fatalf("store assistant msg: %v", err)
	}
	if err := c.Store(ctx, "sess-002", "user", "What is the best pizza in New York?"); err != nil {
		t.Fatalf("store unrelated msg: %v", err)
	}

	// Search globally — should find mining-related messages first
	results, err := c.Search(ctx, "geological events impact NMDC share price", "", 5)
	if err != nil {
		t.Fatalf("search: %v", err)
	}

	t.Logf("Got %d results:", len(results))
	for i, r := range results {
		t.Logf("  [%d] score=%.3f role=%s session=%s content=%s", i, r.Score, r.Role, r.SessionID, r.Content[:min(80, len(r.Content))])
	}

	if len(results) < 2 {
		t.Fatalf("expected at least 2 results, got %d", len(results))
	}

	// Top results should be about mining, not pizza
	for _, r := range results[:2] {
		if r.SessionID != "sess-001" {
			t.Errorf("expected top results from sess-001, got %s: %s", r.SessionID, r.Content[:50])
		}
	}

	// Search within session
	sessResults, err := c.Search(ctx, "mining", "sess-001", 5)
	if err != nil {
		t.Fatalf("session search: %v", err)
	}
	t.Logf("Session search got %d results", len(sessResults))
	for _, r := range sessResults {
		if r.SessionID != "sess-001" {
			t.Errorf("session search returned wrong session: %s", r.SessionID)
		}
	}

	// Delete session
	if err := c.DeleteSession(ctx, "sess-001"); err != nil {
		t.Fatalf("delete session: %v", err)
	}

	// Search again — should only find pizza
	afterDelete, err := c.Search(ctx, "mining stocks", "", 5)
	if err != nil {
		t.Fatalf("search after delete: %v", err)
	}
	t.Logf("After delete: %d results", len(afterDelete))
	for _, r := range afterDelete {
		if r.SessionID == "sess-001" {
			t.Errorf("found deleted session message: %s", r.Content[:50])
		}
	}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
