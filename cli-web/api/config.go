package api

import (
	"encoding/json"
	"fmt"
	"os"
)

// ProviderCred maps a provider to its env var name and default key.
type ProviderCred struct {
	Env string `json:"env"`
	Key string `json:"key"`
}

// CredsFile is the shape of opencode.creds.json.
type CredsFile map[string]ProviderCred

// LoadOpenCodeConfig reads the opencode config from the given path.
func LoadOpenCodeConfig(path string) (map[string]any, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", path, err)
	}
	var cfg map[string]any
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("parse %s: %w", path, err)
	}
	return cfg, nil
}

// LoadCreds reads credentials from the given path.
func LoadCreds(path string) (CredsFile, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", path, err)
	}
	var creds CredsFile
	if err := json.Unmarshal(data, &creds); err != nil {
		return nil, fmt.Errorf("parse %s: %w", path, err)
	}
	return creds, nil
}

// ResolveAPIKeys merges default creds with user-provided BYOK overrides.
// byok maps provider name → user's key (e.g. {"anthropic": "sk-ant-..."}).
// Returns env var name → key value for injection into container.
func ResolveAPIKeys(creds CredsFile, byok map[string]string) map[string]string {
	env := map[string]string{}
	for provider, cred := range creds {
		if userKey, ok := byok[provider]; ok && userKey != "" {
			// BYOK override
			env[cred.Env] = userKey
		} else {
			// Default operator key
			env[cred.Env] = cred.Key
		}
	}
	return env
}
