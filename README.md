# Personal skills

Small, practical skills for Codex. Each skill lives under `skills/<name>/SKILL.md`.

## Requirements

- Git
- Python 3.9 or newer (standard library only; nothing to `pip install`)
  - Linux: usually preinstalled; otherwise install your distribution's `python3` package.
  - macOS: `xcode-select --install` provides `git` and `python3`, or use Homebrew.
  - Windows: `winget install Git.Git Python.Python.3.12`, then open a new terminal.
    Native Windows, WSL and Git Bash are all supported.

The installer copies each skill into `$CODEX_HOME/skills`, which defaults to
`~/.codex/skills` (`%USERPROFILE%\.codex\skills` on Windows). Set `CODEX_HOME`
first if you use a different Codex home.

## Install on a fresh machine

Linux and macOS:

```bash
git clone https://github.com/killedoxygen/personal-skills.git "$HOME/.local/share/personal-skills"
python3 "$HOME/.local/share/personal-skills/install.py"
```

Windows (PowerShell):

```powershell
git clone https://github.com/killedoxygen/personal-skills.git "$env:LOCALAPPDATA\personal-skills"
py -3 "$env:LOCALAPPDATA\personal-skills\install.py"
```

If the `py` launcher is missing, use `python` instead. Start a new Codex session
afterwards to load the skills. Use `--dry-run` to see what would change first.

## Update

Linux and macOS:

```bash
git -C "$HOME/.local/share/personal-skills" pull --ff-only
python3 "$HOME/.local/share/personal-skills/install.py"
```

Windows (PowerShell):

```powershell
git -C "$env:LOCALAPPDATA\personal-skills" pull --ff-only
py -3 "$env:LOCALAPPDATA\personal-skills\install.py"
```

Installed skills are copies, so rerun the installer after every pull (or after
editing a skill in the clone). Rerunning is always safe: unchanged skills are
left alone, skills this installer copied earlier are updated, and new skills are
added. Installs made by the older symlink-based `install.sh` are converted to
copies automatically. `bash install.sh` still works on Linux and macOS; it runs
`install.py`.

## Conflicts and backups

The installer refuses to overwrite anything it did not install unchanged: another
skill with the same name, a copy you edited locally, a file, or a link pointing
elsewhere. It lists every conflict, changes nothing, and exits with status 1. To
replace them:

```bash
python3 install.py --replace      # Windows: py -3 install.py --replace
```

Each replaced entry is first renamed aside, then preserved under
`$CODEX_HOME/skill-backups/personal-skills-<date>-<id>/`. If moving it into the
backup directory fails, the error names the retained old entry. Restore a backup
by moving it back into `$CODEX_HOME/skills`.

All skills are validated and copied to a temporary directory before any installed
skill is touched. Each skill is swapped in with a rename, with rollback attempted
if installing that skill fails. Earlier successful skills remain updated if a
later skill fails. Errors exit with status 1 and say what failed. Run only one
installer at a time; concurrent installs are not supported.

## Skills

- [security-campaign](skills/security-campaign/SKILL.md): five instructions for sustained vulnerability research, reproducible evidence, useful handoffs, and cleanup.

## Add a skill

Create `skills/<name>/SKILL.md` starting with YAML front matter whose `name` is
`<name>` and which has a `description`, followed by its instructions. Commit it and
rerun the installer. The installer rejects skills with missing or mismatched front
matter before changing anything.

## Uninstall

Delete `$CODEX_HOME/skills/<name>` for the skill you want to remove. Each copy
contains a `.personal-skills.json` file that records its source and content hash,
which the installer uses to recognise its own unmodified copies.

## Development

```bash
python3 -m unittest discover -s tests -v
```

CI runs the tests and a real install on Linux, macOS and Windows.
