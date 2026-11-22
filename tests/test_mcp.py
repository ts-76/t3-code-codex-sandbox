from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import re
import subprocess
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
        self.route = mcp.Route(self.route.hostname, 15001, TUNNEL)
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
            patch.object(self.services, "show_http_protection"),
            patch.dict(os.environ, {"TUNNEL_FORCE_PROVISIONING_DNS": "true"}),
            redirect_stdout(StringIO()) as output,
        ):
            def remember_job(*args, **options):
                if args[:2] == ("/bin/launchctl", "bootstrap"):
                    loaded.add(Path(args[-1]).stem.split(".")[-1])
                if args[:2] == ("/bin/launchctl", "bootout"):
                    loaded.remove(args[-1].split(".")[-1])

            run.side_effect = remember_job
            self.services.setup("MCP.EXAMPLE.COM", "15001")
            self.services.setup("", "")
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
            self.assertEqual(loaded, {"ssh"})
            self.assertFalse(self.services.record.exists())
            self.assertEqual(self.services.forward(), mcp.Forward(15001))
            self.assertTrue(credentials.exists())
            with patch.object(mcp, "t3_cli", side_effect=ValueError("no cli")):
                self.services.link_stop()
            self.assertEqual(loaded, set())
            self.assertFalse(self.services.forward_record.exists())

    def test_link_stop_keeps_the_forward_while_the_tunnel_uses_it(self):
        self.services.record.write_text(json.dumps({"hostname": "mcp.example.com", "port": 13773, "tunnel": TUNNEL}))
        with patch.object(mcp, "run") as run, self.assertRaisesRegex(ValueError, "mcp-stop first"):
            self.services.link_stop()
        run.assert_not_called()

    def test_link_setup_replaces_a_stale_link_to_the_same_sandbox(self):
        forward = mcp.Forward(13773)
        links = [{
            "environmentId": "test-sandbox-id", "urls": ["http://127.0.0.1:64096"],
            "access": "auto", "status": "unreachable",
        }]

        def fake_run(*args, **options):
            if args[1:3] == ("environment", "list"):
                return json.dumps(links)
            if args[1:3] == ("environment", "unlink"):
                links.clear()
            if args[1:3] == ("environment", "link"):
                links.append({
                    "environmentId": "test-sandbox-id", "urls": [args[3]],
                    "access": args[-1], "status": "reachable",
                })
            if args[:2] == ("sbx", "exec"):
                return json.dumps({"credential": "PAIRCODE"})
            return ""

        with (
            patch.object(mcp, "t3_cli", return_value="/test/t3"),
            patch.object(self.services, "ensure_forward", return_value=(forward, "test-sandbox-id")),
            patch.object(mcp, "run", side_effect=fake_run) as run,
            redirect_stdout(StringIO()) as output,
        ):
            self.services.link_setup("", "auto")
            commands = [call.args[1:3] for call in run.call_args_list if call.args[0] == "/test/t3"]
            self.assertIn(("environment", "unlink"), commands)
            link = next(call.args for call in run.call_args_list if call.args[1:3] == ("environment", "link"))
            self.assertEqual(link[3:], (forward.local_url, "--pairing-code", "PAIRCODE", "--access", "auto"))
            self.assertIn("reachable", output.getvalue())
            run.reset_mock()
            self.services.link_setup("", "auto")
            self.assertFalse(any(call.args[1:3] == ("environment", "link") for call in run.call_args_list))
        with self.assertRaisesRegex(ValueError, "LINK_ACCESS"):
            self.services.link_setup("", "everything")

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
            patch.object(self.services, "loaded", return_value=True),
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

    def test_pair_reports_which_connection_check_failed_without_issuing_a_code(self):
        with (
            patch.object(self.services, "route", return_value=self.route),
            patch.object(self.services, "local_environment", side_effect=subprocess.TimeoutExpired("sbx", 8)),
            patch.object(mcp, "run") as run,
        ):
            with self.assertRaisesRegex(ValueError, "SSH forward unavailable.*Rerun mcp-setup"):
                self.services.pair("read-only")
            run.assert_not_called()

    def test_reports_http_behavior_for_the_configured_hostname(self):
        for response, expected in (
            ("308\nhttps://mcp.example.com/mcp", "redirects to HTTPS"),
            ("308\nhttps://another.example.com/mcp", "HTTPS redirect not verified"),
            ("401\n", "HTTPS redirect not verified"),
            ("403\n", "rejected"),
        ):
            with self.subTest(response=response), patch.object(mcp, "run", return_value=response) as curl:
                with redirect_stdout(StringIO()) as output:
                    self.services.show_http_protection(self.route)
                self.assertIn(expected, output.getvalue())
                self.assertEqual(curl.call_args.args[-1], "http://mcp.example.com/mcp")


if __name__ == "__main__":
    unittest.main()
