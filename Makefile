.DEFAULT_GOAL := help

export NAME ?= t3-code-codex
export WORKSPACE ?=
export T3_VERSION ?=
export BUILDER ?= sbx-t3-kit-builder

.PHONY: help setup auth

help:
	@printf '%s\n' \
	  'make setup WORKSPACE=/path/to/project [NAME=t3-code-codex] [T3_VERSION=0.1.11]' \
	  'make auth  Sign in to ChatGPT for Docker Sandboxes'

auth:
	sbx secret set openai --oauth

setup:
	@set -eu; \
	if [ -z "$$WORKSPACE" ] || [ ! -d "$$WORKSPACE" ]; then \
	  printf '%s\n' 'Set WORKSPACE to an existing project directory.' >&2; \
	  exit 1; \
	fi; \
	if [ -z "$$NAME" ] || [ -z "$$BUILDER" ]; then \
	  printf '%s\n' 'NAME and BUILDER must be non-empty.' >&2; \
	  exit 1; \
	fi; \
	workspace=$$(CDPATH= cd -P -- "$$WORKSPACE" && pwd -P); \
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
	set --; \
	if [ -n "$$T3_VERSION" ]; then \
	  set -- --kit-arg "t3code-ssh.version=$$T3_VERSION"; \
	fi; \
	BUILDX_BUILDER="$$BUILDER" sbx create --name "$$NAME" --kit ./t3code-ssh "$$@" codex "$$workspace"; \
	printf '\nT3 Code SSH host: %s.sbx\nWorkspace: %s\n' "$$NAME" "$$workspace"
