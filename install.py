#!/usr/bin/env python3
"""Install the skills in this repository into Codex.

Copies each ``skills/<name>`` directory into ``$CODEX_HOME/skills/<name>``
(default ``~/.codex/skills``). Works the same on Linux, macOS and native
Windows using only the Python standard library (Python 3.9+).

Rerunning is safe: unchanged skills are left alone, and copies this installer
made earlier are updated in place. Anything else at a destination -- your own
skill, a locally edited copy, an unknown link -- is a conflict: the installer
changes nothing and exits 1 unless --replace is given, in which case the old
entry is moved to ``$CODEX_HOME/skill-backups/`` first.
"""

import argparse
import errno
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import time

if sys.version_info < (3, 9):
    sys.exit("install.py needs Python 3.9 or newer (found %s)." % sys.version.split()[0])

MARKER = ".personal-skills.json"
IGNORED = {MARKER, "__pycache__", ".DS_Store", "Thumbs.db"}
REPO_DIR = os.path.dirname(os.path.abspath(__file__))


class InstallError(Exception):
    pass


def codex_home():
    value = os.environ.get("CODEX_HOME", "").strip()
    if not value:
        value = os.path.join(os.path.expanduser("~"), ".codex")
    return os.path.abspath(os.path.expanduser(value))


