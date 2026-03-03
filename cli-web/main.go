package main

import (
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/aibusiness/cli-web/api"
	"github.com/aibusiness/cli-web/cli"
	"github.com/aibusiness/cli-web/sandbox"

	"github.com/google/uuid"
	"github.com/joho/godotenv"
)

func main() {
	godotenv.Load() // load .env from current dir
	if len(os.Args) < 2 {
		usage()
		os.Exit(1)
	}

	sessionsDir, _ := filepath.Abs("./sessions")
	os.MkdirAll(sessionsDir, 0o755)

	ctx := context.Background()
	sb, err := sandbox.NewDockerSandbox(sessionsDir)
	if err != nil {
		fatal("init sandbox: %v", err)
	}
	storage := sandbox.NewLocalStorage(sessionsDir)

	switch os.Args[1] {
	case "create":
		cmdCreate(ctx, sb, storage, os.Args[2:])
	case "exec":
		cmdExec(ctx, sb, os.Args[2:])
	case "list":
		cmdList(ctx, sb)
	case "stop":
		cmdStop(ctx, sb, os.Args[2:])
	case "resume":
		cmdResume(ctx, sb, os.Args[2:])
	case "remove":
		cmdRemove(ctx, sb, storage, os.Args[2:])
	case "export":
		cmdExport(ctx, storage, os.Args[2:])
	case "serve":
		cmdServe(sb, storage, os.Args[2:])
	default:
		usage()
		os.Exit(1)
	}
}

func cmdCreate(ctx context.Context, sb *sandbox.DockerSandbox, storage *sandbox.LocalStorage, args []string) {
	toolName := "bash"
	workspace, _ := os.Getwd()
	cfg := cli.ToolConfig{
		APIKeys: map[string]string{},
	}

	for i := 0; i < len(args); i++ {
		switch args[i] {
		case "--tool", "-t":
			i++
			toolName = args[i]
		case "--workspace", "-w":
			i++
			workspace, _ = filepath.Abs(args[i])
		case "--env", "-e":
			i++
			parts := strings.SplitN(args[i], "=", 2)
			if len(parts) == 2 {
				cfg.APIKeys[parts[0]] = parts[1]
			}
		case "--model", "-m":
			i++
			cfg.Model = args[i]
		case "--provider":
			i++
			cfg.Provider = args[i]
		case "--effort":
			i++
			cfg.Effort = args[i]
		case "--skip-permissions":
			cfg.DangerouslySkipPermissions = true
		}
	}

	tool, ok := cli.Get(toolName)
	if !ok {
		fatal("unknown tool: %s", toolName)
	}

	sessionID := uuid.New().String()

	if err := storage.Save(ctx, sessionID); err != nil {
		fatal("init session storage: %v", err)
	}

	// Write tool config files
	sessDir := filepath.Join(storage.BaseDir, sessionID)
	for relPath, content := range tool.ConfigFiles(cfg) {
		absPath := filepath.Join(sessDir, relPath)
		if err := os.MkdirAll(filepath.Dir(absPath), 0o755); err != nil {
			fatal("mkdir config: %v", err)
		}
		if err := os.WriteFile(absPath, []byte(content), 0o644); err != nil {
			fatal("write config: %v", err)
		}
	}

	// Merge env
	env := map[string]string{
		"HOME":       "/session",
		"MEMORY_DIR": "/workspace/.memory",
	}
	for k, v := range tool.BuildEnv(cfg) {
		env[k] = v
	}

	sess, err := sb.Create(ctx, sandbox.CreateOpts{
		Tool:      toolName,
		Workspace: workspace,
		Env:       env,
		SessionID: sessionID,
	})
	if err != nil {
		fatal("create: %v", err)
	}

	fmt.Printf("session: %s\ncontainer: %s\ntool: %s\n", sess.ID, sess.ContainerID[:12], sess.Tool)
}

func cmdExec(ctx context.Context, sb *sandbox.DockerSandbox, args []string) {
	if len(args) < 1 {
		fatal("usage: exec <session-id> [--] <cmd...>")
	}
	sessionID := args[0]
	cmd := args[1:]
	// Strip -- separator
	if len(cmd) > 0 && cmd[0] == "--" {
		cmd = cmd[1:]
	}
	if len(cmd) == 0 {
		fatal("no command specified")
	}

	reader, err := sb.Exec(ctx, sessionID, cmd)
	if err != nil {
		fatal("exec: %v", err)
	}
	output, err := sandbox.ReadAll(reader)
	if err != nil {
		fatal("reading exec output: %v", err)
	}
	fmt.Print(output)
}

