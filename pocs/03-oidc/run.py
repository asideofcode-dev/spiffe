#!/usr/bin/env python3
"""Minimal OIDC Authorization Code: discovery, ID Token, UserInfo, JWKS."""

from __future__ import annotations

import json
import secrets
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jwt
from jwt import PyJWKClient

from _common.http_util import Request, Response, Server, http_json, http_no_redirect, step
from _common.keys import RsaKeyMaterial

OP_PORT = 18004
CLIENT_ID = "oidc-demo-client"
CLIENT_SECRET = "oidc-demo-secret"
REDIRECT_URI = "http://127.0.0.1:9999/callback"
ISSUER = f"http://127.0.0.1:{OP_PORT}"


def main() -> None:
    keys = RsaKeyMaterial.generate(issuer=ISSUER)
    codes: dict[str, dict] = {}
    access_tokens: dict[str, dict] = {}

    users = {
        "alice": {"sub": "alice", "name": "Alice Example", "email": "alice@example.com"},
    }

    def discovery(_req: Request) -> Response:
        return Response(
            200,
            {
                "issuer": ISSUER,
                "authorization_endpoint": f"{ISSUER}/authorize",
                "token_endpoint": f"{ISSUER}/token",
                "userinfo_endpoint": f"{ISSUER}/userinfo",
                "jwks_uri": f"{ISSUER}/.well-known/jwks.json",
                "response_types_supported": ["code"],
                "subject_types_supported": ["public"],
                "id_token_signing_alg_values_supported": ["RS256"],
                "scopes_supported": ["openid", "profile", "email"],
            },
        )

    def jwks(_req: Request) -> Response:
        return Response(200, keys.jwks())

    def authorize(req: Request) -> Response:
        if req.q("response_type") != "code":
            return Response(400, {"error": "unsupported_response_type"})
        if req.q("client_id") != CLIENT_ID:
            return Response(400, {"error": "invalid_client"})
        if "openid" not in (req.q("scope") or "").split():
            return Response(400, {"error": "invalid_scope", "error_description": "openid required"})
        code = secrets.token_urlsafe(16)
        codes[code] = {
            "client_id": CLIENT_ID,
            "redirect_uri": req.q("redirect_uri"),
            "scope": req.q("scope") or "openid",
            "nonce": req.q("nonce"),
            "user": "alice",
            "exp": time.time() + 60,
        }
        loc = (req.q("redirect_uri") or REDIRECT_URI) + "?" + urllib.parse.urlencode(
            {"code": code, "state": req.q("state") or ""}
        )
        return Response(302, headers={"Location": loc}, body="redirect")

    def token(req: Request) -> Response:
        form = req.form()
        if form.get("client_id") != CLIENT_ID or form.get("client_secret") != CLIENT_SECRET:
            return Response(401, {"error": "invalid_client"})
        if form.get("grant_type") != "authorization_code":
            return Response(400, {"error": "unsupported_grant_type"})
        entry = codes.pop(form.get("code", ""), None)
        if not entry or entry["redirect_uri"] != form.get("redirect_uri") or entry["exp"] < time.time():
            return Response(400, {"error": "invalid_grant"})

        now = int(time.time())
        user = users[entry["user"]]
        id_claims = {
            "iss": ISSUER,
            "sub": user["sub"],
            "aud": CLIENT_ID,
            "iat": now,
            "exp": now + 300,
            "auth_time": now,
            "nonce": entry["nonce"],
            "email": user["email"],
            "name": user["name"],
        }
        id_token = jwt.encode(
            id_claims,
            keys.private_key,
            algorithm="RS256",
            headers={"kid": keys.kid, "typ": "JWT"},
        )
        access = secrets.token_urlsafe(24)
        access_tokens[access] = {"sub": user["sub"], "scope": entry["scope"], "exp": time.time() + 300}
        return Response(
            200,
            {
                "access_token": access,
                "token_type": "Bearer",
                "expires_in": 300,
                "id_token": id_token,
                "scope": entry["scope"],
            },
        )

    def userinfo(req: Request) -> Response:
        auth = req.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return Response(401, {"error": "missing_bearer"})
        meta = access_tokens.get(auth[len("Bearer ") :])
        if not meta or meta["exp"] < time.time():
            return Response(401, {"error": "invalid_token"})
        user = users[meta["sub"]]
        return Response(200, user)

    op = Server(
        "127.0.0.1",
        OP_PORT,
        {
            ("GET", "/.well-known/openid-configuration"): discovery,
            ("GET", "/.well-known/jwks.json"): jwks,
            ("GET", "/authorize"): authorize,
            ("POST", "/token"): token,
            ("GET", "/userinfo"): userinfo,
        },
        log_prefix="op",
    ).start()

    try:
        step(1, "OIDC Discovery")
        status, conf = http_json("GET", f"{ISSUER}/.well-known/openid-configuration")
        print(f"HTTP {status}")
        print(json.dumps(conf, indent=2))

        step(2, "Authorization Code with scope=openid profile email")
        nonce = secrets.token_urlsafe(12)
        state = secrets.token_urlsafe(8)
        auth_url = (
            f"{conf['authorization_endpoint']}?"
            + urllib.parse.urlencode(
                {
                    "response_type": "code",
                    "client_id": CLIENT_ID,
                    "redirect_uri": REDIRECT_URI,
                    "scope": "openid profile email",
                    "state": state,
                    "nonce": nonce,
                }
            )
        )
        print(f"GET {auth_url}")
        status, headers = http_no_redirect(auth_url)
        if status != 302:
            raise RuntimeError(f"expected 302, got {status}")
        loc = headers["Location"]
        print(f"302 Location: {loc}")
        code = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)["code"][0]

        step(3, "Token endpoint returns access_token + id_token")
        status, tok = http_json(
            "POST",
            conf["token_endpoint"],
            form={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )
        print(f"HTTP {status}")
        print(f"access_token: {tok['access_token'][:16]}…")
        print(f"id_token:     {tok['id_token'][:48]}…")

        step(4, "Verify ID Token against JWKS")
        jwks_client = PyJWKClient(conf["jwks_uri"])
        signing_key = jwks_client.get_signing_key_from_jwt(tok["id_token"])
        claims = jwt.decode(
            tok["id_token"],
            signing_key.key,
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=ISSUER,
        )
        assert claims["nonce"] == nonce
        print(json.dumps(claims, indent=2))
        print("nonce matched; iss/aud/exp/signature OK")

        step(5, "UserInfo with access token")
        status, info = http_json(
            "GET",
            conf["userinfo_endpoint"],
            headers={"Authorization": f"Bearer {tok['access_token']}"},
        )
        print(f"HTTP {status}: {json.dumps(info, indent=2)}")

        print("\nDone. ID Token authenticates the end-user to the client; access token authorizes API calls.")
        print("Contrast with JWT-SVID (POC 04): there `sub` is a SPIFFE ID, not a user subject.")
    finally:
        op.stop()


if __name__ == "__main__":
    main()
