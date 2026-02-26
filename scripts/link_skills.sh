#!/usr/bin/env bash
# Link all skills into .claude/skills/ and .opencode/skills/
# Picks up:
#   1. scientific-skills/<name>/ (all skills in the main collection)
#   2. Any root-level dir with a .skill marker file
#
# Usage: bash scripts/link_skills.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

TARGETS=(
    "$ROOT/.claude/skills"
    "$ROOT/.opencode/skills"
)

for target in "${TARGETS[@]}"; do
    mkdir -p "$target"

    # Link scientific-skills/*
    for skill in "$ROOT"/scientific-skills/*/; do
        name="$(basename "$skill")"
        ln -sfn "../../scientific-skills/$name" "$target/$name"
    done

    # Link root-level dirs with .skill marker
    for marker in "$ROOT"/*/.skill; do
        [ -f "$marker" ] || continue
        skill_dir="$(dirname "$marker")"
        name="$(basename "$skill_dir")"
        ln -sfn "../../$name" "$target/$name"
    done

    count=$(ls -1 "$target" | wc -l | tr -d ' ')
    echo "Linked $count skills into $target"
done
