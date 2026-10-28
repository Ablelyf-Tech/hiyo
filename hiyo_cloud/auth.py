import base64
import hashlib
import json
import os
import time
from fastapi import HTTPException, Request
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .models import Device, Nonce


from engineering_os.protocol import canonical


def firebase_identity(token, project):
    if not project:
        raise HTTPException(503, "Firebase project not configured")
    try:
        from google.oauth2 import id_token
        from google.auth.transport.requests import Request as GoogleRequest
        from cachecontrol import CacheControl
        import requests

        # Certificate cache honors the provider's cache-control headers, reducing auth egress.
        if not hasattr(firebase_identity, "transport"):
            firebase_identity.transport = GoogleRequest(
                session=CacheControl(requests.Session())
            )
        claims = id_token.verify_firebase_token(
            token, firebase_identity.transport, audience=project
        )
        if (
            claims.get("iss") != "https://securetoken.google.com/" + project
            or not claims.get("email_verified")
            or not claims.get("sub")
            or claims.get("firebase", {}).get("sign_in_provider") == "anonymous"
        ):
            raise ValueError("A nonanonymous identity is required")
        return claims["sub"]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(401, "Invalid or expired Firebase identity") from exc


async def verify_device(request: Request, db_factory):
    headers = request.headers
    device_id = headers.get("x-hiyo-device", "")
    timestamp = headers.get("x-hiyo-timestamp", "")
    nonce = headers.get("x-hiyo-nonce", "")
    if not (1 <= len(nonce) <= 80):
        raise HTTPException(401, "Invalid device nonce")
    try:
        if abs(time.time() - int(timestamp)) > 300:
            raise ValueError("stale")
        body = await request.body()
        with db_factory.begin() as db:
            device = db.scalar(
                select(Device).where(Device.id == device_id, Device.active.is_(True))
            )
            if not device:
                raise ValueError("device")
            key = Ed25519PublicKey.from_public_bytes(
                base64.b64decode(device.public_key, validate=True)
            )
            key.verify(
                base64.b64decode(headers.get("x-hiyo-signature", ""), validate=True),
                canonical(request.method, request.url.path, timestamp, nonce, body),
            )
            db.add(Nonce(device_id=device_id, value=nonce, expires=time.time() + 600))
            device.last_seen = time.time()
            identity = (device.account_id, device.id)
        return identity
    except (ValueError, IntegrityError) as exc:
        raise HTTPException(
            401, "Invalid, expired, revoked, or replayed device request"
        ) from exc
    except Exception as exc:
        raise HTTPException(401, "Device signature verification failed") from exc
