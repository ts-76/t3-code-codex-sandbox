trim() {
    trimmed=${1#"${1%%[![:space:]]*}"}
    printf '%s' "${trimmed%"${trimmed##*[![:space:]]}"}"
}

read_config() {
    unset cfg_NAME cfg_REPO cfg_WORKSPACE cfg_DOTFILES cfg_DOTFILES_NIX \
        cfg_DOTFILES_SCRIPTS cfg_T3_VERSION cfg_BUILDER cfg_GITHUB_AUTH cfg_NETWORK_ALLOW \
        cfg_MCP_HOSTNAME cfg_MCP_LOCAL_PORT cfg_MCP_ACCESS cfg_LINK_ACCESS
    config_file=
    start_dir=${T3_SETUP_CWD:-$PWD}
    case "${CONFIG-}" in
        '')
            [ -e "$start_dir/sandbox.local.conf" ] || return 0
            config_file=$start_dir/sandbox.local.conf
            ;;
        /*) config_file=$CONFIG ;;
        *) config_file=$start_dir/$CONFIG ;;
    esac
    [ -f "$config_file" ] && [ -r "$config_file" ] ||
        fail "Cannot read settings file: $config_file"

    number=0
    while IFS= read -r line || [ -n "$line" ]; do
        number=$((number + 1))
        line=$(trim "$line")
        case "$line" in
            ''|'#'*) continue ;;
            *=*) ;;
            *) fail "$config_file:$number: Expected KEY=value." ;;
        esac
        key=$(trim "${line%%=*}")
        value=$(trim "${line#*=}")
        case "$key" in
            NAME|REPO|WORKSPACE|DOTFILES|DOTFILES_NIX|DOTFILES_SCRIPTS|T3_VERSION|BUILDER|GITHUB_AUTH|NETWORK_ALLOW|MCP_HOSTNAME|MCP_LOCAL_PORT|MCP_ACCESS|LINK_ACCESS)
                export "cfg_$key=$value"
                ;;
            *) fail "$config_file:$number: Unknown setting: $key" ;;
        esac
    done < "$config_file"
}

load_settings() {
    read_config
    NAME=${NAME-${cfg_NAME-t3-code-codex}}
    DETAILS=${DETAILS-0}
    APPLY=${APPLY-0}
    NETWORK_ALLOW=${NETWORK_ALLOW-${cfg_NETWORK_ALLOW-}}
    MCP_HOSTNAME=${MCP_HOSTNAME-${cfg_MCP_HOSTNAME-}}
    MCP_LOCAL_PORT=${MCP_LOCAL_PORT-${cfg_MCP_LOCAL_PORT-}}
    MCP_ACCESS=${MCP_ACCESS-${cfg_MCP_ACCESS-read-only}}
    LINK_ACCESS=${LINK_ACCESS-${cfg_LINK_ACCESS-auto}}

    case "$action" in
        setup)
            # An explicit project source takes precedence over the other source in the file.
            [ -z "${REPO+x}" ] || WORKSPACE=${WORKSPACE-}
            [ -z "${WORKSPACE+x}" ] || REPO=${REPO-}
            if [ -z "${WORKSPACE+x}" ]; then
                WORKSPACE=${cfg_WORKSPACE-}
                case "$WORKSPACE" in ''|/*) ;; *) WORKSPACE="${config_file%/*}/$WORKSPACE" ;; esac
            fi
            T3_VERSION=${T3_VERSION-${cfg_T3_VERSION-}}
            BUILDER=${BUILDER-${cfg_BUILDER-sbx-t3-kit-builder}}
            ;;
    esac
    case "$action" in
        setup|resume)
            REPO=${REPO-${cfg_REPO-}}
            GITHUB_AUTH=${GITHUB_AUTH-${cfg_GITHUB_AUTH-1}}
            ;;
    esac
    WORKSPACE=${WORKSPACE-}
    T3_VERSION=${T3_VERSION-}
    case "$action" in
        setup|resume|dotfiles|dotfiles-update)
            DOTFILES=${DOTFILES-${cfg_DOTFILES-}}
            DOTFILES_NIX=${DOTFILES_NIX-${cfg_DOTFILES_NIX-0}}
            DOTFILES_SCRIPTS=${DOTFILES_SCRIPTS-${cfg_DOTFILES_SCRIPTS-0}}
            ;;
    esac
}
