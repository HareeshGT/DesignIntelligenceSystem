import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any


class ProjectMemory:
    def __init__(self, path: str | None = None):
        self.path = path or os.getenv("DIS_DATABASE_PATH", "./design_intelligence.db")
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _initialize(self):
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS project_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_project_events ON project_events(project_id, id)")

    def append(self, project_id: str, event_type: str, payload: dict[str, Any]) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO project_events(project_id,event_type,payload,created_at) VALUES(?,?,?,?)",
                (project_id, event_type, json.dumps(payload), datetime.now(timezone.utc).isoformat()),
            )

    def get_events(self, project_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT event_type,payload,created_at FROM project_events WHERE project_id=? ORDER BY id",
                (project_id,),
            ).fetchall()
        return [{"event_type": r[0], "payload": json.loads(r[1]), "created_at": r[2]} for r in rows]
