"""auth/tokens.py — kiểm access token Cognito 6 bước, KHÔNG gọi mạng.

Tự sinh khoá RSA, tự ký token đúng hình dạng Cognito (đã xem token thật ở Day 63 bước 4), thay
PyJWKClient bằng JWKS giả. Mỗi ca tấn công phải bị chặn với đúng reason.
"""
import base64
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from auth.tokens import AuthError, TokenVerifier

ISSUER = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TESTPOOL"
CLIENT = "testclient123"
KID = "key-1"


def new_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


KEY = new_key()


class FakeJWKS:
    """Giống PyJWKClient.get_signing_key_from_jwt: chọn public key theo kid, kid lạ → PyJWKClientError."""

    def __init__(self, keys):
        self.keys = keys

    def get_signing_key_from_jwt(self, token):
        kid = jwt.get_unverified_header(token).get("kid")
        if kid not in self.keys:
            raise jwt.PyJWKClientError("Unable to find a signing key that matches")
        return jwt.PyJWK.from_dict({**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.keys[kid])),
                                    "kid": kid, "alg": "RS256"})


class BrokenJWKS:
    def get_signing_key_from_jwt(self, token):
        raise jwt.PyJWKClientConnectionError("Fail to fetch data from the url")


@pytest.fixture
def verifier():
    return TokenVerifier(ISSUER, [CLIENT], jwks_client=FakeJWKS({KID: KEY.public_key()}))


def access_claims(**over):
    now = int(time.time())
    claims = {"sub": "uuid-1", "iss": ISSUER, "client_id": CLIENT, "token_use": "access",
              "scope": "aws.cognito.signin.user.admin", "iat": now, "exp": now + 3600,
              "username": "c003"}                  # Cognito lưu chữ thường (pool không phân biệt hoa/thường)
    claims.update(over)
    return {k: v for k, v in claims.items() if v is not None}


def sign(claims, key=KEY, kid=KID, alg="RS256"):
    return jwt.encode(claims, key, algorithm=alg, headers={"kid": kid})


def reason(verifier, token):
    with pytest.raises(AuthError) as e:
        verifier.customer_id(token)
    return e.value.reason


def b64(obj):
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


# ─── hợp lệ ───

def test_valid_access_token_gives_upper_case_customer_id(verifier):
    assert verifier.customer_id(sign(access_claims())) == "C003"


def test_small_clock_skew_is_accepted(verifier):
    assert verifier.customer_id(sign(access_claims(exp=int(time.time()) - 10))) == "C003"   # < leeway 30s


# ─── 6 bước: mỗi bước sai một kiểu ───

def test_expired(verifier):
    assert reason(verifier, sign(access_claims(exp=int(time.time()) - 120))) == "expired"


def test_issuer_of_another_pool(verifier):
    assert reason(verifier, sign(access_claims(iss=ISSUER.replace("TESTPOOL", "OTHERPOOL")))) == "wrong_issuer"


def test_unknown_client(verifier):
    assert reason(verifier, sign(access_claims(client_id="someone-else"))) == "wrong_client"


def test_id_token_is_not_accepted(verifier):
    id_claims = access_claims(token_use="id", client_id=None, username=None, aud=CLIENT,
                              **{"cognito:username": "c003"})
    assert reason(verifier, sign(id_claims)) == "not_access_token"


@pytest.mark.parametrize("username", ["admin", "C1", "C003; DROP", "", None])
def test_username_not_a_customer_id(verifier, username):
    assert reason(verifier, sign(access_claims(username=username))) == "bad_customer_id"


def test_missing_exp(verifier):
    assert reason(verifier, sign(access_claims(exp=None))) == "malformed"


# ─── tấn công chữ ký ───

def test_alg_none_is_rejected(verifier):
    token = jwt.encode(access_claims(), None, algorithm="none", headers={"kid": KID})
    assert reason(verifier, token) == "bad_signature"


def test_hs256_signed_with_public_key_is_rejected(verifier):
    # tấn công nhầm thuật toán: kẻ gian ký HMAC bằng public key (ai cũng tải được từ JWKS)
    assert reason(verifier, sign(access_claims(), key="any-public-material-0123456789abcdef", alg="HS256")) \
        == "bad_signature"


def test_signed_by_another_key_with_same_kid(verifier):
    assert reason(verifier, sign(access_claims(), key=new_key())) == "bad_signature"


def test_tampered_payload_keeps_old_signature(verifier):
    header, _, signature = sign(access_claims()).split(".")
    forged = ".".join([header, b64(access_claims(username="c020")), signature])   # đổi sang khách khác
    assert reason(verifier, forged) == "bad_signature"


def test_unknown_kid(verifier):
    assert reason(verifier, sign(access_claims(), kid="not-in-jwks")) == "bad_signature"


@pytest.mark.parametrize("token", ["", "abc", "a.b.c", "Bearer xyz"])
def test_garbage(verifier, token):
    assert reason(verifier, token) == "malformed"


# ─── hạ tầng hỏng ≠ người dùng sai ───

def test_jwks_unreachable_is_not_a_user_error():
    v = TokenVerifier(ISSUER, [CLIENT], jwks_client=BrokenJWKS())
    assert reason(v, sign(access_claims())) == "jwks_unavailable"


def test_log_never_contains_token_or_username(verifier, caplog):
    caplog.set_level("INFO", logger="auth")
    token = sign(access_claims())
    verifier.customer_id(token)
    reason(verifier, sign(access_claims(client_id="x")))
    text = caplog.text
    assert "auth=ok" in text and "auth=fail reason=wrong_client" in text
    assert token not in text and "c003" not in text.lower() and "uuid-1" not in text
