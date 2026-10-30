#!/usr/bin/env python3
"""Minimal JWT/JWKS flow: sign → inspect → verify → reject tampering."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jwt
from jwt import PyJWKClient

from _common.http_util import Server, Response, Request, http_json, step
from _common.keys import RsaKeyMaterial


ISSUER = "http://127.0.0.1:18001"
AUDIENCE = "jwt-poc-resource"


def main() -> None:
    keys = RsaKeyMaterial.generate(issuer=ISSUER)

    def jwks(_req: Request) -> Response:
        return Response(200, keys.jwks())

    srv = Server("127.0.0.1", 18001, {("GET", "/.well-known/jwks.json"): jwks}, log_prefix="jwks").start()
    try:
        step(1, "Publish JWKS")
        status, body = http_json("GET", f"{srv.base}/.well-known/jwks.json")
        print(f"HTTP {status}")
        print(json.dumps(body, indent=2))

        step(2, "Sign a JWT (RS256 compact JWS)")
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "sub": "user-42",
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + 60,
            "scope": "read:reports",
        }
        token = jwt.encode(
            claims,
            keys.private_key,
            algorithm="RS256",
            headers={"kid": keys.kid, "typ": "JWT"},
        )
        print(token)
        print(f"segments: {len(token.split('.'))} (header.payload.signature)")

        step(3, "Decode without verifying (inspection)")
        print(json.dumps(jwt.decode(token, options={"verify_signature": False}), indent=2))

        step(4, "Verify via JWKS (kid → public key)")
        jwks_client = PyJWKClient(f"{srv.base}/.well-known/jwks.json")
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        verified = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=AUDIENCE,
            issuer=ISSUER,
        )
        print("verified claims:")
        print(json.dumps(verified, indent=2))

        step(5, "Reject a tampered payload")
        parts = token.split(".")
        # Flip one character in the payload segment if possible.
        payload = parts[1]
        flipped = ("A" if payload[0] != "A" else "B") + payload[1:]
        bad = ".".join([parts[0], flipped, parts[2]])
        try:
            jwt.decode(bad, signing_key.key, algorithms=["RS256"], audience=AUDIENCE, issuer=ISSUER)
            print("UNEXPECTED: tampered token verified")
        except jwt.InvalidTokenError as exc:
            print(f"rejected as expected: {type(exc).__name__}: {exc}")

        print("\nDone. JWT is only a signed claims bag — OAuth/OIDC/SPIFFE decide what claims mean.")
    finally:
        srv.stop()


if __name__ == "__main__":
    main()