def tree_files(root):
    """Return sorted (posix relative path, absolute path) for regular files."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED)
        for name in filenames:
            if name in IGNORED:
                continue
            path = os.path.join(dirpath, name)
            found.append((os.path.relpath(path, root).replace(os.sep, "/"), path))
    return sorted(found)


def tree_hash(root):
    digest = hashlib.sha256()
    for rel, path in tree_files(root):
        digest.update(rel.encode("utf-8") + b"\0")
        with open(path, "rb") as handle:
            digest.update(hashlib.sha256(handle.read()).digest())
    return digest.hexdigest()


def check_skill(source, name):
    """Fail early on a SKILL.md Codex would not load."""
    try:
        with open(os.path.join(source, "SKILL.md"), encoding="utf-8-sig") as handle:
            lines = handle.read().splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise InstallError("Cannot read %s/SKILL.md: %s" % (name, error))
    if not lines or lines[0].strip() != "---" or "---" not in [l.strip() for l in lines[1:]]:
        raise InstallError("%s/SKILL.md must start with a '---' YAML front matter block." % name)
    end = [l.strip() for l in lines].index("---", 1)
    fields = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(":")
        if sep and not line[:1].isspace():
            fields[key.strip()] = value.strip().strip("'\"")
    if fields.get("name") != name:
        raise InstallError("%s/SKILL.md front matter 'name' must be %r." % (name, name))
    if not fields.get("description"):
        raise InstallError("%s/SKILL.md front matter needs a 'description'." % name)


def find_skills():
    skills_root = os.path.join(REPO_DIR, "skills")
    if not os.path.isdir(skills_root):
        raise InstallError("No skills directory at %s." % skills_root)
    skills = []
    for name in sorted(os.listdir(skills_root)):
        source = os.path.join(skills_root, name)
        if os.path.isfile(os.path.join(source, "SKILL.md")):
            check_skill(source, name)
            skills.append((name, source))
    if not skills:
        raise InstallError("No skills found under %s." % skills_root)
    return skills


def is_link(path):
    """True for symlinks and Windows junctions."""
    if os.path.islink(path):
        return True
    isjunction = getattr(os.path, "isjunction", None)  # Python 3.12+
    if isjunction is not None:
        return isjunction(path)
    try:
        return bool(os.lstat(path).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (AttributeError, OSError):
        return False


def read_marker(path):
    try:
        with open(os.path.join(path, MARKER), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def classify(name, source, destination, source_hash):
    """Return (action, reason) for one skill without changing anything."""
    if not os.path.lexists(destination):
        return "install", None
    if is_link(destination):
        # Earlier versions of this installer symlinked skills to the checkout.
        try:
            same = os.path.samefile(os.path.realpath(destination), source)
        except OSError:
            same = False
        if same:
            return "migrate", None
        return "conflict", "a link this installer did not create"
    if not os.path.isdir(destination):
        return "conflict", "a file, not a skill directory"
    marker = read_marker(destination)
    if not marker or marker.get("skill") != name or "hash" not in marker:
        return "conflict", "a directory this installer did not create"
    current = tree_hash(destination)
    if current != marker["hash"]:
        return "conflict", "an installed copy with local edits"
    if current == source_hash:
        return "current", None
    return "update", None


def _make_writable_and_retry(function, path, _info):
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
    function(path)


def remove_tree(path):
    """Delete a directory or link; handles read-only files on Windows."""
    if is_link(path) or not os.path.isdir(path):
        try:
            os.unlink(path)
        except OSError:
            os.rmdir(path)  # Windows directory symlinks and junctions
    elif sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_make_writable_and_retry)
    else:
        shutil.rmtree(path, onerror=_make_writable_and_retry)


def move(source, destination):
    """Rename; copy instead only when the two paths are on different filesystems."""
    try:
        os.replace(source, destination)
    except OSError as error:
        cross_device = error.errno == errno.EXDEV or getattr(error, "winerror", None) == 17
        if not cross_device or os.path.lexists(destination):
            raise
        shutil.move(source, destination)


def stage(name, source, source_hash, work_dir):
    staged = os.path.join(work_dir, name)
    shutil.copytree(source, staged, ignore=shutil.ignore_patterns(*IGNORED))
    if tree_hash(staged) != source_hash:
        raise InstallError("The copy of %s does not match its source; was it changing?" % name)
    with open(os.path.join(staged, MARKER), "w", encoding="utf-8") as handle:
        json.dump({"skill": name, "hash": source_hash, "source": source}, handle, indent=2)
        handle.write("\n")
    return staged


def put_in_place(name, staged, destination, action, backup):
    """Swap one skill into place, restoring the previous entry on failure."""
    aside = None
    if action != "install":
        # A rename within the same directory is atomic and never crosses filesystems.
        aside = tempfile.mkdtemp(prefix=".%s.old-" % name, dir=os.path.dirname(destination))
        os.rmdir(aside)
        os.replace(destination, aside)
    try:
        move(staged, destination)
    except BaseException:
        if os.path.lexists(destination):
            remove_tree(destination)
        if aside:
            os.replace(aside, destination)
        raise
    if action == "conflict":
        target = backup(name)
        try:
            move(aside, target)
        except OSError as error:
            raise InstallError("%s was installed, but its previous version is still at %s "
                               "(backup failed: %s)." % (name, aside, error))
        print("Backed up: %s" % target)
    elif aside:
        try:
            remove_tree(aside)
        except OSError as error:
            print("Warning: could not remove old copy %s: %s" % (aside, error), file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Install or update this repository's skills in $CODEX_HOME/skills "
        "(default ~/.codex/skills).")
    parser.add_argument("--replace", action="store_true",
                        help="back up conflicting entries to $CODEX_HOME/skill-backups and replace them")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change without changing anything")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:  # never crash on a path the console encoding cannot show
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass

    home = codex_home()
    skills_dir = os.path.join(home, "skills")
    try:
        skills = find_skills()
        if os.path.lexists(skills_dir) and not os.path.isdir(skills_dir):
            raise InstallError("%s exists but is not a directory." % skills_dir)

        plan = []
        for name, source in skills:
            source_hash = tree_hash(source)
            destination = os.path.join(skills_dir, name)
            action, reason = classify(name, source, destination, source_hash)
            plan.append((name, source, source_hash, destination, action, reason))

        conflicts = [p for p in plan if p[4] == "conflict"]
        if conflicts and not args.replace:
            for _, _, _, destination, _, reason in conflicts:
                print("Conflict: %s is %s." % (destination, reason), file=sys.stderr)
            print("Nothing was changed. Rerun with --replace to back up and replace %s."
                  % ("it" if len(conflicts) == 1 else "them"), file=sys.stderr)
            return 1

        labels = {"install": "Installed", "update": "Updated", "migrate": "Updated (link replaced by copy)",
                  "conflict": "Replaced", "current": "Already up to date"}
        if args.dry_run:
            for name, _, _, destination, action, _ in plan:
                verb = {"install": "install", "update": "update", "migrate": "update",
                        "conflict": "back up and replace", "current": "leave unchanged"}[action]
                print("Would %s: %s -> %s" % (verb, name, destination))
            return 0

        pending = [p for p in plan if p[4] != "current"]
        for name, *_ in [p for p in plan if p[4] == "current"]:
            print("%s: %s" % (labels["current"], name))
        if not pending:
            return 0

        os.makedirs(skills_dir, exist_ok=True)
        work_dir = tempfile.mkdtemp(prefix=".personal-skills-tmp-", dir=home)
        backup_dir = []

        def backup(name):
            if not backup_dir:
                root = os.path.join(home, "skill-backups")
                os.makedirs(root, exist_ok=True)
                prefix = "personal-skills-%s-" % time.strftime("%Y%m%d-%H%M%S")
                backup_dir.append(tempfile.mkdtemp(prefix=prefix, dir=root))
            return os.path.join(backup_dir[0], name)

        done = []
        try:
            # Copy everything first so a bad source fails before anything is touched.
            staged = [stage(p[0], p[1], p[2], work_dir) for p in pending]
            for (name, _, _, destination, action, _), path in zip(pending, staged):
                put_in_place(name, path, destination, action, backup)
                done.append(name)
                print("%s: %s -> %s" % (labels[action], name, destination))
        except (OSError, InstallError) as error:
            if done:
                print("Completed before the error: %s" % ", ".join(done), file=sys.stderr)
            raise InstallError(str(error))
        finally:
            try:
                remove_tree(work_dir)
            except OSError as error:
                print("Warning: could not remove temporary directory %s: %s" % (work_dir, error),
                      file=sys.stderr)
        print("Start a new Codex session to load new or updated skills.")
        return 0
    except (OSError, InstallError) as error:
        print("Install failed: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
