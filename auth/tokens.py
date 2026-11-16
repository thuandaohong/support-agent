"""Kiểm access token Cognito → customer_id (Day 63). Việc của BACKEND, trước khi gọi Runtime.

Runtime vẫn xác thực IAM (chỉ backend của mình gọi được) nên nó không thấy token người dùng.
Backend phải tự chắc chắn "ai đang hỏi" rồi mới điền customer_id vào payload:
  Day 63: scripts/invoke_runtime.py --auth đóng vai backend, gọi hàm này ở local
  Day 64: API Gateway (JWT authorizer) kiểm token, Lambda đọc claim — cùng 6 bước dưới đây

6 bước, thiếu bước nào là có lỗ hổng:
  1. chữ ký: header alg PHẢI là RS256, key chọn theo kid trong JWKS của pool. Chặn alg "none"
     và HS256 (tấn công nhầm thuật toán: ký HMAC bằng chính public key)
  2. iss = https://cognito-idp.<region>.amazonaws.com/<pool_id> — token của pool khác bị từ chối
  3. exp chưa qua (cho lệch đồng hồ LEEWAY_S giây)
  4. token_use == "access" — ID token không dùng để gọi API
  5. client_id thuộc app client của mình
  6. username đúng định dạng customer_id. Pool không phân biệt hoa/thường nên Cognito lưu chữ
     thường ("c003") → chuẩn hoá .upper() rồi mới so (C003 và c003 là CÙNG một user)

Sai → AuthError(reason). Lỗi do hạ tầng (không tải được JWKS) là "jwks_unavailable": backend trả
503, KHÔNG phải 401 — giống Day 60, hệ hỏng không được coi là lỗi của người dùng.
Log chỉ ghi auth=ok / auth=fail reason=… — không ghi token, sub, username.
"""
from __future__ import annotations

import logging
import os
import re

import jwt

log = logging.getLogger("auth")

CUSTOMER_ID = re.compile(r"^C\d{3,6}$")   # định dạng của sample-data, giống serve.py
LEEWAY_S = 30


class AuthError(Exception):
    """Token không dùng được. reason: mã ngắn để log / trả về, không kèm nội dung token."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class TokenVerifier:
    def __init__(self, issuer: str, client_ids, jwks_client=None):
        self.issuer = issuer.rstrip("/")
        self.client_ids = frozenset(client_ids)
        # PyJWKClient tải JWKS một lần rồi cache key theo kid; kid lạ → tải lại (Cognito xoay key)
        self.jwks = jwks_client or jwt.PyJWKClient(f"{self.issuer}/.well-known/jwks.json", lifespan=3600)

    def customer_id(self, token: str) -> str:
        try:
            customer = self._verify(token)
        except AuthError as e:
            log.info("auth=fail reason=%s", e.reason)
            raise
        log.info("auth=ok")
        return customer

    def _verify(self, token: str) -> str:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.DecodeError:
            raise AuthError("malformed") from None
        if header.get("alg") != "RS256":                          # 1. chặn none / HS256 trước khi chọn key
            raise AuthError("bad_signature")
        try:
            key = self.jwks.get_signing_key_from_jwt(token).key
        except jwt.PyJWKClientConnectionError:
            raise AuthError("jwks_unavailable") from None
        except jwt.PyJWKClientError:                             # kid không có trong JWKS của pool
            raise AuthError("bad_signature") from None
        try:
            claims = jwt.decode(
                token, key, algorithms=["RS256"],
                issuer=self.issuer,                               # 2.
                leeway=LEEWAY_S,                                  # 3. exp (+ iat, nbf nếu có)
                options={"require": ["exp", "iss", "token_use"], "verify_aud": False},
            )
        except jwt.ExpiredSignatureError:
            raise AuthError("expired") from None
        except jwt.InvalidIssuerError:
            raise AuthError("wrong_issuer") from None
        except jwt.InvalidSignatureError:
            raise AuthError("bad_signature") from None
        except jwt.InvalidTokenError:                             # thiếu claim bắt buộc, payload hỏng...
            raise AuthError("malformed") from None

        if claims["token_use"] != "access":                      # 4. (ID token không có client_id)
            raise AuthError("not_access_token")
        if claims.get("client_id") not in self.client_ids:       # 5.
            raise AuthError("wrong_client")
        customer = str(claims.get("username", "")).upper()       # 6.
        if not CUSTOMER_ID.fullmatch(customer):
            raise AuthError("bad_customer_id")
        return customer


def verifier_from_env() -> TokenVerifier:
    """COGNITO_ISSUER + COGNITO_CLIENT_ID (nhiều client: phân cách bằng dấu phẩy). Thiếu → KeyError ngay."""
    return TokenVerifier(os.environ["COGNITO_ISSUER"], os.environ["COGNITO_CLIENT_ID"].split(","))
