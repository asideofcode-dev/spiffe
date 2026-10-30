# POC 03 — OpenID Connect

OIDC is OAuth 2.0 plus an identity layer. This POC adds:

- **Discovery** (`/.well-known/openid-configuration`)
- **JWKS** for ID Token signature verification
- **ID Token** (JWT) issued alongside the access token
- **UserInfo** endpoint

## Flow

1. Discover the OpenID Provider (OP) configuration.
2. Run Authorization Code (same as OAuth) with `scope` including `openid`.
3. Receive `id_token` + `access_token` from `/token`.
4. Verify the ID Token against the OP JWKS (`iss`, `aud`, `exp`, `nonce`).
5. Call UserInfo with the access token.

## Run

```bash
python3 run.py
```

## Spec anchors

- [OpenID Connect Core 1.0](https://openid.net/specs/openid-connect-core-1_0.html)
- [OpenID Connect Discovery 1.0](https://openid.net/specs/openid-connect-discovery-1_0.html)
