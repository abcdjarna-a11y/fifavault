import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import datetime
import re
import random
import traceback
from threading import Thread
from flask import Flask

# ── Optional AsyncGroq import ──────────────────────────────────────────────────
try:
    from groq import AsyncGroq          # pip install groq>=0.9.0
    GROQ_AVAILABLE = True
except ImportError:
    AsyncGroq = None                    # type: ignore[assignment,misc]
    GROQ_AVAILABLE = False

# ── Flask keep-alive (Render / Replit free-tier) ──────────────────────────────
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive!"

def _run_flask():
    port = int(os.environ.get("PORT", 10000))
    # use_reloader=False is critical — avoids double-spawning inside threads
    app.run(host="0.0.0.0", port=port, use_reloader=False)

def keep_alive():
    t = Thread(target=_run_flask, daemon=True)
    t.start()

# ── Config ────────────────────────────────────────────────────────────────────
MY_DISCORD_ID       = 860215082541514752
ALLOWED_ROLE_IDS    = [1541583386441809950, 1544552950977011723]
BOT_TOKEN           = os.environ.get("DISCORD_TOKEN", "")
GROQ_KEY            = os.environ.get("GROQ_API_KEY", "")
JAIL_ROLE_ID        = 1541262891468988416
RELEASE_ROLE_ID     = 1541192334115602483
MEMBER_CHAT_CHANNEL_ID = 1547615336092668034
ADMIN_CHAT_CHANNEL_ID  = 1541609897953722468

AI_MODEL            = "llama3-8b-8192"
AI_SYSTEM_PROMPT    = (
    "أنت بوت ذكي ومساعد تفاعلي محبوك لسيرفر ديسكورد، "
    "تتحدث بلهجة ودية واحترافية وتختصر الإجابات وتستخدم الإيموجيات."
)

# ── Groq async client ─────────────────────────────────────────────────────────
ai_client: "AsyncGroq | None" = None
if GROQ_AVAILABLE and GROQ_KEY:
    ai_client = AsyncGroq(api_key=GROQ_KEY)   # type: ignore[call-arg]

# ── Intents & bot ─────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def split_message(text: str, limit: int = 1990) -> list[str]:
    """
    Split *text* into chunks that each fit within Discord's 2000-char limit.
    Tries to split on newlines first, falls back to hard-cutting at *limit*.
    """
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # Try to find a natural break point (newline) within the limit
        cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


def check_permissions(ctx: commands.Context) -> bool:
    if ctx.author.id == MY_DISCORD_ID:
        return True
    author_role_ids = {role.id for role in ctx.author.roles}   # type: ignore[union-attr]
    return bool(author_role_ids & set(ALLOWED_ROLE_IDS))


def check_slash_permissions(interaction: discord.Interaction) -> bool:
    if interaction.user.id == MY_DISCORD_ID:
        return True
    if hasattr(interaction.user, "roles"):
        author_role_ids = {role.id for role in interaction.user.roles}  # type: ignore[union-attr]
        return bool(author_role_ids & set(ALLOWED_ROLE_IDS))
    return False


def parse_duration(duration_str: str) -> datetime.timedelta | None:
    match = re.match(r"(\d+)([smhd])", duration_str.lower().strip())
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2)
    return {
        "s": datetime.timedelta(seconds=amount),
        "m": datetime.timedelta(minutes=amount),
        "h": datetime.timedelta(hours=amount),
        "d": datetime.timedelta(days=amount),
    }.get(unit)


# ─────────────────────────────────────────────────────────────────────────────
# Events
# ─────────────────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"[BOT] Logged in as: {bot.user}  (id={bot.user.id})")   # type: ignore[union-attr]
    try:
        synced = await bot.tree.sync()
        print(f"[BOT] Synced {len(synced)} slash command(s).")
    except Exception:
        print("[BOT] Failed to sync slash commands:\n" + traceback.format_exc())


