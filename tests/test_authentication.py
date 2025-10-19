"""Tests for PayloadCMS authentication functionality."""

import os
from unittest.mock import MagicMock, patch

import pytest

from payloadcms_client import PayloadRESTClient


class TestAuthentication:
    """Test authentication methods of PayloadRESTClient."""

    def test_login_with_credentials(self):
        """Test login with explicit email and password."""
        client = PayloadRESTClient(base_url="http://localhost:3000")
        
        # Mock the session.post method
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": "Auth Passed",
            "user": {
                "id": "644b8453cd20c7857da5a9b0",
                "email": "dev@payloadcms.com",
                "_verified": True,
                "createdAt": "2023-04-28T08:31:15.788Z",
                "updatedAt": "2023-04-28T11:11:03.716Z"
            },
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            "exp": 1682689147
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(client.session, 'post', return_value=mock_response) as mock_post:
            response = client.login(
                email="dev@payloadcms.com",
                password="password",
                load_env=False
            )
        
        # Verify the request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://localhost:3000/api/users/login"
        assert call_args[1]["json"] == {
            "email": "dev@payloadcms.com",
            "password": "password"
        }
        assert call_args[1]["headers"]["Content-Type"] == "application/json"
        
        # Verify the response
        assert response["message"] == "Auth Passed"
        assert response["user"]["email"] == "dev@payloadcms.com"
        assert response["token"] == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        
        # Verify the token was stored
        assert client.token == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"

    def test_login_with_env_vars(self):
        """Test login with credentials from environment variables."""
        client = PayloadRESTClient(base_url="http://localhost:3000")
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": "Auth Passed",
            "user": {"id": "123", "email": "test@example.com"},
            "token": "test-token",
            "exp": 1234567890
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.dict(os.environ, {
            "PAYLOAD_EMAIL": "test@example.com",
            "PAYLOAD_PASSWORD": "test-password"
        }):
            with patch.object(client.session, 'post', return_value=mock_response):
                response = client.login(load_env=False)
        
        assert response["token"] == "test-token"
        assert client.token == "test-token"

    def test_login_missing_credentials(self):
        """Test login fails when credentials are not provided."""
        client = PayloadRESTClient(base_url="http://localhost:3000")
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Email and password must be provided"):
                client.login(load_env=False)

    def test_login_custom_user_collection(self):
        """Test login with custom user collection."""
        client = PayloadRESTClient(base_url="http://localhost:3000")
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": "Auth Passed",
            "user": {"id": "123", "email": "admin@example.com"},
            "token": "admin-token",
            "exp": 1234567890
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(client.session, 'post', return_value=mock_response) as mock_post:
            client.login(
                email="admin@example.com",
                password="admin-pass",
                user_collection="admins",
                load_env=False
            )
        
        # Verify the URL uses the custom collection
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://localhost:3000/api/admins/login"

    def test_login_http_error(self):
        """Test login handles HTTP errors properly."""
        client = PayloadRESTClient(base_url="http://localhost:3000")
        
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")
        
        with patch.object(client.session, 'post', return_value=mock_response):
            with pytest.raises(Exception, match="401 Unauthorized"):
                client.login(
                    email="wrong@example.com",
                    password="wrong-password",
                    load_env=False
                )

    def test_token_used_in_subsequent_requests(self):
        """Test that token from login is used in subsequent API requests."""
        client = PayloadRESTClient(base_url="http://localhost:3000")
        
        # Mock login
        mock_login_response = MagicMock()
        mock_login_response.json.return_value = {
            "message": "Auth Passed",
            "user": {"id": "123", "email": "test@example.com"},
            "token": "my-auth-token",
            "exp": 1234567890
        }
        mock_login_response.raise_for_status = MagicMock()
        
        with patch.object(client.session, 'post', return_value=mock_login_response):
            client.login(email="test@example.com", password="password", load_env=False)
        
        # Now make a regular API request
        mock_get_response = MagicMock()
        mock_get_response.json.return_value = {"docs": []}
        mock_get_response.status_code = 200
        mock_get_response.raise_for_status = MagicMock()
        
        with patch.object(client.session, 'request', return_value=mock_get_response) as mock_request:
            client.list_documents("posts")
        
        # Verify the Authorization header was included
        call_args = mock_request.call_args
        headers = call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer my-auth-token"

