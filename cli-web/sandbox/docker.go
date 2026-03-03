package sandbox

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"time"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/filters"
	"github.com/docker/docker/api/types/mount"
	"github.com/docker/docker/client"
	"github.com/docker/docker/pkg/stdcopy"
)

const (
	labelPrefix = "cli-sandbox"
	labelSession = labelPrefix + ".session-id"
	labelTool    = labelPrefix + ".tool"
	imageName    = "cli-sandbox:latest"
)

// DockerSandbox implements Sandbox using the Docker engine API.
type DockerSandbox struct {
	cli        *client.Client
	sessionsDir string // host path to sessions/ directory
}

func NewDockerSandbox(sessionsDir string) (*DockerSandbox, error) {
	cli, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
	if err != nil {
		return nil, fmt.Errorf("docker client: %w", err)
	}
	return &DockerSandbox{cli: cli, sessionsDir: sessionsDir}, nil
}

func (d *DockerSandbox) Create(ctx context.Context, opts CreateOpts) (*Session, error) {
	env := make([]string, 0, len(opts.Env))
	for k, v := range opts.Env {
		env = append(env, k+"="+v)
	}
	// Ensure HOME is always set
	hasHome := false
	for _, e := range env {
		if len(e) > 5 && e[:5] == "HOME=" {
			hasHome = true
			break
		}
	}
	if !hasHome {
		env = append(env, "HOME=/session")
	}

	sessionHostDir := d.sessionsDir + "/" + opts.SessionID

	cfg := &container.Config{
		Image:  imageName,
		Cmd:    []string{"sleep", "infinity"},
		Env:    env,
		Labels: map[string]string{
			labelSession: opts.SessionID,
			labelTool:    opts.Tool,
		},
		WorkingDir: "/workspace",
	}

	hostCfg := &container.HostConfig{
		Mounts: []mount.Mount{
			{Type: mount.TypeBind, Source: sessionHostDir, Target: "/session"},
			{Type: mount.TypeBind, Source: opts.Workspace, Target: "/workspace"},
		},
	}

	resp, err := d.cli.ContainerCreate(ctx, cfg, hostCfg, nil, nil, "sandbox-"+opts.SessionID[:12])
	if err != nil {
		return nil, fmt.Errorf("container create: %w", err)
	}

	if err := d.cli.ContainerStart(ctx, resp.ID, container.StartOptions{}); err != nil {
		return nil, fmt.Errorf("container start: %w", err)
	}

	return &Session{
		ID:          opts.SessionID,
		ContainerID: resp.ID,
		Tool:        opts.Tool,
		Status:      "running",
		CreatedAt:   time.Now(),
	}, nil
}

func (d *DockerSandbox) Exec(ctx context.Context, sessionID string, cmd []string) (io.ReadCloser, error) {
	cid, err := d.findContainer(ctx, sessionID)
	if err != nil {
		return nil, err
	}

	execCfg := container.ExecOptions{
		Cmd:          cmd,
		AttachStdout: true,
		AttachStderr: true,
	}
	exec, err := d.cli.ContainerExecCreate(ctx, cid, execCfg)
	if err != nil {
		return nil, fmt.Errorf("exec create: %w", err)
	}

	resp, err := d.cli.ContainerExecAttach(ctx, exec.ID, container.ExecStartOptions{})
	if err != nil {
		return nil, fmt.Errorf("exec attach: %w", err)
	}
	return resp.Conn, nil
}

func (d *DockerSandbox) Stop(ctx context.Context, sessionID string) error {
	cid, err := d.findContainer(ctx, sessionID)
	if err != nil {
		return err
	}
	timeout := 10
	return d.cli.ContainerStop(ctx, cid, container.StopOptions{Timeout: &timeout})
}

func (d *DockerSandbox) Restart(ctx context.Context, sessionID string) error {
	cid, err := d.findContainer(ctx, sessionID)
	if err != nil {
		return err
	}
	return d.cli.ContainerStart(ctx, cid, container.StartOptions{})
}

// EnsureRunning restarts the container if it's not running.
func (d *DockerSandbox) EnsureRunning(ctx context.Context, sessionID string) error {
	f := filters.NewArgs()
	f.Add("label", labelSession+"="+sessionID)
	containers, err := d.cli.ContainerList(ctx, container.ListOptions{All: true, Filters: f})
	if err != nil {
		return err
	}
	if len(containers) == 0 {
		return fmt.Errorf("no container for session %s", sessionID)
	}
	if containers[0].State != "running" {
		return d.cli.ContainerStart(ctx, containers[0].ID, container.StartOptions{})
	}
	return nil
}

func (d *DockerSandbox) Remove(ctx context.Context, sessionID string) error {
	cid, err := d.findContainer(ctx, sessionID)
	if err != nil {
		return err
	}
	return d.cli.ContainerRemove(ctx, cid, container.RemoveOptions{Force: true})
}

func (d *DockerSandbox) List(ctx context.Context) ([]Session, error) {
	f := filters.NewArgs()
	f.Add("label", labelSession)

	containers, err := d.cli.ContainerList(ctx, container.ListOptions{All: true, Filters: f})
	if err != nil {
		return nil, err
	}

	sessions := make([]Session, 0, len(containers))
	for _, c := range containers {
		sessions = append(sessions, Session{
			ID:          c.Labels[labelSession],
			ContainerID: c.ID,
			Tool:        c.Labels[labelTool],
			Status:      c.State,
			CreatedAt:   time.Unix(c.Created, 0),
		})
	}
	return sessions, nil
}

func (d *DockerSandbox) findContainer(ctx context.Context, sessionID string) (string, error) {
	f := filters.NewArgs()
	f.Add("label", labelSession+"="+sessionID)

	containers, err := d.cli.ContainerList(ctx, container.ListOptions{All: true, Filters: f})
	if err != nil {
		return "", err
	}
	if len(containers) == 0 {
		return "", fmt.Errorf("no container for session %s", sessionID)
	}
	return containers[0].ID, nil
}

// ReadAll demuxes Docker multiplexed stream and returns combined stdout+stderr.
func ReadAll(r io.ReadCloser) (string, error) {
	defer r.Close()
	var stdout, stderr bytes.Buffer
	_, err := stdcopy.StdCopy(&stdout, &stderr, r)
	if err != nil {
		// Fallback: might be a raw stream (TTY mode)
		var buf bytes.Buffer
		io.Copy(&buf, r)
		return buf.String(), nil
	}
	if stderr.Len() > 0 {
		stdout.Write(stderr.Bytes())
	}
	return stdout.String(), nil
}
