# Identity protocol POCs (OIDC, OAuth, JWT)

Minimal, runnable proofs of concept for exploring **OAuth 2.0**, **OpenID Connect (OIDC)**, and **JWT** code flows — plus how those ideas show up in SPIFFE as **JWT-SVID**.

These are teaching harnesses, not production software. Secrets are hard-coded. TLS is omitted. Everything binds to `127.0.0.1`.

## Map

| POC | What you exercise | Entry |
|-----|-------------------|-------|
| [`01-jwt`](01-jwt/) | JOSE/JWT: sign → compact serialize → verify; JWKS publish/consume | `python3 run.py` |
| [`02-oauth`](02-oauth/) | OAuth 2.0 Authorization Code + Client Credentials | `python3 run.py` |
| [`03-oidc`](03-oidc/) | OIDC Auth Code: discovery, ID Token, UserInfo, JWKS | `python3 run.py` |
| [`04-jwt-svid`](04-jwt-svid/) | SPIFFE-shaped JWT-SVID issue → Bearer present → JWKS validate | `python3 run.py` |

Shared helpers live in [`_common/`](_common/).

## How the pieces relate

```
                    ┌─────────────────────────────────────┐
                    │              JWT (JOSE)               │
                    │   compact JWS: header.payload.sig     │
                    └───────────────┬─────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
     OAuth access token      OIDC ID Token         JWT-SVID
     (opaque or JWT)         (always JWT;          (JWT with SPIFFE
                              authenticates user)   ID in `sub`)
              │                     │                     │
              └──────────┬──────────┘                     │
                         ▼                                ▼
                   OIDC = OAuth + identity         SPIFFE workload
                   (ID Token, UserInfo,             identity (not
                    Discovery, JWKS)                an OIDC OP)
```

Key distinctions explored in the POCs:

- **OAuth** authorizes *access to a resource* (scopes / access tokens).
- **OIDC** authenticates the *end user* (ID Token) on top of OAuth.
- **JWT** is a token *format*; OAuth/OIDC/SPIFFE all may use it.
- **JWT-SVID** is a SPIFFE identity document: `sub` is a SPIFFE ID, `aud`/`exp` required; it is **not** an OIDC ID Token. See [`standards/JWT-SVID.md`](../standards/JWT-SVID.md). SPIFFE Federation’s bundle endpoint is *analogous* to OIDC `jwks_uri` ([`standards/SPIFFE_Federation.md`](../standards/SPIFFE_Federation.md)).

## Requirements

Python 3.10+ with `PyJWT` and `cryptography` (already present on many systems):

```bash
pip3 install 'PyJWT[crypto]'
```

From this directory:

```bash
cd pocs/01-jwt && python3 run.py
cd pocs/02-oauth && python3 run.py
cd pocs/03-oidc && python3 run.py
cd pocs/04-jwt-svid && python3 run.py
```

Each runner prints numbered steps so you can follow the protocol on the console.
