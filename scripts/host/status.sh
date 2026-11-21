inspection_field() {
    printf '%s\n' "$inspection" |
        awk -v label="$1" '$0 ~ "^[[:space:]]*" label ":[[:space:]]*" {
            sub("^[[:space:]]*" label ":[[:space:]]*", ""); print; exit
        }'
}

show_connection() {
    printf '\nSandbox: %s\nT3 Code SSH host: %s.sbx\n' "$NAME" "$NAME"
}

show_status() {
    case "$DETAILS" in 0|1) ;; *) fail 'Set DETAILS to 0 or 1.' ;; esac
    inspection=$(LC_ALL=C sbx inspect "$NAME")
    show_connection
    printf 'State: %s\nCodex credential mode: %s\nWorking directory: %s\n' \
        "$(inspection_field State)" "$(inspection_field 'Auth mode')" "$(inspection_field 'Working directory')"
    if [ "$DETAILS" = 1 ]; then
        run_sandbox_script status || return
        case "$NAME" in *[!A-Za-z0-9_-]*) return 0 ;; esac
        if [ -f "$HOME/Library/Application Support/t3-code-codex-sandbox/mcp/$NAME/setup.json" ]; then
            "${T3_SETUP_PYTHON:-python3}" ./scripts/host/mcp.py mcp-status "$NAME"
        fi
    fi
}
