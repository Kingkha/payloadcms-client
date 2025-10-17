from __future__ import annotations

from typing import Any, Dict, List

import pytest

from payloadcms_client.articles import ensure_categories


class DummyClient:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

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

    assert len(client.calls) == 2
    first_call, second_call = client.calls

    assert first_call["payload"]["title"] == "Travel"
    assert first_call["payload"]["status"] == "published"
    assert first_call["value"] == "travel"
    assert first_call["depth"] == 0

    assert second_call["payload"]["title"] == "Guide"
    assert second_call["value"] == "guide"

    # Documents returned from the helper include IDs from the simulated response.
    assert [doc["id"] for doc in documents] == [1, 2]


@pytest.mark.parametrize("bad_categories", [[""], ["  "], [123]])
def test_ensure_categories_rejects_invalid_values(bad_categories: List[Any]) -> None:
    client = DummyClient()

    with pytest.raises((TypeError, ValueError)):
        ensure_categories(client, bad_categories)
