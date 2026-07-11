from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import sync


def git_result(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


class SyncBranchTests(TestCase):
    def test_git_pull_uses_current_branch(self):
        repo = Path("repo")
        calls = []

        def fake_run_git(args, cwd):
            calls.append(args)
            if args == ["branch", "--show-current"]:
                return git_result(stdout="master\n")
            if args == ["ls-remote", "--exit-code", "--heads", "origin", "master"]:
                return git_result()
            return git_result()

        with patch.object(sync, "run_git", side_effect=fake_run_git), patch("builtins.print"):
            self.assertTrue(sync.git_pull(repo))

        self.assertIn(["pull", "--rebase", "origin", "master"], calls)
        self.assertNotIn(["pull", "--rebase", "origin", "main"], calls)

    def test_git_pull_skips_missing_remote_branch(self):
        repo = Path("repo")
        calls = []

        def fake_run_git(args, cwd):
            calls.append(args)
            if args == ["branch", "--show-current"]:
                return git_result(stdout="master\n")
            if args == ["ls-remote", "--exit-code", "--heads", "origin", "master"]:
                return git_result(returncode=2, stderr="missing")
            return git_result()

        with patch.object(sync, "run_git", side_effect=fake_run_git), patch("builtins.print"):
            self.assertTrue(sync.git_pull(repo))

        pull_calls = [args for args in calls if args[:1] == ["pull"]]
        self.assertEqual([], pull_calls)

    def test_git_push_uses_current_branch(self):
        repo = Path("repo")
        calls = []

        def fake_run_git(args, cwd):
            calls.append(args)
            if args == ["branch", "--show-current"]:
                return git_result(stdout="master\n")
            if args == ["status", "--porcelain"]:
                return git_result(stdout=" M sessions/example.jsonl\n")
            return git_result()

        with patch.object(sync, "run_git", side_effect=fake_run_git), patch("builtins.print"):
            self.assertTrue(sync.git_push(repo, "push from Windows: 1 files"))

        self.assertIn(["push", "-u", "origin", "master"], calls)
        self.assertNotIn(["push", "origin", "main"], calls)
