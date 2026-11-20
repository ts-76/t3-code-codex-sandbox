#!/bin/sh
set -eu

validate_source() {
    case "$2:$3" in
        0:0|0:1|1:0|1:1) ;;
        *) printf '%s\n' 'Set DOTFILES_SCRIPTS and DOTFILES_NIX to 0 or 1.' >&2; exit 1 ;;
    esac
    case "$1" in
        self) return ;;
        https://*)
            address=${1#https://}
            host=${address%%/*}
            case "$host" in
                ''|*@*) ;;
                *)
                    case "$address" in
                        *[[:space:][:cntrl:]]*|*'?'*|*'#'*) ;;
                        */?*) return ;;
                    esac
                    ;;
            esac
            ;;
    esac
    printf '%s\n' 'Set DOTFILES to self or an HTTPS clone URL without credentials.' >&2
    exit 1
}

is_chezmoi_source() {
    for entry in .chezmoi* dot_* *_dot_*; do
        if [ -e "$entry" ] || [ -L "$entry" ]; then
            return 0
        fi
    done
    return 1
}

install_chezmoi() (
    version=2.74.1
    case "$(uname -m)" in
        x86_64)
            arch=amd64
            checksum=ae01c66b1a6dbf563667c63fbbd9986b3cfa3c98dd266ddee732f63e8af2e9d1
            ;;
        aarch64)
            arch=arm64
            checksum=8c62619c4303770342e7c7e75d168b6cc6efee4ad5e4b994980de7cf794d68e2
            ;;
        *) printf 'No bundled chezmoi download for %s.\n' "$(uname -m)" >&2; exit 1 ;;
    esac
    archive=chezmoi_${version}_linux_$arch.tar.gz
    staging=$(mktemp -d)
    trap 'rm -rf "$staging"' 0
    cd "$staging"
    curl -fsSL --retry 3 "https://github.com/twpayne/chezmoi/releases/download/v$version/$archive" -o "$archive"
    printf '%s  %s\n' "$checksum" "$archive" | sha256sum --check
    tar -xzf "$archive" chezmoi
    mkdir -p "$HOME/.local/bin"
    install -m 755 chezmoi "$HOME/.local/bin/chezmoi"
)

if [ "$1" = --validate ]; then
    validate_source "$2" "$3" "$4"
    exit 0
fi

source=$1
run_scripts=$2
with_nix=$3
validate_source "$source" "$run_scripts" "$with_nix"
if [ "$source" = self ]; then
    if ! account=$(gh api --hostname github.com user --jq .login) || [ -z "$account" ]; then
        printf '%s\n' 'Sign in to GitHub in this sandbox to use DOTFILES=self.' >&2
        exit 1
    fi
    source="https://github.com/$account/dotfiles.git"
fi

directory=$HOME/dotfiles
if [ -e "$directory" ] || [ -L "$directory" ]; then
    if [ -L "$directory" ] || [ ! -d "$directory/.git" ] ||
        [ "$(git -C "$directory" config --local --get remote.origin.url)" != "$source" ]; then
        printf 'Dotfiles destination already exists: %s\n' "$directory" >&2
        exit 1
    fi
else
    GIT_TERMINAL_PROMPT=0 git clone -- "$source" "$directory"
fi
cd "$directory"

export PATH="$HOME/.local/bin:$PATH"
if [ "$with_nix" = 1 ]; then
    if ! command -v nix >/dev/null 2>&1; then
        sudo -n apt-get update
        sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends nix-bin
    fi
    export NIX_CONFIG="${NIX_CONFIG:+$NIX_CONFIG
}extra-experimental-features = nix-command flakes"
fi

if [ -f install.sh ]; then
    bash ./install.sh
else
    if ! is_chezmoi_source; then
        printf 'Cloned dotfiles to %s. Add an install.sh or use a chezmoi source.\n' "$directory" >&2
        exit 1
    fi
    if ! command -v chezmoi >/dev/null 2>&1; then
        install_chezmoi
    fi
    # sbx exec forwards stdin even when there is no controlling /dev/tty.
    set -- init --no-tty --source "$directory" --apply
    if [ "$run_scripts" = 0 ]; then
        set -- "$@" --exclude=scripts
    fi
    chezmoi "$@"
    if [ "$run_scripts" = 0 ]; then
        printf '%s\n' 'Chezmoi applied configuration files. Chezmoi scripts skipped.'
    else
        printf '%s\n' 'Chezmoi applied configuration files and enabled repository scripts.'
    fi
fi
printf 'Dotfiles installed from %s\n' "$directory"
