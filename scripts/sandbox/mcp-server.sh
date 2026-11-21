#!/bin/sh

# The SSH session owns this process only when a desktop SSH server is absent.
# t3 shares its ownership lock and data directory with the desktop connection.
trap 'exit 0' HUP INT TERM
child=
trap '[ -z "$child" ] || kill "$child" 2>/dev/null || :' EXIT

if [ -d "$HOME/workspace" ]; then
    cd "$HOME/workspace" || exit 1
fi
while :; do
    if curl -q --noproxy '*' -fsS --max-time 2 \
        http://127.0.0.1:3773/.well-known/t3/environment >/dev/null 2>&1; then
        sleep 5
        continue
    fi

    # The serve command can print its own pairing token on startup.
    t3 serve --mode desktop --no-browser --host 127.0.0.1 --port 3773 \
        --base-dir "$HOME/.t3" </dev/null >/dev/null 2>&1 &
    child=$!
    wait "$child"
    child=
    printf '%s\n' 'T3 server exited. Checking the sandbox again in 5 seconds.' >&2
    sleep 5
done
