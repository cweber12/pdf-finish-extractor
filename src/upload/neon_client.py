from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import psycopg2
from dotenv import load_dotenv

load_dotenv()

_DATABASE_URL = os.environ["DATABASE_URL"]
_FIREBASE_UID = os.environ["FIREBASE_UID"]
_PROJECT_ID = os.environ["PROJECT_ID"]


class NeonClient:
    """Upserts swatch image metadata into the ``image_assets`` table in Neon.

    Uses ``INSERT … ON CONFLICT (r2_key) DO UPDATE`` so re-importing a catalog
    updates existing rows rather than failing on the unique constraint.
    """

    def __init__(self) -> None:
        self._conn = psycopg2.connect(_DATABASE_URL)

    def upsert(self, material_id: str, r2_key: str, byte_size: int) -> bool:
        """Insert or update a row. Returns ``True`` if the row was updated (duplicate)."""
        image_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        filename = r2_key.rsplit("/", 1)[-1]

        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO image_assets (
                    id, owner_uid, project_id, room_id, item_id,
                    r2_key, filename, content_type, byte_size,
                    alt_text, is_primary, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, NULL, NULL,
                    %s, %s, 'image/webp', %s,
                    %s, true, %s, %s
                )
                ON CONFLICT (r2_key) DO UPDATE SET
                    filename     = EXCLUDED.filename,
                    byte_size    = EXCLUDED.byte_size,
                    updated_at   = EXCLUDED.updated_at
                RETURNING (xmax <> 0) AS was_updated;
                """,
                (
                    image_id,
                    _FIREBASE_UID,
                    _PROJECT_ID,
                    r2_key,
                    filename,
                    byte_size,
                    material_id,  # alt_text stores the human-readable material ID
                    now,
                    now,
                ),
            )
            row = cur.fetchone()
        self._conn.commit()
        return bool(row and row[0])

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
