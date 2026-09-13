import discord
from discord.ext import commands
import asyncio
import aiohttp
import ssl
import os
import datetime
from threading import Thread
from flask import Flask

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()

MY_DISCORD_ID = 860215082541514752  
ALLOWED_ROLE_IDS = [1541583386441809950, 1544552950977011723]  
BOT_TOKEN = os.environ.get("DISCORD_TOKEN")
JAIL_ROLE_ID = 1541262891468988416

intents = discord.Intents.default()
intents.message_content = True  
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

def check_permissions(ctx):
    author_role_ids = [role.id for role in ctx.author.roles]
    has_allowed_role = any(role_id in ALLOWED_ROLE_IDS for role_id in author_role_ids)
    return ctx.author.id == MY_DISCORD_ID or has_allowed_role

@bot.event
async def on_ready():
    print(f'Successfully logged in as: {bot.user}')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    clean_content = message.content.strip().lower()

    if clean_content in ["السلام عليكم", "سلام عليكم"]:
        await message.reply("**__ عليكم السلام ورحمه الله وبركاته __**")
        return

    elif clean_content == "باك":
        await message.reply("منور يا غالي، حياك الله في السيرفر! ✨👋")
        return

    elif clean_content == "بنورك":
        await message.reply("النور نورك يا بعد قلبي 🤍🌹")
        return

    elif bot.user.mentioned_in(message) and not message.mention_everyone:
        if not clean_content.startswith("!"):
            await message.reply("لبيه؟ آمرني، أنا في الخدمة! 🤖🤍")
            return

    await bot.process_commands(message)

@bot.command()
async def rename(ctx, *, new_name: str):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    try:
        old_name = ctx.channel.name
        await ctx.channel.edit(name=new_name)
        await ctx.send(f"✅ Channel name changed from **{old_name}** to **{new_name}**")
    except Exception as e:
        await ctx.send(f"❌ Failed to rename channel. Error: {e}")

@bot.command(name="اسكت")
async def timeout_user(ctx, member: discord.Member, minutes: int):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    try:
        duration = datetime.timedelta(minutes=minutes)
        await member.timeout(duration)
        await ctx.send(f"🤫 تم إعطاء تايم أوت لـ {member.mention} لمدة {minutes} دقائق.")
    except Exception as e:
        await ctx.send(f"❌ فشل إعطاء التايم أوت. تأكد من صلاحيات البوت. الخطأ: {e}")

@bot.command(name="قفل")
async def lock_channel(ctx, channel: discord.TextChannel = None):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    channel = channel or ctx.channel
    try:
        await channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send(f"🔒 تم قفل الشات: {channel.mention}")
    except Exception as e:
        await ctx.send(f"❌ فشل قفل الشات. الخطأ: {e}")

@bot.command(name="فتح")
async def unlock_channel(ctx, channel: discord.TextChannel = None):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    channel = channel or ctx.channel
    try:
        await channel.set_permissions(ctx.guild.default_role, send_messages=True)
        await ctx.send(f"🔓 تم فتح الشات: {channel.mention}")
    except Exception as e:
        await ctx.send(f"❌ فشل فتح الشات. الخطأ: {e}")

@bot.command(name="اسم")
async def change_nickname(ctx, member: discord.Member, *, new_name: str):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    try:
        await member.edit(nick=new_name)
        await ctx.send(f"📝 تم تغيير اسم {member.mention} إلى **{new_name}**")
    except Exception as e:
        await ctx.send(f"❌ فشل تغيير الاسم. قد تكون رتبة الشخص أعلى من البوت. الخطأ: {e}")

@bot.command(name="رتب")
async def give_role(ctx, member: discord.Member, *, role_input: str):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    
    target_role = None
    if role_input.startswith("<&") and role_input.endswith(">"):
        role_id = int(role_input.strip("<@&>"))
        target_role = ctx.guild.get_role(role_id)
    else:
        for role in ctx.guild.roles:
            if role_input.lower() in role.name.lower():
                target_role = role
                break
                
    if not target_role:
        await ctx.send("❌ لم أتمكن من العثور على هذه الرتبة، يرجى كتابة اسم قريب أو منشن للرتبة.")
        return

    try:
        if target_role in member.roles:
            await member.remove_roles(target_role)
            await ctx.send(f"➖ تم إزالة رتبة **{target_role.name}** من {member.mention}")
        else:
            await member.add_roles(target_role)
            await ctx.send(f"➕ تم إعطاء رتبة **{target_role.name}** إلى {member.mention}")
    except Exception as e:
        await ctx.send(f"❌ فشل تعديل الرتبة. تأكد أن رتبة البوت أعلى من الرتبة المطلوبة. الخطأ: {e}")

@bot.command(name="سجن")
async def jail_user(ctx, member: discord.Member):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
        
    jail_role = ctx.guild.get_role(JAIL_ROLE_ID)
    if not jail_role:
        await ctx.send("❌ لم أتمكن من العثور على رتبة السجن في هذا السيرفر، يرجى التأكد من الآيدي.")
        return

    try:
        roles_to_remove = [role for role in member.roles if role != ctx.guild.default_role and not role.managed]
        
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)
            
        await member.add_roles(jail_role)
        await ctx.send(f"⛓️ تم تجريد {member.mention} من جميع رتبهم ونقلهم إلى السجن بنجاح!")
    except Exception as e:
        await ctx.send(f"❌ فشل إتمام عملية السجن. تأكد أن رتبة البوت أعلى من رتب الشخص المستهدف. الخطأ: {e}")

async def main():
    async with bot:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        bot.http.connector = connector
        
        await bot.start(BOT_TOKEN)

asyncio.run(main())
