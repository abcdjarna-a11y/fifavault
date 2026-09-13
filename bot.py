import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import aiohttp
import ssl
import os
import datetime
import re
import random
from threading import Thread
from flask import Flask

try:
    from groq import Groq
except ImportError:
    Groq = None

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
GROQ_KEY = os.environ.get("GROQ_API_KEY")
JAIL_ROLE_ID = 1541262891468988416
RELEASE_ROLE_ID = 1541192334115602483

MEMBER_CHAT_CHANNEL_ID = 1547615336092668034
ADMIN_CHAT_CHANNEL_ID = 1541609897953722468

if GROQ_KEY and Groq:
    ai_client = Groq(api_key=GROQ_KEY)
else:
    ai_client = None

intents = discord.Intents.default()
intents.message_content = True  
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

def check_permissions(ctx):
    author_role_ids = [role.id for role in ctx.author.roles]
    has_allowed_role = any(role_id in ALLOWED_ROLE_IDS for role_id in author_role_ids)
    return ctx.author.id == MY_DISCORD_ID or has_allowed_role

def check_slash_permissions(interaction: discord.Interaction):
    if interaction.user.id == MY_DISCORD_ID:
        return True
    if hasattr(interaction.user, 'roles'):
        author_role_ids = [role.id for role in interaction.user.roles]
        return any(role_id in ALLOWED_ROLE_IDS for role_id in author_role_ids)
    return False

def parse_duration(duration_str: str):
    match = re.match(r"(\d+)([smhd])", duration_str.lower().strip())
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == 's':
        return datetime.timedelta(seconds=amount)
    elif unit == 'm':
        return datetime.timedelta(minutes=amount)
    elif unit == 'h':
        return datetime.timedelta(hours=amount)
    elif unit == 'd':
        return datetime.timedelta(days=amount)
    return None

