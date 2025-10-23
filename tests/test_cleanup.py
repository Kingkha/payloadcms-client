"""Tests for cleanup functionality."""

from unittest.mock import MagicMock, patch

import pytest

from payloadcms_client import PayloadRESTClient
from clean_payloadcms import clean_payloadcms, delete_all_documents


class TestDeleteDocument:
    """Test delete_document method of PayloadRESTClient."""
    
    def test_delete_document_success(self):
        """Test successful document deletion."""
        client = PayloadRESTClient(base_url="http://localhost:3000")
        client.token = "test-token"
        
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.status_code = 204  # No content
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(client.session, 'request', return_value=mock_response) as mock_request:
            result = client.delete_document("posts", "123")
        
        # Verify the request was made correctly
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "DELETE"
        assert "posts/123" in call_args[0][1]
        
        # Verify the response
        assert result == {}
    
    def test_delete_document_with_token(self):
        """Test that delete includes authorization header."""
        client = PayloadRESTClient(base_url="http://localhost:3000")
        client.token = "my-auth-token"
        
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.status_code = 204
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(client.session, 'request', return_value=mock_response) as mock_request:
            client.delete_document("media", "456")
        
        # Verify the Authorization header was included
        call_args = mock_request.call_args
        headers = call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer my-auth-token"


class TestDeleteAllDocuments:
    """Test delete_all_documents function."""
    
    def test_delete_all_documents_empty_collection(self):
        """Test deletion from empty collection."""
        client = PayloadRESTClient(base_url="http://localhost:3000")
        
        # Mock empty list response
        mock_list_response = MagicMock()
        mock_list_response.json.return_value = {"docs": []}
        mock_list_response.status_code = 200
        mock_list_response.raise_for_status = MagicMock()
        
        with patch.object(client.session, 'request', return_value=mock_list_response):
            count = delete_all_documents(client, "posts")
        
        assert count == 0
    
    def test_delete_all_documents_single_batch(self):
        """Test deletion with single batch of documents."""
        client = PayloadRESTClient(base_url="http://localhost:3000")
        client.token = "test-token"
        
        # Mock list response with 3 documents
        mock_docs = [
            {"id": "1", "title": "Post 1"},
            {"id": "2", "title": "Post 2"},
            {"id": "3", "title": "Post 3"},
        ]
        
        mock_list_response = MagicMock()
        mock_list_response.json.side_effect = [
            {"docs": mock_docs},  # First call returns docs
            {"docs": []},  # Second call returns empty (after deletion)
        ]
        mock_list_response.status_code = 200
        mock_list_response.raise_for_status = MagicMock()
        
        mock_delete_response = MagicMock()
        mock_delete_response.json.return_value = {}
        mock_delete_response.status_code = 204
        mock_delete_response.raise_for_status = MagicMock()
        
        with patch.object(client.session, 'request') as mock_request:
            # Return list response for GET, delete response for DELETE
            def request_side_effect(method, *args, **kwargs):
                if method == "GET":
                    return mock_list_response
                elif method == "DELETE":
                    return mock_delete_response
                return mock_response
            
            mock_request.side_effect = request_side_effect
            count = delete_all_documents(client, "posts", verbose=False)
        
        assert count == 3


class TestCleanPayloadCMS:
    """Test clean_payloadcms function."""
    
    def test_clean_all_collections(self):
        """Test cleaning all collections."""
        client = PayloadRESTClient(base_url="http://localhost:3000")
        
        with patch('clean_payloadcms.delete_all_documents') as mock_delete:
            mock_delete.side_effect = [5, 10, 3]  # posts, media, categories
            
            results = clean_payloadcms(
                client,
                clean_posts=True,
                clean_media=True,
                clean_categories=True,
            )
        
        assert results == {"posts": 5, "media": 10, "categories": 3}
        assert mock_delete.call_count == 3
    
    def test_clean_only_posts(self):
        """Test cleaning only posts."""
        client = PayloadRESTClient(base_url="http://localhost:3000")
        
        with patch('clean_payloadcms.delete_all_documents') as mock_delete:
            mock_delete.return_value = 5
            
            results = clean_payloadcms(
                client,
                clean_posts=True,
                clean_media=False,
                clean_categories=False,
            )
        
        assert results == {"posts": 5}
        assert mock_delete.call_count == 1
    
    def test_clean_with_custom_collections(self):
        """Test cleaning with custom collection names."""
        client = PayloadRESTClient(base_url="http://localhost:3000")
        
        with patch('clean_payloadcms.delete_all_documents') as mock_delete:
            mock_delete.side_effect = [2, 4, 1]
            
            results = clean_payloadcms(
                client,
                posts_collection="articles",
                media_collection="files",
                categories_collection="tags",
                clean_posts=True,
                clean_media=True,
                clean_categories=True,
            )
        
        assert results == {"posts": 2, "media": 4, "categories": 1}
        
        # Verify the correct collection names were used
        calls = mock_delete.call_args_list
        assert calls[0][0][1] == "articles"
        assert calls[1][0][1] == "files"
        assert calls[2][0][1] == "tags"

