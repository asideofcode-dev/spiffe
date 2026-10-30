# POC 04 — JWT-SVID (SPIFFE-shaped)

Explores the SPIFFE JWT identity document path that sits next to OAuth/OIDC in this repo’s standards.

This is a **simulation** of issuer → presenter → validator. It does not speak the Workload API; it mirrors the claim and JWKS rules from [`standards/JWT-SVID.md`](../../standards/JWT-SVID.md).

## Flow

1. Trust domain issues a **JWT-SVID** (`sub` = SPIFFE ID, required `aud` + `exp`, `RS256`, optional `kid`).
2. Publish a SPIFFE-ish **JWT bundle** (JWKS with `use: jwt-svid`) — analogous to OIDC `jwks_uri` / Federation bundle endpoint.
3. Workload presents `Authorization: Bearer <jwt-svid>` to a resource.
4. Resource validates signature via JWKS, then enforces `aud`, `exp`, and SPIFFE ID `sub`.
5. Contrast table vs OAuth access token and OIDC ID Token.

## Run

```bash
python3 run.py
```

## Spec anchors

- [`standards/JWT-SVID.md`](../../standards/JWT-SVID.md)
- [`standards/SPIFFE_Trust_Domain_and_Bundle.md`](../../standards/SPIFFE_Trust_Domain_and_Bundle.md)
- [`standards/SPIFFE_Federation.md`](../../standards/SPIFFE_Federation.md) (bundle endpoint ≈ `jwks_uri`)
- [`standards/SPIFFE_Workload_API.md`](../../standards/SPIFFE_Workload_API.md) (`FetchJWTSVID` / `FetchJWTBundles` / `ValidateJWTSVID`)
