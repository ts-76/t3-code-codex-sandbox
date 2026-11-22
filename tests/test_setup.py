import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
NAME = "review-fixture"
DOTFILES_URL = "https://github.com/fixture-user/dotfiles.git"
PROJECT_URL = "https://github.com/fixture-user/project.git"

# Execute the sandbox's shell locally, with an isolated HOME, workspace and Git config.
MOCK_SBX = """#!/usr/bin/env python3
import os
from pathlib import Path
import sys

root = Path(os.environ["FIXTURE_ROOT"])
action, *args = sys.argv[1:]
with (root / "trace").open("a") as trace:
    trace.write(action + "\\n")

created = root / "created"
if action == "ls":
    if created.exists():
        print(created.read_text())
elif action == "inspect":
    if not created.exists():
        sys.exit(1)
    print("  State:                   stopped")
    print("  Auth mode:               oauth · openai")
    print("  Workspace:               " + os.environ.get("FIXTURE_MOUNT", "-"))
    print("  Working directory:       /home/agent/workspace")
elif action == "secret":
    if args[:3] == ["ls", "--global", "--service"]:
        print("configured")
elif action == "create":
    created.write_text(args[args.index("--name") + 1])
    (root / "create-args").write_text("\\n".join(args))
elif action == "policy":
    operation, resource, scope, name, endpoint = args
    assert (resource, scope, name) == ("network", "--sandbox", created.read_text())
    rules = root / "rules"
    allowed = rules.read_text().splitlines() if rules.exists() else []
    if operation == "check":
        sys.exit(endpoint not in allowed)
    assert operation == "allow"
    rules.write_text("\\n".join(allowed + endpoint.split(",")) + "\\n")
elif action == "exec":
    command = args[args.index("--") + 1:]
    command = [
        str(root / "workspace" / arg.removeprefix("/home/agent/workspace/"))
        if arg.startswith("/home/agent/workspace/") else arg
        for arg in command
    ]
    os.execvp(command[0], command)
"""


class SetupTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="t3-sandbox-tests-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        (self.root / "workspace").mkdir()
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        self.trace = self.root / "trace"
        self.env = {
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(self.home),
            "FIXTURE_ROOT": str(self.root),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": f"url.{(self.root / 'dotfiles-source').as_uri()}.insteadOf",
            "GIT_CONFIG_VALUE_0": DOTFILES_URL,
            "GIT_CONFIG_KEY_1": f"url.{(self.root / 'project-source').as_uri()}.insteadOf",
            "GIT_CONFIG_VALUE_1": PROJECT_URL,
        }
        self.install_mock(bin_dir, "sbx", MOCK_SBX)
        self.install_mock(bin_dir, "docker", "#!/bin/sh\nexit 0\n")
        self.install_mock(bin_dir, "gh", """#!/bin/sh
case "$1 $2" in
    'auth status'|'auth login') [ "${FAIL_GITHUB:-}" != yes ] ;;
    'api --hostname') printf '%s\\n' fixture-user ;;
esac
""")
        self.install_mock(bin_dir, "chezmoi", """#!/bin/sh
printf '%s\\n' "$*" > "$FIXTURE_ROOT/chezmoi-args"
""")
        self.install_mock(bin_dir, "nix", "#!/bin/sh\nexit 0\n")
        self.install_mock(bin_dir, "t3", "#!/bin/sh\nprintf '%s\\n' 't3 v0.1.11'\n")
        self.install_mock(bin_dir, "codex", "#!/bin/sh\nprintf '%s\\n' 'codex-cli 0.1.0'\n")
        self.install_mock(bin_dir, "devbox", '#!/bin/sh\n[ "$1" = version ] || exit 1\nprintf "%s\\n" 0.22.0\n')

    def install_mock(self, directory, name, contents):
        path = directory / name
        path.write_text(contents)
        path.chmod(0o755)

    def run_command(self, *command, extra_env=None, success=True):
        result = subprocess.run(
            command, cwd=self.root, env=self.env | (extra_env or {}),
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def make(self, target, *args, **kwargs):
        return self.run_command("make", "-C", str(ROOT), target, f"NAME={NAME}", *args, **kwargs)

    def cli(self, *args, extra_env=None, success=True):
        package = self.root / "package" / "t3_code_codex"
        package.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / "t3_code_codex/__init__.py", package / "__init__.py")
        shutil.copytree(ROOT / "scripts", package / "scripts", dirs_exist_ok=True)
        return self.run_command(
            sys.executable, "-c", "from t3_code_codex import main; raise SystemExit(main())",
            *args, extra_env={"PYTHONPATH": str(package.parent)} | (extra_env or {}), success=success,
        )

    def git(self, repository, *args):
        return self.run_command(
            "git", "-C", str(repository), "-c", "user.name=Fixture",
            "-c", "user.email=fixture@example.invalid", *args,
        ).stdout.strip()

    def repository(self, name, filename, contents):
        repo = self.root / name
        repo.mkdir()
        self.git(repo, "init", "-q", "-b", "main")
        self.commit(repo, filename, contents)
        return repo

    def commit(self, repo, filename, contents):
        (repo / filename).write_text(contents)
        self.git(repo, "add", filename)
        self.git(repo, "commit", "-qm", f"Write {filename}")

    def existing_sandbox(self):
        (self.root / "created").write_text(NAME)

    def test_setup_passes_the_shared_workspace_as_one_argument(self):
        workspace = self.root / "shared project"
        workspace.mkdir()
        result = self.make("setup", f"WORKSPACE={workspace}", "GITHUB_AUTH=0")
        self.assertIn(f"Workspace: {workspace}", result.stdout)
        self.assertIn("Choose Local folder", result.stdout)
        self.assertEqual((self.root / "create-args").read_text().splitlines()[-1], str(workspace))

    def test_setup_failure_resumes_authentication_clone_and_dotfiles(self):
        self.repository("project-source", "README.md", "Project\n")
        self.repository("dotfiles-source", "dot_aliases", "alias hi=true\n")
        options = ("REPO=fixture-user/project", "DOTFILES=self", "DOTFILES_NIX=1")

        interrupted = self.make("setup", *options, success=False, extra_env={"FAIL_GITHUB": "yes"})
        self.assertIn(f"T3 Code SSH host: {NAME}.sbx", interrupted.stdout)
        self.assertIn("GitHub setup: incomplete", interrupted.stderr)
        self.assertIn(" resume ", interrupted.stderr)
        self.assertIn("'DOTFILES_NIX=1'", interrupted.stderr)
        self.assertFalse((self.root / "workspace" / "project").exists())

        retry = next(line.strip() for line in interrupted.stderr.splitlines() if "make -C" in line)
        resumed = self.run_command("sh", "-c", retry)
        self.assertIn("Choose Local folder", resumed.stdout)
        self.assertIn("Dotfiles: applied", resumed.stdout)
        self.assertIn("--exclude=scripts", (self.root / "chezmoi-args").read_text())
        self.assertEqual((self.root / "workspace" / "project" / "README.md").read_text(), "Project\n")
        repeated = self.make("resume", *options)
        self.assertIn("Repository already cloned", repeated.stdout)
        self.assertEqual(self.trace.read_text().splitlines().count("create"), 1)

    def test_resume_refuses_to_clone_into_a_project_conflict(self):
        self.existing_sandbox()
        existing = self.root / "workspace" / "project"
        existing.mkdir()
        (existing / "keep.txt").write_text("keep")
        result = self.make("resume", "REPO=fixture-user/project", "GITHUB_AUTH=0", success=False)
        self.assertIn("Project destination already exists", result.stderr)
        self.assertEqual((existing / "keep.txt").read_text(), "keep")

    def test_resume_refuses_to_clone_into_an_attached_workspace(self):
        self.existing_sandbox()
        result = self.make(
            "resume", "REPO=fixture-user/project", success=False,
            extra_env={"FIXTURE_MOUNT": "/tmp/host-project"},
        )
        self.assertIn("workspace attachment", result.stderr)
        self.assertEqual(self.trace.read_text(), "inspect\n")

    def test_make_retry_keeps_the_workspace_instead_of_the_configured_repository(self):
        workspace = self.root / "shared project"
        workspace.mkdir()
        config = self.root / "settings.conf"
        config.write_text("REPO=fixture-user/project\n")
        interrupted = self.make(
            "setup", f"CONFIG={config}", f"WORKSPACE={workspace}",
            success=False, extra_env={"FAIL_GITHUB": "yes"},
        )
        retry = next(line.strip() for line in interrupted.stderr.splitlines() if "make -C" in line)
        self.assertIn("REPO=", shlex.split(retry))
        resumed = self.run_command("sh", "-c", retry, extra_env={"FIXTURE_MOUNT": str(workspace)})
        self.assertIn("Choose Local folder", resumed.stdout)

    def test_status_checks_inside_only_on_request(self):
        self.existing_sandbox()
        devbox_config = self.home / ".local/share/devbox/global/default/devbox.json"
        devbox_config.parent.mkdir(parents=True)
        devbox_config.write_text("{}")
        status = self.make("status")
        self.assertIn("State: stopped", status.stdout)
        self.assertNotIn("exec", self.trace.read_text())

        detailed = self.make("status", "DETAILS=1")
        self.assertIn("T3 server on PATH: t3 v0.1.11", detailed.stdout)
        self.assertIn("GitHub CLI authentication: available", detailed.stdout)
        self.assertIn("Dotfiles last apply: no record", detailed.stdout)
        self.assertIn("Devbox CLI: 0.22.0", detailed.stdout)
        self.assertIn("exec", self.trace.read_text())

    def test_dotfiles_update_applies_new_revision_and_refuses_dirty_checkout(self):
        repo = self.repository("dotfiles-source", "install.sh", 'printf first > "$HOME/.config-test"\n')
        self.existing_sandbox()
        self.make("dotfiles", "DOTFILES=self")
        self.assertEqual((self.home / ".config-test").read_text(), "first")

        self.commit(repo, "install.sh", 'printf second > "$HOME/.config-test"\n')
        revision = self.git(repo, "rev-parse", "--short", "HEAD")
        self.make("dotfiles-update")
        self.assertEqual((self.home / ".config-test").read_text(), "second")
        status = self.make("status", "DETAILS=1")
        self.assertIn(f"Dotfiles last apply: {revision}", status.stdout)

        checkout = self.home / "dotfiles"
        (checkout / "install.sh").write_text('printf local > "$HOME/.config-test"\n')
        self.commit(repo, "install.sh", 'printf third > "$HOME/.config-test"\n')
        result = self.make("dotfiles-update", success=False)
        self.assertIn("has local changes", result.stderr)
        self.assertEqual(self.git(checkout, "rev-parse", "--short", "HEAD"), revision)
        self.assertEqual((self.home / ".config-test").read_text(), "second")

    def test_dotfiles_can_reapply_an_existing_checkout_without_reentering_the_source(self):
        repo = self.repository("dotfiles-source", "install.sh", 'printf first > "$HOME/.config-test"\n')
        self.existing_sandbox()
        self.make("dotfiles", "DOTFILES=self")
        applied = self.git(repo, "rev-parse", "--short", "HEAD")
        self.commit(repo, "install.sh", 'printf second > "$HOME/.config-test"\n')
        (self.home / ".config-test").unlink()
        result = self.cli("dotfiles", "--name", NAME)
        self.assertIn(f"({applied})", result.stdout)
        self.assertEqual((self.home / ".config-test").read_text(), "first")

    def test_failed_update_keeps_the_previous_successful_apply_in_status(self):
        repo = self.repository("dotfiles-source", "install.sh", "exit 0\n")
        self.existing_sandbox()
        self.make("dotfiles", f"DOTFILES={DOTFILES_URL}")
        applied = self.git(repo, "rev-parse", "--short", "HEAD")

        self.commit(repo, "install.sh", "exit 1\n")
        fetched = self.git(repo, "rev-parse", "--short", "HEAD")
        self.make("dotfiles-update", success=False)
        status = self.make("status", "DETAILS=1")
        self.assertIn(f"Dotfiles checkout: {self.home / 'dotfiles'} ({fetched})", status.stdout)
        self.assertIn(f"Dotfiles last apply: {applied}", status.stdout)

    def test_cli_from_another_directory_provides_a_cli_retry(self):
        result = self.cli(
            "--name", NAME, "--repo", "fixture-user/project", "--dotfiles", "self", "--dotfiles-nix",
            extra_env={"FAIL_GITHUB": "yes"}, success=False,
        )
        command = re.search(r"uvx --from .* t3-code-codex-setup resume .*", result.stderr)
        self.assertIsNotNone(command, result.stderr)
        self.assertIn(f"--name '{NAME}' --repo 'fixture-user/project' --dotfiles 'self'", command[0])
        self.assertIn("--dotfiles-nix", shlex.split(command[0]))

    def test_cli_retry_preserves_workspace_and_explicit_config_overrides(self):
        self.repository("dotfiles-source", "dot_aliases", "alias hi=true\n")
        workspace = self.root / "shared project"
        workspace.mkdir()
        (self.root / "sandbox.local.conf").write_text(
            f"NAME={NAME}\nREPO=fixture-user/project\nGITHUB_AUTH=0\n"
            "DOTFILES=self\nDOTFILES_NIX=1\nDOTFILES_SCRIPTS=1\n"
        )
        interrupted = self.cli(
            "setup", "--workspace", str(workspace), "--github-auth",
            "--no-dotfiles-nix", "--no-run-dotfiles-scripts",
            success=False, extra_env={"FAIL_GITHUB": "yes"},
        )
        self.assertIn("GitHub setup: incomplete", interrupted.stderr)
        retry = next(line.strip() for line in interrupted.stderr.splitlines() if line.lstrip().startswith("uvx "))
        retry_arguments = shlex.split(retry)[4:]
        self.assertIn("--github-auth", retry_arguments)
        self.assertIn("--no-dotfiles-nix", retry_arguments)
        resumed = self.cli(*retry_arguments, extra_env={"FIXTURE_MOUNT": str(workspace)})
        self.assertIn("GitHub authentication: configured", resumed.stdout)
        self.assertIn("Choose Local folder", resumed.stdout)
        self.assertIn("--exclude=scripts", (self.root / "chezmoi-args").read_text())
        self.assertFalse((self.root / "workspace" / "project").exists())

    def test_cli_is_independent_of_invoking_shell_make_options(self):
        self.existing_sandbox()
        status = self.cli("status", "--name", NAME, extra_env={"MAKEFLAGS": "--question"})
        self.assertIn("State: stopped", status.stdout)

    def test_make_config_resolves_the_workspace_and_accepts_overrides(self):
        workspace = self.root / "shared project"
        workspace.mkdir()
        config = self.root / "my settings.conf"
        config.write_text(
            "  NAME = from-config  \nWORKSPACE=shared project\nT3_VERSION=0.1.10\n"
            "CODEX_KIT=docker.io/sbx/codex:0.170.0\nGITHUB_AUTH=0\nNETWORK_ALLOW=packages.example.org"
        )
        result = self.run_command("make", "-C", str(ROOT), "setup", f"CONFIG={config}", "T3_VERSION=0.1.11")
        self.assertIn("Sandbox: from-config", result.stdout)
        self.assertIn(f"Workspace: {workspace}", result.stdout)
        created = (self.root / "create-args").read_text().splitlines()
        self.assertIn("t3code-ssh.version=0.1.11", created)
        self.assertIn("docker.io/sbx/codex:0.170.0", created)
        self.assertNotIn("codex", created)
        self.assertNotIn("policy", self.trace.read_text())

    def test_setup_uses_the_latest_codex_kit_by_default_and_rejects_invalid_references(self):
        self.make("setup", f"NAME={NAME}", "GITHUB_AUTH=0")
        self.assertIn("codex", (self.root / "create-args").read_text().splitlines())
        result = self.make("setup", "NAME=another", "GITHUB_AUTH=0", "CODEX_KIT=--rm", success=False)
        self.assertIn("Set CODEX_KIT to codex", result.stderr)
        resumed = self.cli("resume", "--name", NAME, "--codex-kit", "docker.io/sbx/codex:0.171.0", success=False)
        self.assertIn("--codex-kit require setup", resumed.stderr)

    def test_cli_uses_the_configuration_in_its_calling_directory(self):
        self.repository("dotfiles-source", "dot_aliases", "alias hi=true\n")
        self.existing_sandbox()
        (self.root / "sandbox.local.conf").write_text("NAME=configured\nDOTFILES=self\n")
        result = self.cli("dotfiles", "--name", NAME, "--dotfiles-nix")
        self.assertIn("Dotfiles: applied", result.stdout)
        self.assertIn("--exclude=scripts", (self.root / "chezmoi-args").read_text())

    def test_unknown_config_key_fails_before_contacting_sbx(self):
        config = self.root / "bad.conf"
        config.write_text("NETWORK_ALLOWS=packages.example.org\n")
        result = self.make("status", f"CONFIG={config}", success=False)
        self.assertIn("Unknown setting: NETWORK_ALLOWS", result.stderr)
        self.assertFalse(self.trace.exists())

    def test_network_config_previews_and_only_adds_missing_rules_on_apply(self):
        self.existing_sandbox()
        config = self.root / "network settings.conf"
        config.write_text(f"NAME={NAME}\nNETWORK_ALLOW=cache.example.org, packages.example.org:443, PACKAGES.example.org")
        rules = self.root / "rules"
        rules.write_text("cache.example.org:443\n")

        result = self.cli("network", "--config", config.name)
        self.assertIn("Already allowed: cache.example.org:443", result.stdout)
        self.assertIn("Preview only", result.stdout)
        self.assertEqual(result.stdout.count("To allow: packages.example.org:443"), 1)
        self.assertEqual(rules.read_text(), "cache.example.org:443\n")

        self.make("network", f"CONFIG={config}", "APPLY=1")
        self.cli("network", "--config", config.name, "--apply")
        self.assertEqual(rules.read_text(), "cache.example.org:443\npackages.example.org:443\n")

    def test_malformed_network_list_cannot_apply_any_rules(self):
        self.existing_sandbox()
        self.make("network", "NETWORK_ALLOW=packages.example.org,*.example.org", "APPLY=1", success=False)
        self.assertFalse(self.trace.exists())
        self.assertFalse((self.root / "rules").exists())