@bot.event
async def on_message(message: discord.Message):
    # ── Ignore bots ───────────────────────────────────────────────────────────
    if message.author.bot:
        return

    content       = message.content          # original casing — needed for AI
    clean_content = content.strip().lower()  # lowercased — used for keyword matching

    # ─────────────────────────────────────────────────────────────────────────
    # Block 1 — Arabic prefix text-commands (اسكت / تكلم / اسم / رتب)
    #
    # BUGS FIXED:
    #   • cmd_trigger was assigned `parts` (the whole list) instead of `parts[0]`
    #     so none of the elif branches ever matched.
    #   • MemberConverter received the entire `args` list instead of `args[0]`.
    #   • We now use `await bot.process_commands(message)` for !-prefixed variants
    #     but handle bare Arabic triggers here manually.
    # ─────────────────────────────────────────────────────────────────────────
    ARABIC_TRIGGERS = ("اسكت ", "اص ", "تكلم ", "اسم ", "رتب ")
    if any(clean_content.startswith(t) for t in ARABIC_TRIGGERS):
        parts       = content.split()
        cmd_trigger = parts[0]          # FIX #1: was `parts`, missing [0]
        args        = parts[1:]

        ctx = await bot.get_context(message)

        if cmd_trigger in ("اسكت", "اص"):
            if len(args) >= 2:
                try:
                    # FIX #2: pass args[0] (string), not args (list)
                    member   = await commands.MemberConverter().convert(ctx, args[0])
                    duration = " ".join(args[1:])
                    await bot.get_command("اسكت").callback(ctx, member, duration_str=duration)  # type: ignore[union-attr]
                except Exception:
                    tb = traceback.format_exc()
                    print(f"[CMD:اسكت] ERROR\n{tb}")
                    await ctx.send("❌ خطأ في معالجة أمر اسكت — تأكد من صحة المنشن والوقت.")
            else:
                await ctx.send("❌ الاستخدام: `اسكت @user [مدة مثل 10m أو 1h]`")
            return

        elif cmd_trigger == "تكلم":
            if len(args) >= 1:
                try:
                    member = await commands.MemberConverter().convert(ctx, args[0])
                    await bot.get_command("تكلم").callback(ctx, member)  # type: ignore[union-attr]
                except Exception:
                    tb = traceback.format_exc()
                    print(f"[CMD:تكلم] ERROR\n{tb}")
                    await ctx.send("❌ خطأ في معالجة أمر تكلم — تأكد من صحة المنشن.")
            else:
                await ctx.send("❌ الاستخدام: `تكلم @user`")
            return

        elif cmd_trigger == "اسم":
            if len(args) >= 2:
                try:
                    member   = await commands.MemberConverter().convert(ctx, args[0])
                    new_name = " ".join(args[1:])
                    await bot.get_command("اسم").callback(ctx, member, new_name=new_name)  # type: ignore[union-attr]
                except Exception:
                    tb = traceback.format_exc()
                    print(f"[CMD:اسم] ERROR\n{tb}")
                    await ctx.send("❌ خطأ في معالجة أمر اسم — تأكد من صحة المنشن والاسم.")
            else:
                await ctx.send("❌ الاستخدام: `اسم @user الاسم الجديد`")
            return

        elif cmd_trigger == "رتب":
            if len(args) >= 2:
                try:
                    member     = await commands.MemberConverter().convert(ctx, args[0])
                    role_input = " ".join(args[1:])
                    await bot.get_command("رتب").callback(ctx, member, role_input=role_input)  # type: ignore[union-attr]
                except Exception:
                    tb = traceback.format_exc()
                    print(f"[CMD:رتب] ERROR\n{tb}")
                    await ctx.send("❌ خطأ في معالجة أمر رتب — تأكد من صحة المنشن واسم الرتبة.")
            else:
                await ctx.send("❌ الاستخدام: `رتب @user اسم_الرتبة`")
            return

    # ─────────────────────────────────────────────────────────────────────────
    # Block 2 — Simple keyword auto-replies
    # ─────────────────────────────────────────────────────────────────────────
    KEYWORD_REPLIES: dict[str | tuple[str, ...], str] = {
        ("السلام عليكم", "سلام عليكم"): "**__ عليكم السلام ورحمه الله وبركاته __** 🤝🤍",
        ("باك",)                       : "منور يا غالي، حياك الله في السيرفر! ✨👋",
        ("بنورك",)                     : "بنور نورك يا بعد قلبي 🤍🌹",
        ("مين عمك",)                   : "يوسف 👑🦁",
        ("منور يابوت",)                : "النور نورك ياتاج راسي ✨👑❤️",
        ("مساعدة",)                    : (
            "**__ اهلا ياصديقي! معاك بوت الخاص بسيرفر ، اذا حاب تعرف القوانين "
            "<#1541195966105911368> 📜 ، اذا حاب تعرف اخر الأخبار الخاصة بسيرفر "
            "<#1541192362204860436> 📢 ، اذا حاب تقديم شكوى او توثق نادي او تستفسر "
            "<#1541203674477371502> 🛠️ ، اذا في شي تاني ماحصلته ، فقط قول لي ايش هو "
            "و بعلمك __** 🌟"
        ),
        ("تويتر",)                     : "تفضل رابط الروم الخاص بتويتر: <#1541223961332031528> 🐦🔥",
        ("الدعم",)                     : "تفضل رابط روم الدعم الفني والمساعدة: <#1541203674477371502> 🤝🆘",
    }

    for keys, reply in KEYWORD_REPLIES.items():
        if clean_content in (keys if isinstance(keys, tuple) else (keys,)):
            await message.reply(reply)
            return

    # ─────────────────────────────────────────────────────────────────────────
    # Block 3 — AI Chatbot (mention-triggered, AsyncGroq)
    #
    # BUGS FIXED:
    #   • Replaced sync Groq() with AsyncGroq() + await  →  FIX #3
    #   • choices[0].message.content   →  FIX #4 (was choices.message, missing [0])
    #   • split_message() handles responses > 2000 chars  →  FIX #5
    #   • Full traceback printed to console on error  →  FIX #6
    # ─────────────────────────────────────────────────────────────────────────
    if bot.user and bot.user.mentioned_in(message) and not message.mention_everyone:
        # Ignore messages that start with ! or !# (they are prefix commands, not AI prompts)
        if not clean_content.startswith("!"):
            if message.channel.id in (MEMBER_CHAT_CHANNEL_ID, ADMIN_CHAT_CHANNEL_ID):
                if ai_client:
                    # Strip the mention(s) from the message to get the actual prompt
                    prompt = (
                        content
                        .replace(f"<@{bot.user.id}>", "")
                        .replace(f"<@!{bot.user.id}>", "")
                        .strip()
                    )

                    if not prompt:
                        await message.reply(
                            "لبيه؟ اكتب سؤالك مع المنشن وبجاوبك فوراً! 🧠✨"
                        )
                        return

                    async with message.channel.typing():
                        try:
                            # ── ASYNC Groq call (non-blocking) ────────────────
                            chat_completion = await ai_client.chat.completions.create(
                                messages=[
                                    {"role": "system", "content": AI_SYSTEM_PROMPT},
                                    {"role": "user",   "content": prompt},
                                ],
                                model=AI_MODEL,
                            )

                            # FIX: was `choices.message.content` — missing [0]
                            bot_response: str = chat_completion.choices[0].message.content or ""

                            if not bot_response.strip():
                                await message.reply("🤖 لم أتمكن من توليد رد. حاول مرة ثانية!")
                                return

                            # FIX: chunk long responses to stay under 2000 chars
                            chunks = split_message(bot_response)
                            first  = True
                            for chunk in chunks:
                                if first:
                                    await message.reply(chunk)
                                    first = False
                                else:
                                    await message.channel.send(chunk)

                        except Exception:
                            # FIX: print FULL traceback so you can diagnose the root cause
                            tb = traceback.format_exc()
                            print(f"[AI] CHATBOT ERROR — full traceback:\n{tb}")
                            await message.reply(
                                "🤖 واجهت مشكلة في الخادم أثناء معالجة النص. "
                                "يرجى المحاولة مرة أخرى لاحقاً."
                            )
                    return

                else:
                    await message.reply(
                        "⚙️ نظام الشات بوت قيد التجهيز من قبل الإدارة، "
                        "يرجى تزويدي بمفتاح API الجديد."
                    )
                    return

            else:
                # Bot mentioned outside AI channels → friendly random reply
                responses = [
                    "لبيه؟ آمرني، أنا في الخدمة! 🤖🤍",
                    "يا هلا والله! عيوني لك، كيف أقدر أساعدك؟ 👀✨",
                    "منشنتني؟ أنا هنا وجاهز لأي أمر! 🚀🛡️",
                    "لبيك وسعديك! البوت الخاص بالسيرفر تحت خدمتك دائماً 🌟👑",
                ]
                await message.reply(random.choice(responses))
                return

    # ─────────────────────────────────────────────────────────────────────────
    # Block 4 — Hand off to the commands framework (!-prefix commands)
    # ─────────────────────────────────────────────────────────────────────────
    await bot.process_commands(message)


