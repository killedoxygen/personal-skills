#!/usr/bin/env bash
set -euo pipefail

replace=false
case "${1:-}" in
  '') ;;
  --replace) replace=true ;;
  *) printf 'Usage: bash install.sh [--replace]\n' >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then
  printf 'Usage: bash install.sh [--replace]\n' >&2
  exit 2
fi
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
skills_dir="${CODEX_HOME:-$HOME/.codex}/skills"

# Check every destination before changing any installed skill.
for source in "$repo_dir"/skills/*; do
  [ -f "$source/SKILL.md" ] || continue
  destination="$skills_dir/${source##*/}"
  if [ -L "$destination" ] && [ "$(readlink "$destination")" = "$source" ]; then
    continue
  fi
  if { [ -e "$destination" ] || [ -L "$destination" ]; } && [ "$replace" = false ]; then
    printf 'Already exists: %s\nUse --replace to back it up and install this version.\n' "$destination" >&2
    exit 1
  fi
done

mkdir -p -- "$skills_dir"
backup_dir=''
for source in "$repo_dir"/skills/*; do
  [ -f "$source/SKILL.md" ] || continue
  destination="$skills_dir/${source##*/}"
  if [ -L "$destination" ] && [ "$(readlink "$destination")" = "$source" ]; then
    printf 'Already installed: %s\n' "${source##*/}"
    continue
  fi
  if [ -e "$destination" ] || [ -L "$destination" ]; then
    if [ -z "$backup_dir" ]; then
      mkdir -p -- "${CODEX_HOME:-$HOME/.codex}/skill-backups"
      backup_dir=$(mktemp -d "${CODEX_HOME:-$HOME/.codex}/skill-backups/personal-skills.XXXXXX")
    fi
    mv -- "$destination" "$backup_dir/${source##*/}"
    printf 'Backed up: %s\n' "$backup_dir/${source##*/}"
  fi
  ln -s -- "$source" "$destination"
  printf 'Installed: %s\n' "${source##*/}"
done
