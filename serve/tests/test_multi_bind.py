"""Listening on exactly the addresses asked for: each one answers, and one that will not bind leaves nothing listening."""
import socket
import unittest
import urllib.request
from pathlib import Path

from serve.engine.mock import MockEngine
from serve.frontend import ChatTemplate
from serve.handler import serve
from serve.service import Service
from serve.util.text import ByteTokenizer

TEMPLATE = Path(__file__).resolve().parents[1] / "chat_template.jinja"


class MultiBind(unittest.TestCase):
    def setUp(self):
        tok = ByteTokenizer()
        self.svc = Service(MockEngine(tok, "Thought.</think>\n\nHello."), tok, ChatTemplate(TEMPLATE))

    def test_every_address_answers(self):
        httpd = serve(self.svc, host=["127.0.0.1", "127.0.0.2"], port=0)
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        self.assertEqual(sorted(httpd.hosts), ["127.0.0.1", "127.0.0.2"])
        bodies = set()
        for srv in httpd.httpds:
            host, port = srv.server_address[0], srv.server_address[1]
            with urllib.request.urlopen(f"http://{host}:{port}/metrics", timeout=10) as r:
                self.assertEqual(r.status, 200)
                bodies.add(r.read())
        self.assertEqual(len(bodies), 1)          # one service behind both addresses

    def test_an_address_that_will_not_bind_names_it(self):
        with socket.socket() as probe:            # a port nobody else holds
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        with self.assertRaisesRegex(OSError, r"cannot listen on 256\.0\.0\.1"):
            serve(self.svc, host=["127.0.0.1", "256.0.0.1"], port=port)
        # the address that did bind is given back: a plain socket takes the port only when no listener holds it
        # (the servers set SO_REUSEADDR, which on Windows lets a second one in only if both do)
        with socket.socket() as s:
            s.bind(("127.0.0.1", port))

    def test_one_address_is_still_one_server(self):
        httpd = serve(self.svc, host="127.0.0.1", port=0)
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        self.assertEqual(httpd.hosts, ["127.0.0.1"])
        self.assertEqual(httpd.server_address[0], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
