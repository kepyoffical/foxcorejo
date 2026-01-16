import discord
from discord.ext import commands
from discord import app_commands
import os, json, time
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime, timedelta

load_dotenv()
TOKEN = os.getenv("TOKEN")

GLOBAL_OWNER = 826753238392111106
DATA_FILE = "servers.json"

# ---------------- BOT & INTENTS ----------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- ADATKEZELÉS ----------------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

data = load_data()

def get_server(guild_id):
    gid = str(guild_id)
    if gid not in data:
        data[gid] = {
            "admins": [],
            "log_channel": None,
            "antilink_whitelist": []
        }
        save_data(data)
    return data[gid]

def get_antilink_whitelist(guild_id):
    server = get_server(guild_id)
    if "antilink_whitelist" not in server:
        server["antilink_whitelist"] = []
        save_data(data)
    return server["antilink_whitelist"]

async def get_log_channel(guild):
    server = get_server(guild.id)
    if not server["log_channel"]:
        return None
    return guild.get_channel(server["log_channel"])

# ---------------- JOGOSULTSÁG ----------------
def is_owner(member: discord.Member):
    return member.id == GLOBAL_OWNER or member == member.guild.owner

def is_admin(member: discord.Member):
    server = get_server(member.guild.id)
    return is_owner(member) or member.id in server["admins"]

# ---------------- READY ----------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"🦊 FoxCore online: {bot.user}")

# ---------------- KONSTANTOK ----------------
SPAM_LIMIT = 5
SPAM_TIME = 6
LINK_WORDS = ["http://", "https://", "www.", "discord.gg", "discord.com/invite"]

join_tracker = defaultdict(list)
message_tracker = defaultdict(list)

# ---------------- SEGÉDFÜGGVÉNY: MUTED RANG ----------------
async def get_muted_role(guild: discord.Guild):
    role = discord.utils.get(guild.roles, name="FoxCore Muted")
    if role:
        return role
    # Ha nincs, létrehozza
    perms = discord.Permissions(send_messages=False, speak=False, connect=False, add_reactions=False)
    role = await guild.create_role(name="FoxCore Muted", permissions=perms, reason="FoxCore Anti-Link / Anti-Spam Muted")
    
    # Minden csatornára beállítjuk, hogy ne írjon/hozzáférjen
    for channel in guild.channels:
        await channel.set_permissions(role, send_messages=False, speak=False, connect=False, add_reactions=False)
    return role

# ---------------- PARANCSOK ----------------
@bot.tree.command(name="help", description="FoxCore bot parancsok listája")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**🦊 FoxCore parancsok**\n\n"
        "**Admin kezelés:**\n"
        "/addadmin @user – Admin hozzáadása\n"
        "/removeadmin @user – Admin elvétele\n\n"
        "**Rang kezelés:**\n"
        "/role @user @role – Rang adása\n"
        "/unrole @user @role – Rang elvétele\n\n"
        "**Moderáció:**\n"
        "/ban @user – Tiltás\n"
        "/kick @user – Kirúgás\n\n"
        "**Biztonság:**\n"
        "/setlog #csatorna – Log csatorna beállítása\n"
        "/addantikivetel @user – Link küldés engedélyezése\n"
        "/removeantikivetel @user – Kivételek eltávolítása\n\n"
        "👑 Szerver tulaj = Discord owner\n"
    )

