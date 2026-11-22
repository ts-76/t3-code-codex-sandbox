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
        choices=(
            "setup", "resume", "status", "auth", "github-auth", "dotfiles", "dotfiles-update", "network",
            "link-setup", "link-stop", "mcp-setup", "mcp-pair", "mcp-stop",
        ),
        default="setup",
        help="Create or manage a sandbox, its T3 Code environment link, and optional public MCP access.",
    )
    parser.add_argument("--name", help="Sandbox name (default: t3-code-codex).")
    parser.add_argument("--config", type=Path, help="Settings file (default: ./sandbox.local.conf if present).")
    project = parser.add_mutually_exclusive_group()
    project.add_argument("--repo", help="GitHub repository to clone inside the sandbox.")
    project.add_argument("--workspace", type=Path, help="Local directory to share.")
    parser.add_argument("--t3-version", help="T3 Code version to install.")
    github = parser.add_mutually_exclusive_group()
    github.add_argument(
        "--github-auth", action="store_true", dest="github_auth", default=None,
        help="Enable GitHub sign-in during setup or resume.",
    )
    github.add_argument(
        "--skip-github-auth", action="store_false", dest="github_auth",
        help="Skip GitHub sign-in during setup or resume.",
    )
    parser.add_argument("--details", action="store_true", help="With status, check inside the sandbox and start it if stopped.")
    parser.add_argument("--allow-network", help="With network, override the comma-separated hostname list.")
    parser.add_argument("--apply", action="store_true", help="With network, add the listed rules to the selected sandbox.")
    parser.add_argument("--mcp-hostname", help="With mcp-setup, hostname in a Cloudflare-managed DNS zone.")
    parser.add_argument("--mcp-local-port", help="With link-setup or mcp-setup, Mac SSH forward port (default: 13773).")
    parser.add_argument(
        "--link-access",
        choices=("read-only", "approval-required", "auto-accept-edits", "auto", "full-access"),
        help="With link-setup, the most agents on this Mac may do in the sandbox (default: auto).",
    )
    parser.add_argument(
        "--mcp-access",
        choices=("read-only", "approval-required", "auto-accept-edits", "auto", "full-access"),
        help="With mcp-pair, permission level to select on the OAuth approval screen (default: read-only).",
    )
    parser.add_argument("--dotfiles", help="Install dotfiles from self (signed-in GitHub account) or an HTTPS clone URL.")
    parser.add_argument(
        "--run-dotfiles-scripts",
        action=argparse.BooleanOptionalAction,
        help="Enable or disable chezmoi scripts when applying dotfiles.",
    )
    parser.add_argument(
        "--dotfiles-nix",
        action=argparse.BooleanOptionalAction,
        help="Enable or disable installing Nix before applying dotfiles.",
    )
    args = parser.parse_args()

    if args.action != "setup" and (args.workspace or args.t3_version):
        parser.error("--workspace and --t3-version require setup.")
    if args.action not in ("setup", "resume") and (args.repo is not None or args.github_auth is not None):
        parser.error("--repo and GitHub authentication options require setup or resume.")
    if args.details and args.action != "status":
        parser.error("--details requires status.")
    if args.action != "network" and (args.allow_network is not None or args.apply):
        parser.error("--allow-network and --apply require network.")
    if args.action != "mcp-setup" and args.mcp_hostname is not None:
        parser.error("--mcp-hostname requires mcp-setup.")
    if args.action not in ("link-setup", "mcp-setup") and args.mcp_local_port is not None:
        parser.error("--mcp-local-port requires link-setup or mcp-setup.")
    if args.action != "link-setup" and args.link_access is not None:
        parser.error("--link-access requires link-setup.")
    if args.action != "mcp-pair" and args.mcp_access is not None:
        parser.error("--mcp-access requires mcp-pair.")
    dotfiles_options = (args.dotfiles, args.run_dotfiles_scripts, args.dotfiles_nix)
    if any(value is not None for value in dotfiles_options) and args.action not in (
        "setup", "resume", "dotfiles", "dotfiles-update",
    ):
        parser.error("Dotfiles options require setup, resume, dotfiles or dotfiles-update.")
    package_directory = Path(__file__).resolve().parent
    values = {
        "NAME": args.name,
        "CONFIG": str(args.config.expanduser()) if args.config is not None else None,
        "REPO": args.repo,
        "WORKSPACE": str(args.workspace.expanduser().resolve()) if args.workspace is not None else None,
        "T3_VERSION": args.t3_version,
        "GITHUB_AUTH": args.github_auth,
        "DETAILS": "1" if args.details else None,
        "DOTFILES": args.dotfiles,
        "DOTFILES_SCRIPTS": args.run_dotfiles_scripts,
        "DOTFILES_NIX": args.dotfiles_nix,
        "NETWORK_ALLOW": args.allow_network,
        "APPLY": "1" if args.apply else None,
        "MCP_HOSTNAME": args.mcp_hostname,
        "MCP_LOCAL_PORT": args.mcp_local_port,
        "MCP_ACCESS": args.mcp_access,
        "LINK_ACCESS": args.link_access,
    }
    environment = os.environ | {
        "T3_SETUP_FRONTEND": "uvx", "T3_SETUP_CWD": os.getcwd(), "T3_SETUP_PYTHON": sys.executable,
    }
    for name, value in values.items():
        if isinstance(value, bool):
            environment[name] = "1" if value else "0"
        elif value is not None:
            environment[name] = value
    try:
        os.chdir(package_directory)
        os.execvpe("sh", ["sh", "./scripts/host/setup.sh", args.action], environment)
    except FileNotFoundError:
        print("A POSIX sh is required to run t3-code-codex-setup.", file=sys.stderr)
        return 1