func cmdList(ctx context.Context, sb *sandbox.DockerSandbox) {
	sessions, err := sb.List(ctx)
	if err != nil {
		fatal("list: %v", err)
	}
	if len(sessions) == 0 {
		fmt.Println("no sessions")
		return
	}
	fmt.Printf("%-38s %-12s %-10s %s\n", "SESSION", "CONTAINER", "TOOL", "STATUS")
	for _, s := range sessions {
		cid := s.ContainerID
		if len(cid) > 12 {
			cid = cid[:12]
		}
		fmt.Printf("%-38s %-12s %-10s %s\n", s.ID, cid, s.Tool, s.Status)
	}
}

func cmdStop(ctx context.Context, sb *sandbox.DockerSandbox, args []string) {
	if len(args) < 1 {
		fatal("usage: stop <session-id>")
	}
	if err := sb.Stop(ctx, args[0]); err != nil {
		fatal("stop: %v", err)
	}
	fmt.Println("stopped")
}

func cmdResume(ctx context.Context, sb *sandbox.DockerSandbox, args []string) {
	if len(args) < 1 {
		fatal("usage: resume <session-id>")
	}
	// For now, just restart the container
	sessions, err := sb.List(ctx)
	if err != nil {
		fatal("list: %v", err)
	}
	for _, s := range sessions {
		if s.ID == args[0] && s.Status != "running" {
			// Restart via Docker directly — the container is still there
			reader, err := sb.Exec(ctx, args[0], []string{"echo", "resumed"})
			if err != nil {
				fatal("resume: %v", err)
			}
			defer reader.Close()
			io.Copy(os.Stdout, reader)
			return
		}
	}
	fmt.Println("session already running or not found")
}

func cmdRemove(ctx context.Context, sb *sandbox.DockerSandbox, storage *sandbox.LocalStorage, args []string) {
	if len(args) < 1 {
		fatal("usage: remove <session-id>")
	}
	sb.Remove(ctx, args[0])
	storage.Delete(ctx, args[0])
	fmt.Println("removed")
}

func cmdExport(ctx context.Context, storage *sandbox.LocalStorage, args []string) {
	if len(args) < 1 {
		fatal("usage: export <session-id>")
	}
	if err := storage.Export(ctx, args[0], os.Stdout); err != nil {
		fatal("export: %v", err)
	}
}

func cmdServe(sb *sandbox.DockerSandbox, storage *sandbox.LocalStorage, args []string) {
	addr := ":8080"
	for i := 0; i < len(args); i++ {
		if args[i] == "--addr" || args[i] == "-a" {
			i++
			addr = args[i]
		}
	}
	openCodeConfigPath := os.Getenv("OPENCODE_CONFIG")
	credsPath := os.Getenv("OPENCODE_CREDS")
	if openCodeConfigPath == "" {
		fatal("OPENCODE_CONFIG env var not set (path to opencode.json)")
	}
	if credsPath == "" {
		fatal("OPENCODE_CREDS env var not set (path to opencode.creds.json)")
	}

	chromaDir := os.Getenv("CHROMA_DIR")
	if chromaDir == "" {
		chromaDir = filepath.Join(storage.BaseDir, ".chroma")
	}
	ollamaURL := os.Getenv("OLLAMA_URL")
	if ollamaURL == "" {
		ollamaURL = "http://localhost:11434"
	}
	embeddingModel := os.Getenv("EMBEDDING_MODEL")
	if embeddingModel == "" {
		embeddingModel = "qllama/bge-large-en-v1.5"
	}

	reaper := sandbox.NewReaper(sb, storage, sandbox.DefaultIdleTimeout)
	reaper.Start()
	defer reaper.Stop()

	srv := api.NewServer(sb, storage, api.ServerConfig{
		OpenCodeConfigPath: openCodeConfigPath,
		CredsPath:          credsPath,
		DefaultModel:       os.Getenv("DEFAULT_MODEL"),
		DefaultWorkspace:   os.Getenv("DEFAULT_WORKSPACE"),
		ChromaDir:          chromaDir,
		OllamaURL:          ollamaURL,
		EmbeddingModel:     embeddingModel,
	})
	if err := srv.ListenAndServe(addr); err != nil {
		fatal("serve: %v", err)
	}
}

func usage() {
	fmt.Fprintf(os.Stderr, `Usage: cli-web <command> [args]

Commands:
  create   --tool <name> [--workspace <dir>] [--env KEY=VAL]
  exec     <session-id> [--] <cmd...>
  list
  stop     <session-id>
  resume   <session-id>
  remove   <session-id>
  export   <session-id> > backup.tar.gz
  serve    [--addr :8080]  Start HTTP API server
`)
}

func fatal(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "error: "+format+"\n", args...)
	os.Exit(1)
}
