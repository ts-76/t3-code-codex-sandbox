#!/usr/bin/env python3
"""Manage a macOS SSH forward, a T3 Code environment link, and an optional
Cloudflare Tunnel for one sandbox."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid


T3_PORT = 3773
DEFAULT_LOCAL_PORT = 13773
ENVIRONMENT = "/.well-known/t3/environment"
OAUTH_RESOURCE = "/.well-known/oauth-protected-resource/mcp"
MCP_PATHS = (
    r"^/(api/auth/session|mcp/?|oauth/mcp/(authorize|approval|decision|token|register)"
    r"|\.well-known/(oauth-protected-resource(/mcp)?|oauth-authorization-server(/mcp)?|t3/environment)"
    r"|connect-agent/?|assets/([A-Za-z0-9_-][A-Za-z0-9._-]*/)*[A-Za-z0-9_-][A-Za-z0-9._-]*"
    r"|favicon\.ico|apple-touch-icon\.png|manifest\.webmanifest)$"
)
ACCESS_MODES = {
    "read-only", "approval-required", "auto-accept-edits", "auto", "full-access",
}


def run(*args, capture=False, quiet=False, **options):
    return subprocess.run(
        args, check=True, text=True, capture_output=capture, **options,
        **({"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL} if quiet else {}),
    ).stdout


def private_write(path: Path, data: bytes):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        source = Path(temporary.name)
        try:
            temporary.write(data)
            temporary.flush()
            source.replace(path)
        finally:
            source.unlink(missing_ok=True)


def normalize_hostname(hostname: str) -> str:
    labels = hostname.lower().split(".")
    if len(hostname) > 253 or len(labels) < 2 or not re.fullmatch(r"[a-z][a-z0-9-]*", labels[-1]):
        raise ValueError("Set MCP_HOSTNAME to a DNS hostname, for example mcp.example.com.")
    if not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels):
        raise ValueError("Set MCP_HOSTNAME to a DNS hostname without https://, a port, or a path.")
    return ".".join(labels)


@dataclass(frozen=True)
class Route:
    hostname: str
    port: int
    tunnel: str

    @property
    def public_url(self) -> str:
        return f"https://{self.hostname}"

    @property
    def local_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def cloudflared_config(self, credentials: Path) -> bytes:
        # JSON is valid YAML. Quoting here also handles spaces in users' home paths.
        return json.dumps({
            "tunnel": self.tunnel,
            "credentials-file": str(credentials),
            "ingress": [
                {"hostname": self.hostname, "path": MCP_PATHS, "service": self.local_url},
                {"service": "http_status:404"},
            ],
        }, indent=2).encode() + b"\n"


@dataclass(frozen=True)
class Forward:
    port: int

    @property
    def local_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


def parse_port(value: str) -> int:
    if not re.fullmatch(r"[0-9]{1,5}", value) or not 1024 <= int(value) <= 65535:
        raise ValueError("Set MCP_LOCAL_PORT to an unprivileged port (1024–65535).")
    return int(value)


def t3_cli() -> str:
    found = shutil.which("t3") or str(Path.home() / ".t3/bin/t3")
    if not os.access(found, os.X_OK):
        raise ValueError("Install the T3 Code CLI on the Mac (t3 on PATH or ~/.t3/bin/t3).")
    return found


def tunnel_id(cloudflared: str, sandbox: str, hostname: str) -> str:
    suffix = hashlib.sha256(f"{sandbox}\n{hostname}".encode()).hexdigest()[:16]
    name = f"t3-code-codex-mcp-{suffix}"

    def find():
        try:
            result = json.loads(run(
                cloudflared, "tunnel", "list", "--name", name, "--output", "json", capture=True,
            ))
        except subprocess.CalledProcessError:
            raise ValueError("Could not list Cloudflare tunnels. Check cloudflared tunnel login and account access.") from None
        return next((str(uuid.UUID(t["id"])) for t in (result or []) if t["name"] == name), None)

    existing = find()
    if existing is not None:
        return existing
    run(cloudflared, "tunnel", "create", name)
    created = find()
    if created is None:
        raise ValueError("The tunnel was created but could not be found. Retry mcp-setup.")
    return created


def get_json(url: str) -> dict:
    body = run("/usr/bin/curl", "-q", "--noproxy", "*", "-fs", "--max-time", "3", url, capture=True)
    result = json.loads(body)
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object.")
    return result


def wait_for(check, error: str):
    deadline = time.monotonic() + 35
    while True:
        try:
            result = check()
            if result:
                return result
        except (subprocess.SubprocessError, ValueError):
            pass
        if time.monotonic() >= deadline:
            raise ValueError(error)
        time.sleep(2)


class Services:
    def __init__(self, sandbox: str):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,62}", sandbox):
            raise ValueError("Set NAME to a sandbox name using letters, digits, dashes, or underscores.")
        self.sandbox = sandbox
        self.home = Path.home()
        self.state = self.home / "Library/Application Support/t3-code-codex-sandbox/mcp" / sandbox
        self.agents = self.home / "Library/LaunchAgents"
        self.domain = f"gui/{os.getuid()}"
        self.record = self.state / "setup.json"
        self.forward_record = self.state / "forward.json"
        self.config = self.state / "cloudflared.yml"

    @contextmanager
    def locked(self):
        self.state.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (self.state / "lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def label(self, kind: str) -> str:
        return f"io.github.ts-76.t3-code-codex-sandbox.mcp.{self.sandbox}.{kind}"

    def loaded(self, kind: str) -> bool:
        return subprocess.run(
            ["/bin/launchctl", "print", f"{self.domain}/{self.label(kind)}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0

    def start(self, kind: str, args: list[str]):
        if self.loaded(kind):
            return
        self.agents.mkdir(exist_ok=True)
        job = self.agents / f"{self.label(kind)}.plist"
        log = self.state / f"{kind}.log"
        log.touch(mode=0o600)
        private_write(job, plistlib.dumps({
            "Label": self.label(kind),
            "ProgramArguments": args,
            "RunAtLoad": True,
            "KeepAlive": True,
            "ThrottleInterval": 10,
            "StandardOutPath": str(log),
            "StandardErrorPath": str(log),
        }))
        run("/bin/launchctl", "bootstrap", self.domain, str(job))

    def route(self) -> Route | None:
        if not self.record.exists():
            return None
        try:
            return Route(**json.loads(self.record.read_text()))
        except (TypeError, ValueError):
            raise ValueError(f"Could not read the saved MCP settings at {self.record}.") from None

    def forward(self) -> Forward | None:
        if self.forward_record.exists():
            try:
                return Forward(**json.loads(self.forward_record.read_text()))
            except (TypeError, ValueError):
                raise ValueError(f"Could not read the saved forward settings at {self.forward_record}.") from None
        # Setups from earlier versions recorded the forward port only with the tunnel.
        route = self.route()
        return Forward(route.port) if route else None

    def stop_agent(self, kind: str):
        if self.loaded(kind):
            run("/bin/launchctl", "bootout", f"{self.domain}/{self.label(kind)}")
        (self.agents / f"{self.label(kind)}.plist").unlink(missing_ok=True)

    def local_environment(self, local_url: str) -> str | None:
        if not self.loaded("ssh"):
            return None
        forwarded = get_json(local_url + ENVIRONMENT).get("environmentId")
        direct = json.loads(run(
            "sbx", "exec", self.sandbox, "--", "curl", "-q", "--noproxy", "*", "-fsS",
            "--max-time", "3", f"http://127.0.0.1:{T3_PORT}{ENVIRONMENT}", capture=True, timeout=8,
        ))
        if isinstance(direct, dict) and forwarded and forwarded == direct.get("environmentId"):
            return forwarded
        return None

    def online(self, route: Route, sandbox_id: str) -> bool:
        if not self.loaded("tunnel"):
            return False
        public = route.public_url
        return (
            get_json(public + ENVIRONMENT).get("environmentId") == sandbox_id
            and get_json(public + OAUTH_RESOURCE).get("resource") == f"{public}/mcp"
            and get_json(public + "/api/auth/session").get("authenticated") is False
        )

    def connection_problem(self, route: Route) -> str | None:
        try:
            sandbox_id = self.local_environment(route.local_url)
        except (subprocess.SubprocessError, ValueError):
            sandbox_id = None
        if not sandbox_id:
            return f"SSH forward unavailable or sandbox identity differs. Check {self.state / 'ssh.log'}."
        if not self.loaded("tunnel"):
            return f"Cloudflare Tunnel is not loaded. Check {self.state / 'tunnel.log'}."
        try:
            if self.online(route, sandbox_id):
                return None
        except (subprocess.SubprocessError, ValueError):
            pass
        return f"Public HTTPS or OAuth check failed. Check DNS, TLS and {self.state / 'tunnel.log'}."

    def show_http_protection(self, route: Route):
        try:
            result = run(
                "/usr/bin/curl", "-q", "--noproxy", "*", "-s", "--max-time", "3",
                "-o", os.devnull, "--write-out", "%{http_code}\n%{redirect_url}",
                f"http://{route.hostname}/mcp", capture=True,
            )
        except subprocess.CalledProcessError:
            print("MCP HTTP: unreachable from this Mac. Verify HTTP is blocked or redirected on Cloudflare.")
            return
        code, _, redirect = result.partition("\n")
        if code in {"301", "302", "307", "308"} and redirect == f"{route.public_url}/mcp":
            print(f"MCP HTTP: redirects to HTTPS ({code})")
        elif code in {"403", "404", "410"}:
            print(f"MCP HTTP: rejected ({code})")
        else:
            print(f"MCP HTTP: HTTPS redirect not verified ({code}). Check Single Redirects for this hostname.")

    def ensure_forward(self, port_value: str) -> tuple[Forward, str]:
        saved = self.forward()
        port = parse_port(port_value or str(saved.port if saved else DEFAULT_LOCAL_PORT))
        if saved is not None and saved.port != port:
            raise ValueError("Run mcp-stop and link-stop for this sandbox before changing MCP_LOCAL_PORT.")
        try:
            run("/bin/launchctl", "print", self.domain, quiet=True)
        except subprocess.CalledProcessError:
            raise ValueError("Run this command in your macOS login session.") from None
        if not self.loaded("ssh"):
            with socket.socket() as listener:
                try:
                    listener.bind(("127.0.0.1", port))
                except OSError:
                    raise ValueError(f"Mac port {port} is unavailable. Choose a free MCP_LOCAL_PORT.") from None
        print(f"Forward: checking SSH access to {self.sandbox}.sbx", flush=True)
        try:
            run("sbx", "inspect", self.sandbox, capture=True)
        except subprocess.CalledProcessError:
            raise ValueError(f"Could not inspect {self.sandbox}. Run status to check the sandbox name and Docker login.") from None
        ssh_host = f"{self.sandbox}.sbx"
        ssh = [
            "/usr/bin/ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
            "-o", "ControlMaster=no", "-o", "ControlPath=none", ssh_host,
        ]
        try:
            run(*ssh, "command -v t3 && command -v curl", capture=True)
        except subprocess.CalledProcessError:
            raise ValueError(f"Check that SSH to {ssh_host} works and t3 and curl are on its PATH.") from None
        forward = Forward(port)
        private_write(self.forward_record, json.dumps(asdict(forward), indent=2).encode() + b"\n")

        print("Forward: checking the local SSH forward", flush=True)
        script = Path(__file__).resolve().parents[1] / "sandbox" / "mcp-server.sh"
        self.start("ssh", [
            *ssh[:-1], "-tt", "-o", "ExitOnForwardFailure=yes",
            "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3",
            "-L", f"127.0.0.1:{port}:127.0.0.1:{T3_PORT}", ssh_host,
            f"sh -c {shlex.quote(script.read_text())}",
        ])
        sandbox_id = wait_for(
            lambda: self.local_environment(forward.local_url),
            f"The SSH origin did not identify as {self.sandbox}. Check {self.state / 'ssh.log'}.",
        )
        return forward, sandbox_id

    def linked(self, cli: str, environment_id: str | None = None, url: str | None = None) -> list[dict]:
        links = json.loads(run(cli, "environment", "list", "--json", capture=True) or "[]")
        return [
            link for link in links if isinstance(link, dict) and (
                (environment_id is not None and link.get("environmentId") == environment_id)
                or (url is not None and url in (link.get("urls") or []))
            )
        ]

    def link_setup(self, port_value: str, access: str):
        if access not in ACCESS_MODES:
            raise ValueError(f"Set LINK_ACCESS to one of: {', '.join(sorted(ACCESS_MODES))}.")
        cli = t3_cli()
        forward, sandbox_id = self.ensure_forward(port_value)
        existing = self.linked(cli, environment_id=sandbox_id)
        if any(
            forward.local_url in (link.get("urls") or []) and link.get("access") == access
            and link.get("status") == "reachable" for link in existing
        ):
            print(f"\nSandbox: {self.sandbox}\nLinked environment: {forward.local_url} ({access}, reachable)")
            return
        for link in existing:
            # A link to the same sandbox at another address, such as a desktop-managed SSH port, goes stale.
            print(f"Link: replacing the link at {', '.join(link.get('urls') or [])}", flush=True)
            run(cli, "environment", "unlink", sandbox_id, quiet=True)
        issued = json.loads(run(
            "sbx", "exec", self.sandbox, "--", "sh", "-c",
            'exec t3 auth pairing create --base-dir "$HOME/.t3" "$@"',
            "sh", "--ttl", "5m", "--label", "Mac environment link", "--json", capture=True,
        ))
        credential = issued.get("credential") if isinstance(issued, dict) else None
        if not credential:
            raise ValueError("The sandbox did not issue a pairing code.")
        run(cli, "environment", "link", forward.local_url, "--pairing-code", credential, "--access", access)
        wait_for(
            lambda: any(link.get("status") == "reachable" for link in self.linked(cli, environment_id=sandbox_id)),
            "The link was created but the sandbox is not reachable from T3 Code yet. Run status with details.",
        )
        print(f"\nSandbox: {self.sandbox}\nLinked environment: {forward.local_url} ({access}, reachable)")
        print("Agents on this Mac, and outside agents that reach it through T3 Connect, can now work in the sandbox.")

    def link_stop(self):
        if self.record.exists():
            raise ValueError("Run mcp-stop first. The public tunnel uses this SSH forward.")
        forward = self.forward()
        if forward is None and not self.loaded("ssh"):
            print(f"Forward: none for {self.sandbox}.")
            return
        if forward is not None:
            try:
                cli = t3_cli()
            except ValueError:
                cli = None
            for link in self.linked(cli, url=forward.local_url) if cli else []:
                run(cli, "environment", "unlink", link["environmentId"], quiet=True)
                print(f"Link: removed {link.get('label') or link['environmentId']} from T3 Code on this Mac.")
        self.stop_agent("ssh")
        self.forward_record.unlink(missing_ok=True)
        print(f"Forward stopped for {self.sandbox}. Revoke the link's session in the sandbox under Settings → Sharing & access.")

    def setup(self, hostname: str, port_value: str):
        route = self.route()
        hostname = normalize_hostname(hostname or (route.hostname if route else ""))
        if route is not None and port_value and parse_port(port_value) != route.port:
            raise ValueError("Run mcp-stop for this sandbox before changing its hostname or local port.")
        if route is not None and route.hostname != hostname:
            raise ValueError("Run mcp-stop for this sandbox before changing its hostname or local port.")
        cloudflared = shutil.which("cloudflared")
        if not cloudflared:
            raise ValueError("Install cloudflared on the Mac and run cloudflared tunnel login.")
        forward, sandbox_id = self.ensure_forward(port_value or (str(route.port) if route else ""))

        if route is None:
            route = Route(hostname, forward.port, tunnel_id(cloudflared, self.sandbox, hostname))
        credentials = self.home / ".cloudflared" / f"{route.tunnel}.json"
        if not credentials.is_file():
            raise ValueError(f"Restore the credentials file for this named tunnel: {credentials}")
        private_write(self.record, json.dumps(asdict(route), indent=2).encode() + b"\n")
        private_write(self.config, route.cloudflared_config(credentials))
        tunnel = [cloudflared, "tunnel", "--config", str(self.config)]
        run(*tunnel, "ingress", "validate")

        # Preserve existing DNS records even if the caller has this CLI flag set in their environment.
        env = {key: value for key, value in os.environ.items() if key != "TUNNEL_FORCE_PROVISIONING_DNS"}
        run(*tunnel, "route", "dns", route.tunnel, route.hostname, env=env)
        self.start("tunnel", [*tunnel, "--no-autoupdate", "run", route.tunnel])
        print("MCP setup: checking public HTTPS and OAuth", flush=True)
        wait_for(
            lambda: self.online(route, sandbox_id),
            f"The public MCP checks are pending or failed. Check DNS, TLS and {self.state / 'tunnel.log'}, then rerun mcp-setup.",
        )
        print(f"\nSandbox: {self.sandbox}\nMCP URL: {route.public_url}/mcp\nAuthentication: OAuth")
        self.show_http_protection(route)
        print("Add the URL to your MCP client, then run mcp-pair for a sign-in code.")

    def pair(self, access: str):
        if access not in ACCESS_MODES:
            raise ValueError(f"Set MCP_ACCESS to one of: {', '.join(sorted(ACCESS_MODES))}.")
        route = self.route()
        if route is None:
            raise ValueError("Run mcp-setup for this sandbox first.")
        problem = self.connection_problem(route)
        if problem:
            raise ValueError(f"{problem} Rerun mcp-setup before issuing a code.")
        scopes = ["--scope", "orchestration:read"]
        if access != "read-only":
            scopes += ["--scope", "orchestration:operate"]
        if access == "full-access":
            scopes += ["--scope", "settings:write", "--scope", "source-control:write"]
        print(f"MCP URL: {route.public_url}/mcp\nSelect {access} in the OAuth approval page.", flush=True)
        run(
            "sbx", "exec", self.sandbox, "--", "sh", "-c",
            'exec t3 auth pairing create --base-dir "$HOME/.t3" "$@"',
            "sh", "--ttl", "5m", *scopes,
        )

    def stop(self):
        route = self.route()
        if route is None:
            print(f"MCP setup: none for {self.sandbox}.")
            return
        if not self.forward_record.exists():
            private_write(self.forward_record, json.dumps(asdict(Forward(route.port)), indent=2).encode() + b"\n")
        self.stop_agent("tunnel")
        self.record.unlink()
        self.config.unlink(missing_ok=True)
        print(f"MCP tunnel stopped for {self.sandbox}. Cloudflare DNS and the named tunnel remain available for reuse.")
        print(f"The SSH forward at {route.local_url} keeps serving linked environments. Run link-stop to remove it.")

    def status(self):
        forward = self.forward()
        if forward is None:
            return
        print(f"Local forward: {forward.local_url} ({'running' if self.loaded('ssh') else 'stopped'})")
        try:
            links = self.linked(t3_cli(), url=forward.local_url)
        except (OSError, ValueError, subprocess.SubprocessError):
            links = None
        if links is None:
            print("Linked environment: unknown (T3 Code CLI unavailable)")
        elif not links:
            print("Linked environment: none (run link-setup)")
        for link in links or []:
            print(f"Linked environment: {link.get('status')} ({link.get('access')})")
        route = self.route()
        if route is None:
            return
        print(f"MCP URL: {route.public_url}/mcp")
        problem = self.connection_problem(route)
        if problem:
            print(f"MCP connectivity: {problem}")
        else:
            print("MCP connectivity: verified")
            self.show_http_protection(route)


def main() -> int:
    action, sandbox, *settings = sys.argv[1:]
    try:
        if sys.platform != "darwin":
            raise ValueError("Linked environments and the MCP tunnel are managed on macOS.")
        service = Services(sandbox)
        with service.locked():
            if action == "link-setup":
                service.link_setup(settings[1], settings[3] if len(settings) > 3 else "auto")
            elif action == "link-stop":
                service.link_stop()
            elif action == "mcp-setup":
                service.setup(*settings[:2])
            elif action == "mcp-pair":
                service.pair(settings[2])
            elif action == "mcp-stop":
                service.stop()
            elif action == "mcp-status":
                service.status()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            command = Path(error.cmd[0]).name
            print(f"{action}: {command} exited with status {error.returncode}. See the command output.", file=sys.stderr)
        else:
            print(f"{action}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
