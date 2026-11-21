.DEFAULT_GOAL := help

.PHONY: help setup resume status auth github-auth dotfiles dotfiles-update network

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
	  'Settings: sandbox.local.conf, or CONFIG=/path/to/settings.conf. See config/sandbox.conf.example.'

# GNU Make passes command-line variable assignments to the script as environment variables.
setup resume status auth github-auth dotfiles dotfiles-update network:
	@sh ./scripts/host/setup.sh $@