@bot.tree.command(name="setlog", description="Log csatorna beállítása (anti-raid, anti-nuke)")
async def setlog(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_owner(interaction.user):
        return await interaction.response.send_message("❌ Csak a szerver tulaj!")
    server = get_server(interaction.guild.id)
    server["log_channel"] = channel.id
    save_data(data)
    await interaction.response.send_message(f"✅ Log csatorna beállítva: {channel.mention}")

@bot.tree.command(name="addadmin", description="Admin hozzáadása a szerverhez")
async def addadmin(interaction: discord.Interaction, user: discord.Member):
    if not is_owner(interaction.user):
        return await interaction.response.send_message("❌ Nincs jogosultságod!")
    if user.id == GLOBAL_OWNER:
        return await interaction.response.send_message("❌ Global Owner nem módosítható!")
    server = get_server(interaction.guild.id)
    if user.id not in server["admins"]:
        server["admins"].append(user.id)
        save_data(data)
    await interaction.response.send_message(f"✅ {user.mention} admin lett.")

@bot.tree.command(name="removeadmin", description="Admin eltávolítása")
async def removeadmin(interaction: discord.Interaction, user: discord.Member):
    if not is_owner(interaction.user):
        return await interaction.response.send_message("❌ Nincs jogosultságod!")
    if user.id == GLOBAL_OWNER:
        return await interaction.response.send_message("❌ Global Owner nem eltávolítható!")
    server = get_server(interaction.guild.id)
    if user.id in server["admins"]:
        server["admins"].remove(user.id)
        save_data(data)
    await interaction.response.send_message(f"🗑️ {user.mention} admin elvéve.")

@bot.tree.command(name="role", description="Rang adása egy felhasználónak")
async def role_cmd(interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ Nincs jogosultságod!")
    await user.add_roles(role)
    await interaction.response.send_message(f"🎭 {user.mention} megkapta a **{role.name}** rangot.")
    log = await get_log_channel(interaction.guild)
    if log:
        await log.send(f"🎭 ROLE ADD | {interaction.user.mention} → {user.mention} | {role.name}")

@bot.tree.command(name="unrole", description="Rang elvétele egy felhasználótól")
async def unrole_cmd(interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ Nincs jogosultságod!")
    await user.remove_roles(role)
    await interaction.response.send_message(f"❌ {user.mention} rang elvéve: **{role.name}**")
    log = await get_log_channel(interaction.guild)
    if log:
        await log.send(f"❌ ROLE REMOVE | {interaction.user.mention} → {user.mention} | {role.name}")

@bot.tree.command(name="ban", description="Felhasználó kitiltása a szerverről")
async def ban(interaction: discord.Interaction, user: discord.Member):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ Nincs jogosultságod!")
    await interaction.guild.ban(user, reason="FoxCore ban")
    await interaction.response.send_message(f"🔨 {user} tiltva.")

@bot.tree.command(name="kick", description="Felhasználó kirúgása a szerverről")
async def kick(interaction: discord.Interaction, user: discord.Member):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ Nincs jogosultságod!")
    await interaction.guild.kick(user)
    await interaction.response.send_message(f"👢 {user} kirúgva.")

@bot.tree.command(name="addantikivetel", description="Felhasználó mentesítése az anti-link alól")
async def add_antilink(interaction: discord.Interaction, user: discord.Member):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ Nincs jogosultságod!")
    if is_admin(user) or is_owner(user):
        return await interaction.response.send_message("❌ Owner/Admin soha nem kell kivétel!")
    whitelist = get_antilink_whitelist(interaction.guild.id)
    if user.id not in whitelist:
        whitelist.append(user.id)
        save_data(data)
    await interaction.response.send_message(f"✅ {user.mention} mentesítve az anti-link alól.")

@bot.tree.command(name="removeantikivetel", description="Felhasználó eltávolítása az anti-link kivételekből")
async def remove_antilink(interaction: discord.Interaction, user: discord.Member):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ Nincs jogosultságod!")
    whitelist = get_antilink_whitelist(interaction.guild.id)
    if user.id in whitelist:
        whitelist.remove(user.id)
        save_data(data)
    await interaction.response.send_message(f"🗑️ {user.mention} már nem mentesült.")

# ---------------- ANTI-RAID ----------------
@bot.event
async def on_member_join(member):
    now = time.time()
    joins = join_tracker[member.guild.id]
    joins.append(now)
    join_tracker[member.guild.id] = [t for t in joins if now - t < 10]
    if len(join_tracker[member.guild.id]) >= 5:
        log = await get_log_channel(member.guild)
        if log:
            await log.send(f"🚨 **ANTI-RAID** – 5+ belépés 10 mp alatt! ({len(join_tracker[member.guild.id])} felhasználó)")

# ---------------- ANTI-NUKE ----------------
@bot.event
async def on_guild_channel_delete(channel):
    logs = await channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete).flatten()
    if not logs:
        return
    entry = logs[0]
    user = entry.user
    if user.id == GLOBAL_OWNER or user == channel.guild.owner:
        return
    await channel.guild.ban(user, reason="ANTI-NUKE: Channel törlés")
    log = await get_log_channel(channel.guild)
    if log:
        await log.send(f"💣 **ANTI-NUKE** – {user.mention} bannolva (channel törlés)")

# ---------------- ANTI-SPAM + ANTI-LINK ----------------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    member = message.author
    server_id = message.guild.id

    # OWNER / ADMIN / GLOBAL OWNER kivétel
    if is_admin(member):
        return await bot.process_commands(message)

    # WHITELIST ellenőrzés (Anti-link kivételek)
    whitelist = get_antilink_whitelist(server_id)
    if member.id in whitelist:
        return await bot.process_commands(message)

    now = time.time()

    # --- ANTI-SPAM ---
    msgs = message_tracker[member.id]
    msgs.append(now)
    message_tracker[member.id] = [t for t in msgs if now - t < SPAM_TIME]
    if len(message_tracker[member.id]) >= SPAM_LIMIT:
        role = await get_muted_role(message.guild)
        if role not in member.roles:
            await member.add_roles(role, reason="FoxCore Anti-Spam")
        await message.channel.send(f"🚨 **ANTI-SPAM** – {member.mention} túl sok üzenetet küldött! Rang: {role.name}")
        log = await get_log_channel(message.guild)
        if log:
            await log.send(f"🚨 **ANTI-SPAM LOG**\n👤 Felhasználó: {member.mention}\n📢 Csatorna: {message.channel.mention}\n📝 Tartalom: `{message.content}`")
        message_tracker[member.id].clear()
        return

    # --- ANTI-LINK ---
    lower = message.content.lower()
    if any(word in lower for word in LINK_WORDS):
        role = await get_muted_role(message.guild)
        if role not in member.roles:
            await member.add_roles(role, reason="FoxCore Anti-Link")
        await message.delete()
        await message.channel.send(f"🔗 **ANTI-LINK** – {member.mention} linket küldött! Rang: {role.name}")
        log = await get_log_channel(message.guild)
        if log:
            await log.send(f"🔗 **ANTI-LINK LOG**\n👤 Felhasználó: {member.mention}\n📢 Csatorna: {message.channel.mention}\n📝 Tartalom: `{message.content}`")
        return

    await bot.process_commands(message)

# ---------------- START ----------------
bot.run(TOKEN)
