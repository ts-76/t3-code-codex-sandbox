#!/bin/sh
set -eu

fail() {
    printf '%s\n' "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "Install $1 before running $action."
}

shell_quote() {
    escaped=$(printf '%s' "$1" | sed "s/'/'\\\\''/g")
    printf "'%s'" "$escaped"
}

show_retry() (
    printf 'Resume the remaining setup:\n  '
    if [ "${T3_SETUP_FRONTEND:-}" = uvx ]; then
        printf '%s' 'uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git t3-code-codex-setup resume --name '
        shell_quote "$NAME"
        [ -z "$REPO" ] || { printf ' --repo '; shell_quote "$REPO"; }
        [ -z "$DOTFILES" ] || { printf ' --dotfiles '; shell_quote "$DOTFILES"; }
        [ "$GITHUB_AUTH" = 1 ] || printf ' --skip-github-auth'
        [ "$DOTFILES_NIX" = 0 ] || printf ' --dotfiles-nix'
        [ "$DOTFILES_SCRIPTS" = 0 ] || printf ' --run-dotfiles-scripts'
    else
        set -- "NAME=$NAME" "GITHUB_AUTH=$GITHUB_AUTH"
        [ -z "$REPO" ] || set -- "$@" "REPO=$REPO"
        [ -z "$DOTFILES" ] || set -- "$@" "DOTFILES=$DOTFILES"
        [ "$DOTFILES_NIX" = 0 ] || set -- "$@" "DOTFILES_NIX=$DOTFILES_NIX"
        [ "$DOTFILES_SCRIPTS" = 0 ] || set -- "$@" "DOTFILES_SCRIPTS=$DOTFILES_SCRIPTS"

        printf 'make -C '
        shell_quote "$PWD"
        printf ' resume'
        for argument do
            printf ' '
            make_argument=$(printf '%s' "$argument" | sed 's/\$/&&/g')
            shell_quote "$make_argument"
        done
    fi
    printf '\n'
) >&2

configure_github() {
    if ! sbx exec "$NAME" -- gh auth status --hostname github.com >/dev/null 2>&1; then
        printf '\nSign in to GitHub inside %s. Follow the browser instructions.\n' "$NAME"
        sbx exec "$NAME" -- env GH_PROMPT_DISABLED=1 gh auth login --hostname github.com --git-protocol https --web || return
    fi
    sbx exec "$NAME" -- gh auth setup-git --hostname github.com
}

validate_dotfiles() {
    sh ./setup-dotfiles.sh --validate "$DOTFILES" "$DOTFILES_SCRIPTS" "$DOTFILES_NIX" "$1"
}

configure_dotfiles() (
    mode=$1
    if [ -t 0 ] && [ -t 1 ]; then set -- -it; else set -- -i; fi
    script=$(cat ./setup-dotfiles.sh) &&
        sbx exec "$@" "$NAME" -- sh -c "$script" sh "$DOTFILES" "$DOTFILES_SCRIPTS" "$DOTFILES_NIX" "$mode"
)

clone_project() {
    sbx exec "$NAME" -- sh -c '
        set -eu
        url=$1
        directory=$2
        if [ -e "$directory" ] || [ -L "$directory" ]; then
            if [ ! -L "$directory" ] && [ -d "$directory/.git" ]; then
                origin=$(git -C "$directory" config --local --get remote.origin.url) || origin=
                origin=${origin%/}
                if [ "${origin%.git}" = "${url%.git}" ]; then
                    printf "Repository already cloned at %s\n" "$directory"
                    exit 0
                fi
            fi
            printf "Project destination already exists: %s\n" "$directory" >&2
            exit 1
        fi
        GIT_TERMINAL_PROMPT=0 git clone -- "$url" "$directory"
    ' sh "https://github.com/$repository.git" "$workspace"
}

inspection_field() {
    printf '%s\n' "$inspection" |
        awk -v label="$1" '$0 ~ "^[[:space:]]*" label ":[[:space:]]*" {
            sub("^[[:space:]]*" label ":[[:space:]]*", ""); print; exit
        }'
}

show_connection() {
    printf '\nSandbox: %s\nT3 Code SSH host: %s.sbx\n' "$NAME" "$NAME"
}

