"""Thin REST client for interacting with Payload CMS."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Optional, Tuple
from urllib.parse import urljoin

import requests


def _load_credentials_from_env(
    env_path: str | Path | None,
    email_var: str,
    password_var: str,
) -> Tuple[str, str]:
    """Load email and password credentials from a ``.env`` file."""

    path = Path(env_path or ".env")
    if not path.exists():
        raise ValueError(f"Credential file not found at {path}.")

    values: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value

    email = values.get(email_var)
    password = values.get(password_var)

    if not isinstance(email, str) or not email:
        raise ValueError(
            f"Environment variable '{email_var}' missing from {path} or empty."
        )
    if not isinstance(password, str) or not password:
        raise ValueError(
            f"Environment variable '{password_var}' missing from {path} or empty."
        )

    return email, password


class PayloadRESTClient:
    """Minimal client for Payload CMS REST endpoints."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        token_type: str = "Bearer",
        timeout: int | float | None = 30,
        session: requests.Session | None = None,
        api_prefix: str = "api",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.token_type = token_type
        self.timeout = timeout
        self.session = session or requests.Session()
        self.api_prefix = api_prefix.strip("/")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_url(self, path: str) -> str:
        prefix = f"{self.base_url}/{self.api_prefix}/"
        return urljoin(prefix, path.lstrip("/"))

    def _build_headers(
        self,
        extra: Optional[Mapping[str, str]] = None,
        *,
        content_type: str | None = "application/json",
    ) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "Accept": "application/json",
        }
        if content_type:
            headers["Content-Type"] = content_type
        if self.token:
            headers["Authorization"] = f"{self.token_type} {self.token}"
        if extra:
            headers.update(extra)
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[MutableMapping[str, Any]] = None,
        json: Optional[Mapping[str, Any]] = None,
        data: Optional[Mapping[str, Any]] = None,
        files: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Dict[str, Any]:
        content_type = None if files is not None else "application/json"
        response = self.session.request(
            method,
            self._build_url(path),
            headers=self._build_headers(headers, content_type=content_type),
            params=params,
            json=json,
            data=data,
            files=files,
            timeout=self.timeout,
        )
        response.raise_for_status()
        if response.status_code == 204:
            return {}
        return response.json()

    # ------------------------------------------------------------------
    # Public REST helpers
    # ------------------------------------------------------------------
    def list_documents(
        self,
        collection: str,
        *,
        params: Optional[MutableMapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return the raw list response for a collection."""

        return self._request("GET", f"{collection}", params=params)

    def find_first_by_field(
        self,
        collection: str,
        field: str,
        value: Any,
        *,
        depth: int | None = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the first document whose ``field`` equals ``value``."""

        params: Dict[str, Any] = {f"where[{field}][equals]": value}
        if depth is not None:
            params["depth"] = depth
        result = self.list_documents(collection, params=params)
        docs = result.get("docs") or []
        return docs[0] if docs else None

    def create_document(
        self,
        collection: str,
        payload: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Create a new document in the collection."""

        return self._request("POST", f"{collection}", json=payload)

    def login(
        self,
        user_collection: str,
        *,
        email: str | None = None,
        password: str | None = None,
        env_path: str | Path | None = None,
        email_var: str = "PAYLOADCMS_EMAIL",
        password_var: str = "PAYLOADCMS_PASSWORD",
    ) -> Dict[str, Any]:
        """Authenticate against a Payload user collection and store the token.

        Parameters
        ----------
        user_collection:
            The name of the auth-enabled collection, e.g. ``"users"``.
        email:
            The user's email address.
        password:
            The user's password.
        env_path:
            Optional path to a ``.env`` file containing credentials. Defaults
            to ``".env"`` in the current working directory.
        email_var:
            The environment variable name that stores the email address.
        password_var:
            The environment variable name that stores the password.

        Returns
        -------
        Dict[str, Any]
            The JSON response returned by Payload CMS. The client token is
            updated in-place using the ``token`` value from the response.
        """

        resolved_email = email
        resolved_password = password

        if resolved_email is None or resolved_password is None:
            env_email, env_password = _load_credentials_from_env(
                env_path, email_var, password_var
            )
            resolved_email = resolved_email or env_email
            resolved_password = resolved_password or env_password

        if resolved_email is None or resolved_password is None:
            raise ValueError(
                "Email and password must be provided either directly or via a .env file."
            )

        response = self._request(
            "POST",
            f"{user_collection}/login",
            json={"email": resolved_email, "password": resolved_password},
        )

        token = response.get("token")
        if not isinstance(token, str) or not token:
            raise ValueError("Login response did not include a token string.")

        self.token = token
        return response

    def update_document(
        self,
        collection: str,
        doc_id: Any,
        payload: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Update an existing document by ``id``."""

        return self._request("PATCH", f"{collection}/{doc_id}", json=payload)

    def upsert_by_field(
        self,
        collection: str,
        field: str,
        value: Any,
        payload: Mapping[str, Any],
        *,
        depth: int | None = None,
    ) -> Dict[str, Any]:
        """Create or update a document using ``field`` equality as the key."""

        existing = self.find_first_by_field(
            collection=collection,
            field=field,
            value=value,
            depth=depth,
        )
        if existing:
            doc_id = existing.get("id")
            if doc_id is None:
                raise ValueError(
                    "Existing document is missing an 'id' field required for updates."
                )
            return self.update_document(collection, doc_id, payload)
        return self.create_document(collection, payload)

    def upload_media(
        self,
        collection: str,
        file_path: str | Path,
        *,
        file_field: str = "file",
        data: Optional[Mapping[str, Any]] = None,
        depth: int | None = None,
    ) -> Dict[str, Any]:
        """Upload a file to a media collection."""

        path = Path(file_path)
        params: Dict[str, Any] = {}
        if depth is not None:
            params["depth"] = depth

        with path.open("rb") as fh:
            files = {file_field: (path.name, fh)}
            return self._request(
                "POST",
                f"{collection}",
                params=params or None,
                data=data,
                files=files,
            )
