from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

load_dotenv()

_API_BASE_URL = os.environ["API_BASE_URL"].rstrip("/")
_API_SECRET = os.environ["API_SECRET"]
_FIREBASE_UID = os.environ["FIREBASE_UID"]
_PROJECT_ID = os.environ["PROJECT_ID"]


class WorkerClient:
    """Uploads a swatch image via the Cloudflare Worker API.

    The Worker handles both the R2 upload and the ``image_assets`` DB insert/upsert,
    so no direct R2 credentials or DB write access is needed here.

    Expected endpoint::

        POST /api/v1/materials/{materialId}/swatch
        Authorization: Bearer <API_SECRET>
        Content-Type: multipart/form-data

        file: <webp bytes>
        firebase_uid: <uid>
        project_id: <project_id>

    The Worker returns ``{"inserted": true}`` or ``{"inserted": false}`` to
    indicate whether the row was new or updated.
    """

    def upload(self, webp_bytes: bytes, material_id: str) -> bool:
        """Upload *webp_bytes* for *material_id*. Returns ``True`` if the row was updated."""
        url = f"{_API_BASE_URL}/api/v1/materials/{material_id}/swatch"
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {_API_SECRET}"},
            data={
                "firebase_uid": _FIREBASE_UID,
                "project_id": _PROJECT_ID,
            },
            files={"file": (f"{material_id}.webp", webp_bytes, "image/webp")},
            timeout=30,
        )
        response.raise_for_status()
        return not response.json().get("inserted", True)
