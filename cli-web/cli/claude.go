package cli

import (
	"encoding/json"
)

type Claude struct{}

func (c *Claude) Name() string { return "claude" }

func (c *Claude) BuildEnv(cfg ToolConfig) map[string]string {
	env := map[string]string{
		"CLAUDE_CONFIG_DIR": "/session/.claude",
	}
	// Pass through all API keys (claude only needs ANTHROPIC_API_KEY but
	// MCP servers inside might need others)
	for k, v := range cfg.APIKeys {
		env[k] = v
	}
	return env
}

func (c *Claude) BuildCmd(cfg ToolConfig, mode RunMode) []string {
	args := []string{"claude"}

	if cfg.Model != "" {
		args = append(args, "--model", cfg.Model)
	}
	if cfg.Effort != "" {
		args = append(args, "--effort", cfg.Effort)
	}
	if cfg.MaxBudget != "" {
		args = append(args, "--max-budget-usd", cfg.MaxBudget)
	}
	if cfg.DangerouslySkipPermissions {
		args = append(args, "--dangerously-skip-permissions")
	}
	if len(cfg.AllowedTools) > 0 {
		args = append(args, "--allowedTools")
		args = append(args, cfg.AllowedTools...)
	}

	switch mode {
	case ModeResume:
		if cfg.SessionID != "" {
			args = append(args, "--resume", cfg.SessionID)
		} else {
			args = append(args, "--continue")
		}
	case ModeContinue:
		args = append(args, "--continue")
	case ModeMessage:
		if cfg.Message != "" {
			args = append(args, "-p", cfg.Message)
		}
	}

	args = append(args, cfg.Extra...)
	return args
}

func (c *Claude) ConfigFiles(cfg ToolConfig) map[string]string {
	files := map[string]string{}

	// If skip permissions, write settings.json
	if cfg.DangerouslySkipPermissions {
		settings := map[string]any{
			"permissions": map[string]any{
				"allow": []string{"*"},
			},
		}
		data, _ := json.MarshalIndent(settings, "", "  ")
		files[".claude/settings.json"] = string(data)
	}

	return files
}
