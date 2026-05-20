from __future__ import annotations

import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

_API_BASE_URL = os.environ["API_BASE_URL"].rstrip("/")
_FIREBASE_API_KEY = os.environ["FIREBASE_API_KEY"]
_FIREBASE_REFRESH_TOKEN = os.environ["FIREBASE_REFRESH_TOKEN"]
_FIREBASE_UID = os.environ["FIREBASE_UID"]
_PROJECT_ID = os.environ["PROJECT_ID"]

_TOKEN_EXCHANGE_URL = "https://securetoken.googleapis.com/v1/token"

# Cached ID token and its expiry (unix timestamp)
_id_token: str = ""
_token_expires_at: float = 0.0


def _get_id_token() -> str:
    """Return a valid Firebase ID token, refreshing if needed."""
    global _id_token, _token_expires_at
    if _id_token and time.time() < _token_expires_at - 60:
        return _id_token
    resp = requests.post(
        f"{_TOKEN_EXCHANGE_URL}?key={_FIREBASE_API_KEY}",
        data={
            "grant_type": "refresh_token",
            "refresh_token": _FIREBASE_REFRESH_TOKEN,
        },
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()
    _id_token = payload["id_token"]
    _token_expires_at = time.time() + int(payload.get("expires_in", 3600))
    return _id_token


class WorkerClient:
    """Uploads a swatch image via the Cloudflare Worker API.

    The Worker handles both the R2 upload and the ``image_assets`` DB insert/upsert,
    so no direct R2 credentials or DB write access is needed here.

    Expected endpoint::

        POST /api/v1/materials/{materialId}/swatch
        Authorization: Bearer <firebase_id_token>
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
            headers={"Authorization": f"Bearer {_get_id_token()}"},
            data={
                "firebase_uid": _FIREBASE_UID,
                "project_id": _PROJECT_ID,
            },
            files={"file": (f"{material_id}.webp", webp_bytes, "image/webp")},
            timeout=30,
        )
        response.raise_for_status()
        return not response.json().get("inserted", True)
