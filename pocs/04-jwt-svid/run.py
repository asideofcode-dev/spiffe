#!/usr/bin/env python3
"""Minimal JWT-SVID-shaped flow: issue → Bearer present → JWKS validate."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jwt

from _common.http_util import Request, Response, Server, http_json, step
from _common.keys import RsaKeyMaterial, find_jwk, public_key_from_jwk

TRUST_DOMAIN = "example.org"
SPIFFE_ID = f"spiffe://{TRUST_DOMAIN}/ns/default/sa/reports-client"
AUDIENCE = "spiffe://example.org/reports"
ISSUER_PORT = 18005
RS_PORT = 18006


def main() -> None:
    keys = RsaKeyMaterial.generate(issuer=f"spiffe://{TRUST_DOMAIN}")

    def bundle(_req: Request) -> Response:
        # Simplified SPIFFE JWT bundle (JWKS + spiffe_* fields).
        return Response(200, keys.spiffe_jwt_bundle(TRUST_DOMAIN))

    def reports(req: Request) -> Response:
        auth = req.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return Response(401, {"error": "missing_bearer"})
        token = auth[len("Bearer ") :]
        try:
            header = jwt.get_unverified_header(token)
            alg = header.get("alg")
            # JWT-SVID restricts alg to the RSA/EC/PSS set in the spec.
            allowed = {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512"}
            if alg not in allowed:
                return Response(401, {"error": "invalid_alg", "alg": alg})
            # Resolve key from the SPIFFE JWT bundle. Unlike OIDC jwks_uri keys
            # (use=sig), SPIFFE marks JWT-SVID keys with use=jwt-svid.
            status, bundle_doc = http_json("GET", f"http://127.0.0.1:{ISSUER_PORT}/bundle")
            if status != 200:
                return Response(503, {"error": "bundle_unavailable"})
            jwk = find_jwk(bundle_doc, header.get("kid"))
            if jwk.get("use") not in (None, "jwt-svid", "sig"):
                return Response(401, {"error": "unexpected_key_use", "use": jwk.get("use")})
            pub = public_key_from_jwk(jwk)
            claims = jwt.decode(
                token,
                pub,
                algorithms=list(allowed),
                audience=AUDIENCE,
                options={"require": ["exp", "aud", "sub"]},
            )
        except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
            return Response(401, {"error": "invalid_token", "detail": str(exc)})

        sub = claims["sub"]
        if not sub.startswith("spiffe://"):
            return Response(401, {"error": "sub_not_spiffe_id"})
        return Response(200, {"ok": True, "spiffe_id": sub, "aud": claims["aud"]})

    issuer = Server("127.0.0.1", ISSUER_PORT, {("GET", "/bundle"): bundle}, log_prefix="bundle").start()
    rs = Server("127.0.0.1", RS_PORT, {("GET", "/reports"): reports}, log_prefix="rs").start()

    try:
        step(1, "Issue JWT-SVID (SPIFFE-shaped claims)")
        now = int(time.time())
        svid = jwt.encode(
            {
                "sub": SPIFFE_ID,  # MUST be the SPIFFE ID
                "aud": [AUDIENCE],  # MUST be present
                "exp": now + 60,  # MUST be present
                # iss is not required by JWT-SVID; OIDC ID Tokens require it.
            },
            keys.private_key,
            algorithm="RS256",
            headers={"kid": keys.kid, "typ": "JWT"},
        )
        print(svid)
        print(f"sub={SPIFFE_ID}")
        print(f"aud={AUDIENCE}")

        step(2, "Publish JWT bundle (JWKS with use=jwt-svid)")
        status, body = http_json("GET", f"{issuer.base}/bundle")
        print(f"HTTP {status}")
        print(json.dumps(body, indent=2))
        print("Note: SPIFFE Federation bundle endpoint semantics ≈ OIDC jwks_uri")

        step(3, "Present Bearer JWT-SVID to resource")
        status, body = http_json(
            "GET",
            f"{rs.base}/reports",
            headers={"Authorization": f"Bearer {svid}"},
        )
        print(f"HTTP {status}: {json.dumps(body, indent=2)}")
        assert status == 200, body

        step(4, "Reject wrong audience")
        bad = jwt.encode(
            {"sub": SPIFFE_ID, "aud": ["spiffe://example.org/other"], "exp": now + 60},
            keys.private_key,
            algorithm="RS256",
            headers={"kid": keys.kid},
        )
        status, body = http_json("GET", f"{rs.base}/reports", headers={"Authorization": f"Bearer {bad}"})
        print(f"HTTP {status}: {body}")
        assert status == 401, body

        step(5, "Contrast: OAuth / OIDC / JWT-SVID")
        print(
            """
┌──────────────────┬─────────────────────┬──────────────────────┬──────────────────────────┐
│                  │ OAuth access token  │ OIDC ID Token        │ JWT-SVID                 │
├──────────────────┼─────────────────────┼──────────────────────┼──────────────────────────┤
│ Primary purpose  │ authorize API call  │ authenticate user    │ identify workload        │
│ Format           │ opaque or JWT       │ always JWT           │ JWT (compact JWS)        │
│ sub              │ optional / opaque   │ user subject         │ SPIFFE ID (required)     │
│ aud              │ optional            │ client_id (required) │ required (validator)     │
│ exp              │ common              │ required             │ required                 │
│ iss              │ if JWT, often set   │ required (OP issuer) │ not required by JWT-SVID │
│ Key discovery    │ introspection/JWKS  │ OP jwks_uri          │ SPIFFE JWT bundle/JWKS   │
│ End-user login   │ often yes (code)    │ yes                  │ no (workload attestation)│
└──────────────────┴─────────────────────┴──────────────────────┴──────────────────────────┘
""".rstrip()
        )
        print("\nDone. For the real control plane path see Workload API FetchJWTSVID / ValidateJWTSVID.")
    finally:
        issuer.stop()
        rs.stop()


if __name__ == "__main__":
    main()
