#!/usr/bin/env bash
# Link all skills into .claude/skills/ and .opencode/skills/
# Picks up:
#   1. scientific-skills/<name>/ (all skills in the main collection)
#   2. Any root-level dir with a .skill marker file
#
# Usage: bash scripts/link_skills.sh

set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
SKILLS_ROOT="${SKILLS_ROOT:-$ROOT}"
TARGET_ROOT="${TARGET_ROOT:-$ROOT}"

TARGETS=(
    "$TARGET_ROOT/.claude/skills"
    "$TARGET_ROOT/.opencode/skills"
)

for target in "${TARGETS[@]}"; do
    mkdir -p "$target"

    # Link scientific-skills/*
    for skill in "$SKILLS_ROOT"/scientific-skills/*/; do
        [ -d "$skill" ] || continue
        name="$(basename "$skill")"
        ln -sfn "$skill" "$target/$name"
    done

    # Link root-level dirs with .skill marker
    for marker in "$SKILLS_ROOT"/*/.skill; do
        [ -f "$marker" ] || continue
        skill_dir="$(dirname "$marker")"
        name="$(basename "$skill_dir")"
        ln -sfn "$skill_dir" "$target/$name"
    done

    count=$(ls -1 "$target" 2>/dev/null | wc -l | tr -d ' ')
    echo "Linked $count skills into $target"
done
