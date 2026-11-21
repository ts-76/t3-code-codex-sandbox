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
export DETAILS ?= 0

.PHONY: help setup resume status auth github-auth dotfiles dotfiles-update

help:
	@printf '%s\n' \
	  'make setup                         Create a sandbox (optionally set REPO, WORKSPACE or DOTFILES)' \
	  'make resume NAME=t3-code-codex     Resume setup in an existing sandbox (accepts REPO and DOTFILES)' \
	  'make status NAME=t3-code-codex     Show the sandbox state and SSH host (DETAILS=1 checks inside)' \
	  'make dotfiles DOTFILES=self        Apply dotfiles in an existing sandbox' \
	  'make dotfiles-update               Fetch and apply the existing dotfiles checkout' \
	  'make github-auth                   Sign in to GitHub in the sandbox' \
	  'make auth                          Sign in to ChatGPT for Docker Sandboxes' \
	  'Options: NAME, T3_VERSION, GITHUB_AUTH=0, DOTFILES_NIX=1, DOTFILES_SCRIPTS=1'

setup resume status auth github-auth dotfiles dotfiles-update:
	@sh ./sandbox-setup.sh $@
