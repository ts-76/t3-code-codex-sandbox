import argparse
import os
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Set up a Docker Sandbox for Codex and T3 Code over SSH.",
    )
    parser.add_argument(
        "action",
        nargs="?",
        choices=("setup", "auth", "github-auth"),
        default="setup",
        help="Create a sandbox, sign in to ChatGPT, or resume GitHub sign-in.",
    )
    parser.add_argument("--name", help="Sandbox name (default: t3-code-codex).")
    project = parser.add_mutually_exclusive_group()
    project.add_argument("--repo", help="GitHub repository to clone inside the sandbox.")
    project.add_argument("--workspace", type=Path, help="Local directory to share.")
    parser.add_argument("--t3-version", help="T3 Code version to install.")
    parser.add_argument("--skip-github-auth", action="store_true", help="Skip GitHub sign-in during setup.")
    args = parser.parse_args()

    if args.action != "setup" and (args.repo or args.workspace or args.t3_version or args.skip_github_auth):
        parser.error("--repo, --workspace, --t3-version and --skip-github-auth require setup.")

    package_directory = Path(__file__).resolve().parent
    make_arguments = ["make", "-C", str(package_directory), args.action]
    values = {
        "NAME": args.name,
        "REPO": args.repo or "",
        "WORKSPACE": str(args.workspace.expanduser().resolve()) if args.workspace else "",
        "T3_VERSION": args.t3_version,
        "GITHUB_AUTH": "0" if args.skip_github_auth else None,
    }
    for name, value in values.items():
        if value is not None:
            # GNU Make expands dollars in command-line variable assignments.
            escaped_value = value.replace("$", "$$")
            make_arguments.append(f"{name}={escaped_value}")

    try:
        os.execvp("make", make_arguments)
    except FileNotFoundError:
        print("Install GNU Make before running t3-code-codex-setup.", file=sys.stderr)
        return 1
