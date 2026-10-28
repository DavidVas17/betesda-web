"""Códigos de un solo uso por tiempo (TOTP, RFC 6238), compatibles con Google Authenticator,
Microsoft Authenticator, Authy y similares.

Se implementa con la biblioteca estándar: es un HMAC-SHA1 del intervalo de 30 segundos
actual, truncado a 6 dígitos. No hace falta una dependencia para esto.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlencode

DIGITS = 6
PERIOD = 30
# Se acepta el intervalo anterior y el siguiente: tolera relojes de teléfono algo desfasados.
WINDOW = 1


def generate_secret() -> str:
    """Secreto aleatorio de 160 bits en base32, como lo esperan las apps."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    padded = secret.upper() + "=" * (-len(secret) % 8)
    return base64.b32decode(padded)


def current_step(at: float | None = None) -> int:
    return int((time.time() if at is None else at) // PERIOD)


def code_at(secret: str, step: int) -> str:
    digest = hmac.new(_key(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**DIGITS).zfill(DIGITS)


def matching_step(secret: str, code: str, *, last_step: int = 0, at: float | None = None):
    """El intervalo al que corresponde ``code``, o ``None``.

    Un código ya usado (intervalo ``<= last_step``) se rechaza aunque siga vigente: así nadie
    puede reutilizar un código que vio por encima del hombro.
    """
    code = "".join(ch for ch in str(code) if ch.isdigit())
    if len(code) != DIGITS:
        return None
    now = current_step(at)
    for step in range(now - WINDOW, now + WINDOW + 1):
        if step > last_step and hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


def provisioning_uri(secret: str, account: str, issuer: str) -> str:
    """El enlace ``otpauth://`` que se muestra como código QR."""
    label = quote(f"{issuer}:{account}")
    query = urlencode({"secret": secret, "issuer": issuer, "digits": DIGITS, "period": PERIOD})
    return f"otpauth://totp/{label}?{query}"


def format_secret(secret: str) -> str:
    """El secreto en grupos de 4 para escribirlo a mano sin errores."""
    return " ".join(secret[i : i + 4] for i in range(0, len(secret), 4))
