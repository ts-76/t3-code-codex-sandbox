# T3 Code Codex Sandbox

Docker Sandboxes の Codex ワークロードに T3 Code サーバーを追加する v3 ミックスインです。T3 Code デスクトップアプリから SSH で接続し、サンドボックス内で Codex を実行できます。

[t3code-ssh.yaml](t3code-ssh/t3code-ssh.yaml) は T3 Code の公式 Linux アーカイブをダウンロードし、SHA-256 を照合して組み込みます。T3 Code の既定バージョンは `0.1.11` です。

## 準備

- Docker Sandboxes（`sbx` v0.51.0 で確認）
- ローカルビルド用の Docker Engine と Buildx。macOS では Docker Desktop を起動してください。
- T3 Code デスクトップアプリ

Docker Sandboxes にサインインし、SSH 接続を有効にします。Codex を ChatGPT アカウントで使う場合は、必要に応じて Mac 側の `sbx secret set openai --oauth` で認証します。[Docker の Codex 認証ガイド](https://docs.docker.com/ai/sandboxes/agents/codex/#authentication)

```sh
sbx login
sbx setup ssh
```

## サンドボックスを作成する

```sh
git clone https://github.com/ts-76/t3-code-codex-sandbox.git
cd t3-code-codex-sandbox
```

ローカルビルドに使う `docker-container` ドライバーのビルダーを用意します。同じ名前で作成済みなら再利用できます。

```sh
docker buildx inspect sbx-t3-kit-builder >/dev/null 2>&1 ||
  docker buildx create --name sbx-t3-kit-builder --driver docker-container
```

`/absolute/path/to/project` を共有したい作業フォルダの絶対パスに置き換えます。

```sh
BUILDX_BUILDER=sbx-t3-kit-builder sbx create \
  --name t3-code-codex \
  --kit ./t3code-ssh \
  codex /absolute/path/to/project
```

デスクトップアプリのバージョンが `0.1.11` と異なる場合は、作成時に `--kit-arg t3code-ssh.version=バージョン番号` を指定します。デスクトップアプリは、バージョンが一致する T3 サーバーを再利用します。[T3 Code の SSH 起動処理](https://github.com/pingdotgg/t3code/blob/v0.1.11/packages/ssh/src/tunnel.ts#L2995-L3026)

## T3 Code から接続する

1. **Settings → Environments → Add environment → SSH** を開きます。
2. ホスト名に `t3-code-codex.sbx` を入力して接続します。
3. プロジェクト追加時に `t3-code-codex` を選び、作成時に指定した作業フォルダを開きます。

[Docker の T3 Code 接続ガイド](https://docs.docker.com/ai/sandboxes/integrations/t3-code/)

Apple Silicon の Mac で `sbx kit validate`、新規サンドボックスの作成、SSH トンネル越しの T3 サーバーへの接続、保存済みの ChatGPT OAuth を使った Codex の応答を確認済みです。
