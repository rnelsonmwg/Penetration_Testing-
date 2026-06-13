from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class JsonStore:
    """Small local JSON document store for the MVP.

    The store is intentionally simple and transparent so security teams can
    inspect everything written by the tool. Later versions can replace this
    with SQLite/PostgreSQL/graph storage while preserving the repository API.
    """

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self.base_dir = Path(base_dir or os.getenv("KHEPRI_STORAGE_DIR", ".khepri_data"))
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, collection: str, document_id: str) -> Path:
        safe_collection = collection.replace("/", "_")
        directory = self.base_dir / safe_collection
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{document_id}.json"

    def save(self, collection: str, document_id: str, data: dict[str, Any]) -> None:
        path = self._path(collection, document_id)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def load(self, collection: str, document_id: str) -> dict[str, Any]:
        path = self._path(collection, document_id)
        if not path.exists():
            raise KeyError(f"No {collection} document found for id={document_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list(self, collection: str) -> list[dict[str, Any]]:
        directory = self.base_dir / collection.replace("/", "_")
        if not directory.exists():
            return []
        return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))]

    def append_to_engagement(self, engagement_id: str, key: str, value: dict[str, Any]) -> dict[str, Any]:
        engagement = self.load("engagements", engagement_id)
        engagement.setdefault(key, [])
        engagement[key].append(value)
        self.save("engagements", engagement_id, engagement)
        return engagement

    def update_engagement(self, engagement_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        engagement = self.load("engagements", engagement_id)
        engagement.update(patch)
        self.save("engagements", engagement_id, engagement)
        return engagement
