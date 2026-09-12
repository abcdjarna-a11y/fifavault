import discord
from discord.ext import commands
import asyncio
import aiohttp
import ssl
import os

MY_DISCORD_ID = 860215082541514752  
ALLOWED_ROLE_IDS = [1541583386441809950, 1544552950977011723]  
BOT_TOKEN = os.environ.get("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True  

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Successfully logged in as: {bot.user}')

@bot.command()
async def rename(ctx, *, new_name: str):
    author_role_ids = [role.id for role in ctx.author.roles]
    has_allowed_role = any(role_id in ALLOWED_ROLE_IDS for role_id in author_role_ids)

    if ctx.author.id != MY_DISCORD_ID and not has_allowed_role:
        await ctx.send("🔒 You do not have permission to use this command!")
        return

    try:
        old_name = ctx.channel.name
        await ctx.channel.edit(name=new_name)
        await ctx.send(f"✅ Channel name changed from **{old_name}** to **{new_name}**")
    except Exception as e:
        await ctx.send(f"❌ Failed to rename channel. Make sure the bot has 'Manage Channels' permissions! Error: {e}")

async def main():
    async with bot:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        bot.http.connector = connector
        
        await bot.start(BOT_TOKEN)

asyncio.run(main())
