#!/bin/sh
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
