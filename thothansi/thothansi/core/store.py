"""
Run persistence.

Runs are stored as individual JSON files under the data directory. This keeps
the tool dependency-free (no database to stand up) while still letting the web
dashboard and CLI list and reload past engagements.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Run


class RunStore:
    def __init__(self, data_dir: str | Path):
        self.dir = Path(data_dir) / "runs"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        safe = "".join(c for c in run_id if c.isalnum() or c in "-_")
        return self.dir / f"{safe}.json"

    def save(self, run: Run) -> Path:
        path = self._path(run.id)
        path.write_text(run.model_dump_json(indent=2))
        return path

    def load(self, run_id: str) -> Run:
        path = self._path(run_id)
        if not path.exists():
            raise FileNotFoundError(f"No such run: {run_id}")
        return Run.model_validate_json(path.read_text())

    def list_runs(self) -> list[dict]:
        out = []
        for p in sorted(self.dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(p.read_text())
                out.append(
                    {
                        "id": data.get("id"),
                        "targets": data.get("targets", []),
                        "started_at": data.get("started_at"),
                        "findings": len(
                            [f for r in data.get("results", []) for f in r.get("findings", [])]
                        ),
                    }
                )
            except Exception:
                continue
        return out