# ─────────────────────────────────────────────────────────────────────────────
# Prefix commands
# ─────────────────────────────────────────────────────────────────────────────

@bot.command(name="rename")
async def rename(ctx: commands.Context, *, new_name: str):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    try:
        old_name = ctx.channel.name   # type: ignore[union-attr]
        await ctx.channel.edit(name=new_name)  # type: ignore[union-attr]
        await ctx.send(f"✅ Channel renamed from **{old_name}** → **{new_name}** 📝")
    except Exception:
        tb = traceback.format_exc()
        print(f"[CMD:rename] ERROR\n{tb}")
        await ctx.send("❌ Failed to rename the channel. Check console for details.")


@bot.command(name="اسكت")
async def timeout_user(ctx: commands.Context, member: discord.Member, *, duration_str: str):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    duration = parse_duration(duration_str)
    if not duration:
        await ctx.send("❌ صيغة الوقت خاطئة! يرجى الاستخدام هكذا: `7d` أو `2h` أو `30m` ⏳")
        return
    try:
        await member.timeout(duration)
        await ctx.send(
            f"🤫 تم إعطاء تايم أوت لـ {member.mention} لمدة **{duration_str}** بنجاح."
        )
    except Exception:
        tb = traceback.format_exc()
        print(f"[CMD:اسكت] ERROR\n{tb}")
        await ctx.send("❌ فشل إعطاء التايم أوت. تحقق من السجل في الكونسول.")


