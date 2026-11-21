.DEFAULT_GOAL := help

.PHONY: help setup resume status auth github-auth dotfiles dotfiles-update network mcp-setup mcp-pair mcp-stop

help:
	@printf '%s\n' \
	  'make setup                         Create a sandbox (optionally set REPO, WORKSPACE or DOTFILES)' \
	  'make resume NAME=t3-code-codex     Resume setup in an existing sandbox (accepts REPO and DOTFILES)' \
	  'make status NAME=t3-code-codex     Show the sandbox state and SSH host (DETAILS=1 checks inside)' \
	  'make dotfiles DOTFILES=self        Apply dotfiles in an existing sandbox' \
	  'make dotfiles-update               Fetch and apply the existing dotfiles checkout' \
	  'make github-auth                   Sign in to GitHub in the sandbox' \
	  'make auth                          Sign in to ChatGPT for Docker Sandboxes' \
	  'make network                       Preview NETWORK_ALLOW rules (APPLY=1 adds them)' \
	  'make mcp-setup MCP_HOSTNAME=...     Connect external MCP clients via Cloudflare Tunnel (macOS)' \
	  'make mcp-pair                      Issue a short-lived code (MCP_ACCESS=read-only by default)' \
	  'make mcp-stop                      Stop the local MCP tunnel and SSH forward' \
	  'Settings: sandbox.local.conf, or CONFIG=/path/to/settings.conf. See sandbox.conf.example.'

# GNU Make passes command-line variable assignments to the script as environment variables.
setup resume status auth github-auth dotfiles dotfiles-update network mcp-setup mcp-pair mcp-stop:
	@sh ./scripts/host/setup.sh $@
