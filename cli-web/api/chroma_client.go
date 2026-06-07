package api

import (
	"context"
	"fmt"
	"log"
	"sort"
	"time"

	chroma "github.com/amikos-tech/chroma-go/pkg/api/v2"
	"github.com/amikos-tech/chroma-go/pkg/embeddings"
	"github.com/amikos-tech/chroma-go/pkg/embeddings/ollama"
)

// ChromaClient uses embedded ChromaDB (in-process, no server) + Ollama embeddings.
type ChromaClient struct {
	client chroma.Client
	ef     embeddings.EmbeddingFunction
}

func NewChromaClient(persistPath, ollamaURL, embeddingModel string) *ChromaClient {
	ef, err := ollama.NewOllamaEmbeddingFunction(
		ollama.WithBaseURL(ollamaURL),
		ollama.WithModel(embeddings.EmbeddingModel(embeddingModel)),
	)
	if err != nil {
		log.Printf("warning: ollama embedding init failed: %v", err)
		return nil
	}

	client, err := chroma.NewLocalClient(
		chroma.WithLocalPersistPath(persistPath),
		chroma.WithLocalClientOption(chroma.WithDefaultDatabaseAndTenant()),
	)
	if err != nil {
		log.Printf("warning: chroma local client failed: %v", err)
		return nil
	}

	return &ChromaClient{client: client, ef: ef}
}

func (c *ChromaClient) Close() {
	if c.client != nil {
		c.client.Close()
	}
}

func (c *ChromaClient) sessionCollectionName(sessionID string) string {
	name := "s_" + sessionID
	if len(name) > 63 {
		name = name[:63]
	}
	return name
}

func (c *ChromaClient) getOrCreateCollection(ctx context.Context, name string) (chroma.Collection, error) {
	return c.client.GetOrCreateCollection(ctx, name, chroma.WithEmbeddingFunctionCreate(c.ef))
}

// Append implements MessageStorage.
func (c *ChromaClient) Append(ctx context.Context, msg Message) error {
	if msg.Content == "" {
		return nil
	}
	if msg.ContentType == "" {
		msg.ContentType = "text"
	}
	if msg.Timestamp.IsZero() {
		msg.Timestamp = time.Now()
	}

	sessionID := msg.SessionID
	ts := msg.Timestamp.Format(time.RFC3339)
	docID := chroma.DocumentID(fmt.Sprintf("%s-%d", sessionID[:8], msg.Timestamp.UnixNano()))

	// For stderr (thinking/debug output), truncate the embedding text since it
	// can be very long and isn't useful for semantic search. Full content is
	// still stored as the document.
	embeddingText := msg.Content
	if msg.ContentType == "stderr" {
		const maxEmbedChars = 1500
		if len(embeddingText) > maxEmbedChars {
			embeddingText = embeddingText[:maxEmbedChars]
		}
	}

	meta, err := chroma.NewDocumentMetadataFromMap(map[string]interface{}{
		"session_id":   sessionID,
		"role":         msg.Role,
		"content_type": msg.ContentType,
		"timestamp":    ts,
	})
	if err != nil {
		return fmt.Errorf("build metadata: %w", err)
	}

	sessCol, err := c.getOrCreateCollection(ctx, c.sessionCollectionName(sessionID))
	if err != nil {
		return fmt.Errorf("get session collection: %w", err)
	}
	if err := sessCol.Add(ctx,
		chroma.WithIDs(docID),
		chroma.WithTexts(embeddingText),
		chroma.WithMetadatas(meta),
	); err != nil {
		return fmt.Errorf("add to session: %w", err)
	}

	globalCol, err := c.getOrCreateCollection(ctx, "all_messages")
	if err != nil {
		return fmt.Errorf("get global collection: %w", err)
	}
	if err := globalCol.Add(ctx,
		chroma.WithIDs(docID),
		chroma.WithTexts(embeddingText),
		chroma.WithMetadatas(meta),
	); err != nil {
		return fmt.Errorf("add to global: %w", err)
	}

	return nil
}

type ChromaSearchResult struct {
	Content   string  `json:"content"`
	Role      string  `json:"role"`
	SessionID string  `json:"session_id"`
	Timestamp string  `json:"timestamp"`
	Score     float64 `json:"score"`
}

