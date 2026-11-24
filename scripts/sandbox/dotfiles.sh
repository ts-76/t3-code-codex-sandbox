#!/bin/sh
set -eu

validate_source() {
    case "$2:$3" in
        0:0|0:1|1:0|1:1) ;;
        *) printf '%s\n' 'Set DOTFILES_SCRIPTS and DOTFILES_NIX to 0 or 1.' >&2; exit 1 ;;
    esac
    case "$1" in
        ''|self) return 0 ;;
        https://*)
            address=${1#https://}
            host=${address%%/*}
            case "$host" in
                ''|*@*) ;;
                *)
                    case "$address" in
                        *[[:space:][:cntrl:]]*|*'?'*|*'#'*) ;;
                        */?*) return 0 ;;
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
mode=$4
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
    if [ -L "$directory" ] || [ ! -d "$directory/.git" ]; then
        printf 'Dotfiles destination already exists: %s\n' "$directory" >&2
        exit 1
    fi
    origin=$(git -C "$directory" config --local --get remote.origin.url) || origin=
    if [ -z "$source" ]; then
        if [ -z "$origin" ]; then
            printf 'Dotfiles checkout at %s has no origin. Restore its Git remote and retry.\n' "$directory" >&2
            exit 1
        fi
        validate_source "$origin" "$run_scripts" "$with_nix"
        source=$origin
    fi
    if [ "$origin" != "$source" ]; then
        printf 'Dotfiles checkout at %s has a different origin. Check its remote before retrying.\n' "$directory" >&2
        exit 1
    fi
else
    if [ "$mode" = update ]; then
        printf 'No dotfiles checkout at %s. Run the dotfiles action first.\n' "$directory" >&2
        exit 1
    fi
    if [ -z "$source" ]; then
        printf '%s\n' 'No dotfiles checkout. Specify DOTFILES=self or a clone URL (uvx: --dotfiles).' >&2
        exit 1
    fi
    GIT_TERMINAL_PROMPT=0 git clone -- "$source" "$directory"
fi
cd "$directory"

if [ "$mode" = update ]; then
    changes=$(git status --porcelain)
    if [ -n "$changes" ]; then
        printf 'Dotfiles checkout at %s has local changes. Commit or stash them before updating.\n' "$directory" >&2
        exit 1
    fi
    GIT_TERMINAL_PROMPT=0 git pull --ff-only origin
fi
revision=$(git rev-parse --short HEAD)

export PATH="$HOME/.local/bin:$PATH"
if [ "$with_nix" = 1 ]; then
    if ! command -v nix >/dev/null 2>&1; then
        sudo -n apt-get update
        sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends nix-bin
    fi
    export NIX_CONFIG="${NIX_CONFIG:+$NIX_CONFIG
}extra-experimental-features = nix-command flakes"
    # A fresh /nix volume is empty. Without /nix/store, single-user Nix keeps its store under
    # ~/.local/share/nix on the root disk instead.
    if [ -d /nix ] && [ -w /nix ] && [ ! -e /nix/store ]; then
        mkdir -p /nix/store /nix/var/nix
    fi
fi

if [ -f install.sh ]; then
    bash ./install.sh
    method='install.sh completed'
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
        method='chezmoi, scripts skipped'
        if [ -f "${XDG_DATA_HOME:-$HOME/.local/share}/devbox/global/default/devbox.json" ]; then
            printf '%s\n' 'Devbox configuration: present. Devbox packages: not installed by this action.'
        fi
    else
        printf '%s\n' 'Chezmoi applied configuration files with repository scripts enabled.'
        method='chezmoi, scripts enabled'
    fi
fi
state=${XDG_STATE_HOME:-$HOME/.local/state}/t3-code-codex-sandbox
mkdir -p "$state"
record=$(mktemp "$state/.dotfiles.XXXXXX")
trap 'rm -f "$record"' 0
printf 'Dotfiles last apply: %s (%s)\n' "$revision" "$method" > "$record"
mv -f "$record" "$state/dotfiles"
printf 'Dotfiles: applied from %s (%s)\n' "$directory" "$revision"
