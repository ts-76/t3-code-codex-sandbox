#!/bin/sh
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
if [ -d /nix ]; then
    df -h /nix | awk 'NR == 2 { printf "Nix storage: %s used of %s (%s)\n", $3, $2, $5 }'
fi
if [ -f "${XDG_DATA_HOME:-$HOME/.local/share}/devbox/global/default/devbox.json" ]; then
    printf "%s\n" "Devbox configuration: present"
    tool_version devbox "Devbox CLI" version
fi
