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
    [ "$DETAILS" = 0 ] || run_sandbox_script status
}
