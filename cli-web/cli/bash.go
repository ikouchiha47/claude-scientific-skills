package cli

type Bash struct{}

func (b *Bash) Name() string { return "bash" }

func (b *Bash) BuildEnv(cfg ToolConfig) map[string]string {
	env := map[string]string{}
	for k, v := range cfg.APIKeys {
		env[k] = v
	}
	return env
}

func (b *Bash) BuildCmd(cfg ToolConfig, mode RunMode) []string {
	if mode == ModeMessage && cfg.Message != "" {
		return []string{"bash", "-c", cfg.Message}
	}
	return []string{"bash"}
}

func (b *Bash) ConfigFiles(_ ToolConfig) map[string]string {
	return nil
}
