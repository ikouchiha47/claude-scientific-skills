package cli

type Codex struct{}

func (c *Codex) Name() string { return "codex" }

func (c *Codex) BuildEnv(cfg ToolConfig) map[string]string {
	env := map[string]string{}
	for k, v := range cfg.APIKeys {
		env[k] = v
	}
	return env
}

func (c *Codex) BuildCmd(cfg ToolConfig, mode RunMode) []string {
	args := []string{"codex"}

	if cfg.Model != "" {
		args = append(args, "--model", cfg.Model)
	}

	if mode == ModeMessage && cfg.Message != "" {
		args = append(args, cfg.Message)
	}

	args = append(args, cfg.Extra...)
	return args
}

func (c *Codex) ConfigFiles(_ ToolConfig) map[string]string {
	return nil
}
