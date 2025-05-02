import discord
from discord.ext import commands
from discord import app_commands
import json
# Configuração
TOKEN = "YOUR_TOKEN_HERE"  # Substitua pelo seu token real
INTENTS = discord.Intents.default()
INTENTS.members = True
bot = commands.Bot(command_prefix="!", intents=INTENTS)
server_config = {}
banlist = {}
def load_banlist():
    global banlist
    try:
        with open("banlist.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            banlist.clear()
            if isinstance(data, list):
                for entry in data:
                    if "id" in entry and "servers" in entry:
                        banlist[str(entry["id"])] = entry["servers"]
            else:
                raise ValueError("Invalid format")
    except Exception as e:
        print(f"[ERRO] Falha ao carregar banlist: {e}")
        banlist.clear()
@bot.event
async def on_ready():
    load_banlist()
    try:
        synced = await bot.tree.sync()
        print(f"✅ Bot conectado como {bot.user}")
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
# Comando: /set_language
@bot.tree.command(name="set_language", description="Set bot language / Definir idioma do bot")
@app_commands.describe(language="Choose language / Escolha o idioma")
@app_commands.choices(language=[
    app_commands.Choice(name="English", value="en"),
    app_commands.Choice(name="Português", value="pt")
])
async def set_language(interaction: discord.Interaction, language: app_commands.Choice[str]):
    server_config[interaction.guild.id] = {"lang": language.value}
    await interaction.response.send_message(
        "✅ Idioma definido para Português." if language.value == "pt" else "✅ Language set to English.",
        ephemeral=True
    )
# Comando: /import_list
@bot.tree.command(name="import_list", description="Upload a new banlist file / Enviar nova lista de banimento")
@app_commands.describe(attachment="JSON file containing banned IDs")
async def import_list(interaction: discord.Interaction, attachment: discord.Attachment):
    lang = server_config.get(interaction.guild.id, {}).get("lang", "en")
    if not attachment.filename.lower().endswith(".json"):
        await interaction.response.send_message({
            "en": "❌ Invalid file type. Please upload a .json file.",
            "pt": "❌ Tipo de arquivo inválido. Envie um arquivo .json."
        }[lang], ephemeral=True)
        return
    try:
        file_bytes = await attachment.read()
        data = json.loads(file_bytes.decode())
        # Validate Pro-Cleaner format
        if isinstance(data, list) and all("id" in entry and "servers" in entry for entry in data):
            with open("banlist.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            load_banlist()
            await interaction.response.send_message({
                "en": "✅ New banlist imported successfully.",
                "pt": "✅ Nova lista de banimento importada com sucesso."
            }[lang], ephemeral=True)
        else:
            raise ValueError("Invalid Pro-Cleaner format")
    except Exception as e:
        print(f"[Erro] Falha ao importar: {e}")
        await interaction.response.send_message({
            "en": "❌ Failed to read or parse the JSON file.",
            "pt": "❌ Falha ao ler ou interpretar o arquivo JSON."
        }[lang], ephemeral=True)
# Comando: /scan_server
@bot.tree.command(name="scan_server", description="Scan members against the banlist / Escanear membros na lista")
async def scan_server(interaction: discord.Interaction):
    guild = interaction.guild
    lang = server_config.get(interaction.guild.id, {}).get("lang", "en")
    scanning_message = "🔍 Escaneando membros..." if lang == "pt" else "🔍 Scanning members..."
    await interaction.response.send_message(scanning_message, ephemeral=True)
    # Initialize server config if it doesn't exist
    if guild.id not in server_config:
        server_config[guild.id] = {"lang": "en", "scan_results": []}
    found = []
    for member in guild.members:
        if str(member.id) in banlist:
            found.append((member, banlist[str(member.id)]))
    lang = server_config[guild.id].get("lang", "en")
    server_config[guild.id]["scan_results"] = found
    await interaction.followup.send({
        "en": f"🔎 Found {len(found)} member(s) in the banlist.",
        "pt": f"🔎 Encontrado(s) {len(found)} membro(s) na lista de banimento."
    }[lang], ephemeral=True)
# Comando: /ban_listed
@bot.tree.command(name="ban_listed", description="Ban members found during scan / Banir membros encontrados no escaneamento")
async def ban_listed(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    scan_results = server_config.get(guild_id, {}).get("scan_results", [])
    lang = server_config.get(guild_id, {}).get("lang", "en")
    if not scan_results:
        no_members_message = "⚠️ Nenhum membro encontrado para banir." if lang == "pt" else "⚠️ No members to ban."
        await interaction.response.send_message(no_members_message, ephemeral=True)
        return
    lang = server_config.get(guild_id, {}).get("lang", "en")
    count = 0
    for member, servers in scan_results:
        try:
            server_list = ', '.join(servers)
            messages = {
                "en": f"🚫 You have been banned from **{interaction.guild.name}**.\nReason: You were found in a banlist associated with suspicious servers: {server_list}.",
                "pt": f"🚫 Você foi banido do servidor **{interaction.guild.name}**.\nMotivo: Você está em uma lista de banimento associada a servidores suspeitos: {server_list}."
            }
            try:
                await member.send(messages[lang])
            except:
                pass  # Usuário não permite DMs
            await member.ban(reason="Violated server rules")
            count += 1
        except Exception:
            pass
    await interaction.response.send_message({
        "en": f"🔨 Banned {count} member(s).",
        "pt": f"🔨 {count} membro(s) banido(s)."
    }[lang], ephemeral=True)
@bot.tree.command(name="unban", description="Unban a member by ID / Desbanir membro por ID")
@app_commands.describe(user_id="User ID to unban / ID do usuário para desbanir")
async def unban(interaction: discord.Interaction, user_id: str):
    lang = server_config.get(interaction.guild.id, {}).get("lang", "en")
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message({
            "en": f"✅ Successfully unbanned {user.name}#{user.discriminator}",
            "pt": f"✅ {user.name}#{user.discriminator} foi desbanido com sucesso"
        }[lang], ephemeral=True)
    except discord.NotFound:
        await interaction.response.send_message({
            "en": "❌ User not found",
            "pt": "❌ Usuário não encontrado"
        }[lang], ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message({
            "en": "❌ I don't have permission to unban members",
            "pt": "❌ Não tenho permissão para desbanir membros"
        }[lang], ephemeral=True)
    except ValueError:
        await interaction.response.send_message({
            "en": "❌ Invalid user ID format",
            "pt": "❌ Formato de ID inválido"
        }[lang], ephemeral=True)
bot.run(TOKEN)