@bot.event
async def on_ready():
    print(f'Successfully logged in as: {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands!")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    clean_content = message.content.strip().lower()

    if clean_content.startswith(("اسكت ", "اص ", "تكلم ", "اسم ", "رتب ")):
        ctx = await bot.get_context(message)
        parts = message.content.split()
        cmd_trigger = parts[0]
        args = parts[1:]
        
        if cmd_trigger in ["اسكت", "اص"]:
            ctx.command = bot.get_command("اسكت")
            if len(args) >= 2:
                try:
                    member = await commands.MemberConverter().convert(ctx, args[0])
                    duration = " ".join(args[1:])
                    await bot.get_command("اسكت").callback(ctx, member, duration_str=duration)
                except Exception as e:
                    await ctx.send(f"❌ خطأ في معالجة الأمر: {e}")
            return
        elif cmd_trigger == "تكلم":
            ctx.command = bot.get_command("تكلم")
            if len(args) >= 1:
                try:
                    member = await commands.MemberConverter().convert(ctx, args[0])
                    await bot.get_command("تكلم").callback(ctx, member)
                except Exception as e:
                    await ctx.send(f"❌ خطأ في معالجة الأمر: {e}")
            return
        elif cmd_trigger == "اسم":
            ctx.command = bot.get_command("اسم")
            if len(args) >= 2:
                try:
                    member = await commands.MemberConverter().convert(ctx, args[0])
                    new_name = " ".join(args[1:])
                    await bot.get_command("اسم").callback(ctx, member, new_name=new_name)
                except Exception as e:
                    await ctx.send(f"❌ خطأ في معالجة الأمر: {e}")
            return
        elif cmd_trigger == "رتب":
            ctx.command = bot.get_command("رتب")
            if len(args) >= 2:
                try:
                    member = await commands.MemberConverter().convert(ctx, args[0])
                    role_input = " ".join(args[1:])
                    await bot.get_command("رتب").callback(ctx, member, role_input=role_input)
                except Exception as e:
                    await ctx.send(f"❌ خطأ في معالجة الأمر: {e}")
            return

    if clean_content in ["السلام عليكم", "سلام عليكم"]:
        await message.reply("**__ عليكم السلام ورحمه الله وبركاته __** 🤝🤍")
        return
    elif clean_content == "باك":
        await message.reply("منور يا غالي، حياك الله في السيرفر! ✨👋")
        return
    elif clean_content == "بنورك":
        await message.reply("بنور نورك يا بعد قلبي 🤍🌹")
        return
    elif clean_content == "مين عمك":
        await message.reply("يوسف 👑🦁")
        return
    elif clean_content == "منور يابوت":
        await message.reply("النور نورك ياتاج راسي ✨👑❤️")
        return
    elif clean_content == "مساعدة":
        await message.reply("**__ اهلا ياصديقي! معاك بوت الخاص بسيرفر ، اذا حاب تعرف القوانين <#1541195966105911368> 📜 ، اذا حاب تعرف اخر الأخبار الخاصة بسيرفر <#1541192362204860436> 📢 ، اذا حاب تقديم شكوى او توثق نادي او تستفسر <#1541203674477371502> 🛠️ ، اذا في شي تاني ماحصلته ، فقط قول لي ايش هو و بعلمك __** 🌟")
        return
    elif clean_content == "تويتر":
        await message.reply("تفضل رابط الروم الخاص بتويتر: <#1541223961332031528> 🐦🔥")
        return
    elif clean_content == "الدعم":
        await message.reply("تفضل رابط روم الدعم الفني والمساعدة: <#1541203674477371502> 🤝🆘")
        return

    if bot.user.mentioned_in(message) and not message.mention_everyone:
        if not message.content.strip().startswith("!#") and not clean_content.startswith("!"):
            if message.channel.id in [MEMBER_CHAT_CHANNEL_ID, ADMIN_CHAT_CHANNEL_ID]:
                if ai_client:
                    async with message.channel.typing():
                        try:
                            prompt = message.content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()
                            if not prompt:
                                await message.reply("لبيه؟ اكتب سؤالك مع المنشن وبجاوبك فوراً! 🧠✨")
                                return
                            
                            def get_ai_response():
                                return ai_client.chat.completions.create(
                                    messages=[
                                        {
                                            "role": "system",
                                            "content": "أنت بوت ذكي ومساعد تفاعلي محبوك لسيرفر ديسكورد، تتحدث بلهجة ودية واحترافية وتختصر الإجابات وتستخدم الإيموجيات."
                                        },
                                        {
                                            "role": "user",
                                            "content": prompt,
                                        }
                                    ],
                                    model="llama3-8b-8192",
                                )

                            chat_completion = await asyncio.to_thread(get_ai_response)
                            bot_response = chat_completion.choices.message.content
                            
                            if len(bot_response) > 2000:
                                for i in range(0, len(bot_response), 2000):
                                    await message.reply(bot_response[i:i+2000])
                            else:
                                await message.reply(bot_response)
                                
                        except Exception as e:
                            print(f"CRITICAL CHATBOT ERROR LOG: {e}")
                            await message.reply("🤖 واجهت مشكلة في الخادم أثناء معالجة النص.")
                    return
                else:
                    await message.reply("⚙️ نظام الشات بوت قيد التجهيز من قبل الإدارة، يرجى تزويدي بمفتاح API الجديد.")
                    return
            else:
                responses = [
                    "لبيه؟ آمرني، أنا في الخدمة! 🤖🤍",
                    "يا هلا والله! عيوني لك، كيف أقدر أساعدك؟ 👀✨",
                    "منشنتني؟ أنا هنا وجاهز لأي أمر! 🚀🛡️",
                    "لبيك وسعديك! البوت الخاص بالسيرفر تحت خدمتك دائماً 🌟👑"
                ]
                await message.reply(random.choice(responses))
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
        await ctx.send(f"✅ Channel name changed from **{old_name}** to **{new_name}** 📝")
    except Exception as e:
        await ctx.send(f"❌ Failed to rename channel. Error: {e}")

@bot.command(name="اسكت")
async def timeout_user(ctx, member: discord.Member, duration_str: str):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    duration = parse_duration(duration_str)
    if not duration:
        await ctx.send("❌ صيغة الوقت خاطئة! يرجى الاستخدام هكذا: `7d` أو `2h` أو `30m` ⏳")
        return
    try:
        await member.timeout(duration)
        await ctx.send(f"🤫 تم إعطاء تايم أوت لـ {member.mention} لمدة **{duration_str}** بنجاح.")
    except Exception as e:
        await ctx.send(f"❌ فشل إعطاء التايم أوت. الخطأ: {e}")

@bot.command(name="تكلم")
async def untimeout_user(ctx, member: discord.Member):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    try:
        await member.timeout(None)
        await ctx.send(f"🔊 تم إزالة التايم أوت عن {member.mention}، يمكنه التحدث الآن!")
    except Exception as e:
        await ctx.send(f"❌ فشل إزالة التايم أوت عن العضو. الخطأ: {e}")

@bot.command(name="قفل")
async def lock_channel(ctx, channel: discord.TextChannel = None):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    channel = channel or ctx.channel
    try:
        await channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send(f"🔒 تم قفل الشات بنجاح دون التأثير على الخصوصية: {channel.mention}")
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
        await ctx.send(f"🔓 تم فتح الشات بنجاح: {channel.mention}")
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
        await ctx.send(f"❌ فشل تغيير الاسم. الخطأ: {e}")

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
        await ctx.send("❌ لم أتمكن من العثور على هذه الرتبة.")
        return
    try:
        if target_role in member.roles:
            await member.remove_roles(target_role)
            await ctx.send(f"➖ تم إزالة رتبة **{target_role.name}** من {member.mention}")
        else:
            await member.add_roles(target_role)
            await ctx.send(f"➕ تم إعطاء رتبة **{target_role.name}** إلى {member.mention}")
    except Exception as e:
        await ctx.send(f"❌ فشل تعديل الرتبة. الخطأ: {e}")

@bot.command(name="سجن")
async def jail_user(ctx, member: discord.Member):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    jail_role = ctx.guild.get_role(JAIL_ROLE_ID)
    if not jail_role:
        await ctx.send("❌ لم أتمكن من العثور على رتبة السجن في هذا السيرفر.")
        return
    try:
        roles_to_remove = [role for role in member.roles if role != ctx.guild.default_role and not role.managed]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)
        await member.add_roles(jail_role)
        await ctx.send(f"⛓️ تم تجريد {member.mention} من جميع رتبهم ونقلهم إلى السجن بنجاح!")
    except Exception as e:
        await ctx.send(f"❌ فشل إتمام عملية السجن. الخطأ: {e}")

