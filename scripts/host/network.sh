network_hosts() {
    printf '%s\n' "$NETWORK_ALLOW" | LC_ALL=C awk -F, '
        NR != 1 { exit 1 }
        {
            for (i = 1; i <= NF; i++) {
                host = tolower($i)
                gsub(/^[[:blank:]]+|[[:blank:]]+$/, "", host)
                if (host !~ /^[a-z0-9]([a-z0-9.-]*[a-z0-9])?(:[0-9]+)?$/) exit 1
                count = split(host, parts, ":")
                if (count == 2 && (parts[2] < 1 || parts[2] > 65535)) exit 1
                port = count == 2 ? parts[2] + 0 : 443
                target = parts[1] ":" port
                if (!seen[target]++) print target
            }
        }
    '
}

configure_network() {
    case "$APPLY" in 0|1) ;; *) fail 'Set APPLY to 0 or 1.' ;; esac
    [ -n "$NETWORK_ALLOW" ] || fail 'Set NETWORK_ALLOW to a comma-separated list of hostnames.'
    hosts=$(network_hosts) && [ -n "$hosts" ] ||
        fail 'NETWORK_ALLOW accepts hostnames with an optional port. Separate entries with commas.'
    sbx inspect -- "$NAME" >/dev/null
    printf 'Sandbox: %s\n' "$NAME"
    pending=
    while IFS= read -r host; do
        if sbx policy check network --sandbox "$NAME" "$host" >/dev/null 2>&1; then
            printf 'Already allowed: %s\n' "$host"
        else
            printf 'To allow: %s\n' "$host"
            pending=${pending:+$pending,}$host
        fi
    done <<EOF
$hosts
EOF

    [ -n "$pending" ] || return 0
    if [ "$APPLY" = 0 ]; then
        printf '%s\n' 'Preview only. Run with APPLY=1 (Make) or --apply (uvx) to add these rules.'
        return 0
    fi
    sbx policy allow network --sandbox "$NAME" "$pending"
    result=0
    while IFS= read -r host; do
        sbx policy check network --sandbox "$NAME" "$host" || result=1
    done <<EOF
$hosts
EOF
    return "$result"
}