show_details() {
    sbx exec "$NAME" -- sh -c '
        export PATH="$PATH:$HOME/.local/bin"
        tool_version() {
            if version=$("$1" "$3" 2>/dev/null); then
                printf "%s: %s\n" "$2" "$version"
            else
                printf "%s: unavailable\n" "$2"
            fi
        }
        tool_version t3 "T3 server on PATH" --version
        tool_version codex "Codex CLI" --version
        if gh auth status --hostname github.com >/dev/null 2>&1; then
            printf "%s\n" "GitHub CLI authentication: available"
        else
            printf "%s\n" "GitHub CLI authentication: unavailable"
        fi

        if revision=$(git -C "$HOME/dotfiles" rev-parse --short HEAD 2>/dev/null) && [ -d "$HOME/dotfiles/.git" ]; then
            printf "Dotfiles checkout: %s (%s)\n" "$HOME/dotfiles" "$revision"
        else
            printf "%s\n" "Dotfiles checkout: unavailable"
        fi
        state=${XDG_STATE_HOME:-$HOME/.local/state}/t3-code-codex-sandbox/dotfiles
        if [ -f "$state" ]; then
            cat "$state"
        else
            printf "%s\n" "Dotfiles last apply: no record"
        fi
        if [ -f "${XDG_DATA_HOME:-$HOME/.local/share}/devbox/global/default/devbox.json" ]; then
            printf "%s\n" "Devbox configuration: present"
            tool_version devbox "Devbox CLI" version
        fi
    '
}

finish_setup() {
    if [ "$GITHUB_AUTH" = 1 ]; then
        if ! configure_github; then
            printf 'GitHub setup: incomplete\n' >&2
            show_retry
            exit 1
        fi
        printf 'GitHub authentication: configured\n'
    else
        printf 'GitHub authentication: skipped\n'
    fi

    if [ -n "$REPO" ]; then
        if ! clone_project; then
            printf 'Repository checkout: incomplete\n' >&2
            show_retry
            exit 1
        fi
        printf 'Repository checkout: %s\n' "$workspace"
    fi
    if [ -n "$DOTFILES" ]; then
        if ! configure_dotfiles apply; then
            printf 'Dotfiles: incomplete\n' >&2
            show_retry
            exit 1
        fi
    fi

    printf '\nWorkspace: %s\n' "$workspace"
    printf '%s\n' '' 'Next in T3 Code' \
        '1. Settings -> Environments -> Add environment -> SSH. Enter the SSH host above.' \
        '2. Open Add project and select that SSH environment.'
    if [ -n "$REPO" ] || [ -n "$mounted_workspace" ]; then
        printf '%s\n' '3. Choose Local folder and open the workspace above.'
    elif [ "$GITHUB_AUTH" = 1 ]; then
        printf '%s\n' '3. Choose GitHub repository and select the repository to clone.' \
            '   If Setup Required appears, select your SSH environment in Settings -> Source control & issues and click Rescan.'
    else
        printf '%s\n' '3. Choose Git URL and enter a public repository clone URL.'
    fi
}

prepare_docker() {
    if ! docker version --format '{{.Server.Version}}' >/dev/null 2>&1; then
        [ "$(uname -s)" = Darwin ] || fail 'Start the Docker Engine before running setup.'
        docker desktop start --timeout 60
    fi
    docker buildx version >/dev/null
    docker buildx inspect "$BUILDER" >/dev/null 2>&1 ||
        docker buildx create --name "$BUILDER" --driver docker-container
}

action=$1
require_command sbx
[ -n "$NAME" ] || fail 'Set NAME to the sandbox name.'

case "$action" in
    auth) exec sbx secret set openai --oauth ;;
    github-auth) configure_github; exit ;;
    status)
        case "$DETAILS" in 0|1) ;; *) fail 'Set DETAILS to 0 or 1.' ;; esac
        inspection=$(LC_ALL=C sbx inspect "$NAME")
        show_connection
        printf 'State: %s\nCodex credential mode: %s\nWorking directory: %s\n' \
            "$(inspection_field State)" "$(inspection_field 'Auth mode')" "$(inspection_field 'Working directory')"
        [ "$DETAILS" = 0 ] || show_details
        exit
        ;;
    dotfiles|dotfiles-update)
        mode=apply
        [ "$action" != dotfiles-update ] || mode=update
        validate_dotfiles "$mode"
        configure_dotfiles "$mode"
        exit
        ;;
    setup|resume) ;;
    *) fail "Unknown action: $action" ;;