@bot.command(name="افراج")
async def release_user(ctx, member: discord.Member):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    jail_role = ctx.guild.get_role(JAIL_ROLE_ID)
    release_role = ctx.guild.get_role(RELEASE_ROLE_ID)
    try:
        if jail_role and jail_role in member.roles:
            await member.remove_roles(jail_role)
        if release_role:
            await member.add_roles(release_role)
        await ctx.send(f"🕊️ تم الإفراج عن {member.mention}، وإزالة رتبة السجن وإعطائه الرتبة المحددة!")
    except Exception as e:
        await ctx.send(f"❌ فشل تنفيذ أمر الإفراج. الخطأ: {e}")

@bot.command(name="حذف")
async def delete_messages(ctx, amount: int):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    if amount < 1:
        await ctx.send("❌ الرجاء كتابة رقم أكبر من 0 لحذف الرسائل!")
        return
    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        msg = await ctx.send(f"🧹 تم حذف **{len(deleted) - 1}** رسالة بنجاح!")
        await asyncio.sleep(3)
        await msg.delete()
    except Exception as e:
        await ctx.send(f"❌ فشل حذف الرسائل. الخطأ: {e}")

@bot.command(name="برا")
async def kick_user(ctx, member: discord.Member, *, reason: str = "لا يوجد سبب محدد"):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    try:
        await member.kick(reason=reason)
        await ctx.send(f"🥾 تم طرد العضو {member.mention} بنجاح خارج السيرفر! الباب يوسع جمل.")
    except Exception as e:
        await ctx.send(f"❌ فشل طرد العضو من السيرفر. الخطأ: {e}")

