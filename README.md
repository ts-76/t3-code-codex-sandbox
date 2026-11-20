# T3 Code Codex Sandbox

Docker Sandboxes の Codex ワークロードに T3 Code サーバーを追加する v3 ミックスインです。T3 Code デスクトップアプリから SSH で接続し、サンドボックス内で Codex を実行できます。

[t3code-ssh.yaml](t3code-ssh/t3code-ssh.yaml) は T3 Code の公式 Linux アーカイブをダウンロードし、SHA-256 を照合して組み込みます。T3 Code の既定バージョンは `0.1.11` です。

## 準備

- Docker Sandboxes（`sbx` v0.51.0 で確認）
- ローカルビルド用の Docker Engine と Buildx。macOS では Docker Desktop を使用します。
- `make`（macOS 標準の GNU Make 3.81 で確認）
- T3 Code デスクトップアプリ

## サンドボックスを作成する

初回は `sbx login` で Docker Sandboxes にサインインします。

### GitHub から直接実行する

[`uvx`](https://docs.astral.sh/uv/guides/tools/) が使える場合は、任意のフォルダから実行できます。

```sh
uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git t3-code-codex-setup
```

空のサンドボックスを作成し、必要に応じて Codex と GitHub の認証を案内します。作成時にリポジトリまでクローンする場合は `--repo owner/repo`、別名で作る場合は `--name` を付けます。GitHub 認証を途中で中断した場合は、同じコマンドの末尾に `github-auth` を付けて再開します。オプション一覧は `--help` で確認できます。

### 手元にクローンして実行する

```sh
git clone https://github.com/ts-76/t3-code-codex-sandbox.git
cd t3-code-codex-sandbox
make setup
```

### セットアップ中の認証

1. サンドボックス作成前に、Mac 側に保存済みの OpenAI 認証情報を確認します。必要な場合はブラウザで ChatGPT にログインします。[Docker の Codex 認証ガイド](https://docs.docker.com/ai/sandboxes/agents/codex/#authentication)
2. 作成後、サンドボックス内の GitHub CLI で GitHub 認証を確認し、HTTPS の Git 認証を設定します。ログインが必要な場合は、ターミナルに表示される URL を開いてコードを入力します。[GitHub CLI の認証ガイド](https://cli.github.com/manual/gh_auth_login)

認証が済んだ環境では、T3 Code に SSH 接続を追加した後、プロジェクト追加画面の **GitHub repository** からリポジトリを選べます。必要に応じて、サンドボックスを選択した状態で **Settings → Source control & issues → Rescan** を実行してください。[T3 Code の GitHub 認証ガイド](https://github.com/pingdotgg/t3code/blob/v0.1.11/docs/user/source-control.md#github)

### GitHub からサンドボックス内へクローンする

`REPO` に GitHub の `owner/repo` または HTTPS のクローン URL を指定します。

```sh
make setup REPO=docker/welcome-to-docker
```

`make setup` は Mac のプロジェクトフォルダを共有せずにサンドボックスを作成し、リポジトリを `/home/agent/workspace/<リポジトリ名>` にクローンします。作業ファイルはサンドボックス内に保存されます。残したい変更は、サンドボックスを削除する前に GitHub へ push するかコピーしてください。[Docker のマウントなしワークスペース](https://docs.docker.com/ai/sandboxes/workflows/git/#mountless-sandbox)

非公開リポジトリを使う場合は、そのリポジトリにアクセスできる GitHub アカウントで認証してください。

### Mac の作業フォルダを共有する

Mac 側の既存フォルダを共有したい場合は、`WORKSPACE` にパスを指定します。

```sh
make setup WORKSPACE="/absolute/path/to/project"
```

### 作成時のオプション

`make setup` は macOS で必要に応じて Docker Desktop を起動し、Buildx ビルダーと SSH 接続を準備してからサンドボックスを作成します。完了時にサンドボックス名、SSH ホスト名、作業フォルダ、Codex と GitHub の認証状況、T3 Code で次に選ぶ項目を表示します。`uvx` で実行した場合も同じ案内が表示されます。

既定のサンドボックス名は `t3-code-codex` です。作成済みの環境にはそのまま接続できます。別のリポジトリや T3 Code バージョンで作成する場合は、新しい `NAME` を指定してください。

```sh
make setup REPO=owner/repo NAME=t3-code-codex-project T3_VERSION=0.1.11
```

`T3_VERSION` は使っているデスクトップアプリのバージョンに合わせます。省略時はキットに定義したバージョンを使います。デスクトップアプリは、バージョンが一致する T3 サーバーを再利用します。[T3 Code の SSH 起動処理](https://github.com/pingdotgg/t3code/blob/v0.1.11/packages/ssh/src/tunnel.ts#L2995-L3026)

GitHub 認証を後から行う場合は `make setup GITHUB_AUTH=0` を使います。認証の再開は `make github-auth NAME=t3-code-codex` で行えます。ChatGPT の再認証には `make auth` を使います。

### dotfiles を入れる

GitHub 認証済みのアカウントの `<ユーザー名>/dotfiles` を使う場合は `DOTFILES=self` を指定します。別のリポジトリを使う場合は HTTPS のクローン URL を指定します。

```sh
make setup DOTFILES=self
make setup DOTFILES=https://github.com/owner/dotfiles.git
```

`uvx` では `--dotfiles self` または `--dotfiles <HTTPS のクローン URL>` を付けます。

```sh
uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git t3-code-codex-setup --dotfiles self
```

GitHub 認証と、指定があればプロジェクトのクローンを終えたあと、サンドボックスの `~/dotfiles` に dotfiles をクローンします。リポジトリのルートに `install.sh` がある場合は Bash で実行します。chezmoi 形式の場合は、必要に応じて chezmoi を導入して設定ファイルを適用します。テンプレートが名前やメールアドレスを求める場合は、ターミナルで入力します。

chezmoi テンプレートが `nix` を使う場合は、`DOTFILES_NIX=1` または `--dotfiles-nix` を追加します。サンドボックスに Nix がなければ Debian の `nix-bin` を導入し、適用中は `nix-command` と `flakes` を有効にします。

```sh
make setup DOTFILES=https://github.com/ts-76/dotfiles.git DOTFILES_NIX=1
```

chezmoi のスクリプトも実行する場合は `DOTFILES_SCRIPTS=1` または `--run-dotfiles-scripts` を追加します。Devbox のパッケージを導入するスクリプトを実行するには、サンドボックス内の Devbox と Nix、依存パッケージの配布先へのアクセスが必要です。

既存のサンドボックスに適用する場合や、dotfiles だけ再試行する場合は `make dotfiles NAME=t3-code-codex DOTFILES=self` を実行します。`uvx` の場合はコマンドの末尾に `dotfiles --name t3-code-codex --dotfiles self` を付けます。

## T3 Code から接続する

1. **Settings → Environments → Add environment → SSH** を開きます。
2. セットアップが表示したホスト名を入力して接続します。既定は `t3-code-codex.sbx` です。
3. プロジェクト追加時にその環境を選び、セットアップが表示した作業フォルダを開くか、**GitHub repository** から作業するリポジトリを選びます。

[Docker の T3 Code 接続ガイド](https://docs.docker.com/ai/sandboxes/integrations/t3-code/)

Apple Silicon の Mac で `sbx kit validate`、新規サンドボックスの作成、SSH トンネル越しの T3 サーバーへの接続、保存済みの ChatGPT OAuth を使った Codex の応答を確認済みです。
