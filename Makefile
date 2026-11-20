.DEFAULT_GOAL := help

export NAME ?= t3-code-codex
export REPO ?=
export WORKSPACE ?=
export T3_VERSION ?=
export BUILDER ?= sbx-t3-kit-builder
export GITHUB_AUTH ?= 1

.PHONY: help setup auth github-auth

define configure_github
if ! sbx exec "$$NAME" -- gh auth status --hostname github.com >/dev/null 2>&1; then \
  printf '\nSign in to GitHub inside %s. Follow the browser instructions.\n' "$$NAME"; \
  if ! sbx exec "$$NAME" -- env GH_PROMPT_DISABLED=1 gh auth login --hostname github.com --git-protocol https --web; then \
    printf 'GitHub sign-in did not complete. Run make github-auth NAME=%s to retry.\n' "$$NAME" >&2; \
    exit 1; \
  fi; \
fi; \
sbx exec "$$NAME" -- gh auth setup-git --hostname github.com
endef

help:
	@printf '%s\n' \
	  'make setup REPO=owner/repo           Clone GitHub into the sandbox' \
	  'make setup                          Create an empty sandbox' \
	  'make setup WORKSPACE=/path/to/project  Share a local directory' \
	  'make auth                           Sign in to ChatGPT for Docker Sandboxes' \
	  'make github-auth [NAME=t3-code-codex]  Sign in to GitHub in an existing sandbox' \
	  'Setup options: NAME=t3-code-codex T3_VERSION=0.1.11 GITHUB_AUTH=0 (skip GitHub sign-in)'

auth:
	sbx secret set openai --oauth

github-auth:
	@set -eu; $(configure_github)

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
	if [ -z "$$openai" ]; then \
	  printf '\nSign in to ChatGPT for Docker Sandboxes.\n'; \
	  sbx secret set openai --oauth; \
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
	printf '\nT3 Code SSH host: %s.sbx\nWorkspace: %s\n' "$$NAME" "$$workspace"
