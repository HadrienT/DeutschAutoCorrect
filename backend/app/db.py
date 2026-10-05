"""Tiny SQLite repository (no ORM)."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .models import Analysis, Rubric, default_rubric

SCHEMA = """
CREATE TABLE IF NOT EXISTS rubrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, json TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS recordings (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, student_name TEXT NOT NULL DEFAULT '',
  filename TEXT NOT NULL, audio_path TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'queued',
  stage TEXT NOT NULL DEFAULT 'queued', progress REAL NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
  duration REAL NOT NULL DEFAULT 0, created_at REAL NOT NULL, rubric_id INTEGER,
  analysis_json TEXT, manual_json TEXT NOT NULL DEFAULT '{}'
);
"""


class Database:
    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()
        self._ensure_default_rubric()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def close(self) -> None:
        self._conn.close()

    # ---- rubrics ----
    def _ensure_default_rubric(self) -> None:
        with self._tx() as c:
            if c.execute("SELECT COUNT(*) FROM rubrics").fetchone()[0] == 0:
                r = default_rubric()
                c.execute("INSERT INTO rubrics(name,json,created_at) VALUES(?,?,?)",
                          (r.name, r.model_dump_json(), time.time()))

    @staticmethod
    def _rubric_from_row(row: sqlite3.Row) -> Rubric:
        r = Rubric.model_validate_json(row["json"])
        r.id = row["id"]
        return r

    def list_rubrics(self) -> list[Rubric]:
        with self._tx() as c:
            return [self._rubric_from_row(r) for r in c.execute("SELECT * FROM rubrics ORDER BY id")]

    def get_rubric(self, rid: int) -> Rubric | None:
        with self._tx() as c:
            row = c.execute("SELECT * FROM rubrics WHERE id=?", (rid,)).fetchone()
            return self._rubric_from_row(row) if row else None

    def default_rubric_id(self) -> int:
        with self._tx() as c:
            return c.execute("SELECT MIN(id) FROM rubrics").fetchone()[0]

    def save_rubric(self, rubric: Rubric, rid: int | None = None) -> Rubric:
        data = rubric.model_copy(update={"id": None}).model_dump_json()
        with self._tx() as c:
            if rid is None:
                cur = c.execute("INSERT INTO rubrics(name,json,created_at) VALUES(?,?,?)",
                                (rubric.name, data, time.time()))
                rid = cur.lastrowid
            else:
                c.execute("UPDATE rubrics SET name=?, json=? WHERE id=?", (rubric.name, data, rid))
        out = self.get_rubric(rid)  # type: ignore[arg-type]
        assert out is not None
        return out

    def delete_rubric(self, rid: int) -> bool:
        with self._tx() as c:
            if c.execute("SELECT COUNT(*) FROM rubrics").fetchone()[0] <= 1:
                return False
            c.execute("DELETE FROM rubrics WHERE id=?", (rid,))
            c.execute("UPDATE recordings SET rubric_id=NULL WHERE rubric_id=?", (rid,))
            return True

    # ---- recordings ----
    def create_recording(self, rec_id: str, title: str, student_name: str, filename: str,
                         rubric_id: int | None) -> None:
        with self._tx() as c:
            c.execute(
                "INSERT INTO recordings(id,title,student_name,filename,created_at,rubric_id) "
                "VALUES(?,?,?,?,?,?)",
                (rec_id, title, student_name, filename, time.time(), rubric_id),
            )

    def update_recording(self, rec_id: str, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        with self._tx() as c:
            c.execute(f"UPDATE recordings SET {cols} WHERE id=?", (*fields.values(), rec_id))

    def get_recording(self, rec_id: str) -> dict[str, Any] | None:
        with self._tx() as c:
            row = c.execute("SELECT * FROM recordings WHERE id=?", (rec_id,)).fetchone()
            return dict(row) if row else None

    def list_recordings(self) -> list[dict[str, Any]]:
        with self._tx() as c:
            return [dict(r) for r in c.execute(
                "SELECT id,title,student_name,filename,status,stage,progress,error,duration,"
                "created_at,rubric_id,analysis_json IS NOT NULL AS has_analysis "
                "FROM recordings ORDER BY created_at DESC")]

    def delete_recording(self, rec_id: str) -> bool:
        with self._tx() as c:
            return c.execute("DELETE FROM recordings WHERE id=?", (rec_id,)).rowcount > 0

    def get_analysis(self, rec_id: str) -> Analysis | None:
        rec = self.get_recording(rec_id)
        if not rec or not rec["analysis_json"]:
            return None
        return Analysis.model_validate_json(rec["analysis_json"])

    def save_analysis(self, rec_id: str, analysis: Analysis) -> None:
        self.update_recording(rec_id, analysis_json=analysis.model_dump_json())

    def get_manual(self, rec_id: str) -> dict[str, float]:
        rec = self.get_recording(rec_id)
        return json.loads(rec["manual_json"]) if rec else {}

    def set_manual(self, rec_id: str, manual: dict[str, float]) -> None:
        self.update_recording(rec_id, manual_json=json.dumps(manual))