@bot.command(name="A")
async def show_avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"👤 صورة الحساب الشخصي لـ {member.name}", color=discord.Color.blue())
    embed.set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.tree.command(name="say", description="يجعل البوت يتحدث بلسانك في نفس الروم")
@app_commands.describe(text="النص المراد إرساله")
async def slash_say(interaction: discord.Interaction, text: str):
    if not check_slash_permissions(interaction):
        await interaction.response.send_message("🔒 ليس لديك صلاحية لاستخدام هذا الأمر السري!", ephemeral=True)
        return
    await interaction.response.send_message("⚙️ جاري إرسال النص الخاص بك...", ephemeral=True)
    await interaction.channel.send(text)

@bot.tree.command(name="embed", description="يجعل البوت يرسل إمبد ملون مخصص (خاص بالمالك فقط)")
@app_commands.describe(text="النص المراد إرساله داخل الإمبد")
async def slash_embed(interaction: discord.Interaction, text: str):
    if interaction.user.id != MY_DISCORD_ID:
        await interaction.response.send_message("🔒 هذا الأمر مخصص حصرياً لمالك البوت فقط!", ephemeral=True)
        return
    await interaction.response.send_message("⚙️ جاري تجهيز وإرسال الإمبد الملون...", ephemeral=True)
    embed = discord.Embed(description=text, color=discord.Color.from_rgb(47, 49, 54))
    await interaction.channel.send(embed=embed)

@bot.tree.command(name="help", description="عرض جميع الأوامر المتاحة للبوت وكيفية استخدامها")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 قائمة أوامر البوت الكاملة والشرح 📝",
        description="هنا تجد كل ما يمكن للبوت القيام به في السيرفر مع طريقة الاستخدام الفعالة:",
        color=discord.Color.green()
    )
    embed.add_field(name="🛡️ أوامر الإشراف والمراقبة (Prefix: !)", value=(
        "`!اسكت @user [الوقت]` / `اسكت` / `اص` -> تايم أوت ذكي\n"
        "`!تكلم @user` / `تكلم` -> إلغاء التايم أوت عن العضو تلقائياً وفوراً 🔊\n"
        "`!قفل` / `!فتح` -> التحكم الفعال والمحمي في فتح وإغلاق الرومات 🔒🔓\n"
        "`!حذف [العدد]` -> تنظيف وحذف الرسائل من الشات بسرعة 🧹\n"
        "`!برا @user` -> طرد (Kick) العضو مباشرة خارج السيرفر 🥾\n"
        "`!اسم @user [الاسم الجديد]` / `اسم` -> تعديل اللقب 📝\n"
        "`!رتب @user [اسم الرتبة]` / `رتب` -> منح أو إزالة الرتب بالبحث الذكي ➕➖"
    ), inline=False)
    embed.add_field(name="⛓️ نظام السجن والإفراج", value=(
        "`!سجن @user` -> سحب جميع الرتب ونقله لرتبة السجن المحددة ⛓️\n"
        "`!افراج @user` -> فك السجن عنه ومنحه الرتبة المحددة للبدء من جديد 🕊️"
    ), inline=False)
    embed.add_field(name="⚙️ الأوامر التفاعلية وأوامر السلاش (Slash Commands)", value=(
        "`!A @user` -> استعراض صورة الملف الشخصي (Avatar) للعضو 👤\n"
        "`/say [النص]` -> التحدث بلسان البوت وإرسال نصوص عادية في الروم 💬\n"
        "`/embed [النص]` -> كتابة نصوص وتأطيرها داخل إمبد ملون فاخر (للمالك) 🖼️\n"
        "`/help` -> يعرض لك هذه القائمة المنظمة والإرشادية الرائعة 📜"
    ), inline=False)
    await interaction.response.send_message(embed=embed)

async def main():
    async with bot:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        bot.http.connector = connector
        
        await bot.start(BOT_TOKEN)

asyncio.run(main())
