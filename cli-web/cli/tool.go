package cli

// Tool defines a CLI coding assistant that can run inside a sandbox.
type Tool interface {
	Name() string
	// BuildEnv returns environment variables the container needs.
	BuildEnv(cfg ToolConfig) map[string]string
	// BuildCmd returns the command to launch the tool.
	BuildCmd(cfg ToolConfig, mode RunMode) []string
	// ConfigFiles returns files to write into the session dir before launch.
	// Key is relative path (e.g. ".claude/settings.json"), value is content.
	ConfigFiles(cfg ToolConfig) map[string]string
}

// RunMode controls how the tool is launched.
type RunMode string

const (
	ModeNew      RunMode = "new"
	ModeResume   RunMode = "resume"
	ModeContinue RunMode = "continue"
	ModeMessage  RunMode = "message" // non-interactive, single prompt
)

// ToolConfig is the full configuration for a tool session.
type ToolConfig struct {
	// Model selection
	Model    string `json:"model,omitempty"`    // e.g. "opus", "anthropic/claude-opus-4-6"
	Provider string `json:"provider,omitempty"` // e.g. "anthropic", "openai", "xai"

	// Behavior
	Effort    string `json:"effort,omitempty"`    // "low", "medium", "high" (claude only)
	MaxBudget string `json:"max_budget,omitempty"` // max spend in USD (claude --print only)

	// API keys — multiple providers supported
	APIKeys map[string]string `json:"api_keys,omitempty"` // "ANTHROPIC_API_KEY" → "sk-..."

	// Session
	SessionID string `json:"session_id,omitempty"` // for resume
	Message   string `json:"message,omitempty"`     // for non-interactive

	// Permissions / safety
	DangerouslySkipPermissions bool     `json:"dangerously_skip_permissions,omitempty"`
	AllowedTools               []string `json:"allowed_tools,omitempty"` // claude --allowedTools

	// Tool-specific raw config objects (written as config files)
	OpenCodeConfig map[string]any `json:"opencode_config,omitempty"` // full opencode.json schema

	// Extra flags passed through verbatim
	Extra []string `json:"extra,omitempty"`
}

// Registry maps tool names to implementations.
var Registry = map[string]Tool{}

func Register(t Tool) {
	Registry[t.Name()] = t
}

func Get(name string) (Tool, bool) {
	t, ok := Registry[name]
	return t, ok
}

func init() {
	Register(&Claude{})
	Register(&OpenCode{})
	Register(&Codex{})
	Register(&Bash{})
}
