"""Thin REST client for interacting with Payload CMS."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Optional
from urllib.parse import urljoin

import requests

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore


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
    # Authentication
    # ------------------------------------------------------------------
    def login(
        self,
        email: str | None = None,
        password: str | None = None,
        *,
        user_collection: str = "users",
        load_env: bool = True,
    ) -> Dict[str, Any]:
        """
        Authenticate with Payload CMS and store the token.
        
        If email/password are not provided, attempts to load them from environment
        variables PAYLOAD_EMAIL and PAYLOAD_PASSWORD (optionally loading from .env file).
        
        Args:
            email: User email. If None, reads from PAYLOAD_EMAIL env var.
            password: User password. If None, reads from PAYLOAD_PASSWORD env var.
            user_collection: The user collection slug (default: "users").
            load_env: Whether to load .env file if python-dotenv is available (default: True).
        
        Returns:
            The full response dict including 'token', 'user', 'message', and 'exp'.
        
        Raises:
            ValueError: If credentials are not provided and not found in environment.
            requests.HTTPError: If authentication fails.
        """
        # Load .env file if available
        if load_env and load_dotenv is not None:
            load_dotenv()
        
        # Get credentials from parameters or environment
        if email is None:
            email = os.getenv("PAYLOAD_EMAIL")
        if password is None:
            password = os.getenv("PAYLOAD_PASSWORD")
        
        if not email or not password:
            raise ValueError(
                "Email and password must be provided either as arguments or via "
                "PAYLOAD_EMAIL and PAYLOAD_PASSWORD environment variables."
            )
        
        # Make login request
        url = self._build_url(f"{user_collection}/login")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        response = self.session.post(
            url,
            headers=headers,
            json={"email": email, "password": password},
            timeout=self.timeout,
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Store the token for subsequent requests
        if "token" in data:
            self.token = data["token"]
        
        return data

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
        *,
        depth: int | None = None,
    ) -> Dict[str, Any]:
        """Create a new document in the collection."""

        params: Dict[str, Any] = {}
        if depth is not None:
            params["depth"] = depth
        return self._request("POST", f"{collection}", json=payload, params=params or None)

    def update_document(
        self,
        collection: str,
        doc_id: Any,
        payload: Mapping[str, Any],
        *,
        depth: int | None = None,
    ) -> Dict[str, Any]:
        """Update an existing document by ``id``."""

        params: Dict[str, Any] = {}
        if depth is not None:
            params["depth"] = depth
        return self._request("PATCH", f"{collection}/{doc_id}", json=payload, params=params or None)

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
            return self.update_document(collection, doc_id, payload, depth=depth)
        return self.create_document(collection, payload, depth=depth)

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
