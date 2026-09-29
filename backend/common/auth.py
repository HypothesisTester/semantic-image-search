"""Verify Firebase ID tokens, without a service-account key.

The frontend signs users in with Firebase Auth and sends the resulting ID
token as ``Authorization: Bearer <token>``. The backend takes the user id
from the verified token and never from the request body; otherwise anyone
could search another person's photos by putting their uid in the request.

A Firebase ID token is an RS256-signed JWT. Checking one needs only the
project id and Google's public signing certificates, which are public and
fetched over HTTPS, then cached for as long as Google's Cache-Control header
allows. Following Firebase's documented checks, a token is valid when:

- it is signed with RS256 by the key named in its ``kid`` header
- ``exp`` is in the future and ``iat`` is in the past
- ``aud`` is the project id
- ``iss`` is https://securetoken.google.com/<project id>
- ``sub`` (the user id) is a non-empty string
- ``auth_time`` is in the past
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable, Mapping

import requests
from google.auth import exceptions as google_exceptions
from google.auth import jwt

CERTS_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
)
DEFAULT_MAX_AGE = 3600
CLOCK_SKEW_SECONDS = 10

CertFetcher = Callable[[], tuple[Mapping[str, str], int]]


class AuthError(Exception):
    """Missing or invalid credentials. Services should answer 401."""


def fetch_google_certs(url: str = CERTS_URL, timeout: float = 5.0) -> tuple[dict[str, str], int]:
    """Download Google's signing certificates and how long they may be cached for."""
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    match = re.search(r"max-age=(\d+)", resp.headers.get("Cache-Control", ""))
    max_age = int(match.group(1)) if match else DEFAULT_MAX_AGE
    return resp.json(), max_age


class CertCache:
    """Caches the signing certificates until they expire."""

    def __init__(
        self,
        fetch: CertFetcher = fetch_google_certs,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._fetch = fetch
        self._clock = clock
        self._certs: Mapping[str, str] = {}
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def get(self) -> Mapping[str, str]:
        with self._lock:
            if self._clock() >= self._expires_at:
                try:
                    certs, max_age = self._fetch()
                except Exception as exc:
                    if self._certs:
                        return self._certs  # keep serving slightly stale keys over failing
                    raise AuthError("could not fetch token signing keys") from exc
                self._certs = dict(certs)
                self._expires_at = self._clock() + max_age
            return self._certs


class FirebaseTokenVerifier:
    def __init__(
        self,
        project_id: str,
        certs: CertCache | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not project_id:
            raise ValueError("project_id is required")
        self.project_id = project_id
        self.issuer = f"https://securetoken.google.com/{project_id}"
        self._certs = certs or CertCache()
        self._clock = clock

    def verify(self, token: str) -> str:
        """Return the user id from a valid ID token, or raise AuthError."""
        try:
            header = jwt.decode_header(token)
        except (ValueError, TypeError, google_exceptions.GoogleAuthError) as exc:
            raise AuthError("malformed token") from exc
        if header.get("alg") != "RS256" or not header.get("kid"):
            raise AuthError("token must be RS256-signed and name its key")

        try:
            claims = jwt.decode(
                token,
                certs=self._certs.get(),
                audience=self.project_id,
                clock_skew_in_seconds=CLOCK_SKEW_SECONDS,
            )
        except (ValueError, google_exceptions.GoogleAuthError) as exc:
            raise AuthError("invalid token") from exc

        if claims.get("iss") != self.issuer:
            raise AuthError("token was not issued for this project")
        uid = claims.get("sub")
        if not isinstance(uid, str) or not uid or len(uid) > 128:
            raise AuthError("token has no valid user id")
        auth_time = claims.get("auth_time")
        if not isinstance(auth_time, (int, float)) or auth_time > self._clock() + CLOCK_SKEW_SECONDS:
            raise AuthError("token has an invalid auth_time")
        return uid

    def uid_from_header(self, authorization: str | None) -> str:
        """Return the user id from an ``Authorization: Bearer <token>`` header value."""
        if not authorization:
            raise AuthError("missing Authorization header")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise AuthError("expected 'Authorization: Bearer <token>'")
        return self.verify(token.strip())
