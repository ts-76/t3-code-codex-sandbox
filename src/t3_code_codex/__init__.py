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
        choices=("setup", "resume", "status", "auth", "github-auth", "dotfiles", "dotfiles-update"),
        default="setup",
        help="Create, resume or inspect a sandbox, configure authentication, or manage dotfiles.",
    )
    parser.add_argument("--name", help="Sandbox name (default: t3-code-codex).")
    project = parser.add_mutually_exclusive_group()
    project.add_argument("--repo", help="GitHub repository to clone inside the sandbox.")
    project.add_argument("--workspace", type=Path, help="Local directory to share.")
    parser.add_argument("--t3-version", help="T3 Code version to install.")
    parser.add_argument("--skip-github-auth", action="store_true", help="Skip GitHub sign-in during setup or resume.")
    parser.add_argument("--details", action="store_true", help="With status, check inside the sandbox and start it if stopped.")
    parser.add_argument("--dotfiles", help="Install dotfiles from self (signed-in GitHub account) or an HTTPS clone URL.")
    parser.add_argument(
        "--run-dotfiles-scripts",
        action="store_true",
        help="Run chezmoi scripts when applying dotfiles.",
    )
    parser.add_argument(
        "--dotfiles-nix",
        action="store_true",
        help="Install Nix in the sandbox before applying dotfiles that require it.",
    )
    args = parser.parse_args()

    if args.action != "setup" and (args.workspace or args.t3_version):
        parser.error("--workspace and --t3-version require setup.")
    if args.action not in ("setup", "resume") and (args.repo or args.skip_github_auth):
        parser.error("--repo and --skip-github-auth require setup or resume.")
    if args.details and args.action != "status":
        parser.error("--details requires status.")
    if (args.dotfiles is not None or args.run_dotfiles_scripts or args.dotfiles_nix) and args.action not in (
        "setup", "resume", "dotfiles", "dotfiles-update",
    ):
        parser.error("Dotfiles options require setup, resume, dotfiles or dotfiles-update.")
    if args.action == "dotfiles" and not args.dotfiles:
        parser.error("dotfiles requires --dotfiles self or an HTTPS clone URL.")
    if args.action != "dotfiles-update" and not args.dotfiles and (args.run_dotfiles_scripts or args.dotfiles_nix):
        parser.error("--run-dotfiles-scripts and --dotfiles-nix require --dotfiles.")

    package_directory = Path(__file__).resolve().parent
    make_arguments = ["make", "-C", str(package_directory), args.action]
    values = {
        "NAME": args.name,
        "REPO": args.repo or "",
        "WORKSPACE": str(args.workspace.expanduser().resolve()) if args.workspace else "",
        "T3_VERSION": args.t3_version,
        "GITHUB_AUTH": "0" if args.skip_github_auth else None,
        "DETAILS": "1" if args.details else "0",
        "DOTFILES": args.dotfiles or "",
        "DOTFILES_SCRIPTS": "1" if args.run_dotfiles_scripts else "0",
        "DOTFILES_NIX": "1" if args.dotfiles_nix else "0",
    }
    for name, value in values.items():
        if value is not None:
            # GNU Make expands dollars in command-line variable assignments.
            escaped_value = value.replace("$", "$$")
            make_arguments.append(f"{name}={escaped_value}")

    try:
        os.execvpe("make", make_arguments, os.environ | {"T3_SETUP_FRONTEND": "uvx"})
    except FileNotFoundError:
        print("Install GNU Make before running t3-code-codex-setup.", file=sys.stderr)
        return 1
