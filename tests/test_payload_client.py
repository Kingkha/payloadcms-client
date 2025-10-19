from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from payloadcms_client.payload_client import PayloadRESTClient


class DummyResponse:
    def __init__(self, *, json_data: Dict[str, Any], status_code: int = 200) -> None:
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if 400 <= self.status_code:
            raise AssertionError("DummyResponse.raise_for_status called with error status")

    def json(self) -> Dict[str, Any]:
        return self._json_data


class RecordingSession:
    def __init__(self, *, response: Dict[str, Any]) -> None:
        self.response = response
        self.calls: list[Dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> DummyResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers or {},
                "params": params,
                "json": json,
                "data": data,
                "files": files,
                "timeout": timeout,
            }
        )
        return DummyResponse(json_data=self.response)


def test_login_requests_token_and_updates_client() -> None:
    session = RecordingSession(response={"message": "Auth Passed", "token": "abc123"})
    client = PayloadRESTClient(
        base_url="https://cms.example.com",
        session=session,
        timeout=5,
    )

    response = client.login("users", email="dev@payloadcms.com", password="password")

    assert response["token"] == "abc123"
    assert client.token == "abc123"

    assert len(session.calls) == 1
    call = session.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://cms.example.com/api/users/login"
    assert call["json"] == {"email": "dev@payloadcms.com", "password": "password"}
    assert call["headers"]["Accept"] == "application/json"
    assert call["headers"]["Content-Type"] == "application/json"
    # No token header should be sent before authentication.
    assert "Authorization" not in call["headers"]


def test_login_without_token_raises_value_error() -> None:
    session = RecordingSession(response={"message": "no token"})
    client = PayloadRESTClient(base_url="https://cms.example.com", session=session)

    with pytest.raises(ValueError):
        client.login("users", email="dev@payloadcms.com", password="wrong")

    # Token should remain unset when login fails.
    assert client.token is None


def test_login_reads_credentials_from_env(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "PAYLOADCMS_EMAIL=env-user@example.com\nPAYLOADCMS_PASSWORD=env-secret\n",
        encoding="utf-8",
    )

    session = RecordingSession(response={"message": "Auth Passed", "token": "envtoken"})
    client = PayloadRESTClient(
        base_url="https://cms.example.com",
        session=session,
    )

    response = client.login("users", env_path=env_file)

    assert response["token"] == "envtoken"
    assert client.token == "envtoken"

    call = session.calls[0]
    assert call["json"] == {
        "email": "env-user@example.com",
        "password": "env-secret",
    }


def test_login_env_missing_credentials_raises_value_error(tmp_path: Path) -> None:
    env_file = tmp_path / "creds.env"
    env_file.write_text("PAYLOADCMS_EMAIL=only-email@example.com\n", encoding="utf-8")

    session = RecordingSession(response={"message": "Auth Passed", "token": "envtoken"})
    client = PayloadRESTClient(base_url="https://cms.example.com", session=session)

    with pytest.raises(ValueError):
        client.login("users", env_path=env_file, password_var="PAYLOADCMS_PASSWORD")

    assert not session.calls