@bot.command(name="تكلم")
async def untimeout_user(ctx: commands.Context, member: discord.Member):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    try:
        await member.timeout(None)
        await ctx.send(
            f"🔊 تم إزالة التايم أوت عن {member.mention}، يمكنه التحدث الآن!"
        )
    except Exception:
        tb = traceback.format_exc()
        print(f"[CMD:تكلم] ERROR\n{tb}")
        await ctx.send("❌ فشل إزالة التايم أوت عن العضو.")


@bot.command(name="قفل")
async def lock_channel(ctx: commands.Context, channel: discord.TextChannel | None = None):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    target = channel or ctx.channel
    try:
        await target.set_permissions(ctx.guild.default_role, send_messages=False)  # type: ignore[union-attr]
        await ctx.send(f"🔒 تم قفل الشات بنجاح: {target.mention}")
    except Exception:
        tb = traceback.format_exc()
        print(f"[CMD:قفل] ERROR\n{tb}")
        await ctx.send("❌ فشل قفل الشات.")


@bot.command(name="فتح")
async def unlock_channel(ctx: commands.Context, channel: discord.TextChannel | None = None):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    target = channel or ctx.channel
    try:
        await target.set_permissions(ctx.guild.default_role, send_messages=True)  # type: ignore[union-attr]
        await ctx.send(f"🔓 تم فتح الشات بنجاح: {target.mention}")
    except Exception:
        tb = traceback.format_exc()
        print(f"[CMD:فتح] ERROR\n{tb}")
        await ctx.send("❌ فشل فتح الشات.")


@bot.command(name="اسم")
async def change_nickname(ctx: commands.Context, member: discord.Member, *, new_name: str):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    try:
        await member.edit(nick=new_name)
        await ctx.send(f"📝 تم تغيير اسم {member.mention} إلى **{new_name}**")
    except Exception:
        tb = traceback.format_exc()
        print(f"[CMD:اسم] ERROR\n{tb}")
        await ctx.send("❌ فشل تغيير الاسم.")


