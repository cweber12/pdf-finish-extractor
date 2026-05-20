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
    """Uploads a swatch image for a material.

    Two-step workflow per docs/MATERIAL_SWATCH_UPLOAD_GUIDE.md:

    1. Resolve the material's UUID via
       ``GET /api/v1/projects/{projectId}/materials`` (search by composite ID).
       If not found, create it via
       ``POST /api/v1/projects/{projectId}/materials``.

    2. Upload the WebP bytes via
       ``POST /api/v1/images?entity_type=material&entity_id={uuid}&alt_text=Swatch``

    ``upload()`` returns ``True`` when the material already existed (swatch
    updated), ``False`` when a new material record was created.
    """

    def _resolve_material_uuid(self, material_id: str, token: str) -> tuple[str, bool]:
        """Return (material_uuid, was_existing).

        Searches the project's material list for *material_id*. Creates the
        record if absent.
        """
        headers = {"Authorization": f"Bearer {token}"}
        base = f"{_API_BASE_URL}/api/v1/projects/{_PROJECT_ID}/materials"

        resp = requests.get(base, headers=headers, timeout=15)
        resp.raise_for_status()
        for mat in resp.json().get("materials", []):
            if mat.get("materialId") == material_id:
                return mat["id"], True

        # Not found — create a minimal record
        resp = requests.post(
            base,
            headers={**headers, "Content-Type": "application/json"},
            json={"name": f"Material {material_id}", "material_id": material_id},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["material"]["id"], False

    def upload(self, webp_bytes: bytes, material_id: str) -> bool:
        """Upload *webp_bytes* for *material_id*. Returns ``True`` if the material already existed."""
        token = _get_id_token()
        material_uuid, was_existing = self._resolve_material_uuid(material_id, token)

        resp = requests.post(
            f"{_API_BASE_URL}/api/v1/images",
            params={"entity_type": "material", "entity_id": material_uuid, "alt_text": "Swatch"},
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (f"{material_id}.webp", webp_bytes, "image/webp")},
            timeout=30,
        )
        resp.raise_for_status()
        return was_existing
