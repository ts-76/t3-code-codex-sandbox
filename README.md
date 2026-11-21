# T3 Code Codex Sandbox

Mac の T3 Code から SSH で Docker Sandbox に接続し、サンドボックス内で Codex を使うためのセットアップです。空のサンドボックスを作ったあと、T3 Code で GitHub リポジトリを選べます。

| 項目 | 既定の名前 |
| --- | --- |
| セットアップコマンド | `t3-code-codex-setup` |
| サンドボックス | `t3-code-codex` |
| T3 Code に入力する SSH ホスト | `t3-code-codex.sbx` |

## 新規作成

Docker Sandboxes（`sbx` v0.51.0 で確認）、Docker Desktop と Buildx、GNU Make、T3 Code デスクトップアプリが必要です。初回は `sbx login` で Docker Sandboxes にサインインします。

[`uvx`](https://docs.astral.sh/uv/guides/tools/) があれば、任意のフォルダから実行できます。

```sh
uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git t3-code-codex-setup
```

作成前に Docker Sandboxes の OpenAI 認証を確認し、必要ならブラウザで ChatGPT にログインします。作成直後にサンドボックス名と SSH ホストを表示します。その後、サンドボックス内で GitHub CLI にログインし、HTTPS の Git 認証を設定します。[Docker の Codex 認証ガイド](https://docs.docker.com/ai/sandboxes/agents/codex/#authentication)・[GitHub CLI の認証ガイド](https://cli.github.com/manual/gh_auth_login)

作成時にプロジェクトも準備する場合は、次のどちらかを指定します。

- `--repo owner/repo` で、GitHub からサンドボックス内の `/home/agent/workspace/<リポジトリ名>` にクローンします。GitHub の HTTPS クローン URL も使えます。
- `--workspace /absolute/path/to/project` で、Mac 上の既存フォルダを共有します。

`--name` で別名を付けられます。GitHub 認証を後回しにする場合は `--skip-github-auth` を指定します。T3 Code の既定バージョンは `0.1.11` です。デスクトップアプリの版に合わせる場合は `--t3-version` を指定します。[T3 Code の SSH 起動処理](https://github.com/pingdotgg/t3code/blob/v0.1.11/packages/ssh/src/tunnel.ts#L2995-L3026)

## T3 Code から接続する

1. **Settings → Environments → Add environment → SSH** を開き、ログに表示されたホスト名を入力して接続します。
2. **Add project** で今追加した SSH 環境を選びます。
3. 作業フォルダがあれば **Local folder** で開きます。空の環境なら **GitHub repository** からクローンできます。公開リポジトリは **Git URL** からもクローンできます。

**GitHub repository** に **Setup Required** が出る場合は、**Settings → Source control & issues** で SSH 環境を選び **Rescan** を実行します。[Docker の接続ガイド](https://docs.docker.com/ai/sandboxes/integrations/t3-code/)・[T3 Code の GitHub 認証ガイド](https://github.com/pingdotgg/t3code/blob/v0.1.11/docs/user/source-control.md#github)

## 状態を確認する・途中から再開する

```sh
uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git t3-code-codex-setup status --name t3-code-codex
```

`status` は、稼働状態、SSH ホスト、作業ディレクトリ、Docker Sandboxes が記録した Codex の認証方式を表示します。`--details` を付けると、サンドボックス内の T3 サーバーと Codex CLI の版、GitHub CLI の認証、dotfiles のチェックアウトと最終適用を確認できます。停止中の場合は `--details` の確認時に起動します。

以前 `uvx` で実行したことがあり、新しい操作が認識されない場合は、`uvx` の直後に `--refresh` を付けます。

サンドボックス作成後に GitHub 認証、クローン、dotfiles の適用が止まった場合は、エラーに表示される `resume` コマンドを実行します。たとえば、プロジェクトのクローンを再開するには次のように実行します。

```sh
uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git \
  t3-code-codex-setup resume --name t3-code-codex --repo owner/repo
```

`resume` では、必要な GitHub 認証を確認し、指定されたクローンと dotfiles の適用を行います。同じ宛先に同じリポジトリがあれば、クローンを省略します。認証だけ再試行する場合は、作成時のフラグを外して `github-auth --name t3-code-codex` を使います。ChatGPT の認証をやり直す場合は `auth` を使います。この ChatGPT 認証は Docker Sandboxes 全体で使われます。

## 既存環境に dotfiles を入れる

```sh
uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git \
  t3-code-codex-setup dotfiles --name t3-code-codex --dotfiles self
```

`self` はサンドボックス内で GitHub にログインしたアカウントの `<ユーザー名>/dotfiles` を指します。HTTPS のクローン URL で別のリポジトリを指定できます。新規作成と同時に行う場合は、`setup --dotfiles self` のように指定します。

dotfiles はサンドボックス内の `~/dotfiles` に置きます。ルートに `install.sh` がある場合は Bash で実行します。chezmoi 形式の場合は、必要に応じて chezmoi を導入し、設定ファイルを適用します。名前やメールアドレスを求められたらターミナルで入力してください。

- **Nix を使うテンプレート**には `--dotfiles-nix` を付けます。`ts-76/dotfiles` では Devbox の設定生成に必要です。
- **chezmoi の導入スクリプト**も実行する場合は `--run-dotfiles-scripts` を付けます。Devbox パッケージの導入にはサンドボックス内の Devbox、Nix、配布先へのアクセスが必要です。接続エラーは `sbx policy log t3-code-codex --limit 20` で確認できます。[Docker のネットワーク診断](https://docs.docker.com/ai/governance/troubleshooting/)

## 更新する

| 更新対象 | 操作 |
| --- | --- |
| セットアップコマンド | `uvx --refresh --from …` で GitHub 側の更新を確認する。Make を使う場合はホスト上のキットのクローンで `git pull --ff-only`。 |
| 既存サンドボックスの dotfiles | `dotfiles-update --name t3-code-codex` で取得して再適用する。テンプレートに Nix が必要なら `--dotfiles-nix` も付ける。 |
| 作成時に組み込むキット | `setup --name <新しい名前>` で別のサンドボックスを作る。元の環境を削除する前に、サンドボックス内だけにある作業を退避する。 |

`dotfiles-update` は既存の `~/dotfiles` の `origin` から `git pull --ff-only` します。未コミットの変更があれば取得と適用の前に止まります。`dotfiles` は取得済みの内容を再適用します。これらの操作は既存のサンドボックスを停止せずに実行できます。[Docker のキット更新とデータ保持](https://docs.docker.com/ai/sandboxes/customize/use-kits/#reuse-a-sandbox)

## Make で使う

```sh
git clone https://github.com/ts-76/t3-code-codex-sandbox.git
make -C ./t3-code-codex-sandbox setup
```

`-C` に、キットをクローンしたフォルダを指定します。別の場所から実行する場合は絶対パスを使えます。キットのフォルダ内では `-C` を省略できます。

| 操作 | Make のターゲットと引数 |
| --- | --- |
| 状態確認 | `status NAME=t3-code-codex`。詳細確認は `DETAILS=1` を追加。 |
| 途中から再開 | `resume NAME=t3-code-codex REPO=owner/repo`。必要に応じて元の `REPO`、`DOTFILES` を指定。 |
| GitHub 認証 | `github-auth NAME=t3-code-codex` |
| dotfiles を適用 | `dotfiles NAME=t3-code-codex DOTFILES=self DOTFILES_NIX=1` |
| 取得済みの dotfiles を更新 | `dotfiles-update NAME=t3-code-codex DOTFILES_NIX=1` |

作成時のオプションは `make help` で確認できます。`REPO=owner/repo` でクローンし、`WORKSPACE=/absolute/path/to/project` でホストのフォルダを共有します。`GITHUB_AUTH=0`、`T3_VERSION=0.1.11`、`DOTFILES_SCRIPTS=1` も指定できます。

## キットの開発

[t3code-ssh.yaml](t3code-ssh/t3code-ssh.yaml) は T3 Code の公式 Linux アーカイブをダウンロードし、SHA-256 を照合して組み込みます。配布時はソースからローカルでビルドします。

```sh
sbx kit validate ./t3code-ssh
python3 -B -m unittest discover -s tests
```

回帰テストは Docker Sandboxes と認証を模擬し、作成・途中再開・既存環境の診断・dotfiles の更新を確認します。Apple Silicon の Mac では新規環境の作成、SSH トンネル越しの T3 サーバーへの接続、保存済みの ChatGPT OAuth を使った Codex の応答も確認済みです。
