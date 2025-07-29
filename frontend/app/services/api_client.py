import httpx
import os
from typing import Dict, Any, Tuple, Optional, List

API_BASE_URL = os.getenv("API_BASE_URL", "http://backend:8000/api")

async def login_for_token(username: str, password: str) -> Optional[Dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{API_BASE_URL}/auth/token", data={"username": username, "password": password})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError:
            return None

async def get_current_user(token: str) -> Optional[Dict[str, Any]]:
    headers = {"Authorization": token}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/users/me", headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError:
            return None

async def register_user(username: str, email: str, password: str) -> Tuple[bool, str]:
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{API_BASE_URL}/auth/register", json={"username": username, "email": email, "password": password})
        if response.status_code == 200:
            return True, "Success"
        else:
            return False, response.json().get("detail", "Registration failed")

async def get_connected_accounts(token: str) -> List[Dict[str, str]]:
    headers = {"Authorization": token}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/linkedin/accounts", headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError:
            return []

async def connect_linkedin_account(token: str, code: str) -> Tuple[bool, str]:
    headers = {"Authorization": token}
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{API_BASE_URL}/linkedin/connect", json={"code": code}, headers=headers)
        if response.status_code == 200:
            return True, "Successfully connected LinkedIn account."
        else:
            return False, response.json().get("detail", "Failed to connect LinkedIn account.")

async def disconnect_social_account(token: str, provider: str) -> Tuple[bool, str]:
    headers = {"Authorization": token}
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{API_BASE_URL}/linkedin/disconnect", json={"provider": provider}, headers=headers)
        if response.status_code == 200:
            return True, response.json().get("detail", f"Successfully disconnected {provider}.")
        else:
            return False, response.json().get("detail", "Failed to disconnect account.")

async def create_post(token: str, content: str, channels: list[str], action: str) -> Tuple[bool, str]:
    headers = {"Authorization": token}
    json_payload = {"content": content, "channels": channels}
    params = {"action": action}
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{API_BASE_URL}/posts/", json=json_payload, headers=headers, params=params)
        if response.status_code == 201:
            msg = "Post submitted for publishing!" if action == "post_now" else "Draft saved successfully."
            return True, msg
        else:
            return False, response.json().get("detail", "Failed to create post.")

async def get_drafts(token: str) -> List[Dict[str, Any]]:
    headers = {"Authorization": token}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/posts/drafts", headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError:
            return []

async def delete_post(token: str, post_id: int) -> Tuple[bool, str]:
    headers = {"Authorization": token}
    async with httpx.AsyncClient() as client:
        response = await client.delete(f"{API_BASE_URL}/posts/{post_id}", headers=headers)
        if response.status_code == 204:
            return True, "Draft successfully deleted."
        elif response.status_code == 404:
            return False, "Draft not found."
        else:
            return False, response.json().get("detail", "Failed to delete draft.")