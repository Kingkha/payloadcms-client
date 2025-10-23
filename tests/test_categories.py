from __future__ import annotations

from typing import Any, Dict, List

import pytest

from payloadcms_client.articles import ensure_categories


class DummyClient:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.existing_docs: Dict[str, Dict[str, Any]] = {}

    def find_many_by_field(
        self,
        collection: str,
        field: str,
        values: List[Any],
        *,
        depth: int | None = None,
    ) -> Dict[Any, Dict[str, Any]]:
        """Simulate batch lookup of existing documents."""
        call = {
            "method": "find_many_by_field",
            "collection": collection,
            "field": field,
            "values": values,
            "depth": depth,
        }
        self.calls.append(call)
        # Return any matching documents from existing_docs
        return {k: v for k, v in self.existing_docs.items() if k in values}

    def create_document(
        self,
        collection: str,
        payload: Dict[str, Any],
        *,
        depth: int | None = None,
    ) -> Dict[str, Any]:
        """Simulate creating a new document."""
        call = {
            "method": "create_document",
            "collection": collection,
            "payload": payload,
            "depth": depth,
        }
        self.calls.append(call)
        doc_id = len(self.calls)
        return {"id": doc_id, **payload}

    def update_document(
        self,
        collection: str,
        doc_id: Any,
        payload: Dict[str, Any],
        *,
        depth: int | None = None,
    ) -> Dict[str, Any]:
        """Simulate updating an existing document."""
        call = {
            "method": "update_document",
            "collection": collection,
            "doc_id": doc_id,
            "payload": payload,
            "depth": depth,
        }
        self.calls.append(call)
        return {"id": doc_id, **payload}

    def upsert_by_field(
        self,
        *,
        collection: str,
        field: str,
        value: str,
        payload: Dict[str, Any],
        depth: int | None = None,
    ) -> Dict[str, Any]:
        call = {
            "method": "upsert_by_field",
            "collection": collection,
            "field": field,
            "value": value,
            "payload": payload,
            "depth": depth,
        }
        self.calls.append(call)
        # Simulate Payload returning a document that includes an ID.
        return {"id": len(self.calls), **payload}


def test_ensure_categories_creates_unique_slugs() -> None:
    client = DummyClient()

    documents = ensure_categories(
        client,
        ["Travel", " Guide ", "Travel"],
        collection="categories",
        defaults={"status": "published"},
        depth=0,
    )

    # With batch optimization: 1 find_many_by_field + 2 create_document calls = 3 total
    assert len(client.calls) == 3
    find_call, create_travel, create_guide = client.calls

    # First call should be batch lookup
    assert find_call["method"] == "find_many_by_field"
    assert find_call["values"] == ["travel", "guide"]
    assert find_call["depth"] == 0

    # Second call creates Travel category
    assert create_travel["method"] == "create_document"
    assert create_travel["payload"]["title"] == "Travel"
    assert create_travel["payload"]["status"] == "published"
    assert create_travel["payload"]["slug"] == "travel"
    assert create_travel["depth"] == 0

    # Third call creates Guide category
    assert create_guide["method"] == "create_document"
    assert create_guide["payload"]["title"] == "Guide"
    assert create_guide["payload"]["slug"] == "guide"

    # Documents returned from the helper include IDs from the simulated response.
    assert [doc["id"] for doc in documents] == [2, 3]


def test_ensure_categories_updates_existing() -> None:
    """Test that existing categories are updated, not recreated."""
    client = DummyClient()
    
    # Simulate existing "Travel" category
    client.existing_docs = {
        "travel": {"id": 999, "slug": "travel", "title": "Travel", "status": "draft"}
    }

    documents = ensure_categories(
        client,
        ["Travel", "Guide"],
        collection="categories",
        defaults={"status": "published"},
        depth=0,
    )

    # Should be: 1 find_many_by_field + 1 update (Travel) + 1 create (Guide) = 3 calls
    assert len(client.calls) == 3
    find_call, update_call, create_call = client.calls

    # First call: batch lookup
    assert find_call["method"] == "find_many_by_field"
    assert set(find_call["values"]) == {"travel", "guide"}

    # Second call: update existing Travel
    assert update_call["method"] == "update_document"
    assert update_call["doc_id"] == 999
    assert update_call["payload"]["title"] == "Travel"
    assert update_call["payload"]["status"] == "published"  # Defaults applied

    # Third call: create new Guide
    assert create_call["method"] == "create_document"
    assert create_call["payload"]["title"] == "Guide"

    # Returns 2 documents (1 updated, 1 created)
    assert len(documents) == 2


@pytest.mark.parametrize("bad_categories", [[""], ["  "], [123]])
def test_ensure_categories_rejects_invalid_values(bad_categories: List[Any]) -> None:
    client = DummyClient()

    with pytest.raises((TypeError, ValueError)):
        ensure_categories(client, bad_categories)
