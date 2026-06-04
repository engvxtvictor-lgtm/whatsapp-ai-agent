import asyncio
import sys

# Corrige problema de event loop no Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

print("Testando PUT /api/admins/1")
response = client.put("/api/admins/1", json={"name": "Test", "email": "test@test.com", "role": "admin"})
print("Status:", response.status_code)
print("Response:", response.json())

print("\nTestando DELETE /api/admins/1")
response = client.delete("/api/admins/1")
print("Status:", response.status_code)
print("Response:", response.json())
