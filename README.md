# T3 Code Codex Sandbox

English · [日本語](docs/README.ja.md)

Run Codex in a Docker Sandbox and connect to it over SSH from T3 Code on your Mac. You can start with an empty sandbox and choose a GitHub repository later in T3 Code.

| Item | Default |
| --- | --- |
| Setup command | `t3-code-codex-setup` |
| Sandbox name | `t3-code-codex` |
| SSH host for T3 Code | `t3-code-codex.sbx` |

## Create a sandbox

You need Docker Sandboxes (tested with `sbx` v0.51.0), Docker Desktop and Buildx, and the T3 Code desktop app. Run `sbx login` to sign in to Docker Sandboxes the first time. GNU Make is required for the Make workflow.

With [`uvx`](https://docs.astral.sh/uv/guides/tools/) installed, you can run setup from any directory.

```sh
uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git t3-code-codex-setup
```

Setup checks Docker Sandboxes' OpenAI credentials before creating the sandbox and opens a browser to sign in to ChatGPT if needed. It then prints the sandbox name and SSH hostname. Finally, it signs in to GitHub CLI in the sandbox and configures Git authentication for HTTPS. [Docker's Codex authentication guide](https://docs.docker.com/ai/sandboxes/agents/codex/#authentication) · [GitHub CLI authentication guide](https://cli.github.com/manual/gh_auth_login)

To prepare a project during setup, choose one of these options.

- Use `--repo owner/repo` to clone from GitHub into `/home/agent/workspace/<repository-name>` inside the sandbox. GitHub HTTPS clone URLs also work.
- Use `--workspace /absolute/path/to/project` to share an existing directory on your Mac.

Use `--name` to choose a sandbox name. Pass `--skip-github-auth` to sign in to GitHub later. The default T3 Code version is `0.1.11`. Use `--t3-version` to match your desktop app version. [T3 Code's SSH startup implementation](https://github.com/pingdotgg/t3code/blob/v0.1.11/packages/ssh/src/tunnel.ts#L2995-L3026)

The sandbox is built from Docker's `codex` kit, which resolves to the latest release (`docker.io/sbx/codex:latest`). To pin it, pass `--codex-kit docker.io/sbx/codex:0.171.0` or set `CODEX_KIT` in the settings file. A newer kit can require a newer `sbx` release. Setup adds T3 Code with `sbx create --kit` and `--kit-arg`, which `sbx` v0.51.0 marks as experimental. If setup fails after you upgrade `sbx`, check `sbx create --help` for changes to these options. [Docker's guide to using kits](https://docs.docker.com/ai/sandboxes/customize/use-kits/)

## Connect from T3 Code

1. Open **Settings → Environments → Add environment → SSH** and enter the hostname printed by setup.
2. Open **Add project** and select the SSH environment you just added.
3. Use **Local folder** to open a workspace that already exists. For an empty sandbox, use **GitHub repository** to clone a project. You can also use **Git URL** for public repositories.

If **GitHub repository** shows **Setup Required**, select your SSH environment in **Settings → Source control & issues** and click **Rescan**. [Docker's connection guide](https://docs.docker.com/ai/sandboxes/integrations/t3-code/) · [T3 Code's GitHub authentication guide](https://github.com/pingdotgg/t3code/blob/v0.1.11/docs/user/source-control.md#github)

## Store your settings in a file

If you cloned this repository, copy the [example configuration](sandbox.conf.example) and edit it before running Make.

```sh
cp sandbox.conf.example sandbox.local.conf
make status
```

Both Make and `uvx` can read a settings file stored elsewhere.

```sh
make status CONFIG=/absolute/path/to/sandbox.conf

uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git \
  t3-code-codex-setup status --config /absolute/path/to/sandbox.conf
```

By default, Make looks for `sandbox.local.conf` next to the Makefile, and `uvx` looks for it in the directory you run the command from. Use one `KEY=value` pair per line. Paths with spaces can be written as-is. Relative `WORKSPACE` paths are resolved from the settings file's directory. Start comment lines with `#`.

Command-line values take precedence over the file. For example, use `make status NAME=another-sandbox` or `status --name another-sandbox` to switch targets. With `uvx`, use `--github-auth` or `--skip-github-auth` to override the GitHub setting, and `--no-dotfiles-nix` or `--no-run-dotfiles-scripts` to turn off options enabled in the file.

### Review network access before allowing it

Set `NETWORK_ALLOW` to a comma-separated list of hostnames. The default port is `443`.

```ini
NETWORK_ALLOW=packages.example.com:443,cache.example.com:443
```

After creating the sandbox, run `network` to review the target sandbox and see which hosts are already allowed or would be added.

```sh
make network
make network APPLY=1
```

With `uvx`, run `t3-code-codex-setup network --config /absolute/path/to/sandbox.conf` to preview the rules. Add `--apply` to allow the listed hosts. Use `sbx policy ls <name> --wide` to inspect existing rules and manage removal in Docker Sandboxes. If dotfiles setup stopped because a host was blocked, apply the network rule and run `resume`. [Docker network rules](https://docs.docker.com/reference/cli/sbx/policy/allow/network/)

## Link the sandbox to T3 Code on your Mac

Link the sandbox when agents on your Mac should work in it. Outside agents that reach your Mac through T3 Connect, such as hosted assistants, then reach the sandbox through the same link. Nothing is exposed to the internet. [T3 Code's linked environments guide](https://github.com/pingdotgg/t3code/blob/v0.1.11/docs/user/remote-access.md#link-another-environment) · [T3 Code's external agent guide](https://github.com/pingdotgg/t3code/blob/v0.1.11/docs/user/outside-agents.md#add-t3-code-to-an-assistant-app)

Turn on **Linked environments** under **Settings → Labs** in T3 Code on your Mac. Run the command from your Mac's login session. It needs the T3 Code CLI (`t3`) on your Mac and Python 3.9 or later for the Make workflow.

```sh
make link-setup NAME=t3-code-codex

uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git \
  t3-code-codex-setup link-setup --name t3-code-codex
```

`link-setup` forwards a fixed loopback port on your Mac (`13773` by default) to T3 Code in the sandbox over SSH. A LaunchAgent keeps the forward running while you are logged in, and the SSH session starts T3 Code inside the sandbox if its server stops. The command then links the sandbox to T3 Code on your Mac at that address with a five-minute pairing code. A link to the same sandbox at another address is replaced. The port the desktop app opens for its own SSH connection changes when the app restarts, so a link to it stops answering. Rerunning the command leaves a working link as it is.

`LINK_ACCESS` (`--link-access`) sets the most that agents from your Mac may do in the sandbox. The default is `auto`. An agent never gets more in the sandbox than its own mode on your Mac. Set a distinct `MCP_LOCAL_PORT` (`--mcp-local-port`) if `13773` is busy or if you link multiple sandboxes.

Run `make link-stop NAME=t3-code-codex` (or `link-stop --name t3-code-codex` with `uvx`) to remove the link and stop the SSH forward. Then revoke the link's session in the sandbox under **Settings → Sharing & access**. If you set up the public endpoint below, run `mcp-stop` first.

## Optional: expose the sandbox's MCP endpoint publicly

Use this only when an outside agent must reach the sandbox directly instead of through your Mac, for example when you do not use T3 Connect. It publishes the sandbox's MCP and sign-in paths on a hostname you own, so the sandbox becomes reachable from the internet.

Install `cloudflared` on your Mac and run `cloudflared tunnel login` the first time. Choose an unused, dedicated MCP hostname in a DNS zone you manage with Cloudflare. Run setup from your Mac's login session with the name of an existing sandbox and your chosen hostname. [Cloudflare's tunnel setup guide](https://developers.cloudflare.com/tunnel/features/locally-managed-tunnels/create-local-tunnel/)

Use Cloudflare Single Redirects to redirect HTTP requests for the MCP hostname to HTTPS on the same host. Preserve the path and query string, and register the HTTPS URL with your external client. Direct connections use T3 Code's own OAuth flow. Enabling Cloudflare Access Managed OAuth on the same hostname changes which service handles OAuth discovery. [Cloudflare's redirect setup guide](https://developers.cloudflare.com/rules/url-forwarding/single-redirects/create-dashboard/) · [Cloudflare's MCP authentication guide](https://developers.cloudflare.com/cloudflare-one/access-controls/ai-controls/secure-mcp-servers/)

```sh
make mcp-setup NAME=t3-code-codex MCP_HOSTNAME=mcp.example.com
make status NAME=t3-code-codex DETAILS=1
```

The Make workflow for MCP setup also requires Python 3.9 or later. You can run the same setup with `uvx`.

```sh
uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git \
  t3-code-codex-setup mcp-setup --name t3-code-codex --mcp-hostname mcp.example.com
```

`mcp-setup` reuses the SSH forward from `link-setup`, or starts it if it is not running. It creates a Cloudflare Tunnel and DNS record, verifies that the public URL reaches the same sandbox, and checks the OAuth responses. It reports whether plain HTTP redirects to HTTPS or is rejected. Only the paths needed for MCP and the approval screen are exposed through the tunnel. A LaunchAgent runs the tunnel while you are logged in on the Mac.

Add the MCP URL printed by setup, such as `https://mcp.example.com/mcp`, to your external client using OAuth and start signing in. Generate a sign-in code for the same sandbox and enter it on the approval screen in your browser. The code expires after five minutes. [T3 Code's external agent guide](https://github.com/pingdotgg/t3code/blob/v0.1.11/docs/user/outside-agents.md#approve-a-sign-in)

```sh
make mcp-pair NAME=t3-code-codex

uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git \
  t3-code-codex-setup mcp-pair --name t3-code-codex
```

Access defaults to read-only. To let an external client start threads in the sandbox and run without approval, issue a code with `make mcp-pair NAME=t3-code-codex MCP_ACCESS=full-access` (or `--mcp-access full-access` with `uvx`) and select **Full access** on the approval screen. Any host directory shared with the sandbox is within the agent's working scope. Revoke approved clients under **Settings → Sharing & access** in the target T3 Code environment.

- Set `MCP_HOSTNAME=mcp.example.com` in `sandbox.local.conf` to omit the hostname on the command line. The tunnel uses the same `MCP_LOCAL_PORT` as the link.
- If DNS or TLS is still provisioning, give it time and rerun `mcp-setup`. Once settings have been saved, you can retry with just the sandbox name. The saved hostname, port, and tunnel are reused. Generated configuration and logs are stored at `~/Library/Application Support/t3-code-codex-sandbox/mcp/<sandbox-name>/` on your Mac.
- Run `make mcp-stop NAME=t3-code-codex` (or `mcp-stop --name t3-code-codex` with `uvx`) to stop serving the public endpoint. This stops only the tunnel and keeps the SSH forward for the linked environment. The Cloudflare DNS record and named tunnel remain for reuse. To remove them, run `cloudflared tunnel delete <tunnel-id>` and delete the DNS record in Cloudflare. To change the hostname, stop the service and run `mcp-setup` with the new value.

## Check status and resume setup

```sh
uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git t3-code-codex-setup status --name t3-code-codex
```

`status` shows the sandbox state, SSH hostname, working directory, and the Codex authentication method recorded by Docker Sandboxes. Add `--details` to see the T3 server and Codex CLI versions, GitHub CLI authentication, the dotfiles checkout, and the last dotfiles apply. For kit-managed links and MCP connections, the detailed check also reports the SSH forward, the link's state, and which public check failed or whether the route is reachable. Detailed checks start the sandbox if it is stopped.

If `uvx` has cached an older version and misses a new command, add `--refresh` immediately after `uvx`.

If setup stopped during GitHub sign-in, checkout, or dotfiles installation, run the `resume` command printed with the error. To resume a project checkout, for example, run the following command.

```sh
uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git \
  t3-code-codex-setup resume --name t3-code-codex --repo owner/repo
```

`resume` checks GitHub authentication as needed, clones the requested repository, and applies the requested dotfiles. It skips cloning when the destination already contains the same repository. To retry just GitHub sign-in, use `github-auth --name t3-code-codex` without the setup flags. Use `auth` to sign in to ChatGPT again. This ChatGPT credential is shared across Docker Sandboxes.

## Apply dotfiles to an existing sandbox

```sh
uvx --from git+https://github.com/ts-76/t3-code-codex-sandbox.git \
  t3-code-codex-setup dotfiles --name t3-code-codex --dotfiles self
```

`self` selects `<username>/dotfiles` for the GitHub account signed in inside the sandbox. Pass an HTTPS clone URL to use another repository. To apply dotfiles while creating a sandbox, use `setup --dotfiles self`.

Dotfiles are checked out to `~/dotfiles` inside the sandbox. If the repository root has an `install.sh`, the setup runs it with Bash. For a chezmoi repository, setup installs chezmoi if needed and applies the configuration. Enter your name or email in the terminal if prompted.

- Add `--dotfiles-nix` for templates that need Nix. The `ts-76/dotfiles` repository needs it to generate its Devbox configuration.
- Add `--run-dotfiles-scripts` to run chezmoi installation scripts. Installing Devbox packages requires Devbox, Nix, and network access to the distribution hosts from inside the sandbox. Check connection failures with `sbx policy log t3-code-codex --limit 20`. [Docker network troubleshooting](https://docs.docker.com/ai/governance/troubleshooting/)

## Update the kit or sandbox configuration

| What to update | Command |
| --- | --- |
| Setup command | Use `uvx --refresh --from …` to fetch updates from GitHub. With Make, run `git pull --ff-only` in your local clone. |
| Dotfiles in an existing sandbox | Run `dotfiles-update --name t3-code-codex` to fetch and apply them again. Add `--dotfiles-nix` if the templates need Nix. |
| Kit installed at sandbox creation | Run `setup --name <new-name>` to create another sandbox. Save any work stored only inside the old sandbox before removing it. |

`dotfiles-update` runs `git pull --ff-only` against the existing `~/dotfiles` checkout's `origin`. It stops before fetching or applying if the checkout has uncommitted changes. To reapply the current checkout, run `dotfiles` without specifying its source. Both commands can run while the sandbox is active. [Docker's guidance on reusing a sandbox](https://docs.docker.com/ai/sandboxes/customize/use-kits/#reuse-a-sandbox)

## Use Make

```sh
git clone https://github.com/ts-76/t3-code-codex-sandbox.git
make -C ./t3-code-codex-sandbox setup
```

Pass the cloned kit directory to `-C`. Use an absolute path when running from another directory. You can omit `-C` inside the kit directory.

| Operation | Make target and arguments |
| --- | --- |
| Show status | `status NAME=t3-code-codex`. Add `DETAILS=1` for detailed checks. |
| Resume setup | `resume NAME=t3-code-codex REPO=owner/repo`. Include your original `REPO` and `DOTFILES` settings as needed. |
| Sign in to GitHub | `github-auth NAME=t3-code-codex` |
| Apply dotfiles | `dotfiles NAME=t3-code-codex DOTFILES=self DOTFILES_NIX=1` |
| Update checked-out dotfiles | `dotfiles-update NAME=t3-code-codex DOTFILES_NIX=1` |
| Review network access | `network NAME=t3-code-codex`. Add `APPLY=1` to add the rules. |
| Link to T3 Code on your Mac | `link-setup NAME=t3-code-codex`. Add `LINK_ACCESS=approval-required` to narrow it. |
| Remove the link | `link-stop NAME=t3-code-codex` |

Run `make help` for setup options. Use `REPO=owner/repo` to clone a repository or `WORKSPACE=/absolute/path/to/project` to share a host directory. Other options include `GITHUB_AUTH=0`, `T3_VERSION=0.1.11`, `CODEX_KIT=docker.io/sbx/codex:0.171.0`, and `DOTFILES_SCRIPTS=1`.

## Develop the kit

[`t3code-ssh.yaml`](t3code-ssh/t3code-ssh.yaml) downloads the official T3 Code Linux archive, verifies its SHA-256 checksum, and installs it in the sandbox. The kit is built locally from source.

Docker also publishes a T3 Code kit, but as of November 2026 it does not replace `t3code-ssh`. `docker.io/sbx/t3code-kit` uses the v2 format, which `sbx` refuses to combine with the v3 `codex` kit. The v3 `docker.io/sbx/t3code` installs `t3` 0.0.45, which is fixed when Docker builds the kit and does not match the desktop app. It also installs `libatomic1` with apt when the sandbox is created. The archive that `t3code-ssh` installs includes that library. [Docker's T3 Code kit](https://github.com/docker/sbx-kits-contrib/tree/v3/t3code)

| Path | Contents |
| --- | --- |
| `sandbox.conf.example` | Personal settings template |
| `t3code-ssh/` | Docker Sandboxes kit definition |
| `scripts/host/` | Host-side setup, recovery, configuration, network rules, and diagnostics |
| `scripts/sandbox/` | Repository checkout, dotfiles, and diagnostics inside the sandbox |
| `t3_code_codex/` | Python entry point for `uvx` |
| `tests/` | Regression tests for the Make and Python entry points |

```sh
sbx kit validate ./t3code-ssh
python3 -B -m unittest discover -s tests
```

The regression tests simulate Docker Sandboxes and authentication to cover creation, recovery, diagnostics, and dotfiles updates. Sandbox creation, SSH forwarding to the T3 server, and Codex responses using stored ChatGPT OAuth credentials have also been verified on an Apple Silicon Mac.
