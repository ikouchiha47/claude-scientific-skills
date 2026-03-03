#!/usr/bin/env bash
# Container init: link skills, copy config, ensure venv, then run CMD.
set -euo pipefail

# Link skills: read from /workspace, write into /session
if [ -f /workspace/scripts/link_skills.sh ]; then
    SKILLS_ROOT=/workspace TARGET_ROOT=/session bash /workspace/scripts/link_skills.sh
fi

# Copy CLAUDE.md / AGENTS.md into session
for f in CLAUDE.md AGENTS.md; do
    [ -f "/workspace/$f" ] && cp "/workspace/$f" "/session/$f" 2>/dev/null || true
done

# Copy agent definitions
if [ -d /workspace/agents/claude ]; then
    mkdir -p /session/.claude/agents
    cp /workspace/agents/claude/* /session/.claude/agents/ 2>/dev/null || true
fi
if [ -d /workspace/agents/opencode ]; then
    mkdir -p /session/.opencode/agents
    cp /workspace/agents/opencode/* /session/.opencode/agents/ 2>/dev/null || true
fi

# Ensure workspace venv exists and has playwright
if [ -d /workspace/.venv ]; then
    uv pip install --quiet playwright 2>/dev/null || true
fi

exec "$@"
