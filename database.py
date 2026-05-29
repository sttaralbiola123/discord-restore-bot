import os
from typing import Optional, Dict, List

class Database:
    def __init__(self):
        self.members: Dict[tuple, dict] = {}  # key: (user_id, guild_id)

    def save_member(self, user_id: str, guild_id: str, username: str,
                    access_token: str, refresh_token: str,
                    expires_at: float, verified_at: float):
        key = (user_id, guild_id)
        self.members[key] = {
            "user_id": user_id,
            "guild_id": guild_id,
            "username": username,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "verified_at": verified_at
        }

    def get_member(self, user_id: str, guild_id: str) -> Optional[dict]:
        key = (user_id, guild_id)
        return self.members.get(key)

    def get_all_members(self, guild_id: str):
        return [data for (u, g), data in self.members.items() if g == guild_id]

    # ← Ito ang kulang!
    def get_verified_members(self, guild_id: str) -> List[dict]:
        return self.get_all_members(guild_id)

    def delete_member(self, user_id: str, guild_id: str):
        key = (user_id, guild_id)
        self.members.pop(key, None)

    def update_token(self, user_id: str, guild_id: str,
                     access_token: str, refresh_token: str, expires_at: float):
        member = self.get_member(user_id, guild_id)
        if member:
            member["access_token"] = access_token
            member["refresh_token"] = refresh_token
            member["expires_at"] = expires_at
