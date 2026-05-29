import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import aiohttp
import os
import time
from database import Database
from dotenv import load_dotenv

load_dotenv()

# ─── CONFIG ───────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")  # e.g. https://yourapp.onrender.com/callback
BASE_URL = os.getenv("BASE_URL")          # e.g. https://yourapp.onrender.com

# ─── ANTI-RAID CONFIG ─────────────────────────────────────────
JOIN_THRESHOLD = 10       # max joins
JOIN_WINDOW = 10          # seconds
BAN_ON_RAID = True        # ban or kick during raid

# ─── INTENTS ──────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
db = Database()

# ─── ANTI-RAID TRACKER ────────────────────────────────────────
join_tracker: dict[int, list[float]] = {}  # guild_id -> [timestamps]
raid_mode: dict[int, bool] = {}            # guild_id -> is_raiding


# ══════════════════════════════════════════════════════════════
#  EVENTS
# ══════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.tree.sync()
    print("✅ Slash commands synced.")


@bot.event
async def on_member_join(member: discord.Member):
    guild_id = member.guild.id
    now = time.time()

    # ── Anti-Raid Detection ──────────────────────────
    if guild_id not in join_tracker:
        join_tracker[guild_id] = []

    # Remove old timestamps outside window
    join_tracker[guild_id] = [t for t in join_tracker[guild_id] if now - t < JOIN_WINDOW]
    join_tracker[guild_id].append(now)

    if len(join_tracker[guild_id]) >= JOIN_THRESHOLD:
        if not raid_mode.get(guild_id, False):
            raid_mode[guild_id] = True
            await handle_raid_detected(member.guild)

    if raid_mode.get(guild_id, False):
        try:
            if BAN_ON_RAID:
                await member.ban(reason="🛡️ Anti-Raid: Raid detected")
            else:
                await member.kick(reason="🛡️ Anti-Raid: Raid detected")
        except discord.Forbidden:
            pass
        return

    # ── Send Verification DM ─────────────────────────
    verify_url = f"{BASE_URL}/verify?guild_id={guild_id}&user_id={member.id}"
    embed = discord.Embed(
        title="🔐 Verify Your Account",
        description=(
            f"Welcome to **{member.guild.name}**!\n\n"
            f"To gain access, please verify your Discord account.\n\n"
            f"[➡️ Click here to verify]({verify_url})"
        ),
        color=0x5865F2
    )
    embed.set_footer(text="This uses Discord's official OAuth2 — your password is never shared.")
    try:
        await member.send(embed=embed)
    except discord.Forbidden:
        # DMs disabled — post in a verification channel if exists
        channel = discord.utils.get(member.guild.channels, name="verify")
        if channel:
            await channel.send(f"{member.mention} please verify: {verify_url}")


async def handle_raid_detected(guild: discord.Guild):
    """Alert admins and auto-reset raid mode after 60s."""
    # Find a log/admin channel
    log_channel = discord.utils.get(guild.channels, name="mod-log") or \
                  discord.utils.get(guild.channels, name="logs") or \
                  discord.utils.get(guild.channels, name="general")

    if log_channel:
        embed = discord.Embed(
            title="🚨 RAID DETECTED",
            description=(
                f"**{JOIN_THRESHOLD}+ joins** in {JOIN_WINDOW} seconds detected!\n"
                f"Auto-{'banning' if BAN_ON_RAID else 'kicking'} all new joiners.\n\n"
                f"Raid mode will auto-disable in **60 seconds**.\n"
                f"Or use `/raidmode off` to disable manually."
            ),
            color=0xFF0000
        )
        await log_channel.send(embed=embed)

    # Auto-disable after 60s
    await asyncio.sleep(60)
    raid_mode[guild.id] = False
    if log_channel:
        await log_channel.send("✅ Raid mode automatically disabled.")