@bot.command(name="رتب")
async def give_role(ctx: commands.Context, member: discord.Member, *, role_input: str):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return

    target_role: discord.Role | None = None

    # Handle role mention format <@&ROLE_ID>
    role_mention_match = re.match(r"<@&(\d+)>", role_input.strip())
    if role_mention_match:
        role_id    = int(role_mention_match.group(1))
        target_role = ctx.guild.get_role(role_id)  # type: ignore[union-attr]
    else:
        # Fuzzy name search (case-insensitive substring)
        for role in ctx.guild.roles:                # type: ignore[union-attr]
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
    except Exception:
        tb = traceback.format_exc()
        print(f"[CMD:رتب] ERROR\n{tb}")
        await ctx.send("❌ فشل تعديل الرتبة.")


@bot.command(name="سجن")
async def jail_user(ctx: commands.Context, member: discord.Member):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    jail_role = ctx.guild.get_role(JAIL_ROLE_ID)  # type: ignore[union-attr]
    if not jail_role:
        await ctx.send("❌ لم أتمكن من العثور على رتبة السجن في هذا السيرفر.")
        return
    try:
        removable = [
            r for r in member.roles
            if r != ctx.guild.default_role and not r.managed  # type: ignore[union-attr]
        ]
        if removable:
            await member.remove_roles(*removable)
        await member.add_roles(jail_role)
        await ctx.send(
            f"⛓️ تم تجريد {member.mention} من جميع رتبهم ونقلهم إلى السجن بنجاح!"
        )
    except Exception:
        tb = traceback.format_exc()
        print(f"[CMD:سجن] ERROR\n{tb}")
        await ctx.send("❌ فشل إتمام عملية السجن.")


@bot.command(name="افراج")
async def release_user(ctx: commands.Context, member: discord.Member):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    jail_role    = ctx.guild.get_role(JAIL_ROLE_ID)    # type: ignore[union-attr]
    release_role = ctx.guild.get_role(RELEASE_ROLE_ID)  # type: ignore[union-attr]
    try:
        if jail_role and jail_role in member.roles:
            await member.remove_roles(jail_role)
        if release_role:
            await member.add_roles(release_role)
        await ctx.send(
            f"🕊️ تم الإفراج عن {member.mention}، وإزالة رتبة السجن وإعطائه الرتبة المحددة!"
        )
    except Exception:
        tb = traceback.format_exc()
        print(f"[CMD:افراج] ERROR\n{tb}")
        await ctx.send("❌ فشل تنفيذ أمر الإفراج.")


@bot.command(name="حذف")
async def delete_messages(ctx: commands.Context, amount: int):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    if amount < 1:
        await ctx.send("❌ الرجاء كتابة رقم أكبر من 0 لحذف الرسائل!")
        return
    try:
        deleted = await ctx.channel.purge(limit=amount + 1)  # type: ignore[union-attr]
        msg = await ctx.send(f"🧹 تم حذف **{len(deleted) - 1}** رسالة بنجاح!")
        await asyncio.sleep(3)
        await msg.delete()
    except Exception:
        tb = traceback.format_exc()
        print(f"[CMD:حذف] ERROR\n{tb}")
        await ctx.send("❌ فشل حذف الرسائل.")


@bot.command(name="برا")
async def kick_user(
    ctx: commands.Context,
    member: discord.Member,
    *,
    reason: str = "لا يوجد سبب محدد",
):
    if not check_permissions(ctx):
        await ctx.send("🔒 You do not have permission to use this command!")
        return
    try:
        await member.kick(reason=reason)
        await ctx.send(
            f"🥾 تم طرد العضو {member.mention} بنجاح خارج السيرفر! الباب يوسع جمل."
        )
    except Exception:
        tb = traceback.format_exc()
        print(f"[CMD:برا] ERROR\n{tb}")
        await ctx.send("❌ فشل طرد العضو من السيرفر.")


