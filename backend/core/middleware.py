# Middleware for encrypting/decrypting JSON payloads

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import Response
import json
from backend.core.security import encrypt_payload, decrypt_payload

class EncryptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Decrypt incoming request if header indicates encryption
        if request.headers.get("X-Encrypted", "false").lower() == "true":
            raw_body = await request.body()
            try:
                token = raw_body.decode()
                decrypted = decrypt_payload(token)
                # Replace request body with decrypted JSON bytes
                request._receive = lambda: {"type": "http.request", "body": json.dumps(decrypted).encode()}
            except Exception as exc:
                return JSONResponse({"detail": "Invalid encrypted payload"}, status_code=400)
        # Process request
        response: Response = await call_next(request)
        # Encrypt outgoing JSON response if client expects it
        if response.headers.get("content-type", "").startswith("application/json"):
            try:
                # Need to read the body – FastAPI responses may be streaming
                if hasattr(response, "body"):
                    payload = json.loads(response.body)
                else:
                    # fallback: read from render (works for JSONResponse)
                    payload = json.loads(response.render())
                encrypted = encrypt_payload(payload)
                return JSONResponse(content=encrypted, headers={"X-Encrypted": "true"})
            except Exception:
                # If encryption fails, fall back to original response
                return response
        return response