# ══════════════════════════════════════════════════════════════
#  SLASH COMMANDS
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="setup", description="Setup the bot in this server")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    guild = interaction.guild

    # Create verify role if it doesn't exist
    verified_role = discord.utils.get(guild.roles, name="Verified")
    if not verified_role:
        verified_role = await guild.create_role(
            name="Verified",
            color=discord.Color.green(),
            reason="RestoreBot setup"
        )

    embed = discord.Embed(
        title="✅ Bot Setup Complete",
        description=(
            f"**Verified Role:** {verified_role.mention}\n\n"
            f"**Verification URL:**\n`{BASE_URL}/verify?guild_id={guild.id}`\n\n"
            f"📌 Post this link in your rules or welcome channel so members can verify."
        ),
        color=0x00FF88
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="pull", description="Pull back all verified members into this server")
@app_commands.checks.has_permissions(administrator=True)
async def pull(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    guild_id = str(interaction.guild.id)
    members = db.get_verified_members(guild_id)

    if not members:
        await interaction.followup.send("❌ No verified members found for this server.", ephemeral=True)
        return

    success, failed = 0, 0
    status_embed = discord.Embed(
        title="⏳ Pulling members...",
        description=f"Found **{len(members)}** verified members.",
        color=0xFFAA00
    )
    msg = await interaction.followup.send(embed=status_embed, ephemeral=True)

    async with aiohttp.ClientSession() as session:
        for member_data in members:
            user_id = member_data["user_id"]
            access_token = member_data["access_token"]

            # Refresh token if expired
            if time.time() > member_data.get("expires_at", 0):
                new_token = await refresh_access_token(session, member_data["refresh_token"])
                if new_token:
                    access_token = new_token["access_token"]
                    db.update_token(
                        user_id, guild_id,
                        new_token["access_token"],
                        new_token["refresh_token"],
                        time.time() + new_token["expires_in"]
                    )
                else:
                    failed += 1
                    continue

            # Add member to guild
            result = await add_member_to_guild(session, interaction.guild.id, user_id, access_token)
            if result:
                success += 1
            else:
                failed += 1

            await asyncio.sleep(0.5)  # Rate limit safety

    result_embed = discord.Embed(
        title="✅ Pull Complete",
        description=f"**Success:** {success}\n**Failed:** {failed}\n**Total:** {len(members)}",
        color=0x00FF88
    )
    await interaction.edit_original_response(embed=result_embed)


@bot.tree.command(name="members", description="Show number of verified members")
@app_commands.checks.has_permissions(manage_guild=True)
async def members_cmd(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    members = db.get_verified_members(guild_id)
    await interaction.response.send_message(
        f"📊 **{len(members)}** verified members stored for this server.",
        ephemeral=True
    )


@bot.tree.command(name="raidmode", description="Toggle raid mode on/off")
@app_commands.describe(status="on or off")
@app_commands.checks.has_permissions(administrator=True)
async def raidmode(interaction: discord.Interaction, status: str):
    guild_id = interaction.guild.id
    if status.lower() == "on":
        raid_mode[guild_id] = True
        await interaction.response.send_message("🚨 Raid mode **ENABLED** — all new joiners will be banned.", ephemeral=True)
    elif status.lower() == "off":
        raid_mode[guild_id] = False
        await interaction.response.send_message("✅ Raid mode **DISABLED**.", ephemeral=True)
    else:
        await interaction.response.send_message("Usage: `/raidmode on` or `/raidmode off`", ephemeral=True)


@bot.tree.command(name="unverified", description="Show members who haven't verified yet")
@app_commands.checks.has_permissions(manage_guild=True)
async def unverified(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    guild_id = str(guild.id)

    verified_ids = {m["user_id"] for m in db.get_verified_members(guild_id)}
    unverified_members = [
        m for m in guild.members
        if not m.bot and str(m.id) not in verified_ids
    ]

    if not unverified_members:
        await interaction.followup.send("✅ All members are verified!", ephemeral=True)
        return

    names = "\n".join([f"• {m.mention} ({m.name})" for m in unverified_members[:20]])
    more = f"\n...and {len(unverified_members) - 20} more" if len(unverified_members) > 20 else ""

    embed = discord.Embed(
        title=f"⚠️ {len(unverified_members)} Unverified Members",
        description=names + more,
        color=0xFF6600
    )
    await interaction.followup.send(embed=embed, ephemeral=True)


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

async def add_member_to_guild(session: aiohttp.ClientSession, guild_id: int, user_id: str, access_token: str) -> bool:
    """Use OAuth2 token to add user to guild via Discord API."""
    url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}"
    headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
    payload = {"access_token": access_token}

    async with session.put(url, json=payload, headers=headers) as resp:
        return resp.status in (200, 201, 204)


async def refresh_access_token(session: aiohttp.ClientSession, refresh_token: str) -> dict | None:
    """Refresh an expired OAuth2 access token."""
    url = "https://discord.com/api/v10/oauth2/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    async with session.post(url, data=data) as resp:
        if resp.status == 200:
            return await resp.json()
        return None


if __name__ == "__main__":
    bot.run(BOT_TOKEN)
