.DEFAULT_GOAL := help

export NAME ?= t3-code-codex
export REPO ?=
export WORKSPACE ?=
export T3_VERSION ?=
export BUILDER ?= sbx-t3-kit-builder

.PHONY: help setup auth

help:
	@printf '%s\n' \
	  'make setup REPO=owner/repo           Clone GitHub into the sandbox' \
	  'make setup                          Create an empty sandbox' \
	  'make setup WORKSPACE=/path/to/project  Share a local directory' \
	  'make auth                           Sign in to ChatGPT for Docker Sandboxes' \
	  'Setup options: NAME=t3-code-codex T3_VERSION=0.1.11'

auth:
	sbx secret set openai --oauth

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
	BUILDX_BUILDER="$$BUILDER" sbx create --name "$$NAME" --kit ./t3code-ssh "$$@"; \
	if [ -n "$$REPO" ]; then \
	  if ! sbx exec "$$NAME" -- env GIT_TERMINAL_PROMPT=0 git clone -- "https://github.com/$$repository.git" "$$workspace"; then \
	    printf 'Could not clone the repository. Connect to %s.sbx to retry.\n' "$$NAME" >&2; \
	    exit 1; \
	  fi; \
	fi; \
	printf '\nT3 Code SSH host: %s.sbx\nWorkspace: %s\n' "$$NAME" "$$workspace"
