.DEFAULT_GOAL := help

export NAME ?= t3-code-codex
export REPO ?=
export WORKSPACE ?=
export DOTFILES ?=
export DOTFILES_SCRIPTS ?= 0
export DOTFILES_NIX ?= 0
export T3_VERSION ?=
export BUILDER ?= sbx-t3-kit-builder
export GITHUB_AUTH ?= 1

.PHONY: help setup auth github-auth dotfiles

define configure_github
if ! sbx exec "$$NAME" -- gh auth status --hostname github.com >/dev/null 2>&1; then \
  printf '\nSign in to GitHub inside %s. Follow the browser instructions.\n' "$$NAME"; \
  if ! sbx exec "$$NAME" -- env GH_PROMPT_DISABLED=1 gh auth login --hostname github.com --git-protocol https --web; then \
    printf 'GitHub sign-in did not complete for %s. Retry with github-auth.\n' "$$NAME" >&2; \
    exit 1; \
  fi; \
fi; \
sbx exec "$$NAME" -- gh auth setup-git --hostname github.com
endef

define configure_dotfiles
( \
  if [ -t 0 ] && [ -t 1 ]; then set -- -it; else set -- -i; fi; \
  script=$$(cat ./setup-dotfiles.sh) && \
    sbx exec "$$@" "$$NAME" -- sh -c "$$script" sh "$$DOTFILES" "$$DOTFILES_SCRIPTS" "$$DOTFILES_NIX"; \
)
endef

help:
	@printf '%s\n' \
	  'make setup REPO=owner/repo           Clone GitHub into the sandbox' \
	  'make setup                          Create an empty sandbox' \
	  'make setup WORKSPACE=/path/to/project  Share a local directory' \
	  'make setup DOTFILES=self            Install dotfiles for the signed-in GitHub account' \
	  'make setup DOTFILES=https://…       Install dotfiles from an HTTPS clone URL' \
	  'make auth                           Sign in to ChatGPT for Docker Sandboxes' \
	  'make github-auth [NAME=t3-code-codex]  Sign in to GitHub in an existing sandbox' \
	  'make dotfiles DOTFILES=self          Install or retry dotfiles in an existing sandbox' \
	  'Dotfiles options: DOTFILES_NIX=1 (install Nix), DOTFILES_SCRIPTS=1 (run chezmoi scripts)' \
	  'Setup options: NAME=t3-code-codex T3_VERSION=0.1.11 GITHUB_AUTH=0 (skip GitHub sign-in)'

auth:
	sbx secret set openai --oauth

github-auth:
	@set -eu; $(configure_github)

dotfiles:
	@set -eu; \
	sh ./setup-dotfiles.sh --validate "$$DOTFILES" "$$DOTFILES_SCRIPTS" "$$DOTFILES_NIX"; \
	$(configure_dotfiles)

