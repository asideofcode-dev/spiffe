"""Tiny HTTP helpers built on stdlib."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable


HandlerFn = Callable[["Request"], "Response"]


class Request:
    def __init__(self, method: str, path: str, query: dict[str, list[str]], headers: dict[str, str], body: bytes):
        self.method = method
        self.path = path
        self.query = query
        self.headers = headers
        self.body = body

    def json(self) -> Any:
        if not self.body:
            return {}
        return json.loads(self.body.decode("utf-8"))

    def form(self) -> dict[str, str]:
        ctype = self.headers.get("Content-Type", "")
        if "application/x-www-form-urlencoded" in ctype:
            return {k: v[0] for k, v in urllib.parse.parse_qs(self.body.decode("utf-8")).items()}
        if "application/json" in ctype:
            data = self.json()
            return {str(k): str(v) for k, v in data.items()}
        return {k: v[0] for k, v in urllib.parse.parse_qs(self.body.decode("utf-8")).items()}

    def q(self, name: str, default: str | None = None) -> str | None:
        vals = self.query.get(name)
        return vals[0] if vals else default


class Response:
    def __init__(self, status: int = 200, body: Any = None, headers: dict[str, str] | None = None, raw: bytes | None = None):
        self.status = status
        self.headers = {"Cache-Control": "no-store", **(headers or {})}
        if raw is not None:
            self.raw = raw
        elif isinstance(body, (dict, list)):
            self.raw = json.dumps(body, indent=2).encode("utf-8")
            self.headers.setdefault("Content-Type", "application/json")
        elif body is None:
            self.raw = b""
        else:
            self.raw = str(body).encode("utf-8")
            self.headers.setdefault("Content-Type", "text/plain; charset=utf-8")


def make_handler(routes: dict[tuple[str, str], HandlerFn], log_prefix: str = "srv") -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            print(f"  [{log_prefix}] {self.command} {self.path} -> {args[1] if len(args) > 1 else ''}".rstrip())

        def _dispatch(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            query = urllib.parse.parse_qs(parsed.query)
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            req = Request(self.command, path, query, {k: v for k, v in self.headers.items()}, body)
            fn = routes.get((self.command, path))
            if fn is None:
                resp = Response(404, {"error": "not_found", "path": path})
            else:
                try:
                    resp = fn(req)
                except Exception as exc:  # noqa: BLE001 - POC surface errors as HTTP
                    resp = Response(500, {"error": "server_error", "detail": str(exc)})
            self.send_response(resp.status)
            for k, v in resp.headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(resp.raw)))
            self.end_headers()
            self.wfile.write(resp.raw)

        def do_GET(self) -> None:  # noqa: N802
            self._dispatch()

        def do_POST(self) -> None:  # noqa: N802
            self._dispatch()

    return Handler


class Server:
    def __init__(self, host: str, port: int, routes: dict[tuple[str, str], HandlerFn], log_prefix: str = "srv"):
        self.host = host
        self.port = port
        self._httpd = ThreadingHTTPServer((host, port), make_handler(routes, log_prefix=log_prefix))
        self._thread: threading.Thread | None = None

    @property
    def base(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> "Server":
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread:
            self._thread.join(timeout=2)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, N803
        return None


_NO_REDIRECT = urllib.request.build_opener(_NoRedirect)


def http_json(method: str, url: str, *, data: dict[str, Any] | None = None, form: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> tuple[int, Any]:
    hdrs = dict(headers or {})
    body: bytes | None = None
    if form is not None:
        body = urllib.parse.urlencode(form).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif data is not None:
        body = json.dumps(data).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            if "json" in ctype:
                return resp.status, json.loads(raw.decode("utf-8") or "null")
            return resp.status, raw.decode("utf-8")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001
            payload = raw.decode("utf-8", errors="replace")
        return e.code, payload


def http_no_redirect(url: str) -> tuple[int, dict[str, str]]:
    """GET that returns the first response without following redirects."""
    req = urllib.request.Request(url, method="GET")
    try:
        with _NO_REDIRECT.open(req, timeout=5) as resp:
            return resp.status, {k: v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, {k: v for k, v in e.headers.items()}


def step(n: int, title: str) -> None:
    print(f"\n=== Step {n}: {title} ===")
