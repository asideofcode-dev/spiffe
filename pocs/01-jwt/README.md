# POC 01 — JWT (JOSE)

Explores the raw JWT/JWS building blocks that OAuth, OIDC, and JWT-SVID all sit on.

## Flow

1. Generate an RSA keypair and publish a **JWKS**.
2. Sign a payload → **JWS Compact Serialization** (`header.payload.signature`).
3. Decode without verifying (inspection only).
4. Verify signature + claims using the JWKS (`kid` lookup, `RS256`).
5. Reject a tampered token.

## Run

```bash
python3 run.py
```

## Spec anchors

- [RFC 7519](https://www.rfc-editor.org/rfc/rfc7519) JWT
- [RFC 7515](https://www.rfc-editor.org/rfc/rfc7515) JWS
- [RFC 7517](https://www.rfc-editor.org/rfc/rfc7517) JWK / JWKS
