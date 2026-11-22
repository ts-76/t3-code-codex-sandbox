# T3 Code Codex Sandbox

[English](../README.md) · 日本語

Mac の T3 Code から SSH で Docker Sandbox に接続し、サンドボックス内で Codex を使うためのセットアップです。空のサンドボックスを作ったあと、T3 Code で GitHub リポジトリを選べます。

| 項目 | 既定の名前 |
| --- | --- |
| セットアップコマンド | `t3-code-codex-setup` |
| サンドボックス | `t3-code-codex` |
| T3 Code に入力する SSH ホスト | `t3-code-codex.sbx` |

## 新規作成

Docker Sandboxes（`sbx` v0.51.0 で確認）、Docker Desktop と Buildx、T3 Code デスクトップアプリが必要です。初回は `sbx login` で Docker Sandboxes にサインインします。Make で実行する場合は GNU Make も必要です。

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

## 自分の設定をファイルに置く

手元にクローンして使う場合は、[設定例](../sandbox.conf.example) をコピーして編集します。

```sh
cp sandbox.conf.example sandbox.local.conf
make status
```

別の場所に置いた設定ファイルも、Make と `uvx` の両方から読み込めます。

```sh
make status CONFIG=/absolute/path/to/sandbox.conf

uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git \
  t3-code-codex-setup status --config /absolute/path/to/sandbox.conf
```

ファイルを指定しないときは、Make は Makefile を実行するディレクトリ、`uvx` は呼び出したディレクトリの `sandbox.local.conf` を探します。値は `KEY=value` で1行ずつ書きます。パスに空白があっても引用符は不要です。`WORKSPACE` に相対パスを書くと、設定ファイルと同じ場所が基準になります。コメントは `#` で始まる行に書きます。

コマンドに渡した値が設定ファイルの値より優先されます。たとえば `make status NAME=another-sandbox` や `status --name another-sandbox` で対象を切り替えられます。`uvx` では `--github-auth` または `--skip-github-auth` で GitHub 認証の設定を上書きできます。設定ファイルで有効にした Nix のインストールや chezmoi スクリプトをその回だけ無効にするには、`--no-dotfiles-nix` または `--no-run-dotfiles-scripts` を指定します。

### 通信先を確認してから許可する

設定ファイルの `NETWORK_ALLOW` にホスト名をカンマ区切りで書きます。ポート省略時は `443` です。

```ini
NETWORK_ALLOW=packages.example.com:443,cache.example.com:443
```

サンドボックス作成後、まず `network` で対象の名前、許可済みのホスト、追加するホストを確認します。

```sh
make network
make network APPLY=1
```