esac

case "$GITHUB_AUTH" in 0|1) ;; *) fail 'Set GITHUB_AUTH to 0 or 1.' ;; esac
if [ -n "$DOTFILES" ]; then
    validate_dotfiles apply
elif [ "$DOTFILES_SCRIPTS:$DOTFILES_NIX" != 0:0 ]; then
    fail 'Set DOTFILES when using DOTFILES_SCRIPTS or DOTFILES_NIX.'
fi

mounted_workspace=
workspace=/home/agent/workspace
if [ "$action" = resume ]; then
    [ -z "$WORKSPACE$T3_VERSION" ] || fail 'WORKSPACE and T3_VERSION require setup.'
    inspection=$(LC_ALL=C sbx inspect "$NAME")
    workspace=$(inspection_field 'Working directory')
    [ -n "$workspace" ] || fail 'Could not determine the existing sandbox working directory.'
    workspace_mount=$(inspection_field Workspace)
    clone_source=$(inspection_field 'Clone source')
    if [ "$workspace_mount" != - ] || [ -n "${clone_source#-}" ]; then
        mounted_workspace=$workspace
        [ -z "$REPO" ] || fail 'This sandbox has a workspace attachment. Add its project from T3 Code.'
    fi
elif [ -n "$WORKSPACE" ]; then
    [ -z "$REPO" ] || fail 'Choose either REPO or WORKSPACE.'
    [ -d "$WORKSPACE" ] || fail 'Set WORKSPACE to an existing project directory.'
    workspace=$(CDPATH= cd -P -- "$WORKSPACE" && pwd -P)
    mounted_workspace=$workspace
fi

if [ -n "$REPO" ]; then
    repository=${REPO#https://github.com/}
    repository=${repository%/}
    repository=${repository%.git}
    printf '%s\n' "$repository" | grep -Eq '^[A-Za-z0-9-]+/[A-Za-z0-9_.-]+$' ||
        fail 'Set REPO to owner/repo or https://github.com/owner/repo.git.'
    case "${repository##*/}" in .|..) fail 'Set REPO to a GitHub repository.' ;; esac
    workspace="$workspace/${repository##*/}"
fi

if [ "$action" = setup ]; then
    [ -n "$BUILDER" ] || fail 'Set BUILDER to the Docker Buildx builder name.'
    sandboxes=$(sbx ls --quiet)
    if printf '%s\n' "$sandboxes" | grep -Fqx -- "$NAME"; then
        printf 'Sandbox %s already exists. Connect to %s.sbx or choose another NAME.\n' "$NAME" "$NAME" >&2
        if [ -z "$WORKSPACE$T3_VERSION" ]; then show_retry; fi
        exit 1
    fi
    require_command docker
    openai=$(sbx secret ls --global --service openai --quiet &&
        sbx secret ls --sandbox "$NAME" --service openai --quiet)
    codex_auth='existing Docker Sandboxes credential'
    if [ -z "$openai" ]; then
        printf '\nSign in to ChatGPT for Docker Sandboxes.\n'
        sbx secret set openai --oauth
        codex_auth='ChatGPT sign-in completed'
    fi

    prepare_docker
    sbx setup ssh
    set -- codex
    [ -z "$mounted_workspace" ] || set -- "$@" "$mounted_workspace"
    [ -z "$T3_VERSION" ] || set -- --kit-arg "t3code-ssh.version=$T3_VERSION" "$@"
    github=$(sbx secret ls --global --service github --quiet &&
        sbx secret ls --sandbox "$NAME" --service github --quiet)
    [ -n "$github" ] || set -- --env GH_TOKEN= --env GITHUB_TOKEN= "$@"
    BUILDX_BUILDER="$BUILDER" sbx create --name "$NAME" --kit ./t3code-ssh "$@"
    show_connection
    printf 'Codex authentication: %s\n' "$codex_auth"
else
    show_connection
fi

finish_setup
