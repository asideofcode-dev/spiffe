"""Ephemeral RSA keypair + JWKS helpers for the POCs."""

from __future__ import annotations

import base64
import secrets
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers


def _b64url_uint(n: int) -> str:
    length = (n.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(n.to_bytes(length, "big")).rstrip(b"=").decode("ascii")


def _b64url_to_int(s: str) -> int:
    pad = "=" * (-len(s) % 4)
    return int.from_bytes(base64.urlsafe_b64decode(s + pad), "big")


def public_key_from_jwk(jwk: dict[str, Any]) -> rsa.RSAPublicKey:
    if jwk.get("kty") != "RSA":
        raise ValueError(f"unsupported kty: {jwk.get('kty')}")
    return RSAPublicNumbers(_b64url_to_int(jwk["e"]), _b64url_to_int(jwk["n"])).public_key()


def find_jwk(jwks: dict[str, Any], kid: str | None) -> dict[str, Any]:
    keys = jwks.get("keys") or []
    if kid:
        for k in keys:
            if k.get("kid") == kid:
                return k
    if len(keys) == 1:
        return keys[0]
    raise KeyError(f"no JWK matched kid={kid!r}")


@dataclass
class RsaKeyMaterial:
    private_key: rsa.RSAPrivateKey
    kid: str
    issuer: str

    @classmethod
    def generate(cls, issuer: str, kid: str | None = None) -> "RsaKeyMaterial":
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        return cls(private_key=key, kid=kid or secrets.token_hex(8), issuer=issuer)

    @property
    def public_key(self) -> rsa.RSAPublicKey:
        return self.private_key.public_key()

    def pem_private(self) -> bytes:
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

    def jwk(self) -> dict[str, Any]:
        pub = self.public_key.public_numbers()
        return {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": self.kid,
            "n": _b64url_uint(pub.n),
            "e": _b64url_uint(pub.e),
        }

    def jwks(self) -> dict[str, Any]:
        return {"keys": [self.jwk()]}

    def spiffe_jwt_bundle(self, trust_domain: str) -> dict[str, Any]:
        """SPIFFE Trust Domain bundle shape with a jwt-svid key (simplified)."""
        jwk = self.jwk()
        jwk["use"] = "jwt-svid"
        return {
            "keys": [jwk],
            "spiffe_sequence": 1,
            "spiffe_refresh_hint": 300,
            # Non-standard annotation for the POC only — real bundles are keyed by trust domain externally.
            "_poc_trust_domain": trust_domain,
        }