`uvx` では `t3-code-codex-setup network --config /absolute/path/to/sandbox.conf` で確認し、追加する場合だけ `--apply` を付けます。設定済みの他のルールを外したいときは、`sbx policy ls <名前> --wide` で確認して Docker Sandboxes 側で変更します。dotfiles の取得が通信許可の前に止まった場合は、許可を適用したあとに `resume` で続行できます。[Docker の通信ルール](https://docs.docker.com/reference/cli/sbx/policy/allow/network/)

## Mac の T3 Code にサンドボックスをリンクする

Mac のエージェントにサンドボックスで作業させる場合は、リンクでつなぎます。T3 Connect 経由で Mac に接続しているクラウドのアシスタントなどの外部エージェントも、同じリンクを通ってサンドボックスに届きます。インターネットには何も公開しません。[T3 Code の Linked environments ガイド](https://github.com/pingdotgg/t3code/blob/v0.1.11/docs/user/remote-access.md#link-another-environment)・[T3 Code の外部エージェント接続ガイド](https://github.com/pingdotgg/t3code/blob/v0.1.11/docs/user/outside-agents.md#add-t3-code-to-an-assistant-app)

Mac の T3 Code で **Settings → Labs** の **Linked environments** を有効にします。コマンドは Mac のログインセッション内で実行します。Mac に T3 Code の CLI（`t3`）が必要です。Make を使う場合は Python 3.9 以降も必要です。

```sh
make link-setup NAME=t3-code-codex

uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git \
  t3-code-codex-setup link-setup --name t3-code-codex
```

`link-setup` は、Mac の固定のループバックポート（既定は `13773`）からサンドボックス内の T3 Code へ SSH で転送します。転送は Mac のログイン中に LaunchAgent が動かし続けます。サンドボックス内の T3 が止まると、SSH セッションが T3 を起動します。続けて、5分間有効なペアリングコードで、そのアドレスのサンドボックスを Mac の T3 Code にリンクします。同じサンドボックスへのリンクが別のアドレスにある場合は張り替えます。デスクトップアプリが自分の SSH 接続のために開くポートはアプリの再起動で変わるため、そこへのリンクは応答しなくなります。動いているリンクは、再実行してもそのまま残します。

`LINK_ACCESS`（`--link-access`）で、Mac のエージェントがサンドボックスでできることの上限を決めます。既定は `auto` です。エージェントがサンドボックスで持つ権限は、Mac での自分のモードを超えません。`13773` が使用中の場合や、複数のサンドボックスをリンクする場合は `MCP_LOCAL_PORT`（`--mcp-local-port`）を個別に指定します。

リンクを外して SSH 転送を止めるときは `make link-stop NAME=t3-code-codex`（`uvx` では `link-stop --name t3-code-codex`）を実行します。そのあと、サンドボックスの **Settings → Sharing & access** でリンクのセッションを取り消します。下の公開設定をしている場合は、先に `mcp-stop` を実行します。

## 任意：サンドボックスの MCP をインターネットに公開する

Mac を経由せず、外部エージェントをサンドボックスに直接つなぐ必要がある場合だけ使います。たとえば T3 Connect を使わない場合です。手持ちのホスト名でサンドボックスの MCP とサインインの経路を公開するため、サンドボックスにインターネットから届くようになります。

外部 MCP クライアントから接続する場合は、Mac に `cloudflared` を入れ、初回に `cloudflared tunnel login` を実行します。Cloudflare で DNS を管理しているドメインから、MCP 専用の空いているホスト名を選びます。Mac のログインセッション内で、作成済みのサンドボックス名とホスト名を指定します。[Cloudflare の設定ガイド](https://developers.cloudflare.com/tunnel/features/locally-managed-tunnels/create-local-tunnel/)

Cloudflare の Single Redirects で、MCP 専用のホスト名への HTTP リクエストを同じホストの HTTPS へ転送します。パスとクエリ文字列を保持し、外部クライアントには最初から HTTPS の URL を登録します。直接接続では T3 Code 自身が OAuth を提供するため、このホストで Cloudflare Access の Managed OAuth を有効にすると認証先が変わります。[Cloudflare のリダイレクト設定](https://developers.cloudflare.com/rules/url-forwarding/single-redirects/create-dashboard/)・[Cloudflare の MCP 認証ガイド](https://developers.cloudflare.com/cloudflare-one/access-controls/ai-controls/secure-mcp-servers/)

```sh
make mcp-setup NAME=t3-code-codex MCP_HOSTNAME=mcp.example.com
make status NAME=t3-code-codex DETAILS=1
```

Make を使う場合は Python 3.9 以降も必要です。`uvx` でも同じ設定を実行できます。

```sh
uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git \
  t3-code-codex-setup mcp-setup --name t3-code-codex --mcp-hostname mcp.example.com
```

`mcp-setup` は `link-setup` の SSH 転送を使います。転送が動いていなければ起動します。Cloudflare Tunnel と DNS レコードを作成し、公開 URL が同じサンドボックスを指していることと OAuth の応答を確認します。平文 HTTP が HTTPS に転送されるか、拒否されるかも表示します。T3 Code の MCP と承認画面に必要な経路だけをトンネルに通します。トンネルは Mac のログイン中に LaunchAgent で動作します。

セットアップに表示された `https://mcp.example.com/mcp` を外部クライアントに OAuth 接続として追加し、サインインを開始します。同じサンドボックスの承認コードを発行し、ブラウザの承認画面に入力します。有効期限は5分です。[T3 Code の外部エージェント接続ガイド](https://github.com/pingdotgg/t3code/blob/v0.1.11/docs/user/outside-agents.md#approve-a-sign-in)

```sh
make mcp-pair NAME=t3-code-codex

uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git \
  t3-code-codex-setup mcp-pair --name t3-code-codex
```

既定は読み取り専用です。外部クライアントからこのサンドボックスでスレッドを作成し、承認なしで実行させる場合は、`make mcp-pair NAME=t3-code-codex MCP_ACCESS=full-access`（`uvx` では `--mcp-access full-access`）でコードを発行し、承認画面でも **Full access** を選びます。接続先のサンドボックスがホストのフォルダを共有している場合は、そのフォルダもエージェントの作業範囲に入ります。接続済みクライアントは T3 Code の対象環境の **Settings → Sharing & access** で取り消せます。

- `sandbox.local.conf` に `MCP_HOSTNAME=mcp.example.com` を書くと、実行時にホスト名を省略できます。トンネルはリンクと同じ `MCP_LOCAL_PORT` を使います。
- DNS や TLS の反映待ちで止まったら、時間を置いて `mcp-setup` を再実行します。設定が保存されたあとは、サンドボックス名だけで再試行でき、ホスト名・ポート・トンネルを再利用します。生成した設定とログは Mac の `~/Library/Application Support/t3-code-codex-sandbox/mcp/<サンドボックス名>/` にあります。
- 公開を止めるときは `make mcp-stop NAME=t3-code-codex`（`uvx` では `mcp-stop --name t3-code-codex`）を実行します。止まるのはトンネルだけで、SSH 転送はリンクのために残ります。Cloudflare 上の DNS レコードと名前付きトンネルは再利用できるよう残ります。消す場合は `cloudflared tunnel delete <トンネル ID>` を実行し、Cloudflare で DNS レコードを削除します。ホスト名を切り替える場合は、停止後に新しい値で `mcp-setup` を実行します。

## 状態を確認する・途中から再開する

```sh
uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git t3-code-codex-setup status --name t3-code-codex
```

`status` は、稼働状態、SSH ホスト、作業ディレクトリ、Docker Sandboxes が記録した Codex の認証方式を表示します。`--details` を付けると、サンドボックス内の T3 サーバーと Codex CLI の版、GitHub CLI の認証、dotfiles のチェックアウトと最終適用を確認できます。キットで管理するリンクと MCP 接続については、SSH 転送とリンクの状態、公開経路に到達できたか、どの段階で失敗したかも表示します。停止中の場合は `--details` の確認時に起動します。

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

`dotfiles-update` は既存の `~/dotfiles` の `origin` から `git pull --ff-only` します。未コミットの変更があれば取得と適用の前に止まります。取得済みの内容を再適用するには、取得元を指定せずに `dotfiles` を実行します。これらの操作は既存のサンドボックスを停止せずに実行できます。[Docker のキット更新とデータ保持](https://docs.docker.com/ai/sandboxes/customize/use-kits/#reuse-a-sandbox)

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
| 通信許可の確認 | `network NAME=t3-code-codex`。ルールを追加するときだけ `APPLY=1` を指定。 |
| Mac の T3 Code にリンク | `link-setup NAME=t3-code-codex`。権限を絞るときは `LINK_ACCESS=approval-required` を指定。 |
| リンクを外す | `link-stop NAME=t3-code-codex` |

作成時のオプションは `make help` で確認できます。`REPO=owner/repo` でクローンし、`WORKSPACE=/absolute/path/to/project` でホストのフォルダを共有します。`GITHUB_AUTH=0`、`T3_VERSION=0.1.11`、`DOTFILES_SCRIPTS=1` も指定できます。

## キットの開発

[t3code-ssh.yaml](../t3code-ssh/t3code-ssh.yaml) は T3 Code の公式 Linux アーカイブをダウンロードし、SHA-256 を照合して組み込みます。配布時はソースからローカルでビルドします。

| パス | 内容 |
| --- | --- |
| `sandbox.conf.example` | 個人設定のテンプレート |
| `t3code-ssh/` | Docker Sandboxes のキット定義 |
| `scripts/host/` | ホストで実行する作成・再開、設定、通信許可、診断 |
| `scripts/sandbox/` | サンドボックス内で実行するクローン、dotfiles、診断 |
| `t3_code_codex/` | `uvx` から使う Python の入口 |
| `tests/` | Make と Python の入口を通す回帰テスト |

```sh
sbx kit validate ./t3code-ssh
python3 -B -m unittest discover -s tests
```

回帰テストは Docker Sandboxes と認証を模擬し、作成・途中再開・既存環境の診断・dotfiles の更新を確認します。Apple Silicon の Mac では新規環境の作成、SSH トンネル越しの T3 サーバーへの接続、保存済みの ChatGPT OAuth を使った Codex の応答も確認済みです。