@bot.command(name="A")
async def show_avatar(ctx: commands.Context, member: discord.Member | None = None):
    target = member or ctx.author
    embed  = discord.Embed(
        title=f"👤 صورة الحساب الشخصي لـ {target.name}",
        color=discord.Color.blue(),
    )
    embed.set_image(url=target.display_avatar.url)
    await ctx.send(embed=embed)


# ─────────────────────────────────────────────────────────────────────────────
# Slash commands
# ─────────────────────────────────────────────────────────────────────────────

@bot.tree.command(name="say", description="يجعل البوت يتحدث بلسانك في نفس الروم")
@app_commands.describe(text="النص المراد إرساله")
async def slash_say(interaction: discord.Interaction, text: str):
    if not check_slash_permissions(interaction):
        await interaction.response.send_message(
            "🔒 ليس لديك صلاحية لاستخدام هذا الأمر السري!", ephemeral=True
        )
        return
    await interaction.response.send_message("⚙️ جاري إرسال النص الخاص بك...", ephemeral=True)
    await interaction.channel.send(text)  # type: ignore[union-attr]


@bot.tree.command(name="embed", description="يجعل البوت يرسل إمبد ملون مخصص (خاص بالمالك فقط)")
@app_commands.describe(text="النص المراد إرساله داخل الإمبد")
async def slash_embed(interaction: discord.Interaction, text: str):
    if interaction.user.id != MY_DISCORD_ID:
        await interaction.response.send_message(
            "🔒 هذا الأمر مخصص حصرياً لمالك البوت فقط!", ephemeral=True
        )
        return
    await interaction.response.send_message(
        "⚙️ جاري تجهيز وإرسال الإمبد الملون...", ephemeral=True
    )
    embed = discord.Embed(description=text, color=discord.Color.from_rgb(47, 49, 54))
    await interaction.channel.send(embed=embed)  # type: ignore[union-attr]


@bot.tree.command(name="help", description="عرض جميع الأوامر المتاحة للبوت وكيفية استخدامها")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 قائمة أوامر البوت الكاملة والشرح 📝",
        description="هنا تجد كل ما يمكن للبوت القيام به في السيرفر مع طريقة الاستخدام الفعالة:",
        color=discord.Color.green(),
    )
    embed.add_field(
        name="🛡️ أوامر الإشراف والمراقبة (Prefix: !)",
        value=(
            "`!اسكت @user [الوقت]` / `اسكت @user [الوقت]` / `اص @user [الوقت]` → تايم أوت ذكي\n"
            "`!تكلم @user` / `تكلم @user` → إلغاء التايم أوت فوراً 🔊\n"
            "`!قفل` / `!فتح` → التحكم في فتح/إغلاق الرومات 🔒🔓\n"
            "`!حذف [العدد]` → تنظيف الرسائل من الشات 🧹\n"
            "`!برا @user` → طرد العضو خارج السيرفر 🥾\n"
            "`!اسم @user [الاسم الجديد]` / `اسم @user [الاسم]` → تعديل اللقب 📝\n"
            "`!رتب @user [اسم الرتبة]` / `رتب @user [الرتبة]` → منح أو إزالة الرتب ➕➖"
        ),
        inline=False,
    )
    embed.add_field(
        name="⛓️ نظام السجن والإفراج",
        value=(
            "`!سجن @user` → سحب جميع الرتب ونقله لرتبة السجن ⛓️\n"
            "`!افراج @user` → فك السجن ومنح رتبة البداية 🕊️"
        ),
        inline=False,
    )
    embed.add_field(
        name="⚙️ الأوامر التفاعلية والسلاش",
        value=(
            "`!A @user` → استعراض صورة الملف الشخصي 👤\n"
            "`/say [النص]` → التحدث بلسان البوت 💬\n"
            "`/embed [النص]` → إرسال إمبد ملون (للمالك فقط) 🖼️\n"
            "`/help` → عرض هذه القائمة 📜"
        ),
        inline=False,
    )
    await interaction.response.send_message(embed=embed)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    async with bot:
        await bot.start(BOT_TOKEN)


if __name__ == "__main__":
    keep_alive()          # Start Flask keep-alive thread before the event loop
    asyncio.run(main())
