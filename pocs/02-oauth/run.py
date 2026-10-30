#!/usr/bin/env python3
"""Minimal OAuth 2.0: Authorization Code + Client Credentials."""

from __future__ import annotations

import secrets
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common.http_util import Request, Response, Server, http_json, http_no_redirect, step

AS_PORT = 18002
RS_PORT = 18003
CLIENT_ID = "demo-client"
CLIENT_SECRET = "demo-secret"
REDIRECT_URI = "http://127.0.0.1:9999/callback"
RESOURCE = "http://127.0.0.1:18003/reports"


def main() -> None:
    codes: dict[str, dict] = {}
    tokens: dict[str, dict] = {}

    def authorize(req: Request) -> Response:
        # Auto-approve: real ASs show a login + consent screen here.
        if req.q("response_type") != "code":
            return Response(400, {"error": "unsupported_response_type"})
        if req.q("client_id") != CLIENT_ID:
            return Response(400, {"error": "invalid_client"})
        if req.q("redirect_uri") != REDIRECT_URI:
            return Response(400, {"error": "invalid_redirect_uri"})
        code = secrets.token_urlsafe(16)
        codes[code] = {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": req.q("scope") or "",
            "user": "alice",
            "exp": time.time() + 60,
        }
        loc = REDIRECT_URI + "?" + urllib.parse.urlencode({"code": code, "state": req.q("state") or ""})
        return Response(302, headers={"Location": loc}, body="redirect")

    def token(req: Request) -> Response:
        form = req.form()
        grant = form.get("grant_type")
        if form.get("client_id") != CLIENT_ID or form.get("client_secret") != CLIENT_SECRET:
            return Response(401, {"error": "invalid_client"})

        if grant == "authorization_code":
            entry = codes.pop(form.get("code", ""), None)
            if not entry or entry["redirect_uri"] != form.get("redirect_uri") or entry["exp"] < time.time():
                return Response(400, {"error": "invalid_grant"})
            access = secrets.token_urlsafe(24)
            tokens[access] = {
                "sub": entry["user"],
                "client_id": CLIENT_ID,
                "scope": entry["scope"],
                "exp": time.time() + 300,
                "grant": "authorization_code",
            }
            return Response(200, {"access_token": access, "token_type": "Bearer", "expires_in": 300, "scope": entry["scope"]})

        if grant == "client_credentials":
            access = secrets.token_urlsafe(24)
            scope = form.get("scope") or "reports:read"
            tokens[access] = {
                "sub": CLIENT_ID,
                "client_id": CLIENT_ID,
                "scope": scope,
                "exp": time.time() + 300,
                "grant": "client_credentials",
            }
            return Response(200, {"access_token": access, "token_type": "Bearer", "expires_in": 300, "scope": scope})

        return Response(400, {"error": "unsupported_grant_type"})

    def reports(req: Request) -> Response:
        auth = req.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return Response(401, {"error": "missing_bearer"})
        access = auth[len("Bearer ") :]
        meta = tokens.get(access)
        if not meta or meta["exp"] < time.time():
            return Response(401, {"error": "invalid_token"})
        if "reports:read" not in meta["scope"].split():
            return Response(403, {"error": "insufficient_scope"})
        return Response(200, {"ok": True, "caller": meta["sub"], "grant": meta["grant"], "data": ["q1", "q2"]})

    as_srv = Server(
        "127.0.0.1",
        AS_PORT,
        {("GET", "/authorize"): authorize, ("POST", "/token"): token},
        log_prefix="as",
    ).start()
    rs_srv = Server("127.0.0.1", RS_PORT, {("GET", "/reports"): reports}, log_prefix="rs").start()

    try:
        # --- Authorization Code ---
        step(1, "Authorization Code — browser hits /authorize")
        state = secrets.token_urlsafe(8)
        auth_url = (
            f"{as_srv.base}/authorize?"
            + urllib.parse.urlencode(
                {
                    "response_type": "code",
                    "client_id": CLIENT_ID,
                    "redirect_uri": REDIRECT_URI,
                    "scope": "reports:read",
                    "state": state,
                }
            )
        )
        print(f"GET {auth_url}")
        # Do not follow the redirect — capture the authorization code from Location.
        status, headers = http_no_redirect(auth_url)
        if status != 302:
            raise RuntimeError(f"expected 302, got {status}")
        loc = headers["Location"]
        print(f"302 Location: {loc}")
        q = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)
        code = q["code"][0]
        assert q["state"][0] == state

        step(2, "Client exchanges code at /token")
        status, tok = http_json(
            "POST",
            f"{as_srv.base}/token",
            form={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )
        print(f"HTTP {status}: {tok}")
        access_user = tok["access_token"]

        step(3, "Call resource server with user access token")
        status, body = http_json("GET", RESOURCE, headers={"Authorization": f"Bearer {access_user}"})
        print(f"HTTP {status}: {body}")

        # --- Client Credentials ---
        step(4, "Client Credentials — machine client hits /token")
        status, tok2 = http_json(
            "POST",
            f"{as_srv.base}/token",
            form={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "scope": "reports:read",
            },
        )
        print(f"HTTP {status}: {tok2}")

        step(5, "Call resource server with client credentials token")
        status, body = http_json("GET", RESOURCE, headers={"Authorization": f"Bearer {tok2['access_token']}"})
        print(f"HTTP {status}: {body}")

        print("\nDone. OAuth issues access tokens for authorization — it does not define user identity claims.")
        print("OIDC (POC 03) adds the ID Token for authentication.")
    finally:
        as_srv.stop()
        rs_srv.stop()


if __name__ == "__main__":
    main()
