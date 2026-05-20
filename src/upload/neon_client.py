from __future__ import annotations

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

_DATABASE_URL = os.environ["DATABASE_URL"]
_FIREBASE_UID = os.environ["FIREBASE_UID"]
_PROJECT_ID = os.environ["PROJECT_ID"]


class NeonClient:
    """Read-only Neon client used for duplicate detection in the preview panel.

    Writes are handled by the Cloudflare Worker (see :class:`~src.upload.worker_client.WorkerClient`).
    """

    def __init__(self) -> None:
        self._conn = psycopg2.connect(_DATABASE_URL)

    def material_ids_in_db(self, material_ids: list[str]) -> set[str]:
        """Return the subset of *material_ids* that already have rows in ``image_assets``."""
        if not material_ids:
            return set()
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT alt_text FROM image_assets WHERE owner_uid = %s AND project_id = %s"
                " AND alt_text = ANY(%s)",
                (_FIREBASE_UID, _PROJECT_ID, material_ids),
            )
            return {row[0] for row in cur.fetchall()}

    def close(self) -> None:
        self._conn.close()
