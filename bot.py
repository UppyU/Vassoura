import discord
from discord.ext import commands
from discord import app_commands
import json
import aiohttp
import asyncio

# Configuração
TOKEN = "YOUR_TOKEN_HERE"  # Substitua pelo seu token real
INTENTS = discord.Intents.default()
INTENTS.members = True
bot = commands.Bot(command_prefix="!", intents=INTENTS)

BANLIST_URL = "https://rocleaner.com/condolist.json"
server_config = {}
banlist_set = set()
banlist_map = {}

async def load_banlist():
    global banlist_set, banlist_map
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(BANLIST_URL) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    temp_set = set()
                    temp_map = {}
                    if isinstance(data, list):
                        for entry in data:
                            if "id" in entry and "servers" in entry:
                                uid = str(entry["id"])
                                temp_set.add(uid)
                                temp_map[uid] = entry["servers"]
                        banlist_set = temp_set
                        banlist_map = temp_map
                    else:
                        raise ValueError("Formato inválido da banlist")
                else:
                    raise ValueError(f"Erro HTTP: {resp.status}")
    except Exception as e:
        print(f"[ERRO] Falha ao carregar banlist da URL: {e}")
        banlist_set.clear()
        banlist_map.clear()

@bot.event
async def on_ready():
    await load_banlist()
    try:
        synced = await bot.tree.sync()
        print(f"✅ Bot conectado como {bot.user}")
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.tree.command(name="set_language", description="Set bot language / Definir idioma do bot")
@app_commands.describe(language="Choose language / Escolha o idioma")
@app_commands.choices(language=[
    app_commands.Choice(name="English", value="en"),
    app_commands.Choice(name="Português", value="pt")
])
async def set_language(interaction: discord.Interaction, language: app_commands.Choice[str]):
    server_config[interaction.guild.id] = {"lang": language.value, "scan_results": []}
    await interaction.response.send_message(
        "✅ Idioma definido para Português." if language.value == "pt" else "✅ Language set to English.",
        ephemeral=True
    )

@bot.tree.command(name="upload_list", description="Enviar URL da lista de banimento personalizada")
@app_commands.describe(url="URL pública de um arquivo JSON contendo a lista")
async def upload_list(interaction: discord.Interaction, url: str):
    lang = server_config.get(interaction.guild.id, {}).get("lang", "en")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    temp_set = set()
                    temp_map = {}
                    if isinstance(data, list):
                        for entry in data:
                            if "id" in entry and "servers" in entry:
                                uid = str(entry["id"])
                                temp_set.add(uid)
                                temp_map[uid] = entry["servers"]
                        global banlist_set, banlist_map
                        banlist_set = temp_set
                        banlist_map = temp_map
                        await interaction.response.send_message({
                            "en": "✅ Custom banlist loaded successfully.",
                            "pt": "✅ Lista de banimento personalizada carregada com sucesso."
                        }[lang], ephemeral=True)
                    else:
                        raise ValueError("Formato inválido")
                else:
                    raise Exception(f"Erro HTTP {resp.status}")
    except Exception as e:
        await interaction.response.send_message({
            "en": f"❌ Failed to load banlist: {e}",
            "pt": f"❌ Falha ao carregar lista: {e}"
        }[lang], ephemeral=True)

@bot.tree.command(name="scan_server", description="Scan members against the banlist / Escanear membros na lista")
async def scan_server(interaction: discord.Interaction):
    guild = interaction.guild
    lang = server_config.get(interaction.guild.id, {}).get("lang", "en")
    await interaction.response.send_message("🔍 Escaneando..." if lang == "pt" else "🔍 Scanning...", ephemeral=True)

    found = []
    for member in guild.members:
        uid = str(member.id)
        if uid in banlist_set:
            found.append((member, banlist_map.get(uid, [])))

    server_config.setdefault(guild.id, {})["scan_results"] = found

    if found:
        lines = [f"- {member} (`{member.id}`): {', '.join(servers)}" for member, servers in found]
        result = "\n".join(lines)
        message = {
            "en": f"🔎 Found {len(found)} member(s) in the banlist:\n{result}",
            "pt": f"🔎 Encontrado(s) {len(found)} membro(s) na lista de banimento:\n{result}"
        }[lang]
    else:
        message = {
            "en": "✅ No suspicious members found.",
            "pt": "✅ Nenhum membro suspeito encontrado."
        }[lang]

    await interaction.followup.send(message, ephemeral=True)

@bot.tree.command(name="ban_listed", description="Ban members found during scan / Banir membros encontrados no escaneamento")
async def ban_listed(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    results = server_config.get(guild_id, {}).get("scan_results", [])
    lang = server_config.get(guild_id, {}).get("lang", "en")

    if not results:
        await interaction.response.send_message({
            "en": "⚠️ No members to ban.",
            "pt": "⚠️ Nenhum membro encontrado para banir."
        }[lang], ephemeral=True)
        return

    warning_1 = {
        "en": "⚠️ WARNING: You are about to permanently ban the listed users.",
        "pt": "⚠️ AVISO: Você está prestes a banir permanentemente os usuários listados."
    }[lang]
    warning_2 = {
        "en": "This action is irreversible and the ban is PERMANENT.",
        "pt": "Esta ação é irreversível e o banimento é PERMANENTE."
    }[lang]
    await interaction.response.send_message(f"{warning_1}\n{warning_2}", ephemeral=True)

    count = 0
    for member, servers in results:
        try:
            msg = {
                "en": f"🚫 You were banned from **{interaction.guild.name}**. Reason: participation in these servers: {', '.join(servers)}",
                "pt": f"🚫 Você foi banido de **{interaction.guild.name}**. Motivo: participação em estes servidores: {', '.join(servers)}"
            }[lang]
            try:
                await member.send(msg)
            except:
                pass
            await member.ban(reason="Participação em servidores suspeitos")
            count += 1
        except Exception:
            pass

    await interaction.followup.send({
        "en": f"🔨 Permanently banned {count} member(s).",
        "pt": f"🔨 {count} membro(s) banido(s) permanentemente."
    }[lang], ephemeral=True)

bot.run(TOKEN)
