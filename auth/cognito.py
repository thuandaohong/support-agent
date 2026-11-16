"""Phía "người dùng đăng nhập" cho script và integration test (Day 63) — CHỈ chạy ở máy dev.

Đóng vai trình duyệt của khách: đăng nhập user test bằng ADMIN_USER_PASSWORD_AUTH → access token.
Flow này đòi quyền IAM cognito-idp:AdminInitiateAuth (máy dev có), nên người ngoài không dùng được;
frontend thật (Day 64) dùng SRP. Pool / client tra theo TÊN (infra/auth/auth.env), không lưu id.
Mật khẩu đọc từ infra/auth/test-users.env (03-test-users.sh sinh, gitignore) — không in ra.
"""
from __future__ import annotations

import os
from pathlib import Path

import boto3

from auth.tokens import TokenVerifier

REGION = os.environ.get("AWS_REGION", "us-east-1")
POOL_NAME = os.environ.get("POOL_NAME", "support-users")
CLIENT_NAME = os.environ.get("CLIENT_NAME", "support-web")
USERS_FILE = Path(__file__).resolve().parent.parent / "infra" / "auth" / "test-users.env"


class Cognito:
    def __init__(self):
        self.idp = boto3.client("cognito-idp", region_name=REGION)
        self.pool_id = self._pool_id()
        self.client_id = self._client_id()
        self.issuer = f"https://cognito-idp.{REGION}.amazonaws.com/{self.pool_id}"
        self._passwords: dict[str, str] | None = None

    def _pool_id(self) -> str:
        for p in self.idp.list_user_pools(MaxResults=60)["UserPools"]:
            if p["Name"] == POOL_NAME:
                return p["Id"]
        raise SystemExit(f"Không thấy user pool {POOL_NAME} — chạy infra/auth/01-user-pool.sh")

    def _client_id(self) -> str:
        for c in self.idp.list_user_pool_clients(UserPoolId=self.pool_id, MaxResults=60)["UserPoolClients"]:
            if c["ClientName"] == CLIENT_NAME:
                return c["ClientId"]
        raise SystemExit(f"Không thấy app client {CLIENT_NAME} — chạy infra/auth/02-app-client.sh")

    def verifier(self) -> TokenVerifier:
        return TokenVerifier(self.issuer, [self.client_id])

    def password(self, username: str) -> str:
        if self._passwords is None:
            if not USERS_FILE.exists():
                raise SystemExit(f"Thiếu {USERS_FILE} — chạy infra/auth/03-test-users.sh")
            lines = USERS_FILE.read_text().splitlines()
            self._passwords = dict(line.split("=", 1) for line in lines if "=" in line)
        if username not in self._passwords:
            raise SystemExit(f"Không có user test {username} (TEST_USERS trong infra/auth/auth.env)")
        return self._passwords[username]

    def login(self, username: str) -> dict:
        """Đăng nhập → {"AccessToken", "IdToken", "RefreshToken", ...}."""
        r = self.idp.admin_initiate_auth(
            UserPoolId=self.pool_id, ClientId=self.client_id, AuthFlow="ADMIN_USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": self.password(username)},
        )
        return r["AuthenticationResult"]
