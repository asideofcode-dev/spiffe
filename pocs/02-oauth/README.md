# POC 02 — OAuth 2.0

Explores two common grant flows against a tiny in-memory Authorization Server (AS) and Resource Server (RS).

## Flows

### Authorization Code

1. Client redirects the user-agent to the AS `/authorize`.
2. User authenticates (auto-approved in this POC) → AS returns `code` to `redirect_uri`.
3. Client exchanges `code` (+ `client_secret`) at `/token` → **access token**.
4. Client calls RS with `Authorization: Bearer <access_token>`.

### Client Credentials

1. Confidential client posts `grant_type=client_credentials` to `/token`.
2. AS returns an access token (no end-user).
3. Client calls RS with the bearer token.

## Run

```bash
python3 run.py
```

## Spec anchors

- [RFC 6749](https://www.rfc-editor.org/rfc/rfc6749) OAuth 2.0
- [RFC 6750](https://www.rfc-editor.org/rfc/rfc6750) Bearer Token Usage