func (c *ChromaClient) Search(ctx context.Context, query string, sessionID string, k int) ([]ChromaSearchResult, error) {
	colName := "all_messages"
	if sessionID != "" {
		colName = c.sessionCollectionName(sessionID)
	}

	col, err := c.getOrCreateCollection(ctx, colName)
	if err != nil {
		return nil, fmt.Errorf("get collection: %w", err)
	}

	results, err := col.Query(ctx,
		chroma.WithQueryTexts(query),
		chroma.WithNResults(k),
		chroma.WithIncludeQuery(chroma.IncludeDocuments, chroma.IncludeMetadatas, chroma.IncludeDistances),
	)
	if err != nil {
		return nil, fmt.Errorf("query: %w", err)
	}

	var out []ChromaSearchResult
	idGroups := results.GetIDGroups()
	docGroups := results.GetDocumentsGroups()
	metaGroups := results.GetMetadatasGroups()
	distGroups := results.GetDistancesGroups()

	for i := range idGroups {
		for j := range idGroups[i] {
			r := ChromaSearchResult{}
			if i < len(docGroups) && j < len(docGroups[i]) {
				r.Content = fmt.Sprintf("%v", docGroups[i][j])
			}
			if i < len(distGroups) && j < len(distGroups[i]) {
				r.Score = 1.0 - float64(distGroups[i][j])
			}
			if i < len(metaGroups) && j < len(metaGroups[i]) {
				meta := metaGroups[i][j]
				if meta != nil {
					if v, ok := meta.GetString("role"); ok {
						r.Role = v
					}
					if v, ok := meta.GetString("session_id"); ok {
						r.SessionID = v
					}
					if v, ok := meta.GetString("timestamp"); ok {
						r.Timestamp = v
					}
				}
			}
			out = append(out, r)
		}
	}

	return out, nil
}

// List implements MessageStorage — returns all messages for a session sorted by timestamp.
func (c *ChromaClient) List(ctx context.Context, sessionID string) ([]Message, error) {
	col, err := c.getOrCreateCollection(ctx, c.sessionCollectionName(sessionID))
	if err != nil {
		return nil, fmt.Errorf("get collection: %w", err)
	}

	results, err := col.Get(ctx,
		chroma.WithIncludeGet(chroma.IncludeDocuments, chroma.IncludeMetadatas),
	)
	if err != nil {
		return nil, fmt.Errorf("get all: %w", err)
	}

	ids := results.GetIDs()
	docs := results.GetDocuments()
	metas := results.GetMetadatas()

	msgs := make([]Message, 0, len(ids))
	for i := range ids {
		m := Message{SessionID: sessionID}
		if i < len(docs) {
			m.Content = fmt.Sprintf("%v", docs[i])
		}
		if i < len(metas) && metas[i] != nil {
			if v, ok := metas[i].GetString("role"); ok {
				m.Role = v
			}
			if v, ok := metas[i].GetString("content_type"); ok {
				m.ContentType = v
			}
			if v, ok := metas[i].GetString("timestamp"); ok {
				if t, err := time.Parse(time.RFC3339, v); err == nil {
					m.Timestamp = t
				}
			}
		}
		if m.ContentType == "" {
			m.ContentType = "text"
		}
		msgs = append(msgs, m)
	}

	// Sort by timestamp
	sort.Slice(msgs, func(i, j int) bool {
		return msgs[i].Timestamp.Before(msgs[j].Timestamp)
	})

	return msgs, nil
}

// Delete implements MessageStorage.
func (c *ChromaClient) Delete(ctx context.Context, sessionID string) error {
	return c.DeleteSession(ctx, sessionID)
}

func (c *ChromaClient) UpdateLast(ctx context.Context, sessionID, content string) error {
	sessCol, err := c.getOrCreateCollection(ctx, c.sessionCollectionName(sessionID))
	if err != nil {
		return err
	}

	results, err := sessCol.Get(ctx,
		chroma.WithWhereGet(chroma.EqString("role", "assistant")),
		chroma.WithIncludeGet(chroma.IncludeMetadatas, chroma.IncludeDocuments),
	)
	if err != nil {
		return nil
	}
	ids := results.GetIDs()
	if len(ids) == 0 {
		return nil
	}

	lastID := ids[len(ids)-1]

	sessCol.Delete(ctx, chroma.WithIDsDelete(lastID))
	globalCol, _ := c.getOrCreateCollection(ctx, "all_messages")
	if globalCol != nil {
		globalCol.Delete(ctx, chroma.WithIDsDelete(lastID))
	}

	if content != "" {
		meta, _ := chroma.NewDocumentMetadataFromMap(map[string]interface{}{
			"session_id": sessionID,
			"role":       "assistant",
			"timestamp":  time.Now().Format(time.RFC3339),
		})
		sessCol.Add(ctx, chroma.WithIDs(lastID), chroma.WithTexts(content), chroma.WithMetadatas(meta))
		if globalCol != nil {
			globalCol.Add(ctx, chroma.WithIDs(lastID), chroma.WithTexts(content), chroma.WithMetadatas(meta))
		}
	}

	return nil
}

func (c *ChromaClient) DeleteSession(ctx context.Context, sessionID string) error {
	colName := c.sessionCollectionName(sessionID)

	sessCol, err := c.getOrCreateCollection(ctx, colName)
	if err == nil {
		results, err := sessCol.Get(ctx, chroma.WithIncludeGet(chroma.IncludeMetadatas))
		if err == nil {
			ids := results.GetIDs()
			if len(ids) > 0 {
				globalCol, _ := c.getOrCreateCollection(ctx, "all_messages")
				if globalCol != nil {
					globalCol.Delete(ctx, chroma.WithIDsDelete(ids...))
				}
			}
		}
	}

	return c.client.DeleteCollection(ctx, colName)
}

func (c *ChromaClient) Health() bool {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	return c.client.Heartbeat(ctx) == nil
}
