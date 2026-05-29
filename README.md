# Discord Restore Bot

RestoreCord-like Discord bot — OAuth2 verification, member restore, anti-raid.

## Features
- 🔐 OAuth2 verification (saves member tokens)
- 🔄 Member pull-back (`/pull` — re-adds all verified members)
- 🛡️ Auto raid detection + lockdown
- 📊 `/members`, `/unverified` commands
- 🌐 Custom verification web page

---

## Setup Guide

### 1. Create Discord Application
1. Go to https://discord.com/developers/applications
2. Click **New Application** → give it a name
3. Go to **Bot** → **Add Bot** → copy the **Token**
4. Go to **OAuth2** → copy **Client ID** and **Client Secret**
5. Under **OAuth2 → Redirects**, add:
   ```
   https://YOUR-APP-NAME.onrender.com/callback
   ```
6. Under **Bot → Privileged Gateway Intents**, enable:
   - ✅ Server Members Intent
   - ✅ Message Content Intent

### 2. Invite Bot to Server
Use this URL (replace CLIENT_ID):
```
https://discord.com/api/oauth2/authorize?client_id=CLIENT_ID&permissions=8&scope=bot%20applications.commands
```

### 3. Deploy to Render
1. Push this code to a GitHub repo
2. Go to https://render.com → **New Web Service**
3. Connect your GitHub repo
4. Set these **Environment Variables**:

| Variable | Value |
|---|---|
| `BOT_TOKEN` | Your bot token |
| `DISCORD_CLIENT_ID` | Your app client ID |
| `DISCORD_CLIENT_SECRET` | Your app client secret |
| `BASE_URL` | `https://YOUR-APP.onrender.com` |
| `REDIRECT_URI` | `https://YOUR-APP.onrender.com/callback` |

5. Set **Start Command**: `python main.py`
6. Add a **Disk** (under Advanced): mount path `/data`, 1GB
7. Change `DB_PATH` env var to `/data/members.db`

### 4. Run `/setup` in Your Server
After the bot is online, type `/setup` in any channel to initialize.

---

## Bot Commands

| Command | Description | Permission |
|---|---|---|
| `/setup` | Initialize bot in server | Admin |
| `/pull` | Re-add all verified members | Admin |
| `/members` | Show verified member count | Manage Server |
| `/unverified` | Show unverified members | Manage Server |
| `/raidmode on/off` | Toggle raid lockdown | Admin |

---

## How Verification Works
1. Member joins → gets DM with verification link
2. Member clicks link → redirected to Discord OAuth2
3. Member authorizes → token saved to database
4. Bot auto-adds them to the server

When you need to restore members (e.g. after nuke/migration):
- Run `/pull` → bot uses saved tokens to re-add everyone
