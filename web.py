from flask import Flask, request, redirect, render_template_string
import aiohttp
import asyncio
import os
import time
import urllib.parse
from database import Database
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
db = Database()

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
BASE_URL = os.getenv("BASE_URL")

OAUTH2_SCOPES = "identify guilds.join"

# ══════════════════════════════════════════════════════════════
#  HTML TEMPLATES
# ══════════════════════════════════════════════════════════════

VERIFY_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Verify — Discord</title>
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    :root {
      --bg: #0a0b0f;
      --surface: #13151c;
      --border: #1e2130;
      --accent: #5865f2;
      --accent-glow: rgba(88,101,242,0.35);
      --text: #e8eaf0;
      --muted: #6b7280;
    }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'DM Sans', sans-serif;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }
    .bg-grid {
      position: fixed; inset: 0;
      background-image: linear-gradient(var(--border) 1px, transparent 1px),
                        linear-gradient(90deg, var(--border) 1px, transparent 1px);
      background-size: 48px 48px;
      opacity: 0.4;
      pointer-events: none;
    }
    .glow {
      position: fixed;
      width: 600px; height: 600px;
      background: var(--accent-glow);
      border-radius: 50%;
      filter: blur(120px);
      top: 50%; left: 50%;
      transform: translate(-50%, -50%);
      pointer-events: none;
    }
    .card {
      position: relative;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 48px 40px;
      width: 100%;
      max-width: 420px;
      text-align: center;
      box-shadow: 0 0 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.04) inset;
    }
    .shield {
      width: 64px; height: 64px;
      background: linear-gradient(135deg, var(--accent), #7983f5);
      border-radius: 18px;
      display: flex; align-items: center; justify-content: center;
      font-size: 28px;
      margin: 0 auto 24px;
      box-shadow: 0 8px 32px var(--accent-glow);
    }
    h1 {
      font-family: 'Syne', sans-serif;
      font-size: 26px;
      font-weight: 800;
      margin-bottom: 8px;
      letter-spacing: -0.5px;
    }
    .server-name {
      color: var(--accent);
    }
    p {
      color: var(--muted);
      font-size: 14px;
      line-height: 1.6;
      margin-bottom: 32px;
    }
    .btn {
      display: block;
      width: 100%;
      background: var(--accent);
      color: #fff;
      text-decoration: none;
      padding: 14px;
      border-radius: 12px;
      font-family: 'DM Sans', sans-serif;
      font-weight: 500;
      font-size: 15px;
      transition: all 0.2s;
      box-shadow: 0 4px 20px var(--accent-glow);
    }
    .btn:hover {
      background: #4752c4;
      transform: translateY(-1px);
      box-shadow: 0 8px 28px var(--accent-glow);
    }
    .note {
      margin-top: 20px;
      font-size: 12px;
      color: var(--muted);
    }
    .note span { color: #4ade80; }
  </style>
</head>
<body>
  <div class="bg-grid"></div>
  <div class="glow"></div>
  <div class="card">
    <div class="shield">🛡️</div>
    <h1>Verify to access<br><span class="server-name">{{ server_name }}</span></h1>
    <p>Connect your Discord account to prove you're a real person and gain access to the server.</p>
    <a href="{{ oauth_url }}" class="btn">🔐 Verify with Discord</a>
    <div class="note"><span>🔒 Secure</span> — We never see your password. Discord OAuth2 only.</div>
  </div>
</body>
</html>
"""

SUCCESS_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Verified!</title>
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: #0a0b0f; color: #e8eaf0;
      font-family: 'DM Sans', sans-serif;
      min-height: 100vh; display: flex;
      align-items: center; justify-content: center;
    }
    .card {
      background: #13151c; border: 1px solid #1e2130;
      border-radius: 20px; padding: 48px 40px;
      max-width: 400px; width: 100%; text-align: center;
    }
    .check {
      width: 64px; height: 64px;
      background: linear-gradient(135deg, #22c55e, #4ade80);
      border-radius: 50%; display: flex;
      align-items: center; justify-content: center;
      font-size: 28px; margin: 0 auto 24px;
      box-shadow: 0 8px 32px rgba(34,197,94,0.3);
    }
    h1 { font-family: 'Syne', sans-serif; font-size: 26px; font-weight: 800; margin-bottom: 8px; }
    p { color: #6b7280; font-size: 14px; line-height: 1.6; }
    .username { color: #5865f2; font-weight: 600; }
  </style>
</head>
<body>
  <div class="card">
    <div class="check">✓</div>
    <h1>You're verified!</h1>
    <p>Welcome, <span class="username">{{ username }}</span>!<br>
    You've been added to the server. You can close this tab now.</p>
  </div>
</body>
</html>
"""

ERROR_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Error</title>
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: #0a0b0f; color: #e8eaf0;
      font-family: 'DM Sans', sans-serif;
      min-height: 100vh; display: flex;
      align-items: center; justify-content: center;
    }
    .card {
      background: #13151c; border: 1px solid #1e2130;
      border-radius: 20px; padding: 48px 40px;
      max-width: 400px; width: 100%; text-align: center;
    }
    .icon { font-size: 48px; margin-bottom: 20px; }
    h1 { font-family: 'Syne', sans-serif; font-size: 24px; font-weight: 800; margin-bottom: 8px; }
    p { color: #6b7280; font-size: 14px; }
    .err { color: #ef4444; font-size: 12px; margin-top: 12px; }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">⚠️</div>
    <h1>Something went wrong</h1>
    <p>{{ message }}</p>
    <p class="err">{{ error }}</p>
  </div>
</body>
</html>
"""

# ══════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════

@app.route("/verify")
def verify():
    guild_id = request.args.get("guild_id")
    user_id = request.args.get("user_id", "")

    if not guild_id:
        return "Missing guild_id", 400

    # Build OAuth2 URL
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": OAUTH2_SCOPES,
        "state": f"{guild_id}:{user_id}",  # pass guild+user in state
    }
    oauth_url = "https://discord.com/api/oauth2/authorize?" + urllib.parse.urlencode(params)

    return render_template_string(
        VERIFY_PAGE,
        server_name="the server",
        oauth_url=oauth_url
    )


@app.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state", ":")
    error = request.args.get("error")

    if error:
        return render_template_string(ERROR_PAGE,
            message="You cancelled the verification.",
            error=error), 400

    if not code:
        return render_template_string(ERROR_PAGE,
            message="No code returned from Discord.",
            error=""), 400

    guild_id, user_id = (state.split(":", 1) + [""])[:2]

    # Exchange code for tokens (sync via asyncio)
    token_data = asyncio.run(_exchange_code(code))
    if not token_data or "access_token" not in token_data:
        return render_template_string(ERROR_PAGE,
            message="Failed to get access token from Discord.",
            error=str(token_data)), 400

    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]
    expires_at = time.time() + token_data["expires_in"]

    # Get user info
    user_info = asyncio.run(_get_user_info(access_token))
    if not user_info:
        return render_template_string(ERROR_PAGE,
            message="Failed to get user info.",
            error=""), 400

    actual_user_id = user_info["id"]
    username = user_info.get("username", "Unknown")

    # Save to DB
    db.save_member(
        user_id=actual_user_id,
        guild_id=guild_id,
        username=username,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        verified_at=time.time()
    )

    # Auto-add to guild
    asyncio.run(_add_to_guild(guild_id, actual_user_id, access_token))

    return render_template_string(SUCCESS_PAGE, username=username)


@app.route("/health")
def health():
    return {"status": "ok"}, 200


# ══════════════════════════════════════════════════════════════
#  ASYNC HELPERS (called via asyncio.run)
# ══════════════════════════════════════════════════════════════

async def _exchange_code(code: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.post("https://discord.com/api/v10/oauth2/token", data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        }) as resp:
            return await resp.json()


async def _get_user_info(access_token: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get("https://discord.com/api/v10/users/@me", headers={
            "Authorization": f"Bearer {access_token}"
        }) as resp:
            return await resp.json()


async def _add_to_guild(guild_id: str, user_id: str, access_token: str):
    bot_token = os.getenv("BOT_TOKEN")
    async with aiohttp.ClientSession() as session:
        await session.put(
            f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}",
            json={"access_token": access_token},
            headers={
                "Authorization": f"Bot {bot_token}",
                "Content-Type": "application/json"
            }
        )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
