#!/usr/bin/env python3
"""Manage a macOS SSH forward and Cloudflare Tunnel for one sandbox."""

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


def tunnel_id(cloudflared: str, sandbox: str, hostname: str) -> str:
    suffix = hashlib.sha256(f"{sandbox}\n{hostname}".encode()).hexdigest()[:16]
    name = f"t3-code-codex-mcp-{suffix}"

    def find():
        result = json.loads(run(cloudflared, "tunnel", "list", "--name", name, "--output", "json", capture=True))
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
        except (subprocess.CalledProcessError, ValueError):
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
        return Route(**json.loads(self.record.read_text()))

    def local_environment(self, route: Route) -> str | None:
        if not self.loaded("ssh"):
            return None
        forwarded = get_json(route.local_url + ENVIRONMENT).get("environmentId")
        direct = json.loads(run(
            "sbx", "exec", self.sandbox, "--", "curl", "-q", "--noproxy", "*", "-fsS",
            "--max-time", "3", f"http://127.0.0.1:{T3_PORT}{ENVIRONMENT}", capture=True,
        )).get("environmentId")
        if forwarded and forwarded == direct:
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

    def setup(self, hostname: str, port_value: str):
        hostname = normalize_hostname(hostname)
        if not re.fullmatch(r"[0-9]{1,5}", port_value) or not 1024 <= int(port_value) <= 65535:
            raise ValueError("Set MCP_LOCAL_PORT to an unprivileged port (1024–65535).")
        port = int(port_value)
        route = self.route()
        if route is not None and (route.hostname, route.port) != (hostname, port):
            raise ValueError("Run mcp-stop for this sandbox before changing its hostname or local port.")

        cloudflared = shutil.which("cloudflared")
        if not cloudflared:
            raise ValueError("Install cloudflared on the Mac and run cloudflared tunnel login.")
        try:
            run("/bin/launchctl", "print", self.domain, quiet=True)
        except subprocess.CalledProcessError:
            raise ValueError("Run mcp-setup in your macOS login session.") from None
        if not self.loaded("ssh"):
            with socket.socket() as listener:
                try:
                    listener.bind(("127.0.0.1", port))
                except OSError:
                    raise ValueError(f"Mac port {port} is unavailable. Choose a free MCP_LOCAL_PORT.") from None
        run("sbx", "inspect", self.sandbox, capture=True)
        ssh_host = f"{self.sandbox}.sbx"
        ssh = [
            "/usr/bin/ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
            "-o", "ControlMaster=no", "-o", "ControlPath=none", ssh_host,
        ]
        try:
            run(*ssh, "command -v t3 && command -v curl", capture=True)
        except subprocess.CalledProcessError:
            raise ValueError(f"Check that SSH to {ssh_host} works and t3 and curl are on its PATH.") from None
        if route is None:
            route = Route(hostname, port, tunnel_id(cloudflared, self.sandbox, hostname))
        credentials = self.home / ".cloudflared" / f"{route.tunnel}.json"
        if not credentials.is_file():
            raise ValueError(f"Restore the credentials file for this named tunnel: {credentials}")
        private_write(self.record, json.dumps(asdict(route), indent=2).encode() + b"\n")
        private_write(self.config, route.cloudflared_config(credentials))
        tunnel = [cloudflared, "tunnel", "--config", str(self.config)]
        run(*tunnel, "ingress", "validate")

        script = Path(__file__).resolve().parents[1] / "sandbox" / "mcp-server.sh"
        self.start("ssh", [
            *ssh[:-1], "-tt", "-o", "ExitOnForwardFailure=yes",
            "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3",
            "-L", f"127.0.0.1:{port}:127.0.0.1:{T3_PORT}", ssh_host,
            f"sh -c {shlex.quote(script.read_text())}",
        ])
        sandbox_id = wait_for(
            lambda: self.local_environment(route),
            f"The SSH origin did not identify as {self.sandbox}. Check {self.state / 'ssh.log'}.",
        )

        # Preserve existing DNS records even if the caller has this CLI flag set in their environment.
        env = {key: value for key, value in os.environ.items() if key != "TUNNEL_FORCE_PROVISIONING_DNS"}
        run(*tunnel, "route", "dns", route.tunnel, route.hostname, env=env)
        self.start("tunnel", [*tunnel, "--no-autoupdate", "run", route.tunnel])
        wait_for(
            lambda: self.online(route, sandbox_id),
            f"The public MCP checks are pending or failed. Check DNS, TLS and {self.state / 'tunnel.log'}, then rerun mcp-setup.",
        )
        print(f"\nSandbox: {self.sandbox}\nMCP URL: {route.public_url}/mcp\nAuthentication: OAuth")
        print("Add the URL to your MCP client, then run mcp-pair for a sign-in code.")

    def pair(self, access: str):
        if access not in ACCESS_MODES:
            raise ValueError(f"Set MCP_ACCESS to one of: {', '.join(sorted(ACCESS_MODES))}.")
        route = self.route()
        if route is None:
            raise ValueError("Run mcp-setup for this sandbox first.")
        sandbox_id = self.local_environment(route)
        if not sandbox_id or not self.online(route, sandbox_id):
            raise ValueError("The MCP endpoint is unavailable. Rerun mcp-setup before issuing a code.")
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
        if self.route() is None:
            print(f"MCP setup: none for {self.sandbox}.")
            return
        for kind in ("tunnel", "ssh"):
            if self.loaded(kind):
                run("/bin/launchctl", "bootout", f"{self.domain}/{self.label(kind)}")
            (self.agents / f"{self.label(kind)}.plist").unlink(missing_ok=True)
        self.record.unlink()
        self.config.unlink(missing_ok=True)
        print(f"MCP forwarding stopped for {self.sandbox}. Cloudflare DNS and the named tunnel remain available for reuse.")

    def status(self):
        route = self.route()
        if route is None:
            return
        print(f"MCP URL: {route.public_url}/mcp")
        try:
            sandbox_id = self.local_environment(route)
            ready = bool(sandbox_id and self.online(route, sandbox_id))
        except (subprocess.CalledProcessError, ValueError):
            ready = False
        print(f"MCP connectivity: {'verified' if ready else 'unavailable (check with mcp-setup)'}")


def main() -> int:
    action, sandbox, *settings = sys.argv[1:]
    try:
        if sys.platform != "darwin":
            raise ValueError("MCP tunnel setup is available on macOS.")
        service = Services(sandbox)
        with service.locked():
            if action == "mcp-setup":
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
