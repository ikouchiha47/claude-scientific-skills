package cli

import (
	"encoding/json"
	"fmt"
)

type OpenCode struct{}

func (o *OpenCode) Name() string { return "opencode" }

func (o *OpenCode) BuildEnv(cfg ToolConfig) map[string]string {
	env := map[string]string{}
	for k, v := range cfg.APIKeys {
		env[k] = v
	}
	return env
}

func (o *OpenCode) BuildCmd(cfg ToolConfig, mode RunMode) []string {
	args := []string{"opencode"}

	// OpenCode uses provider/model format: -m anthropic/claude-opus-4-6
	if cfg.Model != "" {
		model := cfg.Model
		if cfg.Provider != "" {
			model = cfg.Provider + "/" + cfg.Model
		}
		args = append(args, "-m", model)
	}

	switch mode {
	case ModeMessage:
		args = append(args, "run")
		if cfg.Message != "" {
			args = append(args, cfg.Message)
		}
	}

	args = append(args, cfg.Extra...)
	return args
}

func (o *OpenCode) ConfigFiles(cfg ToolConfig) map[string]string {
	files := map[string]string{}

	// If OpenCodeConfig is provided, write it directly as opencode.json
	if cfg.OpenCodeConfig != nil {
		data, _ := json.MarshalIndent(cfg.OpenCodeConfig, "", "  ")
		files["opencode.json"] = string(data)
		return files
	}

	// Otherwise build a minimal config from Model/Provider
	if cfg.Model != "" || cfg.Provider != "" {
		config := map[string]any{
			"$schema": "https://opencode.ai/config.json",
		}
		if cfg.Model != "" {
			model := cfg.Model
			if cfg.Provider != "" {
				model = fmt.Sprintf("%s/%s", cfg.Provider, cfg.Model)
			}
			config["model"] = model
		}
		data, _ := json.MarshalIndent(config, "", "  ")
		files["opencode.json"] = string(data)
	}

	return files
}
