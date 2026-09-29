"""Token verification tests, using our own RSA key in place of Google's."""

import datetime as dt
import time

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from google.auth import crypt, jwt

from common.auth import AuthError, CertCache, FirebaseTokenVerifier

PROJECT = "demo-project"
ISSUER = f"https://securetoken.google.com/{PROJECT}"


def make_key_and_cert():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return key_pem, cert.public_bytes(serialization.Encoding.PEM).decode()


KEY_PEM, CERT_PEM = make_key_and_cert()
OTHER_KEY_PEM, _ = make_key_and_cert()


def token(key_pem=KEY_PEM, kid="k1", **overrides):
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": PROJECT,
        "sub": "uid123",
        "iat": now - 10,
        "exp": now + 3600,
        "auth_time": now - 60,
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    signer = crypt.RSASigner.from_string(key_pem, key_id=kid)
    return jwt.encode(signer, claims).decode()


@pytest.fixture
def verifier():
    return FirebaseTokenVerifier(PROJECT, certs=CertCache(fetch=lambda: ({"k1": CERT_PEM}, 3600)))


def test_valid_token_returns_the_uid(verifier):
    assert verifier.verify(token()) == "uid123"
    assert verifier.uid_from_header(f"Bearer {token()}") == "uid123"


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "another-project"},
        {"iss": "https://securetoken.google.com/another-project"},
        {"iss": "https://accounts.google.com"},
        {"exp": int(time.time()) - 3600, "iat": int(time.time()) - 7200},
        {"iat": int(time.time()) + 3600},
        {"sub": ""},
        {"sub": None},
        {"auth_time": int(time.time()) + 3600},
        {"auth_time": None},
    ],
    ids=[
        "wrong-audience",
        "wrong-project-issuer",
        "non-firebase-issuer",
        "expired",
        "issued-in-future",
        "empty-uid",
        "missing-uid",
        "auth-time-in-future",
        "missing-auth-time",
    ],
)
def test_invalid_claims_are_rejected(verifier, overrides):
    with pytest.raises(AuthError):
        verifier.verify(token(**overrides))


def test_token_signed_by_another_key_is_rejected(verifier):
    with pytest.raises(AuthError):
        verifier.verify(token(key_pem=OTHER_KEY_PEM))


def test_unknown_key_id_is_rejected(verifier):
    with pytest.raises(AuthError):
        verifier.verify(token(kid="unknown"))


def test_tampered_payload_is_rejected(verifier):
    header, payload, signature = token().split(".")
    forged = jwt.encode(crypt.RSASigner.from_string(OTHER_KEY_PEM, "k1"), {"sub": "attacker"})
    forged_payload = forged.decode().split(".")[1]
    with pytest.raises(AuthError):
        verifier.verify(f"{header}.{forged_payload}.{signature}")


def test_unsigned_token_is_rejected(verifier):
    header, payload, _ = token().split(".")
    import base64
    import json

    none_header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=")
    with pytest.raises(AuthError):
        verifier.verify(f"{none_header.decode()}.{payload}.")


@pytest.mark.parametrize("header", [None, "", "Bearer", "Bearer ", "Basic abc", "garbage"])
def test_bad_authorization_headers(verifier, header):
    with pytest.raises(AuthError):
        verifier.uid_from_header(header)


def test_malformed_token(verifier):
    with pytest.raises(AuthError):
        verifier.verify("not.a.jwt")


def test_certs_are_cached_until_they_expire():
    calls = []
    now = [1000.0]

    def fetch():
        calls.append(1)
        return {"k1": CERT_PEM}, 60

    cache = CertCache(fetch=fetch, clock=lambda: now[0])
    cache.get()
    cache.get()
    assert len(calls) == 1
    now[0] += 61
    cache.get()
    assert len(calls) == 2


def test_stale_certs_are_served_if_a_refresh_fails():
    now = [0.0]
    responses = [({"k1": CERT_PEM}, 60)]

    def fetch():
        if not responses:
            raise ConnectionError("network down")
        return responses.pop()

    cache = CertCache(fetch=fetch, clock=lambda: now[0])
    assert "k1" in cache.get()
    now[0] += 120
    assert "k1" in cache.get()  # refresh failed, old certs still used


def test_no_certs_at_all_is_an_auth_error():
    def fetch():
        raise ConnectionError("network down")

    verifier = FirebaseTokenVerifier(PROJECT, certs=CertCache(fetch=fetch))
    with pytest.raises(AuthError, match="signing keys"):
        verifier.verify(token())
