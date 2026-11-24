"""End-to-end tests for install.py. Run: python -m unittest discover -s tests -v

Each test copies the installer into a temporary "repo" whose path contains
spaces, then runs it as a subprocess against a temporary CODEX_HOME.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINDOWS = os.name == "nt"
SKILL = "---\nname: {name}\ndescription: Test skill {name}.\n---\nDo {name}.\n"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def can_symlink(where):
    try:
        os.symlink(where, os.path.join(where, "probe"), target_is_directory=True)
        os.unlink(os.path.join(where, "probe"))
        return True
    except (OSError, NotImplementedError):
        return False


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="skills test ")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = os.path.join(self.tmp, "my repo")
        self.home = os.path.join(self.tmp, "codex home")
        os.makedirs(self.repo)
        shutil.copy2(os.path.join(ROOT, "install.py"), self.repo)
        shutil.copy2(os.path.join(ROOT, "install.sh"), self.repo)
        for name in ("alpha", "beta"):
            self.write_skill(name)

    def write_skill(self, name, text=None):
        write(os.path.join(self.repo, "skills", name, "SKILL.md"), text or SKILL.format(name=name))

    def installed(self, name, *parts):
        return os.path.join(self.home, "skills", name, *parts)

    def run_installer(self, *args, env=None, command=None):
        environment = dict(os.environ, CODEX_HOME=self.home, PYTHONIOENCODING="utf-8")
        environment.update(env or {})
        command = command or [sys.executable, os.path.join(self.repo, "install.py")]
        return subprocess.run(command + list(args), env=environment, cwd=self.tmp,
                              capture_output=True, text=True, encoding="utf-8")

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def snapshot(self):
        files = {}
        for dirpath, _, names in os.walk(self.home):
            for name in names:
                path = os.path.join(dirpath, name)
                files[os.path.relpath(path, self.home)] = read(path)
        return files

    def test_fresh_install_copies_skills_and_extra_files(self):
        write(os.path.join(self.repo, "skills", "alpha", "references", "notes.md"), "notes\n")
        result = self.assert_ok(self.run_installer())
        self.assertIn("Installed: alpha", result.stdout)
        self.assertEqual(read(self.installed("alpha", "SKILL.md")), SKILL.format(name="alpha"))
        self.assertEqual(read(self.installed("alpha", "references", "notes.md")), "notes\n")
        self.assertFalse(os.path.islink(self.installed("alpha")))
        leftovers = [n for n in os.listdir(self.home) if n.startswith(".personal-skills-tmp")]
        self.assertEqual(leftovers, [])

    def test_rerun_is_a_no_op(self):
        self.assert_ok(self.run_installer())
        before = self.snapshot()
        result = self.assert_ok(self.run_installer())
        self.assertIn("Already up to date: alpha", result.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_update_replaces_unmodified_copy_without_backup(self):
        self.assert_ok(self.run_installer())
        self.write_skill("alpha", SKILL.format(name="alpha") + "New line.\n")
        write(os.path.join(self.repo, "skills", "gamma", "SKILL.md"), SKILL.format(name="gamma"))
        result = self.assert_ok(self.run_installer())
        self.assertIn("Updated: alpha", result.stdout)
        self.assertIn("Installed: gamma", result.stdout)
        self.assertIn("New line.", read(self.installed("alpha", "SKILL.md")))
        self.assertFalse(os.path.exists(os.path.join(self.home, "skill-backups")))

    def test_update_removes_files_deleted_from_source(self):
        extra = os.path.join(self.repo, "skills", "alpha", "old.md")
        write(extra, "old\n")
        self.assert_ok(self.run_installer())
        os.remove(extra)
        self.assert_ok(self.run_installer())
        self.assertFalse(os.path.exists(self.installed("alpha", "old.md")))

    def test_unmanaged_directory_is_refused_and_nothing_changes(self):
        write(self.installed("beta", "SKILL.md"), "mine\n")
        before = self.snapshot()
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Conflict:", result.stderr)
        self.assertIn("--replace", result.stderr)
        # alpha had no conflict, but the run is all-or-nothing up front.
        self.assertEqual(self.snapshot(), before)

    def test_locally_edited_copy_is_a_conflict(self):
        self.assert_ok(self.run_installer())
        with open(self.installed("alpha", "SKILL.md"), "a", encoding="utf-8") as handle:
            handle.write("My edit.\n")
        self.write_skill("alpha", SKILL.format(name="alpha") + "Upstream.\n")
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertIn("local edits", result.stderr)
        self.assertIn("My edit.", read(self.installed("alpha", "SKILL.md")))

    def test_replace_backs_up_conflicts(self):
        write(self.installed("alpha", "SKILL.md"), "mine\n")
        write(self.installed("alpha", "keep.txt"), "keep\n")
        result = self.assert_ok(self.run_installer("--replace"))
        self.assertIn("Backed up:", result.stdout)
        backups = os.path.join(self.home, "skill-backups")
        [run] = os.listdir(backups)
        self.assertTrue(run.startswith("personal-skills-"))
        self.assertEqual(read(os.path.join(backups, run, "alpha", "keep.txt")), "keep\n")
        self.assertEqual(read(self.installed("alpha", "SKILL.md")), SKILL.format(name="alpha"))
        self.assertFalse(os.path.exists(self.installed("alpha", "keep.txt")))

    def test_file_in_the_way_is_a_conflict(self):
        write(self.installed("alpha"), "a file\n")
        self.assertEqual(self.run_installer().returncode, 1)
        self.assert_ok(self.run_installer("--replace"))
        self.assertTrue(os.path.isdir(self.installed("alpha")))

    def test_dry_run_changes_nothing(self):
        result = self.assert_ok(self.run_installer("--dry-run"))
        self.assertIn("Would install: alpha", result.stdout)
        self.assertFalse(os.path.exists(self.home))

    def test_invalid_skill_fails_before_any_change(self):
        self.write_skill("beta", "no front matter\n")
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertIn("beta/SKILL.md", result.stderr)
        self.assertFalse(os.path.exists(self.home))

    def test_name_must_match_directory(self):
        self.write_skill("beta", SKILL.format(name="other"))
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertIn("'name' must be 'beta'", result.stderr)

    def test_crlf_and_bom_front_matter_is_accepted(self):
        text = "﻿" + SKILL.format(name="beta").replace("\n", "\r\n")
        with open(os.path.join(self.repo, "skills", "beta", "SKILL.md"), "w",
                  encoding="utf-8", newline="") as handle:
            handle.write(text)
        self.assert_ok(self.run_installer())

    def test_default_home_is_dot_codex_in_user_home(self):
        user = os.path.join(self.tmp, "user home")
        os.makedirs(user)
        env = {"CODEX_HOME": "", "HOME": user, "USERPROFILE": user}
        self.assert_ok(self.run_installer(env=env))
        self.assertTrue(os.path.isfile(os.path.join(user, ".codex", "skills", "alpha", "SKILL.md")))

    def test_relative_codex_home_resolves_against_cwd(self):
        self.assert_ok(self.run_installer(env={"CODEX_HOME": "rel home"}))
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "rel home", "skills", "alpha", "SKILL.md")))

    def test_non_ascii_paths(self):
        self.home = os.path.join(self.tmp, "codex höme 测试")
        self.assert_ok(self.run_installer())
        self.assertTrue(os.path.isfile(self.installed("alpha", "SKILL.md")))

    def test_skills_path_that_is_a_file_fails_clearly(self):
        write(os.path.join(self.home, "skills"), "oops\n")
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a directory", result.stderr)

    def test_legacy_symlink_to_checkout_is_migrated(self):
        if not can_symlink(self.tmp):
            self.skipTest("symlinks unavailable (Windows without Developer Mode)")
        os.makedirs(os.path.join(self.home, "skills"))
        source = os.path.join(self.repo, "skills", "alpha")
        os.symlink(source, self.installed("alpha"), target_is_directory=True)
        result = self.assert_ok(self.run_installer())
        self.assertIn("link replaced by copy", result.stdout)
        self.assertFalse(os.path.islink(self.installed("alpha")))
        self.assertTrue(os.path.isfile(os.path.join(source, "SKILL.md")), "source must survive")

    def test_foreign_symlink_is_a_conflict_and_target_survives(self):
        if not can_symlink(self.tmp):
            self.skipTest("symlinks unavailable (Windows without Developer Mode)")
        elsewhere = os.path.join(self.tmp, "elsewhere")
        write(os.path.join(elsewhere, "SKILL.md"), "other\n")
        os.makedirs(os.path.join(self.home, "skills"))
        os.symlink(elsewhere, self.installed("alpha"), target_is_directory=True)
        self.assertEqual(self.run_installer().returncode, 1)
        self.assert_ok(self.run_installer("--replace"))
        self.assertEqual(read(os.path.join(elsewhere, "SKILL.md")), "other\n")
        self.assertFalse(os.path.islink(self.installed("alpha")))

    @unittest.skipIf(WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "needs POSIX permissions as a non-root user")
    def test_failure_reports_error_and_keeps_previous_copy(self):
        self.assert_ok(self.run_installer())
        self.write_skill("alpha", SKILL.format(name="alpha") + "Upstream.\n")
        skills = os.path.join(self.home, "skills")
        os.chmod(skills, 0o555)
        self.addCleanup(os.chmod, skills, 0o755)
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Install failed:", result.stderr)
        self.assertEqual(read(self.installed("alpha", "SKILL.md")), SKILL.format(name="alpha"))

    @unittest.skipIf(WINDOWS, "POSIX wrapper")
    def test_shell_wrapper_passes_arguments(self):
        result = self.assert_ok(self.run_installer(
            "--dry-run", command=["sh", os.path.join(self.repo, "install.sh")]))
        self.assertIn("Would install: alpha", result.stdout)

    def test_repository_skills_are_valid(self):
        sys.path.insert(0, ROOT)
        self.addCleanup(sys.path.remove, ROOT)
        import install
        names = [name for name, _ in install.find_skills()]
        self.assertIn("security-campaign", names)


if __name__ == "__main__":
    unittest.main()