setup:
	@set -eu; \
	if [ -n "$$REPO" ] && [ -n "$$WORKSPACE" ]; then \
	  printf '%s\n' 'Choose either REPO or WORKSPACE.' >&2; \
	  exit 1; \
	fi; \
	if [ -z "$$NAME" ] || [ -z "$$BUILDER" ]; then \
	  printf '%s\n' 'NAME and BUILDER must be non-empty.' >&2; \
	  exit 1; \
	fi; \
	case "$$GITHUB_AUTH" in \
	  0|1) ;; \
	  *) printf '%s\n' 'Set GITHUB_AUTH to 0 or 1.' >&2; exit 1 ;; \
	esac; \
	if [ -n "$$DOTFILES" ]; then \
	  sh ./setup-dotfiles.sh --validate "$$DOTFILES" "$$DOTFILES_SCRIPTS" "$$DOTFILES_NIX"; \
	elif [ "$$DOTFILES_SCRIPTS:$$DOTFILES_NIX" != 0:0 ]; then \
	  printf '%s\n' 'Set DOTFILES when using DOTFILES_SCRIPTS or DOTFILES_NIX.' >&2; exit 1; \
	fi; \
	workspace=/home/agent/workspace; \
	set --; \
	if [ -n "$$WORKSPACE" ]; then \
	  if [ ! -d "$$WORKSPACE" ]; then \
	    printf '%s\n' 'Set WORKSPACE to an existing project directory.' >&2; \
	    exit 1; \
	  fi; \
	  workspace=$$(CDPATH= cd -P -- "$$WORKSPACE" && pwd -P); \
	  set -- "$$workspace"; \
	fi; \
	if [ -n "$$REPO" ]; then \
	  repository=$${REPO#https://github.com/}; \
	  repository=$${repository%/}; \
	  repository=$${repository%.git}; \
	  if ! printf '%s\n' "$$repository" | grep -Eq '^[A-Za-z0-9-]+/[A-Za-z0-9_.-]+$$'; then \
	    printf '%s\n' 'Set REPO to owner/repo or https://github.com/owner/repo.git.' >&2; \
	    exit 1; \
	  fi; \
	  case "$${repository##*/}" in \
	    .|..) printf '%s\n' 'Set REPO to a GitHub repository.' >&2; exit 1 ;; \
	  esac; \
	  workspace="$$workspace/$${repository##*/}"; \
	fi; \
	sandboxes=$$(sbx ls --quiet); \
	if printf '%s\n' "$$sandboxes" | grep -Fqx -- "$$NAME"; then \
	  printf 'Sandbox %s already exists. Connect to %s.sbx or choose another NAME.\n' "$$NAME" "$$NAME" >&2; \
	  exit 1; \
	fi; \
	openai=$$(sbx secret ls --global --service openai --quiet && \
	  sbx secret ls --sandbox "$$NAME" --service openai --quiet); \
	codex_auth='existing Docker Sandboxes credential'; \
	if [ -z "$$openai" ]; then \
	  printf '\nSign in to ChatGPT for Docker Sandboxes.\n'; \
	  sbx secret set openai --oauth; \
	  codex_auth='ChatGPT sign-in completed'; \
	fi; \
	if ! docker version --format '{{.Server.Version}}' >/dev/null 2>&1; then \
	  if [ "$$(uname -s)" != Darwin ]; then \
	    printf '%s\n' 'Start the Docker Engine before running make setup.' >&2; \
	    exit 1; \
	  fi; \
	  docker desktop start --timeout 60; \
	fi; \
	docker buildx version >/dev/null; \
	docker buildx inspect "$$BUILDER" >/dev/null 2>&1 || \
	  docker buildx create --name "$$BUILDER" --driver docker-container; \
	sbx setup ssh; \
	set -- codex "$$@"; \
	if [ -n "$$T3_VERSION" ]; then \
	  set -- --kit-arg "t3code-ssh.version=$$T3_VERSION" "$$@"; \
	fi; \
	github=$$(sbx secret ls --global --service github --quiet && \
	  sbx secret ls --sandbox "$$NAME" --service github --quiet); \
	if [ -z "$$github" ]; then \
	  set -- --env GH_TOKEN= --env GITHUB_TOKEN= "$$@"; \
	fi; \
	BUILDX_BUILDER="$$BUILDER" sbx create --name "$$NAME" --kit ./t3code-ssh "$$@"; \
	if [ "$$GITHUB_AUTH" = 1 ]; then \
	  $(configure_github); \
	fi; \
	if [ -n "$$REPO" ]; then \
	  if ! sbx exec "$$NAME" -- env GIT_TERMINAL_PROMPT=0 git clone -- "https://github.com/$$repository.git" "$$workspace"; then \
	    printf 'Could not clone the repository. Connect to %s.sbx to retry.\n' "$$NAME" >&2; \
	    exit 1; \
	  fi; \
	fi; \
	if [ -n "$$DOTFILES" ]; then \
	  if ! $(configure_dotfiles); then \
	    printf 'Sandbox %s.sbx is ready. Retry using the dotfiles command with the same name and source.\n' "$$NAME" >&2; \
	    exit 1; \
	  fi; \
	fi; \
	printf '\nSandbox: %s\nT3 Code SSH host: %s.sbx\nWorkspace: %s\n' "$$NAME" "$$NAME" "$$workspace"; \
	printf 'Codex authentication: %s\n' "$$codex_auth"; \
	if [ "$$GITHUB_AUTH" = 1 ]; then \
	  printf '%s\n' 'GitHub authentication: configured'; \
	else \
	  printf '%s\n' 'GitHub authentication: skipped'; \
	fi; \
	if [ -n "$$DOTFILES" ]; then \
	  printf '%s\n' 'Dotfiles: installed in ~/dotfiles'; \
	fi; \
	printf '%s\n' '' 'Next in T3 Code' \
	  '1. Settings -> Environments -> Add environment -> SSH. Enter the SSH host above.' \
	  '2. Open Add project and select the SSH environment you just added.'; \
	if [ -n "$$REPO" ] || [ -n "$$WORKSPACE" ]; then \
	  printf '%s\n' '3. Choose Local folder and open the workspace above.'; \
	elif [ "$$GITHUB_AUTH" = 1 ]; then \
	  printf '%s\n' '3. Choose GitHub repository and select the repository to clone.' \
	    '   If Setup Required appears, select your SSH environment in Settings -> Source control & issues and click Rescan.'; \
	else \
	  printf '%s\n' '3. Choose Git URL and enter a public repository clone URL.'; \
	fi
