from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from scripts.host import mcp


TUNNEL = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"


class McpTest(unittest.TestCase):
    def setUp(self):
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        self.home = Path(home.name)
        with patch.object(Path, "home", return_value=self.home):
            self.services = mcp.Services("test-sandbox")
        self.route = mcp.Route("mcp.example.com", 13773, TUNNEL)
        self.services.state.mkdir(parents=True)

    def test_hostname_and_ingress_are_scoped_to_mcp(self):
        self.assertEqual(mcp.normalize_hostname("MCP.Example.COM"), self.route.hostname)
        for bad in ("https://mcp.example.com", "*.example.com", "mcp.example.com:443", "127.0.0.1", "local"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                mcp.normalize_hostname(bad)
        config = json.loads(self.route.cloudflared_config(self.home / "test credential.json"))
        public, fallback = config["ingress"]
        self.assertEqual(public["hostname"], self.route.hostname)
        self.assertEqual(public["service"], "http://127.0.0.1:13773")
        self.assertEqual(fallback, {"service": "http_status:404"})
        for path in (
            "/mcp", "/connect-agent", "/api/auth/session", "/oauth/mcp/approval",
            "/oauth/mcp/token", mcp.OAUTH_RESOURCE, mcp.ENVIRONMENT, "/assets/main.js",
        ):
            self.assertRegex(path, public["path"])
        for path in ("/", "/ws", "/api/auth/browser-session", "/mcp-admin", "/pair", "/assets/../ws"):
            self.assertFalse(re.search(public["path"], path))

    def test_setup_reuses_the_route_and_can_stop_locally(self):
        credentials = self.home / ".cloudflared" / f"{TUNNEL}.json"
        credentials.parent.mkdir()
        credentials.touch()
        loaded = set()
        with (
            patch.object(mcp.shutil, "which", return_value="/test/cloudflared"),
            patch.object(mcp.socket, "socket"),
            patch.object(mcp, "tunnel_id", return_value=TUNNEL) as lookup,
            patch.object(mcp, "run") as run,
            patch.object(self.services, "loaded", side_effect=lambda kind: kind in loaded),
            patch.object(self.services, "local_environment", return_value="test-sandbox-id"),
            patch.object(self.services, "online", return_value=True),
            patch.dict(os.environ, {"TUNNEL_FORCE_PROVISIONING_DNS": "true"}),
            redirect_stdout(StringIO()) as output,
        ):
            def remember_job(*args, **options):
                if args[:2] == ("/bin/launchctl", "bootstrap"):
                    loaded.add(Path(args[-1]).stem.split(".")[-1])
                if args[:2] == ("/bin/launchctl", "bootout"):
                    loaded.remove(args[-1].split(".")[-1])

            run.side_effect = remember_job
            self.services.setup("MCP.EXAMPLE.COM", "13773")
            self.services.setup("mcp.example.com", "13773")
            self.assertEqual(self.services.route(), self.route)
            self.assertEqual(self.services.record.stat().st_mode & 0o777, 0o600)
            self.assertIn("https://mcp.example.com/mcp", output.getvalue())
            lookup.assert_called_once()
            bootstraps = [call for call in run.call_args_list if call.args[:2] == ("/bin/launchctl", "bootstrap")]
            self.assertEqual(len(bootstraps), 2)
            dns = [call for call in run.call_args_list if call.args[-4:-2] == ("route", "dns")]
            self.assertEqual(len(dns), 2)
            for call in dns:
                self.assertEqual(call.args[-2:], (TUNNEL, self.route.hostname))
                self.assertNotIn("TUNNEL_FORCE_PROVISIONING_DNS", call.kwargs["env"])
            with self.assertRaisesRegex(ValueError, "mcp-stop"):
                self.services.setup("second.example.com", "13773")
            self.services.stop()
            self.assertEqual(loaded, set())
            self.assertFalse(self.services.record.exists())
            self.assertTrue(credentials.exists())

    def test_public_check_requires_the_sandbox_and_its_oauth_resource(self):
        responses = {
            self.route.public_url + mcp.ENVIRONMENT: {"environmentId": "different-sandbox-id"},
            self.route.public_url + mcp.OAUTH_RESOURCE: {"resource": self.route.public_url + "/other"},
            self.route.public_url + "/api/auth/session": {"authenticated": False},
        }
        with patch.object(mcp, "get_json", side_effect=responses.__getitem__), patch.object(
            self.services, "loaded", return_value=True
        ):
            self.assertFalse(self.services.online(self.route, "test-sandbox-id"))
            responses[self.route.public_url + mcp.ENVIRONMENT]["environmentId"] = "test-sandbox-id"
            self.assertFalse(self.services.online(self.route, "test-sandbox-id"))
            responses[self.route.public_url + mcp.OAUTH_RESOURCE]["resource"] = self.route.public_url + "/mcp"
            self.assertTrue(self.services.online(self.route, "test-sandbox-id"))

    def test_pairing_issues_a_short_lived_code_with_explicit_scopes(self):
        with (
            patch.object(self.services, "route", return_value=self.route),
            patch.object(self.services, "local_environment", return_value="test-sandbox-id"),
            patch.object(self.services, "online", return_value=True),
            patch.object(mcp, "run") as run,
            redirect_stdout(StringIO()),
        ):
            self.services.pair("read-only")
            self.assertEqual(run.call_args.args[:4], ("sbx", "exec", "test-sandbox", "--"))
            self.assertEqual(run.call_args.args[8:], ("--ttl", "5m", "--scope", "orchestration:read"))
            self.services.pair("full-access")
            self.assertEqual(run.call_args.args[8:], (
                "--ttl", "5m", "--scope", "orchestration:read", "--scope", "orchestration:operate",
                "--scope", "settings:write", "--scope", "source-control:write",
            ))


if __name__ == "__main__":
    unittest.main()
