import httpx
import os
from typing import Dict, Any, Tuple, Optional, List

API_BASE_URL = os.getenv("API_BASE_URL", "http://backend:8000/api")

async def login_for_token(username: str, password: str) -> Optional[Dict[str, Any]]:
    # ... (code unchanged)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_BASE_URL}/auth/token",
                data={"username": username, "password": password}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError:
            return None

async def get_current_user(token: str) -> Optional[Dict[str, Any]]:
    # ... (code unchanged)
    headers = {"Authorization": token}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/users/me", headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError:
            return None

async def register_user(username: str, email: str, password: str) -> Tuple[bool, str]:
    # ... (code unchanged)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/auth/register",
            json={"username": username, "email": email, "password": password}
        )
        if response.status_code == 200:
            return True, "Success"
        else:
            detail = response.json().get("detail", "Registration failed")
            return False, detail

async def get_connected_accounts(token: str) -> List[Dict[str, str]]:
    # ... (code unchanged)
    headers = {"Authorization": token}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/linkedin/accounts", headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError:
            return []

async def connect_linkedin_account(token: str, code: str) -> Tuple[bool, str]:
    # ... (code unchanged)
    headers = {"Authorization": token}
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/linkedin/connect",
            json={"code": code},
            headers=headers
        )
        if response.status_code == 200:
            return True, "Successfully connected LinkedIn account."
        else:
            detail = response.json().get("detail", "Failed to connect LinkedIn account.")
            return False, detail

async def disconnect_social_account(token: str, provider: str) -> Tuple[bool, str]:
    headers = {"Authorization": token}
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/linkedin/disconnect",
            json={"provider": provider},
            headers=headers
        )
        if response.status_code == 200:
            detail = response.json().get("detail", f"Successfully disconnected {provider}.")
            return True, detail
        else:
            detail = response.json().get("detail", "Failed to disconnect account.")
            return False, detail