from __future__ import annotations

import os
import uuid

import boto3
from dotenv import load_dotenv

load_dotenv()

_ENDPOINT = f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
_BUCKET = os.environ["R2_BUCKET_NAME"]
_FIREBASE_UID = os.environ["FIREBASE_UID"]
_PROJECT_ID = os.environ["PROJECT_ID"]


class R2Client:
    """Uploads swatch images to Cloudflare R2.

    Path format::

        users/{uid}/projects/{projectId}/materials/{materialId}/{imageId}.webp
    """

    def __init__(self) -> None:
        self._s3 = boto3.client(
            "s3",
            endpoint_url=_ENDPOINT,
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
        )

    def upload(self, webp_bytes: bytes, material_id: str) -> str:
        """Upload *webp_bytes* and return the full R2 key."""
        image_id = str(uuid.uuid4())
        r2_key = (
            f"users/{_FIREBASE_UID}/projects/{_PROJECT_ID}"
            f"/materials/{material_id}/{image_id}.webp"
        )
        self._s3.put_object(
            Bucket=_BUCKET,
            Key=r2_key,
            Body=webp_bytes,
            ContentType="image/webp",
        )
        return r2_key
