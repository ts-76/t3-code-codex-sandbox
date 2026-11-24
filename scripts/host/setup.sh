#!/bin/sh
set -eu

fail() {
    printf '%s\n' "$*" >&2
    exit 1
}

. ./scripts/host/settings.sh
. ./scripts/host/status.sh
. ./scripts/host/network.sh

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
        [ -z "$config_file" ] || { printf ' --config '; shell_quote "$config_file"; }
        [ -z "$REPO${cfg_REPO-}" ] || { printf ' --repo '; shell_quote "$REPO"; }
        [ -z "$DOTFILES${cfg_DOTFILES-}" ] || { printf ' --dotfiles '; shell_quote "$DOTFILES"; }
        if [ "$GITHUB_AUTH" = 0 ]; then printf ' --skip-github-auth'; else printf ' --github-auth'; fi
        if [ "$DOTFILES_NIX" = 1 ]; then printf ' --dotfiles-nix'; else printf ' --no-dotfiles-nix'; fi
        if [ "$DOTFILES_SCRIPTS" = 1 ]; then printf ' --run-dotfiles-scripts'; else printf ' --no-run-dotfiles-scripts'; fi
    else
        set -- "NAME=$NAME" "GITHUB_AUTH=$GITHUB_AUTH"
        [ -z "$config_file" ] || set -- "$@" "CONFIG=$config_file"
        [ -z "$REPO${cfg_REPO-}" ] || set -- "$@" "REPO=$REPO"
        [ -z "$DOTFILES${cfg_DOTFILES-}" ] || set -- "$@" "DOTFILES=$DOTFILES"
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
    sh ./scripts/sandbox/dotfiles.sh --validate "$DOTFILES" "$DOTFILES_SCRIPTS" "$DOTFILES_NIX"
}

configure_dotfiles() (
    mode=$1
    if [ -t 0 ] && [ -t 1 ]; then set -- -it; else set -- -i; fi
    script=$(cat ./scripts/sandbox/dotfiles.sh) &&
        sbx exec "$@" "$NAME" -- sh -c "$script" sh "$DOTFILES" "$DOTFILES_SCRIPTS" "$DOTFILES_NIX" "$mode"
)

run_sandbox_script() (
    script=$(cat "./scripts/sandbox/$1.sh") || return
    shift
    sbx exec "$NAME" -- sh -c "$script" sh "$@"
)

clone_project() {
    run_sandbox_script clone-project "https://github.com/$repository.git" "$workspace"
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
load_settings
case "$action" in mcp-stop|link-stop) ;; *) require_command sbx ;; esac
[ -n "$NAME" ] || fail 'Set NAME to the sandbox name.'

case "$action" in
    auth) exec sbx secret set openai --oauth ;;
    github-auth) configure_github; exit ;;
    status) show_status; exit ;;
    network) configure_network; exit ;;
    link-setup|link-stop|mcp-setup|mcp-pair|mcp-stop)
        python=${T3_SETUP_PYTHON:-python3}
        require_command "$python"
        exec "$python" ./scripts/host/mcp.py "$action" "$NAME" \
            "$MCP_HOSTNAME" "$MCP_LOCAL_PORT" "$MCP_ACCESS" "$LINK_ACCESS"
        ;;
    dotfiles|dotfiles-update)
        mode=apply
        [ "$action" != dotfiles-update ] || mode=update
        validate_dotfiles
        configure_dotfiles "$mode"
        exit
        ;;
    setup|resume) ;;
    *) fail "Unknown action: $action" ;;
esac

case "$GITHUB_AUTH" in 0|1) ;; *) fail 'Set GITHUB_AUTH to 0 or 1.' ;; esac
if [ -n "$DOTFILES" ]; then
    validate_dotfiles
elif [ "$DOTFILES_SCRIPTS:$DOTFILES_NIX" != 0:0 ]; then
    fail 'Set DOTFILES when using DOTFILES_SCRIPTS or DOTFILES_NIX.'
fi

mounted_workspace=
workspace=/home/agent/workspace
if [ "$action" = resume ]; then
    [ -z "$WORKSPACE$T3_VERSION$CODEX_KIT$NIX_VOLUME" ] || fail 'WORKSPACE, T3_VERSION, CODEX_KIT and NIX_VOLUME require setup.'
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
    case "$CODEX_KIT" in
        ''|codex) ;;
        -*|*[!A-Za-z0-9._/:@-]*) fail 'Set CODEX_KIT to codex or a Codex kit reference such as docker.io/sbx/codex:0.171.0.' ;;
    esac
    printf '%s\n' "$NIX_VOLUME" | grep -Eqx '([1-9][0-9]*[gG])?' ||
        fail 'Set NIX_VOLUME to a size in gigabytes, such as 30g.'
    sandboxes=$(sbx ls --quiet)
    if printf '%s\n' "$sandboxes" | grep -Fqx -- "$NAME"; then
        printf 'Sandbox %s already exists. Connect to %s.sbx or choose another NAME.\n' "$NAME" "$NAME" >&2
        if [ -z "$WORKSPACE$T3_VERSION$CODEX_KIT$NIX_VOLUME" ]; then show_retry; fi
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
    set -- "${CODEX_KIT:-codex}"
    [ -z "$mounted_workspace" ] || set -- "$@" "$mounted_workspace"
    [ -z "$T3_VERSION" ] || set -- --kit-arg "t3code-ssh.version=$T3_VERSION" "$@"
    [ -z "$NIX_VOLUME" ] || set -- --kit ./nix-volume --kit-arg "nix-volume.size=$NIX_VOLUME" "$@"
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
