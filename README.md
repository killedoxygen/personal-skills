# Personal skills

Small, practical skills for Codex. Each skill lives under `skills/<name>/SKILL.md`.

## Install on a fresh machine

Requires Git and Bash (Linux, macOS, or WSL):

```bash
git clone https://github.com/killedoxygen/personal-skills.git "$HOME/.local/share/personal-skills"
bash "$HOME/.local/share/personal-skills/install.sh"
```

The installer links each skill into `${CODEX_HOME:-$HOME/.codex}/skills`.
Keep the clone: installed skills point to it. Run the installer again safely at any time.
Start a new Codex session after installation to discover the skills.

Existing files are left in place by default. To replace a conflicting skill:

```bash
bash "$HOME/.local/share/personal-skills/install.sh" --replace
```

Replaced directories and links are preserved under
`${CODEX_HOME:-$HOME/.codex}/skill-backups/personal-skills.*`.

## Update

```bash
git -C "$HOME/.local/share/personal-skills" pull --ff-only
bash "$HOME/.local/share/personal-skills/install.sh"
```

Linked skills update with the checkout; rerunning the installer adds newly published skills.

## Skills

- [security-campaign](skills/security-campaign/SKILL.md): five instructions for sustained vulnerability research, reproducible evidence, useful handoffs, and cleanup.

## Add a skill

Create `skills/<name>/SKILL.md` with YAML `name` and `description` fields followed by its instructions, commit it, and rerun the installer.

## Uninstall

Remove the installed symlink for the skill you want to uninstall. If replacing a previous
installation, move its directory or link back from the printed backup path.
