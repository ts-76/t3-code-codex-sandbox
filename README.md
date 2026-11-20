# T3 Code Codex Sandbox

Docker Sandboxes の Codex ワークロードに T3 Code サーバーを追加する v3 ミックスインです。T3 Code デスクトップアプリから SSH で接続し、サンドボックス内で Codex を実行できます。

[t3code-ssh.yaml](t3code-ssh/t3code-ssh.yaml) は T3 Code の公式 Linux アーカイブをダウンロードし、SHA-256 を照合して組み込みます。T3 Code の既定バージョンは `0.1.11` です。

## 準備

- Docker Sandboxes（`sbx` v0.51.0 で確認）
- ローカルビルド用の Docker Engine と Buildx。macOS では Docker Desktop を使用します。
- `make`（macOS 標準の GNU Make 3.81 で確認）
- T3 Code デスクトップアプリ

## サンドボックスを作成する

```sh
git clone https://github.com/ts-76/t3-code-codex-sandbox.git
cd t3-code-codex-sandbox
```

初回は `sbx login` で Docker Sandboxes にサインインします。Codex を ChatGPT アカウントで使う場合は `make auth` で認証してください。保存済みの認証情報は再利用できます。[Docker の Codex 認証ガイド](https://docs.docker.com/ai/sandboxes/agents/codex/#authentication)

共有したい作業フォルダを `WORKSPACE` に指定します。

```sh
make setup WORKSPACE="/absolute/path/to/project"
```

`make setup` は macOS で必要に応じて Docker Desktop を起動し、Buildx ビルダーと SSH 接続を準備してからサンドボックスを作成します。完了時に SSH ホスト名と作業フォルダを表示します。

既定のサンドボックス名は `t3-code-codex` です。作成済みの環境にはそのまま接続できます。別の作業フォルダや T3 Code バージョンで作成する場合は、新しい `NAME` を指定してください。

```sh
make setup WORKSPACE="/absolute/path/to/project" NAME=t3-code-codex-project T3_VERSION=0.1.11
```

`T3_VERSION` は使っているデスクトップアプリのバージョンに合わせます。省略時はキットに定義したバージョンを使います。デスクトップアプリは、バージョンが一致する T3 サーバーを再利用します。[T3 Code の SSH 起動処理](https://github.com/pingdotgg/t3code/blob/v0.1.11/packages/ssh/src/tunnel.ts#L2995-L3026)

## T3 Code から接続する

1. **Settings → Environments → Add environment → SSH** を開きます。
2. `make setup` が表示したホスト名を入力して接続します。既定は `t3-code-codex.sbx` です。
3. プロジェクト追加時にその環境を選び、作成時に指定した作業フォルダを開きます。

[Docker の T3 Code 接続ガイド](https://docs.docker.com/ai/sandboxes/integrations/t3-code/)

Apple Silicon の Mac で `sbx kit validate`、新規サンドボックスの作成、SSH トンネル越しの T3 サーバーへの接続、保存済みの ChatGPT OAuth を使った Codex の応答を確認済みです。
