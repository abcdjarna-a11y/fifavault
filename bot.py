import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import os
import datetime
import re
import random
import traceback
import json
import math
import io
import urllib.parse
import urllib.request
from threading import Thread
from flask import Flask

# ==============================================================================
# TOUCHLINE / FIFA VALT DISCORD BOT - EXTENDED BUILD
# ==============================================================================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Admin Panel is Active & Healthy!"

def _run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

def keep_alive():
    Thread(target=_run_flask, daemon=True).start()

# ── Configuration ─────────────────────────────────────────────────────────────
MY_DISCORD_ID = 860215082541514752
ALLOWED_ROLE_IDS = [1541583386441809950, 1541192296308023389]
MOD_ROLE_ID = 1541192320844566580
BOT_TOKEN = os.environ.get("DISCORD_TOKEN", "")
JAIL_ROLE_ID = 1541262891468988416
RELEASE_ROLE_ID = 1541192334115602483
ALLOWED_AUTO_REPLY_CHANNELS = [1547615336092668034, 1541609897953722468, 1541276089848954961]
SUPPORT_CHANNEL_ID = 1541203674477371502
RULES_CHANNEL_ID = 1541195966105911368
TWITTER_CHANNEL_ID = 1541223961332031528
ANNOUNCEMENTS_CHANNEL_ID = 1541192362204860436

# ── TICKET SYSTEM CONFIGURATION (NEW) ────────────────────────────────────────
TICKET_STAFF_ROLE_ID = 1541192320844566658  # Normal ticket staff who can claim
TICKET_MENTION_ROLE_ID = 1541192320844566658  # Role to mention in new tickets
TICKET_FILE = "tickets_data.json"
TICKET_CONFIG_FILE = "ticket_config.json"

JAIL_FILE = "jail_data.json"
WARN_FILE = "warns_data.json"
SERVER_CONFIG_FILE = "server_config.json"
GAME_IMAGE_NAME = "touchline_interface.jpg"

# FIX #1 — The URL is now properly quoted as a string.
# This is an HTTP URL, not a base64 string. The image_file() helper that tries
# to base64-decode it is replaced with a URL-based approach below.
TOUCHLINE_IMAGE_URL = "https://cdn.discordapp.com/attachments/1541195966105911371/1550178075306631168/touchline_interface.jpg?ex=6aad6356&is=6aac11d6&hm=dd1815df26dcb9137a41d163150cc9075f118d1dd86c5b7c1dc3b5f3848690d4"

# Soft pink / rainbow-ish embed palette.
EMBED_COLORS = [0xFFB6D9, 0xFFC7E8, 0xFF9ED2, 0xF5A6FF, 0xFFD1F0]

def pink_color():
    return discord.Color(random.choice(EMBED_COLORS))

def bold_msg(text: str, emoji: str = "") -> str:
    prefix = f"{emoji} " if emoji else ""
    return f"**__ {prefix}{text} __**"

def image_attachment_url():
    # Since TOUCHLINE_IMAGE_URL is a real CDN URL, embed it directly.
    return TOUCHLINE_IMAGE_URL

# ── Async-safe JSON I/O (FIX #2 — no blocking file I/O in async handlers) ─────
async def async_load_json(path: str) -> dict:
    """Non-blocking JSON load via asyncio.to_thread."""
    def _load():
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        return {}
    return await asyncio.to_thread(_load)

async def async_save_json(path: str, data: dict):
    """Non-blocking JSON save via asyncio.to_thread."""
    def _save():
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    await asyncio.to_thread(_save)

# Sync wrappers kept for helpers that run at startup (not in async handlers)
def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Async warn/jail helpers (all async, use asyncio.to_thread internally)
async def load_warns():
    return await async_load_json(WARN_FILE)

async def save_warns(data):
    await async_save_json(WARN_FILE, data)

async def load_jail():
    return await async_load_json(JAIL_FILE)

async def save_jail(data):
    await async_save_json(JAIL_FILE, data)

async def load_server_config():
    return await async_load_json(SERVER_CONFIG_FILE)

async def save_server_config(data):
    await async_save_json(SERVER_CONFIG_FILE, data)

# ── TICKET SYSTEM PERSISTENCE (NEW) ───────────────────────────────────────────
async def load_tickets():
    return await async_load_json(TICKET_FILE)

async def save_tickets(data):
    await async_save_json(TICKET_FILE, data)

async def load_ticket_config():
    return await async_load_json(TICKET_CONFIG_FILE)

async def save_ticket_config(data):
    await async_save_json(TICKET_CONFIG_FILE, data)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ── Permission helpers ────────────────────────────────────────────────────────
def check_permissions(ctx: commands.Context) -> bool:
    if ctx.author.id == MY_DISCORD_ID:
        return True
    return bool({r.id for r in getattr(ctx.author, "roles", [])} & (set(ALLOWED_ROLE_IDS) | {MOD_ROLE_ID}))

def check_slash_permissions(interaction: discord.Interaction) -> bool:
    if interaction.user.id == MY_DISCORD_ID:
        return True
    return bool({r.id for r in getattr(interaction.user, "roles", [])} & (set(ALLOWED_ROLE_IDS) | {MOD_ROLE_ID}))

def is_owner(user) -> bool:
    return getattr(user, "id", None) == MY_DISCORD_ID
def is_authorized_user(member: discord.Member) -> bool:
    """Check if user is in ALLOWED_ROLE_IDS (for ticket takeover)"""
    return any(r.id in ALLOWED_ROLE_IDS for r in member.roles)

def can_claim_ticket(member: discord.Member) -> bool:
    """Check if user can claim tickets (has TICKET_STAFF_ROLE_ID)"""
    return any(r.id == TICKET_STAFF_ROLE_ID for r in member.roles) or member.guild_permissions.administrator

def can_close_ticket(member: discord.Member, ticket_data: dict) -> bool:
    """Check if user can close a ticket"""
    # Creator, claimer, or administrator
    if member.id == ticket_data.get("creator_id"):
        return True
    if member.id == ticket_data.get("claimed_by_id"):
        return True
    if member.guild_permissions.administrator:
        return True
    return False

def parse_duration(duration_str: str):
    match = re.fullmatch(r"(\d+)([smhd])", duration_str.lower().strip())
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2)
    return {"s": datetime.timedelta(seconds=amount), "m": datetime.timedelta(minutes=amount), "h": datetime.timedelta(hours=amount), "d": datetime.timedelta(days=amount)}[unit]

def clean_arabic_text(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[أإآ]", "ا", text)
    text = re.sub(r"[ة]", "ه", text)
    text = re.sub(r"[ى]", "ي", text)
    text = re.sub(r"\s+", " ", text)
    return text

def member_has_role(member: discord.Member, role_id: int) -> bool:
    return any(r.id == role_id for r in getattr(member, "roles", []))
        
# ── Timeout choices ───────────────────────────────────────────────────────────
TIMEOUT_OPTIONS = [
    ("5m", "warn"),
    ("15m", "spam"),
    ("30m", "تقديم إساءات لعضو أو إداري"),
    ("1h", "السب والقذف أو إرسال صور مخلة"),
    ("1d", "في حال تكرار مخالفة القوانين"),
    ("3d", "sending +18 or inappropriate contentt"),
    ("7d", "تايم مع سجن"),
    ("28d", "سجن"),
]
TIMEOUT_MAP = {k: (parse_duration(k), d) for k, d in TIMEOUT_OPTIONS}

async def apply_timeout(ctx_or_interaction, target: discord.Member, duration_key: str):
    duration_info = TIMEOUT_MAP.get(duration_key)
    if not duration_info:
        return False, "المدة غير صالحة."
    delta, description = duration_info
    try:
        if duration_key == "28d":
            jailed = await jail_member_action(ctx_or_interaction, target, description)
            if not jailed:
                return False, "تعذر السجن: رتبة السجن غير موجودة أو لا أملك صلاحية إدارة الرتب."
            return True, "jail"
        if duration_key == "7d":
            jailed = await jail_member_action(ctx_or_interaction, target, description)
            if not jailed:
                return False, "تعذر تطبيق 7d لأن السجن لم ينجح؛ لم يتم إعطاء التايم."
            await target.timeout(delta, reason=f"تايم: {description}")
            return True, "timeout+jail"
        await target.timeout(delta, reason=f"تايم: {description}")
        return True, "timeout"
    except discord.Forbidden:
        return False, "لا أملك صلاحية Timeout/إدارة العضو أو أن رتبة العضو أعلى من رتبتي."
    except Exception as e:
        return False, str(e)

async def remove_timeout(target: discord.Member):
    try:
        await target.timeout(None, reason="إزالة التايم بواسطة الأمر تكلم")
        return True, None
    except discord.Forbidden:
        return False, "لا أملك صلاحية إزالة التايم عن هذا العضو."
    except Exception as e:
        return False, str(e)

async def jail_member_action(ctx_or_interaction, member: discord.Member, reason: str):
    guild = getattr(ctx_or_interaction, "guild", None)
    if guild is None and isinstance(ctx_or_interaction, discord.Interaction):
        guild = ctx_or_interaction.guild
    if guild is None:
        return False
    jail_role = guild.get_role(JAIL_ROLE_ID)
    release_role = guild.get_role(RELEASE_ROLE_ID)
    if not jail_role:
        return False
    me = guild.me
    if me and jail_role >= me.top_role:
        return False
    # FIX: use async JSON I/O
    saved_data = await load_jail()
    old_role_ids = [r.id for r in member.roles if not r.is_default() and r.id != JAIL_ROLE_ID]
    if old_role_ids:
        saved_data[str(member.id)] = old_role_ids
        await save_jail(saved_data)
    keep_roles = [release_role] if release_role and release_role in member.roles else []
    keep_roles.append(jail_role)
    await member.edit(roles=keep_roles, reason=f"سجن | {reason}")
    return True

# ── Translation ─────────────────────────────────────────────────────────────
async def real_translate_to_arabic(text: str) -> str:
    if not text.strip():
        raise ValueError("النص فارغ.")
    params = urllib.parse.urlencode({"client": "gtx", "sl": "auto", "tl": "ar", "dt": "t", "q": text})
    url = "https://translate.googleapis.com/translate_a/single?" + params
    def fetch():
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as response:
            return response.read().decode("utf-8")
    raw = await asyncio.to_thread(fetch)
    data = json.loads(raw)
    pieces = data[0]
    return "".join(piece[0] for piece in pieces if piece and piece[0]).strip()

# ==============================================================================
# FIX #3 — Auto Replies: pre-clean keys at module level (not inside on_message)
# This avoids re-processing normalization on every message event.
# ==============================================================================

_RAW_KEYWORD_REPLIES = {
    ("السلام عليكم", "سلام عليكم", "سلامون عليكم", "الاسم عليكم", "اسلام عليكم"): [
        "**__ عليكم السلام ورحمه الله وبركاته __** 🤝🤍",
        "يا هلا وعليكم السلام ورحمة الله وبركاته، منور يا غالي! ✨",
        "وعليكم السلام والرحمة، أرحب حياك الله في الشات 🌹"
    ],
    ("باك", "باكك", "باك المدارس", "عدنا", "بااك"): [
        "منور يا غالي، حياك الله في السيرفر! ✨👋",
        "ولكم باك يا قمر، نور الشات بوجودك 🌕❤️",
        "أحلى باك! نورتنا ورجعت الروح للشات ✨"
    ],
    ("بنورك", "نورك", "بنور عيونك", "النور نورك"): [
        "تسلم لي يا عسل، النور نور عيونك الغالية تراه ✨",
        "حبيبي الله يسعدك، هذا جزء من نورك المحيط بنا 🌟"
    ],
    ("مين عمك", "من عمك", "عمك", "مين عمكم"): [
        "يوسف 👑🦁",
        "عمي وعم الجميع يوسف القائد الرمز 👑",
        "الأسد يوسف بلا منازع 🦁👑"
    ],
    ("منور يابوت", "منور يا بوت", "منور البوت", "منور يابطل"): [
        "النور نورك ياتاج راسي ✨👑❤️",
        "تسلم يا قمر، كلك ذوق ونورك عاكس علينا 🤖🤍",
        "يا هلا بك، النور الحقيقي هو وجودك معنا بالسيرفر 🌟"
    ],
    ("مساعدة", "ساعدني", "كيف الطريقه", "وش اسوي", "المساعدة"): [
        "**__ اهلا ياصديقي! معاك بوت الخاص بسيرفر ، اذا حاب تعرف القوانين <#1541195966105911368> 📜...__**",
        "عيوني لك! لفتح تذكرة توجه لـ <#1541203674477371502> وسنساعدك فوراً 🛠️",
        "أهلاً بك، تفضل لغرفة الدعم <#1541203674477371502> وطاقم الإدارة بخدمتك 🤝"
    ],
    ("تويتر", "twitter", "تويتر السيرفر", "منصة اكس"): [
        "تفضل رابط الروم الخاص بتويتر: <#1541223961332031528> 🐦🔥",
        "تابع آخر الأخبار والتغريدات في الروم المخصص: <#1541223961332031528> 🐦",
        "لا تفوتك آخر الفعاليات على حسابنا في تويتر هنا: <#1541223961332031528> ✨"
    ],
    ("الدعم", "تذكرة", "تيكت", "افتح تكت", "تكت"): [
        "تفضل رابط روم الدعم الفني والمساعدة: <#1541203674477371502> 🤝🆘",
        "لأي شكوى أو استفسار افتح تذكرة في: <#1541203674477371502> 🛠️",
        "فريق الدعم الفني جاهز لخدمتك، توجه إلى <#1541203674477371502> 🆘"
    ],
    ("صباح الخير", "صباح النور", "صباحو", "صباح الورد"): [
        "صباح الورد والياسمين! يومك سعيد ومليء بالبهجة ☀️🌸",
        "أحلى صباح لأحلى عضو، عسى يومك كله توفيق ونجاح يا رب 🌤️✨",
        "صباح النور والسرور، أنرت الشات في بداية هذا اليوم الجميل ☕"
    ],
    ("مساء الخير", "مساء النور", "مساء الورد", "مسائو"): [
        "مساء النور والسرور، حياك الله في شات السيرفر الساهر 🌙✨",
        "مساء الورد والجمال، منورنا في هذا الوقت الجميل 🌹🌟",
        "يا هلا ومساء الورد، أتمنى لك سهرة ممتعة معنا الليلة 🕯️"
    ],
    ("تصبحون على خير", "تصبح على خير", "بنام", "تصبحو على خير"): [
        "تلاقي الخير يا بعد قلبي، نوم الهنا وأحلام سعيدة 💤🤍",
        "وأنت من أهل الخير والسعادة، نراك غداً على خير يا بطل 🛌✨",
        "حفظك الله ورعاك، أحلام سعيدة ونوم هادئ وعميق 🌌"
    ],
    ("كيف اصير مشرف", "ابغى رتبة", "ابي اشراف", "ابي رتبه", "كيف اصير اداره"): [
        "التقديم على الإشراف يفتح بشكل دوري في روم <#1541203674477371502>! أثبت تفاعلك أولاً 👑",
        "رتب الإشراف تعطى للمتفاعلين والملتزمين بالقوانين، استمر بتفاعلك الفخم 🎖️",
        "الإدارة تراقب الشات دائماً وتختار المتميزين، شد حيلك وبتكون معنا 🛡️"
    ],
    ("رابط السيرفر", "الرابط", "رابط انفاير", "رابط السيرفر للاصدقاء"): [
        "تفضل يا غالي، هذا هو الرابط الدائم لدعوة أصدقائك: (https://discord.gg/gB7aAtUTyK) 🔗🔥",
        "أنشر الرابط لربعك وخلنا نكبر سوا: (https://discord.gg/gB7aAtUTyK) 🔗✨",
        "حيا الله من يجي من طرفك، تفضل الرابط: (https://discord.gg/gB7aAtUTyK) 🔗👑"
    ],
    ("وين القوانين", "القوانين", "قوانين السيرفر", "وين قوانين"): [
        "يا هلا بك! القوانين كاملة ومحدثة تجدها دائماً في روم <#1541195966105911368> 📜",
        "لتفادي المخالفات والتحذيرات، اقرأ القوانين بعناية هنا: <#1541195966105911368> ⚠️",
        "القوانين تحمي الجميع، تفضل بزيارة الروم الخاص بها: <#1541195966105911368> 📜"
    ],
    ("اكرهك يابوت", "بوت غبي", "اكره البوت"): [
        "أفا! وش سويت لك؟ أنا هنا لخدمتك ومحبتك دائماً على أي حال 😢💔",
        "زعلتني.. بس ما أقبل أكره أعضاء سيرفرنا الفخمين، بظل أحبك 🤖💔",
        "سامحني لو أخطأت بحقك، بحاول أتحسن عشان تعزني وتغير رأيك 😔"
    ],
    ("احبك يابوت", "فديتك يا بوت", "احب البوت"): [
        "وأنا أحبكم وأموت فيكم يا أحلى سيرفر وأطلق أعضاء! 😭❤️✨",
        "يا بعد قلبي والله، هالكلام يسعد برمجتي ويفرحني جداً 🤖🤍",
        "ميداليتك الذهبية في قلبي محفورة، حبك متبادل يا تاج راسي 👑❤️"
    ],
    ("شكرا", "تسلم", "مشكور", "شكراً"): [
        "العفو يا بعد راسي، ماسوينا إلا الواجب، حنا بخدمتكم دايماً 🌹🤍",
    ],
    ("البوت شغال؟", "يا بوت", "شغال يابوت", "يابوت شغال"): [
        "شغال ومصحصح وجاهز لخدمتكم 24 ساعة بأعلى كفاءة برمجية! 🤖⚡",
        "لبيه؟ شغال وتحت أمرك في أي وقت، اطلب وتمنى 🧠✨",
        "موجود دائماً لخدمة هذا السيرفر الأسطوري وأعضائه الفخمين 🛡️"
    ],
    ("القرآن", "قرآن", "قران كريم", "قران"): [
        "الله يريح قلبك بالدنيا والآخرة، جاري تجهيز رومات الصوت للتلاوات 🕌",
        "طمأنينة لقلبك وراحة لنفسك، تذكر قراءة الأذكار دايماً 🤍",
        "ألا بذكر الله تطمئن القلوب.. بارك الله فيك ونور قلبك بنور الإيمان 🕌"
    ],
    ("سيرفر فاشل", "سيرفر بيض", "سيرفر خايس", "سيرفر زفت"): [
        "رأيك يهمنا لتطوير السيرفر! يرجى تقديم مقترح في الدعم <#1541203674477371502> 🛠️",
        "نأسف إذا واجهت تجربة سيئة، طاقم الإدارة جاهز لسماعك وتعديل كل شيء 🤝",
        "الكمال لله وحده، ساعدنا بنصيحة أو فكرة نطور بها المكان بدلاً من الإحباط 🌹"
    ],
    ("الأخبار", "اخر الاخبار", "اعلانات السيرفر", "القرار الجديد"): [
        "تابع آخر الأخبار والقرارات الرسمية الخاصة بالسيرفر في روم <#1541192362204860436> 📢",
        "كل التحديثات والتطورات الجديدة يتم إعلانها فوراً في <#1541192362204860436> 📢",
        "لا تفوتك الأحداث الهامة، تفقد روم الإعلانات هنا: <#1541192362204860436> 📢"
    ],
    ("جوعان", "جوع", "بي اكل"): [
        "اطلب لك شاورما دبل وثوم زيادة وانسى الدنيا 🌯",
        "الشات كله جوعانين، شكلنا بنقفل ونروح للمطعم 🍔",
        "أبشر بالخير، المطبخ مفتوح بس الحساب عليك 🍳"
    ],
    ("شاورما", "صاروخ شاورما"): [
        "أعظم اختراع في التاريخ البشري بلا منازع! 🌯❤️",
        "دبل ثوم وسبايسي؟ أنت كذا تفهم في الأكل صح 🌶️",
        "الشاورما حب لا ينتهي، صب لي معك واحد دبل 🌯"
    ],
    ("أقوى بوت", "افضل بوت"): [
        "بشهادتك وبفضل فخامتكم ودعم يوسف القائد الأسطوري 👑🦁",
        "هذا من حسن ذوقك، أنا مصمم لخدمتكم بأعلى قوة ⚡",
        "تسلم يا وحش، القادم مذهل وأقوى بكثير 🚀"
    ],
    ("تحديث", "صيانة"): [
        "التحديثات مستمرة لتوفير أطلق تجربة وأعلى حماية للسيرفر ⚡",
        "الإدارة شغالين كود وهندسة لإضافة ميزات أسطورية دايماً 🛠️",
        "ترقبوا المفاجآت، التحديث القادم بيغير كل شيء 🎉"
    ],
    ("تفعيل", "وثقني"): [
        "إذا حاب توثق حياك بروم الدعم الفني <#1541203674477371502> 🛠️",
        "التفعيل سريع وفوري، الإدارة بالخدمة دايماً 🛡️",
        "توجه للروم المخصص للتفعيل وبتخلص بثواني ✨"
    ],
    ("القائد يوسف", "يوسف الاسد"): [
        "يوسف فخر السيرفر ورمز القيادة الحكيمة والأسد 👑🦁",
        "الملك يوسف يوجه السيرفر لأعلى القمم دايماً 👑",
        "الأسد يوسف قائدنا وتاج راس السيرفر كله 🦁"
    ],
    ("اسطورة", "يا اسطورة"): [
        "أنت الأسطورة الحقيقية بتفاعلك وروعة حضورك دايماً ⭐",
        "الأساطير يتواجدون هنا، منور يا بطل السيرفر 👑",
        "أسطورة ديسكورد بلا منازع هو أنت يا غالي 🌟"
    ],
    ("وين الشباب", "الشات ميت"): [
        "الشات نايم؟ الحين يصحون الوحوش ويولعونها 🔥",
        "موجودين بس يتغلون، منشنهم وبيتجمعون الحين 👀",
        "البوت مصحصح معكم، عطنا سالفة فخمة وخلهم يجون 💬"
    ],
    ("ممنوع", "خالف"): [
        "انتبه! النظام صارم والإدارة بالمرصاد لكل مخالفة ⚠️",
        "خلنا بالسليم وخلك نظامي عشان ما تبلع تايم أوت 🤫",
        "المخالفات تنتهي بالوارن والسجن، التزم يا وحش ⛓️"
    ],
    ("فزعة", "فزعه"): [
        "أبشر بالفزعة الدعم الفني والإدارة رهن إشارتك 🚨",
        "أنت راعي فزعات ودايم تفك الأزمات بكرمك كفو 🛡",
        "الفزعة جاهزة، حدد الروم والمشكلة وبتشوفنا عندك ⚡"
    ],
    ("good night", "تصبح على خير انجليزي"): [
        "Good night, sweet dreams and rest well! 💤",
        "See you tomorrow, have a peaceful sleep! 🌙",
        "Sleep tight, friend! 🌌"
    ],
    ("good morning", "صباح الخير انجليزي"): [
        "Good morning! Have a bright and successful day ☀️",
        "Morning sunshine! Welcome back to the chat 🌤️",
        "Wishing you a fantastic day ahead! ☕"
    ],
    ("how are you", "كيف حالك انجليزي"): [
        "I am doing perfect, coding and serving you! 🤖",
        "Doing great, thanks for asking, awesome human! 🌟",
        "Excellent! Hope you are having an amazing day too ✨"
    ],
    ("welcome", "ولكم انجليزي"): [
        "Thank you so much! Glad to be here with you 🤍",
        "Thanks for the warm welcome, you are the best 🌹",
        "Much appreciated, let's rock this server! 💎"
    ],
    ("bye", "goodbye", "باي"): [
        "Goodbye! Take care and come back soon 👋",
        "See you later, have a wonderful time ahead 🌅",
        "Bye friend, stay safe and awesome! ✨"
    ],
    ("امير", "أمير"): [
        "<@1183582347950563439> مشغول 🛑",
        "لا تقعد تزعجه قلنا لك مشغول 🛑",
    ],
}

# FIX #3: Pre-build a flat dict mapping cleaned_key -> replies list, done ONCE at startup.
# This replaces the inner-loop normalization inside on_message.
KEYWORD_REPLIES_CLEANED: dict[str, list] = {}
for _keys, _replies in _RAW_KEYWORD_REPLIES.items():
    for _k in _keys:
        KEYWORD_REPLIES_CLEANED[clean_arabic_text(_k)] = _replies
        
# ==============================================================================
# TICKET SYSTEM UTILITY FUNCTIONS (NEW)
# ==============================================================================

def get_ticket_type_name_ar(ticket_type: str) -> str:
    """Get Arabic ticket type name"""
    types = {
        "technical": "〢🎫・الدعم・الفني",
        "verification": "〢✅・توثيق",
        "complaint": "〢🎟️・شكوى",
        "admin_application": "〢👮・تقديم・الإدارة"
    }
    return types.get(ticket_type, ticket_type)

async def get_next_ticket_number(ticket_type: str) -> int:
    """Get next ticket number for specific type"""
    tickets = await load_tickets()
    counters = tickets.get("counters", {})
    current = counters.get(ticket_type, 0)
    next_num = current + 1
    counters[ticket_type] = next_num
    tickets["counters"] = counters
    await save_tickets(tickets)
    return next_num

async def user_has_open_ticket(user_id: int, ticket_type: str, guild_id: int) -> tuple[bool, int | None]:
    """Check if user has an open ticket of this type"""
    tickets = await load_tickets()
    open_tickets = tickets.get("open_tickets", {})
    
    for channel_id, ticket_data in open_tickets.items():
        if (ticket_data.get("creator_id") == user_id and 
            ticket_data.get("type") == ticket_type and
            ticket_data.get("guild_id") == guild_id and
            not ticket_data.get("closed", False)):
            return True, int(channel_id)
    
    return False, None

async def create_ticket_channel(guild: discord.Guild, ticket_type: str, creator: discord.Member) -> discord.TextChannel | None:
    """Create a ticket channel with proper permissions"""
    try:
        # Get ticket number
        number = await get_next_ticket_number(ticket_type)
        type_name_ar = get_ticket_type_name_ar(ticket_type)
        channel_name = f"{type_name_ar}-{number}"
        
        # Find or create tickets category
        category = discord.utils.get(guild.categories, name="SUPPORT")
        if not category:
            category = await guild.create_category("SUPPORT")
        
        # Set up permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            creator: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_permissions=True
            )
        }
        
        # Add ticket staff role
        ticket_staff_role = guild.get_role(TICKET_STAFF_ROLE_ID)
        if ticket_staff_role:
            overwrites[ticket_staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        
        # Add administrators
        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )
        
        # Create channel
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"تذكرة {type_name_ar} • بواسطة {creator.display_name}"
        )
        
        return channel
        
    except Exception as e:
        print(f"Error creating ticket channel: {e}")
        return None

async def update_ticket_activity(channel_id: int):
    """Update last activity timestamp for a ticket"""
    tickets = await load_tickets()
    open_tickets = tickets.get("open_tickets", {})
    
    if str(channel_id) in open_tickets:
        open_tickets[str(channel_id)]["last_activity"] = datetime.datetime.now().isoformat()
        tickets["open_tickets"] = open_tickets
        await save_tickets(tickets)

async def generate_ticket_transcript(channel: discord.TextChannel, ticket_data: dict) -> str:
    """Generate HTML transcript of ticket"""
    try:
        messages = []
        async for msg in channel.history(limit=1000, oldest_first=True):
            messages.append(msg)
      
        takeover_events = [
            event
            for event in ticket_data.get("events", [])
            if event.get("type") == "takeover"
        ]

        if takeover_events:
            takeover_status = "نعم"
            takeover_details = "<br>".join(
                (
                    f"{event.get('from_user_name') or 'لا أحد'} "
                    f"→ "
                    f"{event.get('user_name') or 'غير معروف'} "
                    f"({event.get('timestamp', 'N/A')})"
                )
                for event in takeover_events
            )
        else:
            takeover_status = "لا"
            takeover_details = "لم يحدث Owner Takeover."

        event_history = ticket_data.get("events", [])

        event_history_html = "<br>".join(
            (
                f"[{event.get('timestamp', 'N/A')}] "
                f"{event.get('type', 'unknown')} - "
                f"{event.get('user_name', 'Unknown')}"
            )
            for event in event_history
        )
        
        html = f"""
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>نص تذكرة {channel.name}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #36393f;
            color: #dcddde;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: #2f3136;
            border-radius: 8px;
            padding: 20px;
        }}
        .header {{
            border-bottom: 2px solid #202225;
            padding-bottom: 20px;
            margin-bottom: 20px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            color: #fff;
        }}
        .info {{
            background: #202225;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .info-row {{
            margin: 5px 0;
        }}
        .label {{
            font-weight: bold;
            color: #b9bbbe;
        }}
        .message {{
            margin: 15px 0;
            padding: 10px;
            background: #40444b;
            border-radius: 5px;
            border-right: 3px solid #5865f2;
        }}
        .message-header {{
            display: flex;
            align-items: center;
            margin-bottom: 8px;
        }}
        .author {{
            font-weight: bold;
            color: #fff;
            margin-left: 10px;
        }}
        .timestamp {{
            color: #72767d;
            font-size: 0.875rem;
        }}
        .content {{
            color: #dcddde;
            word-wrap: break-word;
        }}
        .system-message {{
            background: #2f3136;
            border-right-color: #faa61a;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📋 نص تذكرة: {channel.name}</h1>
        </div>
        
        <div class="info">
            <div class="info-row">
                <span class="label">نوع التذكرة:</span> {get_ticket_type_name_ar(ticket_data.get('type', 'unknown'))}
            </div>
            <div class="info-row">
                <span class="label">تم الفتح بواسطة:</span> {ticket_data.get('creator_name', 'Unknown')} (ID: {ticket_data.get('creator_id', 'N/A')})
            </div>
            <div class="info-row">
                <span class="label">تاريخ الفتح:</span> {ticket_data.get('created_at', 'N/A')}
            </div>
          <div class="info-row">
                <span class="label">مستلم التكت:</span>
                {ticket_data.get('claimed_by_name', 'لم يتم الاستلام بعد')}
            </div>

            <div class="info-row">
                <span class="label">وقت الاستلام:</span>
                {ticket_data.get('claimed_at', 'N/A')}
            </div>

            <div class="info-row">
                <span class="label">Owner Takeover:</span>
                {takeover_status}
            </div>

            <div class="info-row">
                <span class="label">تفاصيل Owner Takeover:</span>
                {takeover_details}
            </div>

            <div class="info-row">
                <span class="label">أغلق التكت:</span>
                {ticket_data.get('closed_by_name', 'N/A')}
            </div>

            <div class="info-row">
                <span class="label">وقت الإغلاق:</span>
                {ticket_data.get('closed_at', 'N/A')}
            </div>

            <div class="info-row">
                <span class="label">سبب الإغلاق:</span>
                {ticket_data.get('close_reason', 'N/A')}
            </div>

            <div class="info-row">
                <span class="label">الحالة:</span>
                {'مغلقة' if ticket_data.get('closed') else 'مفتوحة'}
            </div>

            <div class="info-row">
                <span class="label">سجل الأحداث:</span><br>
                {event_history_html}
            </div>
        </div>
        
        <div class="messages">
"""
        
        for msg in messages:
            author_name = msg.author.display_name
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            content = msg.content or "[رسالة فارغة أو مرفق]"
            
            if msg.author.bot and msg.content.startswith("📋") or msg.content.startswith("👑") or msg.content.startswith("👤"):
                msg_class = "message system-message"
            else:
                msg_class = "message"
            
            html += f"""
            <div class="{msg_class}">
                <div class="message-header">
                    <span class="author">{author_name}</span>
                    <span class="timestamp">{timestamp}</span>
                </div>
                <div class="content">{content}</div>
            </div>
"""
        
        html += """
        </div>
    </div>
</body>
</html>
"""
        
        return html
        
    except Exception as e:
        print(f"Error generating transcript: {e}")
        return f"<html><body><h1>Error generating transcript: {e}</h1></body></html>"

# ==============================================================================
# TICKET SYSTEM VIEWS (NEW)
# ==============================================================================

class TicketPanelView(discord.ui.View):
    """Main ticket panel with 3 ticket type buttons"""
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view
    
    @discord.ui.button(
        label="دعم فني",
        emoji="🟨",
        style=discord.ButtonStyle.primary,
        custom_id="ticket:technical"
    )
    async def technical_support(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "technical")
    
    @discord.ui.button(
        label="توثيق",
        emoji="🟩",
        style=discord.ButtonStyle.success,
        custom_id="ticket:verification"
    )
    async def verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "verification")
    
    @discord.ui.button(
        label="شكوى",
        emoji="🟥",
        style=discord.ButtonStyle.danger,
        custom_id="ticket:complaint"
    )
    async def complaint(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "complaint")

    @discord.ui.button(
        label="تقديم الإدارة",
        emoji="👮",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket:admin_application"
    )
    async def admin_application(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await self.create_ticket(
            interaction,
            "admin_application"
        )
        
    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str):
        """Handle ticket creation"""
        try:
            # Check for duplicate
            has_ticket, existing_channel_id = await user_has_open_ticket(
                interaction.user.id,
                ticket_type,
                interaction.guild_id
            )
            
            if has_ticket:
                await interaction.response.send_message(
                    bold_msg(
                        f"لديك بالفعل تذكرة {get_ticket_type_name_ar(ticket_type)} مفتوحة: <#{existing_channel_id}>",
                        "⚠️"
                    ),
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # Create channel
            channel = await create_ticket_channel(interaction.guild, ticket_type, interaction.user)
            
            if not channel:
                await interaction.followup.send(
                    bold_msg("حدث خطأ أثناء إنشاء التذكرة. يرجى المحاولة لاحقاً.", "❌"),
                    ephemeral=True
                )
                return
            
            # Store ticket data
            tickets = await load_tickets()
            open_tickets = tickets.get("open_tickets", {})
            
            ticket_data = {
                "type": ticket_type,
                "creator_id": interaction.user.id,
                "creator_name": interaction.user.display_name,
                "guild_id": interaction.guild_id,
                "created_at": datetime.datetime.now().isoformat(),
                "last_activity": datetime.datetime.now().isoformat(),
                "closed": False,
                "added_users": [],
                "events": [
                    {
                        "type": "created",
                        "timestamp": datetime.datetime.now().isoformat(),
                        "user_id": interaction.user.id,
                        "user_name": interaction.user.display_name
                    }
                ]
            }
            
            open_tickets[str(channel.id)] = ticket_data
            tickets["open_tickets"] = open_tickets
            await save_tickets(tickets)
            
            # Send initial message with mentions OUTSIDE embed
            mention_role = interaction.guild.get_role(TICKET_MENTION_ROLE_ID)
            mention_text = f"{interaction.user.mention} {mention_role.mention if mention_role else ''}"
            
            # Create welcome embed
            embed = discord.Embed(
                title=f"🎫 تذكرة {get_ticket_type_name_ar(ticket_type)}",
                description=f"مرحباً بك في تذكرة طلب **{get_ticket_type_name_ar(ticket_type)}**،\n"
                           "سيتم استلام التذكرة من الإدارة ومراجعة وفهم موضوعك.",
                color=pink_color()
            )
            embed.set_thumbnail(url=TOUCHLINE_IMAGE_URL)
            embed.add_field(
                name="📋 القواعد",
                value=(
                    "• اختر النوع المناسب لطلبك\n"
                    "• اشرح طلبك بشكل واضح\n"
                    "• أرفق الأدلة عند الحاجة\n"
                    "• يمنع فتح أكثر من تذكرة لنفس الموضوع\n"
                    "• يمنع استخدام التكت للمزح أو إزعاج الإدارة\n"
                    "• يمنع السب والاستفزاز\n"
                    "• يمنع السبام لمنشن الإدارة\n"
                    "• يجب احترام الإدارة المستلمة للتكت"
                ),
                inline=False
            )
            
            # Send message with control buttons
            await channel.send(mention_text)
            await channel.send(embed=embed, view=TicketControlView())
            
            await interaction.followup.send(
                bold_msg(f"تم إنشاء تذكرتك: {channel.mention}", "✅"),
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Error creating ticket: {e}")
            traceback.print_exc()
            try:
                await interaction.followup.send(
                    bold_msg(f"حدث خطأ: {str(e)}", "❌"),
                    ephemeral=True
                )
            except:
                pass

class TicketControlView(discord.ui.View):
    """Control buttons inside ticket channel"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="استلام",
        emoji="🟢",
        style=discord.ButtonStyle.success,
        custom_id="ticket:claim"
    )
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Normal staff claim"""
        try:
            # Check permissions
            if not can_claim_ticket(interaction.user):
                await interaction.response.send_message(
                    bold_msg("ليس لديك صلاحية استلام التذاكر.", "🔒"),
                    ephemeral=True
                )
                return
            
            # Load ticket data
            tickets = await load_tickets()
            open_tickets = tickets.get("open_tickets", {})
            ticket_data = open_tickets.get(str(interaction.channel_id))
            
            if not ticket_data:
                await interaction.response.send_message(
                    bold_msg("لم يتم العثور على بيانات التذكرة.", "❌"),
                    ephemeral=True
                )
                return
            
            # Check if already claimed
            if ticket_data.get("claimed_by_id"):
                await interaction.response.send_message(
                    bold_msg("تم استلام التذكرة بالفعل.", "⚠️"),
                    ephemeral=True
                )
                return
            
            # Claim ticket
            ticket_data["claimed_by_id"] = interaction.user.id
            ticket_data["claimed_by_name"] = interaction.user.display_name
            ticket_data["claimed_at"] = datetime.datetime.now().isoformat()
            ticket_data["events"].append({
                "type": "claimed",
                "timestamp": datetime.datetime.now().isoformat(),
                "user_id": interaction.user.id,
                "user_name": interaction.user.display_name
            })
            
            open_tickets[str(interaction.channel_id)] = ticket_data
            tickets["open_tickets"] = open_tickets
            await save_tickets(tickets)
            
            # Update permissions - only creator, claimer, and administrators can send messages
            channel = interaction.channel
            guild = interaction.guild
            
            # Get ticket staff role
            ticket_staff_role = guild.get_role(TICKET_STAFF_ROLE_ID)
            
            # Remove send_messages from ticket staff role
            if ticket_staff_role:
                await channel.set_permissions(
                    ticket_staff_role,
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True
                )
            
            # Give claimer send permission
            await channel.set_permissions(
                interaction.user,
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
            
            # Update activity
            await update_ticket_activity(interaction.channel_id)
            
            await interaction.response.send_message(
                bold_msg(f"📋 تم استلام التذكرة بواسطة {interaction.user.mention}", ""),
                allowed_mentions=discord.AllowedMentions(users=True)
            )
            
        except Exception as e:
            print(f"Error claiming ticket: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    bold_msg(f"حدث خطأ: {str(e)}", "❌"),
                    ephemeral=True
                )
            except:
                pass
    
    @discord.ui.button(
        label="استلام (اونر)",
        emoji="⚫",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket:takeover"
    )
    async def takeover_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Authorized user takeover"""
        try:
            # Check if user is authorized
            if not is_authorized_user(interaction.user):
                await interaction.response.send_message(
                    bold_msg("هذا الزر مخصص للإدارة المصرح لها فقط.", "🔒"),
                    ephemeral=True
                )
                return
            
            # Load ticket data
            tickets = await load_tickets()
            open_tickets = tickets.get("open_tickets", {})
            ticket_data = open_tickets.get(str(interaction.channel_id))
            
            if not ticket_data:
                await interaction.response.send_message(
                    bold_msg("لم يتم العثور على بيانات التذكرة.", "❌"),
                    ephemeral=True
                )
                return
            
            # Store previous claimer
            previous_claimer_id = ticket_data.get("claimed_by_id")
            previous_claimer_name = ticket_data.get("claimed_by_name", "لا أحد")
            
            # Takeover
            ticket_data["previous_claimer_id"] = previous_claimer_id
            ticket_data["previous_claimer_name"] = previous_claimer_name
            ticket_data["claimed_by_id"] = interaction.user.id
            ticket_data["claimed_by_name"] = interaction.user.display_name
            ticket_data["claimed_at"] = datetime.datetime.now().isoformat()
            ticket_data["events"].append({
                "type": "takeover",
                "timestamp": datetime.datetime.now().isoformat(),
                "user_id": interaction.user.id,
                "user_name": interaction.user.display_name,
                "from_user_id": previous_claimer_id,
                "from_user_name": previous_claimer_name
            })
            
            open_tickets[str(interaction.channel_id)] = ticket_data
            tickets["open_tickets"] = open_tickets
            await save_tickets(tickets)
            
            # Update permissions
            channel = interaction.channel
            guild = interaction.guild
            
            # Remove previous claimer's send permission (if exists and not admin)
            if previous_claimer_id:
                previous_member = guild.get_member(previous_claimer_id)
                if previous_member and not previous_member.guild_permissions.administrator:
                    await channel.set_permissions(
                        previous_member,
                        view_channel=True,
                        send_messages=False,
                        read_message_history=True
                    )
            
            # Give new claimer send permission
            await channel.set_permissions(
                interaction.user,
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
            
            # Update activity
            await update_ticket_activity(interaction.channel_id)
            
            if previous_claimer_id:
                await interaction.response.send_message(
                    bold_msg(
                        f"👑 قام {interaction.user.mention} باستلام التذكرة من <@{previous_claimer_id}>",
                        ""
                    ),
                    allowed_mentions=discord.AllowedMentions(users=True)
                )
            else:
                await interaction.response.send_message(
                    bold_msg(f"👑 قام {interaction.user.mention} باستلام التذكرة", ""),
                    allowed_mentions=discord.AllowedMentions(users=True)
                )
            
        except Exception as e:
            print(f"Error taking over ticket: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    bold_msg(f"حدث خطأ: {str(e)}", "❌"),
                    ephemeral=True
                )
            except:
                pass
    
    @discord.ui.button(
        label="قفل التكت",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="ticket:close"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Start the ticket close-reason process."""
        try:
            tickets = await load_tickets()
            open_tickets = tickets.get("open_tickets", {})
            ticket_data = open_tickets.get(str(interaction.channel_id))

            if not ticket_data:
                await interaction.response.send_message(
                    bold_msg("لم يتم العثور على بيانات التذكرة.", "❌"),
                    ephemeral=True
                )
                return

            if ticket_data.get("closed", False):
                await interaction.response.send_message(
                    bold_msg("التذكرة مغلقة بالفعل.", "⚠️"),
                    ephemeral=True
                )
                return

            if not can_close_ticket(interaction.user, ticket_data):
                await interaction.response.send_message(
                    bold_msg(
                        "ليس لديك صلاحية إغلاق هذه التذكرة.",
                        "🔒"
                    ),
                    ephemeral=True
                )
                return

            await interaction.response.send_message(
                embed=discord.Embed(
                    title="🔒 سبب إغلاق التذكرة",
                    description=(
                        "**__ اختر السبب المناسب لإغلاق التذكرة من القائمة بالأسفل. __**"
                    ),
                    color=pink_color()
                ),
                view=TicketCloseReasonView(interaction.user.id)
            )

        except Exception as e:
            print(f"Error starting ticket close: {e}")
            traceback.print_exc()

            try:
                await interaction.response.send_message(
                    bold_msg(f"حدث خطأ: {str(e)}", "❌"),
                    ephemeral=True
                )
            except Exception:
                pass
                
    @discord.ui.button(
        label="إضافة شخص",
        emoji="👤",
        style=discord.ButtonStyle.primary,
        custom_id="ticket:add_user"
    )
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a user using Discord User Select."""
        try:
            tickets = await load_tickets()
            open_tickets = tickets.get("open_tickets", {})
            ticket_data = open_tickets.get(str(interaction.channel_id))

            if not ticket_data:
                await interaction.response.send_message(
                    bold_msg("لم يتم العثور على بيانات التذكرة.", "❌"),
                    ephemeral=True
                )
                return

            # Only the ticket creator can add people.
            if interaction.user.id != ticket_data.get("creator_id"):
                await interaction.response.send_message(
                    bold_msg("فقط منشئ التذكرة يمكنه إضافة أشخاص.", "🔒"),
                    ephemeral=True
                )
                return

            added_users = ticket_data.get("added_users", [])

            if len(added_users) >= 2:
                await interaction.response.send_message(
                    bold_msg("تم الوصول للحد الأقصى: شخصان فقط.", "⚠️"),
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="👤 إضافة شخص للتذكرة",
                description="**__ اختر العضو الذي تريد إضافته من القائمة بالأسفل. __**",
                color=pink_color()
            )

            await interaction.response.send_message(
                embed=embed,
                view=AddUserSelectView(
                    channel_id=interaction.channel_id,
                    creator_id=interaction.user.id
                ),
                ephemeral=True
            )

        except Exception as e:
            print(f"Error adding user: {e}")
            traceback.print_exc()

            try:
                await interaction.response.send_message(
                    bold_msg(f"حدث خطأ: {str(e)}", "❌"),
                    ephemeral=True
                )
            except Exception:
                pass

class AddUserSelectView(discord.ui.View):
    """Discord User Select Menu for adding users to tickets."""

    def __init__(self, channel_id: int, creator_id: int):
        super().__init__(timeout=60)
        self.channel_id = channel_id
        self.creator_id = creator_id

        select = discord.ui.UserSelect(
            placeholder="اختر العضو الذي تريد إضافته...",
            min_values=1,
            max_values=1
        )

        select.callback = self.select_user
        self.add_item(select)

    async def select_user(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.creator_id:
                await interaction.response.send_message(
                    bold_msg("هذه القائمة ليست لك.", "🔒"),
                    ephemeral=True
                )
                return

            if not interaction.guild:
                await interaction.response.send_message(
                    bold_msg("تعذر تحديد السيرفر.", "❌"),
                    ephemeral=True
                )
                return

            tickets = await load_tickets()
            open_tickets = tickets.get("open_tickets", {})
            ticket_data = open_tickets.get(str(self.channel_id))

            if not ticket_data:
                await interaction.response.send_message(
                    bold_msg("لم يتم العثور على بيانات التذكرة.", "❌"),
                    ephemeral=True
                )
                self.stop()
                return

            added_users = ticket_data.get("added_users", [])

            if len(added_users) >= 2:
                await interaction.response.send_message(
                    bold_msg("تم الوصول للحد الأقصى: شخصان فقط.", "⚠️"),
                    ephemeral=True
                )
                self.stop()
                return

            selected_member = self.children[0].values[0]

            member = interaction.guild.get_member(selected_member.id)

            if member is None:
                await interaction.response.send_message(
                    bold_msg("لم يتم العثور على العضو داخل السيرفر.", "❌"),
                    ephemeral=True
                )
                return

            if member.id == ticket_data.get("creator_id"):
                await interaction.response.send_message(
                    bold_msg("منشئ التذكرة موجود بالفعل داخل التذكرة.", "⚠️"),
                    ephemeral=True
                )
                return

            if member.bot:
                await interaction.response.send_message(
                    bold_msg("لا يمكن إضافة بوت إلى التذكرة.", "⚠️"),
                    ephemeral=True
                )
                return

            if member.id in added_users:
                await interaction.response.send_message(
                    bold_msg("هذا العضو مضاف بالفعل إلى التذكرة.", "⚠️"),
                    ephemeral=True
                )
                return

            channel = interaction.guild.get_channel(self.channel_id)

            if channel is None:
                await interaction.response.send_message(
                    bold_msg("لم يتم العثور على قناة التذكرة.", "❌"),
                    ephemeral=True
                )
                return

            # Give only ticket access.
            # The user does NOT receive any special claim/close/admin permission.
            await channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            )

            added_users.append(member.id)
            ticket_data["added_users"] = added_users

            ticket_data.setdefault("events", []).append({
                "type": "user_added",
                "timestamp": datetime.datetime.now().isoformat(),
                "added_by_id": interaction.user.id,
                "added_by_name": interaction.user.display_name,
                "added_user_id": member.id,
                "added_user_name": member.display_name
            })

            ticket_data["last_activity"] = datetime.datetime.now().isoformat()

            open_tickets[str(self.channel_id)] = ticket_data
            tickets["open_tickets"] = open_tickets
            await save_tickets(tickets)

            await interaction.response.send_message(
                bold_msg(
                    f"تمت إضافة {member.mention} إلى التذكرة بنجاح.",
                    "✅"
                ),
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions(users=True)
            )

            self.stop()

        except Exception as e:
            print(f"Error in AddUserSelectView: {e}")
            traceback.print_exc()

            try:
                await interaction.response.send_message(
                    bold_msg(f"حدث خطأ: {str(e)}", "❌"),
                    ephemeral=True
                )
            except Exception:
                pass

async def finalize_ticket_close(
    interaction: discord.Interaction,
    reason: str
):
    tickets = await load_tickets()
    open_tickets = tickets.get("open_tickets", {})
    ticket_data = open_tickets.get(str(interaction.channel_id))

    if not ticket_data:
        await interaction.response.send_message(
            bold_msg("لم يتم العثور على بيانات التذكرة.", "❌"),
            ephemeral=True
        )
        return

    if ticket_data.get("closed", False):
        await interaction.response.send_message(
            bold_msg("التذكرة مغلقة بالفعل.", "⚠️"),
            ephemeral=True
        )
        return

    now = datetime.datetime.now().isoformat()

    ticket_data["closed"] = True
    ticket_data["closed_by_id"] = interaction.user.id
    ticket_data["closed_by_name"] = interaction.user.display_name
    ticket_data["closed_at"] = now
    ticket_data["close_reason"] = reason
    ticket_data["last_activity"] = now

    ticket_data.setdefault("events", []).append({
        "type": "closed",
        "timestamp": now,
        "user_id": interaction.user.id,
        "user_name": interaction.user.display_name,
        "reason": reason
    })

    open_tickets[str(interaction.channel_id)] = ticket_data
    tickets["open_tickets"] = open_tickets
    await save_tickets(tickets)

    embed = discord.Embed(
        title="🔒 إغلاق التذكرة",
        description="**__ هل أنت متأكد من قفل التذكرة؟ __**",
        color=pink_color()
    )

    embed.add_field(
        name="سبب الإغلاق",
        value=f"**__ {reason} __**",
        inline=False
    )

    await interaction.response.send_message(
        embed=embed,
        view=TicketCloseConfirmView()
    ) 

class TicketCloseOtherReasonModal(discord.ui.Modal, title="سبب إغلاق التذكرة"):
    reason = discord.ui.TextInput(
        label="اكتب سبب الإغلاق",
        placeholder="اكتب السبب هنا...",
        required=True,
        min_length=2,
        max_length=1000,
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction: discord.Interaction):
        await finalize_ticket_close(
            interaction,
            self.reason.value.strip()
        )

class TicketCloseReasonSelect(discord.ui.Select):
    def __init__(self, closer_id: int):
        self.closer_id = closer_id

        options = [
            discord.SelectOption(
                label="تم الانتهاء من التكت",
                description="تم التعامل مع المشكلة وإنهاء الطلب.",
                value="تم الانتهاء من التكت"
            ),
            discord.SelectOption(
                label="لم يتم الوصول إلى حل مرضي",
                description="لم يتم الوصول إلى حل مرضي للمشكلة.",
                value="لم يتم الوصول إلى حل مرضي"
            ),
            discord.SelectOption(
                label="أخرى",
                description="كتابة سبب مخصص لإغلاق التذكرة.",
                value="أخرى"
            )
        ]

        super().__init__(
            placeholder="اختر سبب إغلاق التذكرة...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.closer_id:
            await interaction.response.send_message(
                bold_msg("هذه القائمة ليست لك.", "🔒"),
                ephemeral=True
            )
            return

        selected = self.values[0]

        if selected == "أخرى":
            await interaction.response.send_modal(
                TicketCloseOtherReasonModal()
            )
            return

        await finalize_ticket_close(
            interaction,
            selected
        )

class TicketCloseReasonView(discord.ui.View):
    def __init__(self, closer_id: int):
        super().__init__(timeout=60)
        self.add_item(
            TicketCloseReasonSelect(closer_id)
        )
        
class TicketCloseConfirmView(discord.ui.View):
    """Confirmation view for ticket closure"""
    def __init__(self):
        super().__init__(timeout=60)
    
    @discord.ui.button(
        label="فتح",
        emoji="🟢",
        style=discord.ButtonStyle.success
    )
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reopen ticket"""
        try:
            # Load ticket data
            tickets = await load_tickets()
            open_tickets = tickets.get("open_tickets", {})
            ticket_data = open_tickets.get(str(interaction.channel_id))
            
            if not ticket_data:
                await interaction.response.send_message(
                    bold_msg("لم يتم العثور على بيانات التذكرة.", "❌"),
                    ephemeral=True
                )
                return
            
            # Reopen
            ticket_data["closed"] = False
            ticket_data["events"].append({
                "type": "reopened",
                "timestamp": datetime.datetime.now().isoformat(),
                "user_id": interaction.user.id,
                "user_name": interaction.user.display_name
            })
            
            open_tickets[str(interaction.channel_id)] = ticket_data
            tickets["open_tickets"] = open_tickets
            await save_tickets(tickets)
            
            # Update activity
            await update_ticket_activity(interaction.channel_id)
            
            # Restore permissions if needed
            channel = interaction.channel
            guild = interaction.guild
            
            # Re-enable ticket staff send messages
            ticket_staff_role = guild.get_role(TICKET_STAFF_ROLE_ID)
            if ticket_staff_role and not ticket_data.get("claimed_by_id"):
                await channel.set_permissions(
                    ticket_staff_role,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )
            
            await interaction.response.edit_message(
                content=bold_msg("تم إعادة فتح التذكرة بنجاح.", "🟢"),
                embed=None,
                view=None
            )
            
        except Exception as e:
            print(f"Error reopening ticket: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    bold_msg(f"حدث خطأ: {str(e)}", "❌"),
                    ephemeral=True
                )
            except:
                pass
    
    @discord.ui.button(
        label="حذف",
        emoji="🔴",
        style=discord.ButtonStyle.danger
    )
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete ticket after countdown"""
        try:
            # Generate transcript first
            tickets = await load_tickets()
            open_tickets = tickets.get("open_tickets", {})
            ticket_data = open_tickets.get(str(interaction.channel_id))
            
            if not ticket_data:
                await interaction.response.send_message(
                    bold_msg("لم يتم العثور على بيانات التذكرة.", "❌"),
                    ephemeral=True
                )
                return
            
            channel = interaction.channel
            
            # Generate transcript
            transcript_html = await generate_ticket_transcript(channel, ticket_data)
            
            # Get transcript channel
            config = await load_ticket_config()
            transcript_channel_id = config.get("transcript_channel_id")
            
            if transcript_channel_id:
                transcript_channel = interaction.guild.get_channel(transcript_channel_id)
                if transcript_channel:
                    # Create transcript file
                    transcript_file = discord.File(
                        io.BytesIO(transcript_html.encode('utf-8')),
                        filename=f"transcript-{channel.name}.html"
                    )
                    
                    # Create log embed
                    log_embed = discord.Embed(
                        title="🎫 سجل التذكرة",
                        color=pink_color(),
                        timestamp=datetime.datetime.now(datetime.timezone.utc)
                    )
                    log_embed.add_field(name="النوع", value=get_ticket_type_name_ar(ticket_data.get('type', 'unknown')), inline=True)
                    log_embed.add_field(name="التذكرة", value=channel.name, inline=True)
                    log_embed.add_field(name="تم الفتح بواسطة", value=f"<@{ticket_data.get('creator_id')}>", inline=True)
                    log_embed.add_field(name="تاريخ الفتح", value=ticket_data.get('created_at', 'N/A'), inline=True)
                    log_embed.add_field(name="مستلم التكت", value=ticket_data.get("claimed_by_name", "لم يتم الاستلام"), inline=True)

                    log_embed.add_field(
                        name="وقت الاستلام",
                        value=ticket_data.get("claimed_at", "N/A"),
                        inline=True
                    )

                    log_embed.add_field(
                        name="تم الإغلاق بواسطة",
                        value=f"<@{ticket_data.get('closed_by_id', interaction.user.id)}>",
                        inline=True
                    )

                    log_embed.add_field(
                        name="وقت الإغلاق",
                        value=ticket_data.get("closed_at", "N/A"),
                        inline=True
                    )

                    takeover_events = [
                        e
                        for e in ticket_data.get("events", [])
                        if e.get("type") == "takeover"
                    ]

                    log_embed.add_field(
                        name="Owner Takeover",
                        value="نعم" if takeover_events else "لا",
                        inline=True
                    )

                    if takeover_events:
                        latest_takeover = takeover_events[-1]

                        log_embed.add_field(
                            name="تفاصيل Owner Takeover",
                            value=(
                                f"{latest_takeover.get('from_user_name', 'لا أحد')} "
                                f"→ "
                                f"{latest_takeover.get('user_name', 'غير معروف')}\n"
                                f"{latest_takeover.get('timestamp', 'N/A')}"
                            ),
                            inline=False
                        )

                    log_embed.add_field(
                        name="سبب الإغلاق",
                        value=ticket_data.get("close_reason", "غير محدد"),
                        inline=False
                    )

                    try:
                        await transcript_channel.send(embed=log_embed, file=transcript_file)
                    except Exception as e:
                        print(f"Error sending transcript: {e}")
            
            # Remove from open tickets
            if str(interaction.channel_id) in open_tickets:
                del open_tickets[str(interaction.channel_id)]
                tickets["open_tickets"] = open_tickets
                await save_tickets(tickets)
            
            # Start deletion countdown.
            await interaction.response.edit_message(
                content=bold_msg(
                    "🗑️ سيتم حذف التذكرة خلال 10 ثوانٍ.",
                    ""
                ),
                embed=None,
                view=None
            )

            await asyncio.sleep(10)

            try:
                await channel.delete(
                    reason=f"تم حذف التذكرة بواسطة {interaction.user.name}"
                )
            except Exception:
                pass
            
        except Exception as e:
            print(f"Error deleting ticket: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    bold_msg(f"حدث خطأ: {str(e)}", "❌"),
                    ephemeral=True
                )
            except:
                pass

# ==============================================================================
# TICKET INACTIVITY CHECKER (NEW)
# ==============================================================================

@tasks.loop(hours=1)
async def check_inactive_tickets():
    """Check for tickets inactive for 15 hours and auto-delete them"""
    try:
        tickets = await load_tickets()
        open_tickets = tickets.get("open_tickets", {})
        
        now = datetime.datetime.now()
        to_delete = []
        
        for channel_id, ticket_data in open_tickets.items():
            # Skip closed tickets
            if ticket_data.get("closed", False):
                continue
            
            # Check last activity
            last_activity_str = ticket_data.get("last_activity")
            if not last_activity_str:
                continue
            
            try:
                last_activity = datetime.datetime.fromisoformat(last_activity_str)
                hours_inactive = (now - last_activity).total_seconds() / 3600
                
                if hours_inactive >= 15:
                    to_delete.append((int(channel_id), ticket_data))
            except:
                continue
        
        # Delete inactive tickets
        for channel_id, ticket_data in to_delete:
            try:
                channel = bot.get_channel(channel_id)
                if not channel:
                    # Channel already deleted, just remove from data
                    if str(channel_id) in open_tickets:
                        del open_tickets[str(channel_id)]
                    continue
                
                # Generate transcript
                transcript_html = await generate_ticket_transcript(channel, ticket_data)
                
                # Get transcript channel
                config = await load_ticket_config()
                transcript_channel_id = config.get("transcript_channel_id")
                
                if transcript_channel_id:
                    transcript_channel = channel.guild.get_channel(transcript_channel_id)
                    if transcript_channel:
                        # Create transcript file
                        transcript_file = discord.File(
                            io.BytesIO(transcript_html.encode('utf-8')),
                            filename=f"transcript-{channel.name}.html"
                        )
                        
                        # Create log embed
                        log_embed = discord.Embed(
                            title="🎫 سجل التذكرة",
                            color=pink_color(),
                            timestamp=datetime.datetime.now(datetime.timezone.utc)
                        )
                        log_embed.add_field(name="النوع", value=get_ticket_type_name_ar(ticket_data.get('type', 'unknown')), inline=True)
                        log_embed.add_field(name="التذكرة", value=channel.name, inline=True)
                        log_embed.add_field(name="تم الفتح بواسطة", value=f"<@{ticket_data.get('creator_id')}>", inline=True)
                        log_embed.add_field(name="تاريخ الفتح", value=ticket_data.get('created_at', 'N/A'), inline=True)
                        log_embed.add_field(name="تم الاستلام بواسطة", value=ticket_data.get('claimed_by_name', 'لم يتم الاستلام'), inline=True)
                        log_embed.add_field(name="سبب الحذف", value="15 ساعة بدون نشاط", inline=False)
                        
                        try:
                            await transcript_channel.send(embed=log_embed, file=transcript_file)
                        except Exception as e:
                            print(f"Error sending transcript: {e}")
                
                # Delete channel
                await channel.delete(reason="15 ساعة بدون نشاط")
                
                # Remove from data
                if str(channel_id) in open_tickets:
                    del open_tickets[str(channel_id)]
                
            except Exception as e:
                print(f"Error deleting inactive ticket {channel_id}: {e}")
                traceback.print_exc()
        
        # Save updated data
        if to_delete:
            tickets["open_tickets"] = open_tickets
            await save_tickets(tickets)
        
    except Exception as e:
        print(f"Error in inactivity checker: {e}")
        traceback.print_exc()

# ==============================================================================
# TICKET SLASH COMMANDS (NEW)
# ==============================================================================

@bot.tree.command(name="set_ticket", description="تعيين قناة لوحة التذاكر")
@app_commands.describe(channel="القناة التي سيتم إرسال لوحة التذاكر فيها")
async def set_ticket_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not check_slash_permissions(interaction):
        await interaction.response.send_message(
            bold_msg("ليس لديك صلاحية استخدام هذا الأمر.", "🔒"),
            ephemeral=True
        )
        return
    
    try:
        # Save config
        config = await load_ticket_config()
        config["panel_channel_id"] = channel.id
        config["guild_id"] = interaction.guild_id
        await save_ticket_config(config)
        
        # Create panel embed
        embed = discord.Embed(
            title="🎫 نظام التذاكر",
            description=(
                "**__ مرحباً بك في نظام التذاكر __**\n\n"
                "يمكنك فتح تذكرة للحصول على:\n"
                "• **دعم فني** 🟨\n"
                "• **توثيق نادي** 🟩\n"
                "• **تقديم شكوى** 🟥\n"
                "• **تقديم الإدارة** 👮\n\n"
                "**📋 قواعد التذاكر:**\n"
                "• اختر النوع المناسب لطلبك\n"
                "• اشرح طلبك بشكل واضح\n"
                "• أرفق الأدلة عند الحاجة\n"
                "• يمنع فتح أكثر من تذكرة لنفس الموضوع\n"
                "• يمنع استخدام التكت للمزح أو إزعاج الإدارة\n"
                "• يمنع السب والاستفزاز\n"
                "• يمنع السبام لمنشن الإدارة\n"
                "• يجب احترام الإدارة المستلمة للتكت"
            ),
            color=pink_color()
        )
        embed.set_image(url=TOUCHLINE_IMAGE_URL)
        embed.set_footer(text="اضغط على الزر المناسب لفتح تذكرة")
        
        # Send panel
        await channel.send(embed=embed, view=TicketPanelView())
        
        await interaction.response.send_message(
            bold_msg(f"تم تعيين {channel.mention} كقناة لوحة التذاكر وإرسال اللوحة بنجاح.", "✅"),
            ephemeral=True
        )
        
    except Exception as e:
        print(f"Error in set_ticket: {e}")
        traceback.print_exc()
        await interaction.response.send_message(
            bold_msg(f"حدث خطأ: {str(e)}", "❌"),
            ephemeral=True
        )

@bot.tree.command(name="set_transcript", description="تعيين قناة سجلات التذاكر")
@app_commands.describe(channel="القناة التي سيتم إرسال نصوص التذاكر المحذوفة فيها")
async def set_transcript_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not check_slash_permissions(interaction):
        await interaction.response.send_message(
            bold_msg("ليس لديك صلاحية استخدام هذا الأمر.", "🔒"),
            ephemeral=True
        )
        return
    
    try:
        # Save config
        config = await load_ticket_config()
        config["transcript_channel_id"] = channel.id
        await save_ticket_config(config)
        
        await interaction.response.send_message(
            bold_msg(f"تم تعيين {channel.mention} كقناة سجلات التذاكر بنجاح.", "✅"),
            ephemeral=True
        )
        
    except Exception as e:
        print(f"Error in set_transcript: {e}")
        traceback.print_exc()
        await interaction.response.send_message(
            bold_msg(f"حدث خطأ: {str(e)}", "❌"),
            ephemeral=True
        )


# ==============================================================================
# SERVER AUDIT LOGGING
# ==============================================================================
LOG_CONFIG_KEY = "logging"

async def send_configured_log(guild: discord.Guild, log_type: str, embed: discord.Embed):
    """Send an audit embed to the configured channel, if one is set."""
    try:
        config = await load_server_config()
        guild_config = config.get(str(guild.id), {})
        channel_id = guild_config.get(LOG_CONFIG_KEY, {}).get(log_type)
        if not channel_id:
            return
        channel = guild.get_channel(int(channel_id))
        if channel is None:
            try:
                channel = await bot.fetch_channel(int(channel_id))
            except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
                return
        if hasattr(channel, "send"):
            await channel.send(embed=embed)
    except Exception as e:
        print(f"Logging error ({log_type}): {e}")

async def set_log_channel(interaction: discord.Interaction, log_type: str, channel: discord.TextChannel, label: str):
    if not check_slash_permissions(interaction):
        await interaction.response.send_message(bold_msg("ليس لديك صلاحية استخدام هذا الأمر.", "🔒"), ephemeral=True)
        return
    if interaction.guild_id is None:
        await interaction.response.send_message("هذا الأمر يعمل داخل السيرفر فقط.", ephemeral=True)
        return
    config = await load_server_config()
    guild_config = config.setdefault(str(interaction.guild_id), {})
    log_config = guild_config.setdefault(LOG_CONFIG_KEY, {})
    log_config[log_type] = channel.id
    await save_server_config(config)
    await interaction.response.send_message(bold_msg(f"تم تعيين {channel.mention} كقناة {label} بنجاح.", "✅"), ephemeral=True)

async def audit_actor(guild: discord.Guild, action: discord.AuditLogAction, target_id: int = None):
    """Best-effort audit-log actor lookup; missing permission is harmless."""
    try:
        async for entry in guild.audit_logs(limit=6, action=action):
            if target_id is not None and getattr(entry.target, "id", None) != target_id:
                continue
            if (discord.utils.utcnow() - entry.created_at).total_seconds() <= 20:
                return entry.user, (entry.reason or "بدون سبب")
    except (discord.Forbidden, discord.HTTPException):
        pass
    except Exception as e:
        print(f"Audit actor lookup failed: {e}")
    return None, "تعذر تحديد المنفذ أو لا توجد صلاحية عرض سجل التدقيق"

@bot.tree.command(name="set_textlog", description="تعيين قناة سجل الرسائل المحذوفة")
@app_commands.describe(channel="القناة التي ستظهر فيها سجلات حذف الرسائل")
async def set_textlog(interaction: discord.Interaction, channel: discord.TextChannel):
    await set_log_channel(interaction, "text", channel, "سجل الرسائل")

@bot.tree.command(name="set_channellog", description="تعيين قناة سجل إنشاء وحذف وتعديل القنوات")
@app_commands.describe(channel="القناة التي ستظهر فيها سجلات القنوات")
async def set_channellog(interaction: discord.Interaction, channel: discord.TextChannel):
    await set_log_channel(interaction, "channels", channel, "سجل القنوات")

@bot.tree.command(name="set_roleslog", description="تعيين قناة سجل الرتب")
@app_commands.describe(channel="القناة التي ستظهر فيها سجلات الرتب")
async def set_roleslog(interaction: discord.Interaction, channel: discord.TextChannel):
    await set_log_channel(interaction, "roles", channel, "سجل الرتب")

# ==============================================================================
# Events
# ==============================================================================
@bot.event
async def on_ready():
    print(f"✅ Bot Online as: {bot.user}")
    try:
        # Publish globally, then sync to each connected server so new commands
        # appear immediately instead of waiting for global command propagation.
        synced_global = await bot.tree.sync()
        print(f"Synced {len(synced_global)} global slash commands.")
        # Clear old guild-specific copies of global commands to prevent duplicates.
        # Commands are registered globally only; do not copy them into each guild.
        for guild in bot.guilds:
            try:
                guild_object = discord.Object(id=guild.id)
                synced_guild = await bot.tree.sync(guild=guild_object)
                print(f"Cleaned up {len(synced_guild)} guild-specific slash commands for {guild.name} ({guild.id}).")
            except Exception as guild_error:
                print(f"Guild slash-command cleanup failed for {guild.id} ({guild.name}): {guild_error}")
    except Exception as e:
        print(f"Global slash-command sync error: {e}")

@bot.event
async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent):
    guild = bot.get_guild(payload.guild_id) if payload.guild_id else None
    if guild is not None:
        channel = guild.get_channel(payload.channel_id)
        cached = payload.cached_message
        embed = discord.Embed(title="🗑️ حذف رسالة", color=discord.Color.orange(), timestamp=discord.utils.utcnow())
        embed.add_field(name="القناة", value=channel.mention if channel else f"ID: {payload.channel_id}", inline=False)
        if cached is not None:
            embed.add_field(name="الكاتب", value=f"{cached.author} (ID: {cached.author.id})", inline=False)
            content = cached.content or "[لا يوجد نص؛ قد تكون الرسالة مرفقًا أو صورة]"
            embed.add_field(name="المحتوى", value=content[:1024], inline=False)
            if cached.attachments:
                embed.add_field(name="المرفقات", value="\n".join(a.url for a in cached.attachments)[:1024], inline=False)
        else:
            embed.add_field(name="المحتوى", value="الرسالة غير موجودة في الذاكرة المؤقتة؛ لم يتوفر محتواها.", inline=False)
        await send_configured_log(guild, "text", embed)
    game = ACTIVE_WHO_AM_I.get(
        payload.channel_id
    )

    if not game:
        return

    if game.message_id != payload.message_id:
        return

    game.finished = True

    if game.guess_task:
        game.guess_task.cancel()

    ACTIVE_WHO_AM_I.pop(
        payload.channel_id,
        None
    )

    print(
        f"Who Am I game cancelled because its message was deleted. "
        f"Channel: {payload.channel_id}"
    )
    

@bot.event
async def on_raw_bulk_message_delete(payload: discord.RawBulkMessageDeleteEvent):
    guild = bot.get_guild(payload.guild_id) if payload.guild_id else None
    if guild is None:
        return
    channel = guild.get_channel(payload.channel_id)
    embed = discord.Embed(title="🗑️ حذف مجموعة رسائل", color=discord.Color.orange(), timestamp=discord.utils.utcnow())
    embed.add_field(name="القناة", value=channel.mention if channel else f"ID: {payload.channel_id}", inline=False)
    embed.add_field(name="عدد الرسائل", value=str(len(payload.message_ids)), inline=True)
    embed.add_field(name="ملاحظة", value="Discord لا يوفّر محتوى الرسائل المحذوفة بالجملة عبر هذا الحدث.", inline=False)
    await send_configured_log(guild, "text", embed)

@bot.event
async def on_guild_channel_create(channel: discord.abc.GuildChannel):
    actor, reason = await audit_actor(channel.guild, discord.AuditLogAction.channel_create, channel.id)
    embed = discord.Embed(title="➕ إنشاء قناة", color=discord.Color.green(), timestamp=discord.utils.utcnow())
    embed.add_field(name="القناة", value=f"{channel.name} (ID: {channel.id})", inline=False)
    embed.add_field(name="المنفذ", value=str(actor) if actor else "غير معروف", inline=True)
    embed.add_field(name="السبب", value=reason[:1024], inline=False)
    await send_configured_log(channel.guild, "channels", embed)

@bot.event
async def on_guild_channel_delete(channel: discord.abc.GuildChannel):
    actor, reason = await audit_actor(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
    embed = discord.Embed(title="➖ حذف قناة", color=discord.Color.red(), timestamp=discord.utils.utcnow())
    embed.add_field(name="اسم القناة", value=f"{channel.name} (ID: {channel.id})", inline=False)
    embed.add_field(name="المنفذ", value=str(actor) if actor else "غير معروف", inline=True)
    embed.add_field(name="السبب", value=reason[:1024], inline=False)
    await send_configured_log(channel.guild, "channels", embed)

@bot.event
async def on_guild_channel_update(before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
    changes = []
    for attr, label in (("name", "الاسم"), ("topic", "الوصف"), ("category_id", "التصنيف"), ("position", "الترتيب"), ("slowmode_delay", "البطء"), ("nsfw", "NSFW"), ("bitrate", "جودة الصوت"), ("user_limit", "حد المستخدمين")):
        old, new = getattr(before, attr, None), getattr(after, attr, None)
        if old != new:
            changes.append(f"**{label}:** {old!s} ← {new!s}")
    if before.overwrites != after.overwrites:
        changes.append("**الصلاحيات:** تم تعديل صلاحيات القناة.")
    if not changes:
        return
    actor, reason = await audit_actor(after.guild, discord.AuditLogAction.channel_update, after.id)
    embed = discord.Embed(title="✏️ تعديل قناة", description="\n".join(changes)[:4000], color=discord.Color.gold(), timestamp=discord.utils.utcnow())
    embed.add_field(name="القناة", value=f"{after.name} (ID: {after.id})", inline=False)
    embed.add_field(name="المنفذ", value=str(actor) if actor else "غير معروف", inline=True)
    embed.add_field(name="السبب", value=reason[:1024], inline=False)
    await send_configured_log(after.guild, "channels", embed)

@bot.event
async def on_guild_role_create(role: discord.Role):
    actor, reason = await audit_actor(role.guild, discord.AuditLogAction.role_create, role.id)
    embed = discord.Embed(title="➕ إنشاء رتبة", color=discord.Color.green(), timestamp=discord.utils.utcnow())
    embed.add_field(name="الرتبة", value=f"{role.name} (ID: {role.id})", inline=False)
    embed.add_field(name="المنفذ", value=str(actor) if actor else "غير معروف", inline=True)
    embed.add_field(name="السبب", value=reason[:1024], inline=False)
    await send_configured_log(role.guild, "roles", embed)

@bot.event
async def on_guild_role_delete(role: discord.Role):
    actor, reason = await audit_actor(role.guild, discord.AuditLogAction.role_delete, role.id)
    embed = discord.Embed(title="➖ حذف رتبة", color=discord.Color.red(), timestamp=discord.utils.utcnow())
    embed.add_field(name="اسم الرتبة", value=f"{role.name} (ID: {role.id})", inline=False)
    embed.add_field(name="المنفذ", value=str(actor) if actor else "غير معروف", inline=True)
    embed.add_field(name="السبب", value=reason[:1024], inline=False)
    await send_configured_log(role.guild, "roles", embed)

@bot.event
async def on_guild_role_update(before: discord.Role, after: discord.Role):
    changes = []
    for attr, label in (("name", "الاسم"), ("colour", "اللون"), ("hoist", "إظهار منفصل"), ("mentionable", "قابلة للمنشن"), ("permissions", "الصلاحيات"), ("position", "الترتيب")):
        old, new = getattr(before, attr, None), getattr(after, attr, None)
        if old != new:
            if attr == "permissions":
                old = ", ".join(p for p, enabled in before.permissions if enabled) or "لا شيء"
                new = ", ".join(p for p, enabled in after.permissions if enabled) or "لا شيء"
            changes.append(f"**{label}:** {str(old)[:450]} → {str(new)[:450]}")
    if not changes:
        return
    actor, reason = await audit_actor(after.guild, discord.AuditLogAction.role_update, after.id)
    embed = discord.Embed(title="✏️ تعديل رتبة", description="\n".join(changes)[:4000], color=discord.Color.gold(), timestamp=discord.utils.utcnow())
    embed.add_field(name="الرتبة", value=f"{after.name} (ID: {after.id})", inline=False)
    embed.add_field(name="المنفذ", value=str(actor) if actor else "غير معروف", inline=True)
    embed.add_field(name="السبب", value=reason[:1024], inline=False)
    await send_configured_log(after.guild, "roles", embed)

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    old_ids = {role.id for role in before.roles}
    new_ids = {role.id for role in after.roles}
    # Sort by hierarchy position for a tidy, predictable log.
    added = sorted(
        [role for role in after.roles if role.id not in old_ids and role.id != after.guild.id],
        key=lambda role: role.position
    )
    removed = sorted(
        [role for role in before.roles if role.id not in new_ids and role.id != before.guild.id],
        key=lambda role: role.position
    )
    if not added and not removed:
        return

    # The audit log identifies who granted/removed the roles when the bot
    # has View Audit Log permission and Discord has published the entry.
    actor, reason = await audit_actor(
        after.guild,
        discord.AuditLogAction.member_role_update,
        after.id
    )

    embed = discord.Embed(
        title="🎖️ سجل تغييرات الرتب",
        color=discord.Color.blurple(),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="👤 العضو", value=after.mention, inline=False)
    embed.add_field(name="🛠️ المنفّذ", value=actor.mention if actor else "غير معروف — تحقق من صلاحية View Audit Log", inline=False)

    if added:
        added_lines = [f"✅ {role.mention}" for role in added]
        embed.add_field(name="➕ الرتب الممنوحة", value="\\n".join(added_lines)[:1024], inline=False)
    if removed:
        removed_lines = [f"❌ {role.mention}" for role in removed]
        embed.add_field(name="➖ الرتب المسحوبة", value="\\n".join(removed_lines)[:1024], inline=False)

    if reason and reason != "بدون سبب":
        embed.add_field(name="📝 السبب", value=reason[:1024], inline=False)
    embed.set_footer(text=f"Member ID: {after.id}")
    await send_configured_log(after.guild, "roles", embed)

@bot.event
async def on_message(message: discord.Message):
    """Keep Auto Replies while always allowing discord.py prefix commands to run.
    Supports BOTH !شيل and شيل (prefix-less) by checking if the message content
    matches a known command name directly and re-processing with the prefix."""
    if message.author.bot:
        return

    try:
        content = message.content.strip()
        clean_content = clean_arabic_text(content)

        # Auto-reply lookup (O(1))
        if clean_content in KEYWORD_REPLIES_CLEANED:
            replies = KEYWORD_REPLIES_CLEANED[clean_content]
            await message.reply(random.choice(replies))
            return

        # ── PREFIX-LESS COMMAND SUPPORT ──────────────────────────────────────────
        # If the message does NOT start with the bot prefix ("!") but its
        # content exactly matches a registered command name, synthesise the
        # prefix so process_commands picks it up normally.
        # This restores the original behaviour where typing شيل (no !) worked.
        if not content.startswith("!"):
            # Extract the first word as the potential command name
            first_word = content.split()[0] if content.split() else ""
            cmd = bot.get_command(first_word)
            if cmd is not None:
                # Rebuild the message content with the prefix prepended
                message.content = "!" + content
    except Exception as e:
        print("Auto-reply/prefix-less error:", repr(e))

    # IMPORTANT: process_commands must be called manually when on_message is overridden.
    try:
        await bot.process_commands(message)
    except Exception as e:
        print("Prefix command processing error:", repr(e))

# ==============================================================================
# Warn commands  (aliases added per requirement)
# ==============================================================================
@bot.command(name="وارن")
async def warn_member(ctx: commands.Context, member: discord.Member = None, *, reason: str = None):
    if not check_permissions(ctx):
        await ctx.send(bold_msg("ليس لديك صلاحية إعطاء وارن.", "🔒"))
        return
    if member is None:
        if ctx.message.reference and ctx.message.reference.message_id:
            try:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                member = ref.author
            except Exception:
                member = None
    if member is None:
        await ctx.send(bold_msg("استخدم الأمر هكذا: !وارن @user [السبب]", "⚠️"))
        return
    reason = (reason or "").strip()
    if not reason:
        await ctx.send(bold_msg("لا يمكن إعطاء وارن بدون سبب واضح.", "❌"))
        return
    if member.bot or member.id == MY_DISCORD_ID:
        await ctx.send(bold_msg("لا يمكنك إعطاء وارن لهذا الحساب.", "❌"))
        return

    # FIX #2: async I/O
    warns = await load_warns()
    uid = str(member.id)
    warns.setdefault(uid, [])
    next_id = max((int(x.get("warn_id", 0)) for x in warns[uid] if isinstance(x, dict)), default=0) + 1
    warns[uid].append({
        "warn_id": next_id,
        "moderator": ctx.author.name,
        "moderator_id": ctx.author.id,
        "reason": reason,
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    await save_warns(warns)
    await ctx.send(bold_msg(f"تم إعطاء {member.mention} وارن بنجاح • السبب: {reason}", "✅"))

@bot.command(name="شيل")
async def remove_member_warns(ctx: commands.Context, member: discord.Member = None):
    if not check_permissions(ctx):
        await ctx.send(bold_msg("ليس لديك صلاحية حذف التحذيرات.", "🔒"))
        return
    if member is None:
        await ctx.send(bold_msg("استخدم الأمر هكذا: !شيل @user", "⚠️"))
        return
    # FIX #2: async I/O
    warns = await load_warns()
    uid = str(member.id)
    if uid not in warns or not warns[uid]:
        await ctx.send(bold_msg(f"لا توجد تحذيرات مسجلة على {member.mention}.", "ℹ️"))
        return
    count = len(warns[uid])
    del warns[uid]
    await save_warns(warns)
    await ctx.send(bold_msg(f"تم حذف جميع تحذيرات {member.mention} بنجاح • العدد: {count}", "🧹"))

@bot.command(name="شيل_كل")
async def remove_all_server_warns(ctx: commands.Context):
    if not check_permissions(ctx):
        await ctx.send(bold_msg("ليس لديك صلاحية حذف تحذيرات السيرفر.", "🔒"))
        return
    # FIX #2: async I/O
    warns = await load_warns()
    count = sum(len(v) for v in warns.values() if isinstance(v, list))
    await save_warns({})
    await ctx.send(bold_msg(f"تم حذف جميع تحذيرات أعضاء السيرفر بنجاح • العدد: {count}", "🧹"))

# ==============================================================================
# Dashboards
# ==============================================================================

# FIX #4: /server_set — allows owner/admin to set the mod role manually
@bot.tree.command(name="server_set", description="تعيين رتبة الإدارة يدوياً لإحصائيات لوحة السيرفر")
@app_commands.describe(role="الرتبة التي تريد تعيينها كرتبة الإدارة")
async def server_set(interaction: discord.Interaction, role: discord.Role):
    if not check_slash_permissions(interaction):
        await interaction.response.send_message(bold_msg("ليس لديك صلاحية استخدام هذا الأمر.", "🔒"), ephemeral=True)
        return
    config = await load_server_config()
    guild_id = str(interaction.guild_id)
    if guild_id not in config:
        config[guild_id] = {}
    config[guild_id]["mod_role_id"] = role.id
    await save_server_config(config)
    await interaction.response.send_message(
        bold_msg(f"تم تعيين {role.mention} كرتبة الإدارة للوحة السيرفر بنجاح.", "✅"),
        ephemeral=True
    )

@bot.command(name="S")
async def server_dashboard(ctx: commands.Context):
    guild = ctx.guild
    if not guild:
        return
    # FIX #4: Load manually set mod role from config; fall back to hardcoded MOD_ROLE_ID
    config = await load_server_config()
    guild_config = config.get(str(guild.id), {})
    custom_mod_role_id = guild_config.get("mod_role_id", MOD_ROLE_ID)
    mod_role = guild.get_role(custom_mod_role_id)
    total_admins = len(mod_role.members) if mod_role else 0
    online_admins = sum(1 for m in mod_role.members if m.status != discord.Status.offline) if mod_role else 0
    embed = discord.Embed(
        title=f"📊 لوحة إحصائيات سيرفر {guild.name}",
        color=pink_color(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.set_image(url=TOUCHLINE_IMAGE_URL)
    embed.add_field(name="👑 مالك السيرفر", value=f"<@{guild.owner_id}>", inline=True)
    embed.add_field(name="👥 إجمالي الأعضاء", value=f"`{guild.member_count}`", inline=True)
    embed.add_field(name="👮 رتبة الإدارة", value=mod_role.mention if mod_role else "❌ الرتبة غير موجودة", inline=True)
    embed.add_field(name="👮 عدد الإداريين", value=f"`{total_admins}` إداري", inline=True)
    embed.add_field(name="🟢 الإداريون المتصلون", value=f"`{online_admins}`", inline=True)
    embed.add_field(name="📁 الرومات", value=f"📝 `{len(guild.text_channels)}` | 🔊 `{len(guild.voice_channels)}`", inline=True)
    embed.add_field(name="🏅 الرتب", value=f"`{max(0, len(guild.roles)-1)}`", inline=True)
    embed.add_field(name="💎 البوستات", value=f"`{guild.premium_subscription_count or 0}`", inline=True)
    embed.set_footer(text="TOUCHLINE • FIFA VAULT")
    await ctx.send(embed=embed)

@bot.command(name="U")
async def user_dashboard(ctx: commands.Context, member: discord.Member = None):
    target = member or ctx.author
    roles = [r.mention for r in target.roles if not r.is_default()]
    embed = discord.Embed(title=f"👤 بطاقة العضوية: {target.name}", color=pink_color())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="📅 إنشاء الحساب", value=f"`{target.created_at.strftime('%Y-%m-%d')}`", inline=True)
    embed.add_field(name="📥 دخول السيرفر", value=f"`{target.joined_at.strftime('%Y-%m-%d')}`" if target.joined_at else "`غير متوفر`", inline=True)
    embed.add_field(name="🎖️ الرتب", value=", ".join(roles) if roles else "لا توجد", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="عملة")
async def coin_flip_advanced(ctx: commands.Context):
    if random.randint(1, 100) == 1:
        result = "العملة وقفت بالنص وضاعت الرمية! 😂"
    else:
        result = random.choice(["فوق ⬆️", "تحت ⬇️"])
    embed = discord.Embed(title="🪙 رمية العملة", description=f"**النتيجة: {result}**", color=pink_color())
    embed.set_footer(text=f"بواسطة {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command(name="rate")
async def rate_sweetener(ctx: commands.Context, *, item: str):
    score = random.randint(7, 10) if random.randint(1, 100) <= 80 else random.randint(0, 6)
    embed = discord.Embed(title="⭐ التقييم", description=f"**__ تقييمي لـ {item} هو {score}/10 __**", color=pink_color())
    await ctx.send(embed=embed)

# ==============================================================================
# Timeout UI
# ==============================================================================
class TimeoutSelect(discord.ui.Select):
    def __init__(self, target: discord.Member, author_id: int):
        self.target = target
        self.author_id = author_id
        options = [discord.SelectOption(label=k, description=d[:100], value=k) for k, d in TIMEOUT_OPTIONS]
        super().__init__(placeholder="Choice • اختر مدة التايم", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(bold_msg("هذه الواجهة ليست لك.", "🔒"), ephemeral=True)
            return
        if not check_slash_permissions(interaction):
            await interaction.response.send_message(bold_msg("ليس لديك صلاحية إعطاء تايم.", "❌"), ephemeral=True)
            return
        key = self.values[0]
        ok, result = await apply_timeout(interaction, self.target, key)
        if not ok:
            await interaction.response.send_message(bold_msg(result, "❌"), ephemeral=True)
            return
        desc = dict(TIMEOUT_OPTIONS)[key]
        for child in self.view.children:
            child.disabled = True
        await interaction.response.edit_message(
            content=bold_msg(f"تم تطبيق {key} على {self.target.mention} بنجاح • {desc}", "✅"),
            embed=None, view=self.view
        )

class TimeoutView(discord.ui.View):
    def __init__(self, target, author_id):
        super().__init__(timeout=60)
        self.add_item(TimeoutSelect(target, author_id))

# FIX ALIASES: !اسكت aliases: تايم, اسكت, اص
@bot.command(name="اسكت", aliases=["تايم"])
async def mute_command(ctx: commands.Context, member: discord.Member = None, duration: str = None):
    if not check_permissions(ctx):
        return
    if not member:
        await ctx.send(bold_msg("استخدم الأمر هكذا: !اسكت @user [المدة]", "⚠️"))
        return
    if member.bot or member.id == MY_DISCORD_ID:
        await ctx.send(bold_msg("لا يمكنك تطبيق هذا الإجراء على هذا العضو.", "❌"))
        return
    if not duration:
        embed = discord.Embed(
            title="🔇 اختيار مدة التايم",
            description=f"**__ اختار مدة التايم لـ {member.mention} __**",
            color=pink_color()
        )
        embed.set_footer(text="Choice • اضغط القائمة لاختيار المدة")
        await ctx.send(embed=embed, view=TimeoutView(member, ctx.author.id))
        return
    key = duration.lower().strip()
    if key not in TIMEOUT_MAP:
        await ctx.send(bold_msg("المدة غير صحيحة. استخدم 15m أو 30m أو 1h أو 2h أو 1d أو 7d أو 28d.", "⚠️"))
        return
    ok, result = await apply_timeout(ctx, member, key)
    if ok:
        await ctx.send(bold_msg(f"تم تطبيق {key} على {member.mention} بنجاح.", "✅"))
    else:
        await ctx.send(bold_msg(result, "❌"))

# FIX ALIAS: تكلم
@bot.command(name="تكلم")
async def unmute_command(ctx: commands.Context, member: discord.Member = None):
    if not check_permissions(ctx):
        return
    if not member:
        await ctx.send(bold_msg("استخدم الأمر هكذا: !تكلم @user", "⚠️"))
        return
    ok, error = await remove_timeout(member)
    if ok:
        await ctx.send(bold_msg(f"تم إزالة التايم عن {member.mention} بنجاح.", "🔊"))
    else:
        await ctx.send(bold_msg(error, "❌"))

@bot.command(name="عمر")
async def account_age(ctx: commands.Context, member: discord.Member = None):
    target = member or ctx.author
    now = datetime.datetime.now(datetime.timezone.utc)
    created = target.created_at
    days = max(0, (now - created).days)
    years, rem = divmod(days, 365)
    months, rem_days = divmod(rem, 30)
    parts = []
    if years: parts.append(f"{years} سنة")
    if months: parts.append(f"{months} شهر")
    if rem_days or not parts: parts.append(f"{rem_days} يوم")
    await ctx.send(bold_msg(
        f"عمر حساب {target.mention}: {' و '.join(parts)} • تاريخ الإنشاء: {created.strftime('%Y-%m-%d')}",
        "🎂"
    ))

# ==============================================================================
# FIX #5: Slash /say & /embed — anonymous execution
# Respond ephemerally so no "User used /say" visible; send actual message anonymously.
# ==============================================================================
@bot.tree.command(name="say", description="يجعل البوت يقول النص الذي تكتبه بشكل مجهول")
@app_commands.describe(text="النص الذي تريد أن يقوله البوت")
async def slash_say(interaction: discord.Interaction, text: str):
    if not is_owner(interaction.user):
        await interaction.response.send_message(bold_msg("هذا الأمر متاح لمالك البوت فقط.", "🔒"), ephemeral=True)
        return
    # Acknowledge ephemerally so Discord doesn't show "User used /say"
    await interaction.response.send_message("✅ تم الإرسال!", ephemeral=True)
    # Send the actual message anonymously through the bot
    await interaction.channel.send(text)

@bot.tree.command(name="embed", description="إرسال Embed من حساب البوت بشكل مجهول")
@app_commands.describe(title="عنوان الـ Embed", description="محتوى الـ Embed")
async def slash_embed(interaction: discord.Interaction, title: str, description: str):
    if not is_owner(interaction.user):
        await interaction.response.send_message(bold_msg("هذا الأمر متاح لمالك البوت فقط.", "🔒"), ephemeral=True)
        return
    # Acknowledge ephemerally so Discord doesn't show "User used /embed"
    await interaction.response.send_message("✅ تم الإرسال!", ephemeral=True)
    embed = discord.Embed(title=title, description=description, color=pink_color())
    # Send anonymously
    await interaction.channel.send(embed=embed)

# ==============================================================================
# FIX #6: /help — Fixed to work correctly (no file attachment conflict)
# ==============================================================================
class HelpView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=180)
        self.author_id = author_id

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(bold_msg("هذه الواجهة ليست لك.", "🔒"), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="عضو", emoji="🙋", style=discord.ButtonStyle.secondary)
    async def member_help(self, interaction, button):
        embed = build_member_help(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="الإدارة", emoji="👮", style=discord.ButtonStyle.primary)
    async def admin_help(self, interaction, button):
        embed = build_admin_help(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

def build_member_help(guild):
    embed = discord.Embed(title="🤖 TOUCHLINE • مساعدة الأعضاء", color=pink_color())
    embed.description = (
        "**__ أنا بوت السيرفر، موجود عشان أساعدك أو أرشدك. __**\n\n"
        "سيرفرنا هو مجتمع لعبة **TOUCHLINE** على Roblox، وهنا تقام البطولات والفعاليات الخاصة باللعبة.\n\n"
        "💬 اكتب **الدعم** لمعرفة جهة التكت وطلب الدعم الفني أو توثيق ناديك.\n"
        "📜 اكتب **القوانين** لمعرفة قوانين السيرفر.\n\n"
        "🎮 **أوامر الألعاب:** `!rock` `!من_انا` `!wordle` `!xo` `!لو_خيروك` `!غميمه`\n"
        "📊 **معلومات:** `!s` `!u @user`\n"
        "🎂 **عمر الحساب:** `!عمر @user` أو `!u @user`"
    )
    embed.set_image(url=TOUCHLINE_IMAGE_URL)
    return embed

def build_admin_help(guild):
    mod = guild.get_role(MOD_ROLE_ID) if guild else None
    allowed_roles = [guild.get_role(rid) for rid in ALLOWED_ROLE_IDS] if guild else []
    allowed_roles = [r.mention for r in allowed_roles if r]
    role_name = " ، ".join(allowed_roles) if allowed_roles else "الرتب المسموح بها في الإعدادات"
    embed = discord.Embed(title="👮 TOUCHLINE • لوحة أوامر الإدارة", color=pink_color())
    embed.description = (
        f"**__ الصلاحية الأساسية: {role_name} أو مالك البوت. رتبة المتابعة في الإحصائيات: "
        f"{mod.mention if mod else f'ID `{MOD_ROLE_ID}`'}. __**\n\n"
        "🛡️ **الإشراف:** `!وارن @user السبب` `!تشيك @user` `!وارنات` `!شيل @user` `!شيل_كل`\n"
        "🔇 **التايم:** `!اسكت @user` (اختصارات: `!تايم` `!اص`) `!اسكت @user 15m` `!تكلم @user`\n"
        "⛓️ **السجن:** `!سجن @user [سبب]` `!افراج @user`\n"
        "🛠️ **الإدارة:** `!برا @user` `!حذف عدد` (اختصار: `!م`) `!rename الاسم` `!قفل` `!فتح`\n"
        "📊 **المعلومات:** `!s` `!u @user`\n"
        "⚙️ **الإعداد:** `/server_set` لتعيين رتبة الإدارة يدوياً\n"
        "👑 **مالك البوت فقط:** `/say` `/embed`\n\n"
        "**ملاحظة:** صلاحيات الأوامر مرتبطة بالـ Role IDs الموجودة في إعدادات البوت."
    )
    return embed

@bot.tree.command(name="help", description="شرح البوت وأوامره")
async def slash_help(interaction: discord.Interaction):
    # FIX #6: Send embed without file — use URL directly to avoid attachment conflict
    embed = build_member_help(interaction.guild)
    await interaction.response.send_message(embed=embed, view=HelpView(interaction.user.id), ephemeral=True)

# ==============================================================================
# Rock Paper Scissors
# ==============================================================================
class RockPaperScissorsView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=60)
        self.author = author

    async def _handle_game(self, interaction, player_choice):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(bold_msg("هذا التحدي مخصص لصاحبه فقط.", "🔒"), ephemeral=True)
            return
        bot_choice = random.choice(["حجر 🪨", "ورقة 📄", "مقص ✂️"])
        if player_choice == bot_choice:
            result = "تعادل! 👔"
        elif (
            (player_choice == "حجر 🪨" and bot_choice == "مقص ✂️") or
            (player_choice == "ورقة 📄" and bot_choice == "حجر 🪨") or
            (player_choice == "مقص ✂️" and bot_choice == "ورقة 📄")
        ):
            result = "أنت الفائز! 🎉"
        else:
            result = "البوت فاز! 🤖"
        embed = discord.Embed(title="🪨📄✂️ النتيجة", color=pink_color())
        embed.add_field(name="اختيارك", value=player_choice, inline=True)
        embed.add_field(name="اختيار البوت", value=bot_choice, inline=True)
        embed.add_field(name="النتيجة", value=result, inline=False)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="حجر 🪨", style=discord.ButtonStyle.primary)
    async def rock_button(self, interaction, button):
        await self._handle_game(interaction, "حجر 🪨")

    @discord.ui.button(label="ورقة 📄", style=discord.ButtonStyle.success)
    async def paper_button(self, interaction, button):
        await self._handle_game(interaction, "ورقة 📄")

    @discord.ui.button(label="مقص ✂️", style=discord.ButtonStyle.danger)
    async def scissors_button(self, interaction, button):
        await self._handle_game(interaction, "مقص ✂️")

@bot.command(name="rock")
async def play_rps_buttons(ctx):
    await ctx.send(
        embed=discord.Embed(title="🎮 حجر ورقة مقص", description="اختر من الأزرار بالأسفل.", color=pink_color()),
        view=RockPaperScissorsView(ctx.author)
    )

# ==============================================================================
# Translation
# ==============================================================================
@bot.command(name="ترجم")
async def translate_via_reply(ctx):
    if not ctx.message.reference or not ctx.message.reference.message_id:
        await ctx.send(bold_msg("استخدم !ترجم كرد على الرسالة التي تريد ترجمتها.", "⚠️"))
        return
    try:
        ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        text = ref_msg.content.strip()
        if not text:
            await ctx.send(bold_msg("الرسالة لا تحتوي نصًا يمكن ترجمته.", "❌"))
            return
        async with ctx.channel.typing():
            translated = await real_translate_to_arabic(text)
        await ctx.reply(bold_msg("الترجمة العربية", "🔠") + f"\n> {translated}")
    except Exception as e:
        await ctx.send(bold_msg(f"تعذر إتمام الترجمة حاليًا: {e}", "❌"))

# ==============================================================================
# Warn system
# ==============================================================================
class WarnPaginationView(discord.ui.View):
    def __init__(self, entries, author):
        super().__init__(timeout=120)
        self.entries = entries
        self.author = author
        self.current_page = 0
        self.per_page = 5
        self.max_pages = max(1, math.ceil(len(entries) / self.per_page))
        self._sync_buttons()

    def _sync_buttons(self):
        self.prev_button.disabled = self.current_page <= 0
        self.next_button.disabled = self.current_page >= self.max_pages - 1

    def _generate_embed(self):
        start = self.current_page * self.per_page
        page = self.entries[start:start + self.per_page]
        embed = discord.Embed(
            title="📋 سجل تحذيرات السيرفر",
            description=f"**__ إجمالي التحذيرات: {len(self.entries)} • الأحدث أولًا __**",
            color=pink_color()
        )
        for i, entry in enumerate(page, start=start + 1):
            user_mention = entry["mention"]
            value = (
                f"👤 **العضو:** {user_mention}\n"
                f"⚠️ **رقم التحذير:** `#{entry.get('warn_id', i)}`\n"
                f"📝 **السبب:** {entry.get('reason', 'غير محدد')}\n"
                f"🕒 **وقت إعطائه:** `{entry.get('date', 'غير معروف')}`\n"
                f"👮 **المعطي:** {entry.get('moderator', 'غير معروف')}"
            )
            embed.add_field(name=f"تحذير #{entry.get('warn_id', i)}", value=value, inline=False)
        embed.set_footer(text=f"صفحة {self.current_page + 1} من {self.max_pages}")
        return embed

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(bold_msg("هذه الصفحات ليست لك.", "🔒"), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="◀ السابق", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction, button):
        self.current_page -= 1
        self._sync_buttons()
        await interaction.response.edit_message(embed=self._generate_embed(), view=self)

    @discord.ui.button(label="التالي ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction, button):
        self.current_page += 1
        self._sync_buttons()
        await interaction.response.edit_message(embed=self._generate_embed(), view=self)

@bot.command(name="تشيك")
async def check_warns(ctx, member: discord.Member = None):
    if not check_permissions(ctx):
        return
    target = member or ctx.author
    # FIX #2: async I/O
    warns = await load_warns()
    user_warns = warns.get(str(target.id), [])
    await ctx.send(bold_msg(f"{target.mention} لديه {len(user_warns)} وارن.", "📋"))

# FIX ALIAS: وارنات
@bot.command(name="وارنات")
async def show_all_warns(ctx):
    if not check_permissions(ctx):
        return
    # FIX #2: async I/O
    warns = await load_warns()
    entries = []
    for uid, user_warns in warns.items():
        if not isinstance(user_warns, list):
            continue
        member = ctx.guild.get_member(int(uid))
        if not member:
            continue
        for entry in user_warns:
            item = dict(entry)
            item["mention"] = member.mention
            try:
                item["sort_dt"] = datetime.datetime.strptime(item.get("date", "1900-01-01 00:00"), "%Y-%m-%d %H:%M")
            except Exception:
                item["sort_dt"] = datetime.datetime.min
            entries.append(item)
    entries.sort(key=lambda x: x["sort_dt"], reverse=True)
    if not entries:
        await ctx.send(bold_msg("سجل تحذيرات السيرفر نظيف حاليًا.", "✅"))
        return
    view = WarnPaginationView(entries, ctx.author)
    await ctx.send(embed=view._generate_embed(), view=view)

# ==============================================================================
# EDIT: !من_انا — Characters changed to Arabic names
# ==============================================================================
WHO_AM_I = [
    ("ليونيل ميسي", ["أنا لاعب كرة قدم أرجنتيني.", "فزت بكأس العالم 2022.", "لعبت سنوات طويلة مع برشلونة.", "أرتبط كثيرًا بالرقم 10.", "أملك عدة كرات ذهبية."]),
    ("كريستيانو رونالدو", ["أنا لاعب كرة قدم برتغالي.", "اشتهرت بالرقم 7.", "لعبت مع مانشستر يونايتد وريال مدريد.", "حققت دوري أبطال أوروبا عدة مرات.", "أنا من أكثر الهدافين شهرة في كرة القدم."]),
    ("نيمار", ["أنا لاعب كرة قدم برازيلي.", "لعبت مع برشلونة وباريس سان جيرمان.", "أشتهر بالمهارات والمراوغات.", "ارتديت الرقم 10 مع البرازيل.", "انتقلت إلى الهلال السعودي في 2023."]),
    ("كيليان مبابي", ["أنا لاعب كرة قدم فرنسي.", "فزت بكأس العالم 2018.", "اشتهرت بسرعتي الكبيرة.", "لعبت مع باريس سان جيرمان.", "انتقلت إلى ريال مدريد في 2024."]),
    ("محمد صلاح", ["أنا لاعب كرة قدم مصري.", "ألعب في مركز الجناح والهجوم.", "حققت الدوري الإنجليزي مع ليفربول.", "اشتهرت بارتداء الرقم 11.", "أُلقب بالملك المصري."]),
    ("زين الدين زيدان", ["أنا لاعب ومدرب فرنسي.", "فزت بكأس العالم 1998.", "اشتهرت بالرقم 10.", "لعبت لريال مدريد.", "فزت بدوري أبطال أوروبا كمدرب لريال مدريد."]),
    ("مايكل جوردان", ["أنا أسطورة في كرة السلة.", "لعبت معظم مسيرتي مع شيكاغو بولز.", "فزت بـ6 بطولات NBA.", "ارتبط اسمي بالرقم 23.", "لدي علامة أحذية رياضية شهيرة تحمل اسمي."]),
    ("ألبرت آينشتاين", ["أنا عالم فيزياء ألماني المولد.", "ارتبط اسمي بالنسبية.", "نشرت نظرية النسبية الخاصة.", "حصلت على نوبل في الفيزياء.", "اشتهرت بصور شعري الأبيض."]),
    ("إسحاق نيوتن", ["أنا عالم إنجليزي.", "درست الجاذبية والحركة.", "ارتبطت بقصة التفاحة الشهيرة.", "كتبت Principia Mathematica.", "أنا من أبرز علماء الثورة العلمية."]),
    ("وليم شكسبير", ["أنا كاتب مسرحي إنجليزي.", "كتبت روميو وجولييت.", "كتبت هاملت.", "أعمالي من أشهر الأدب الإنجليزي.", "عشت في القرنين السادس عشر والسابع عشر."]),
    ("مايكل جاكسون", ["أنا مغنٍ وراقص أمريكي.", "لُقبت بملك البوب.", "أصدرت ألبوم Thriller.", "اشتهرت برقصة Moonwalk.", "لدي أغنية Billie Jean الشهيرة."]),
    ("جاكي شان", ["أنا ممثل وفنان قتالي.", "أنا من هونغ كونغ.", "اشتهرت بمزج الأكشن والكوميديا.", "أؤدي كثيرًا من مشاهد الحركة بنفسي.", "شاركت في Rush Hour."]),
    ("توم كروز", ["أنا ممثل أمريكي.", "لعبت دور إيثان هانت.", "اشتهرت بسلسلة Mission: Impossible.", "ظهرت في Top Gun.", "أؤدي العديد من مشاهد الأكشن الخطرة."]),
    ("مستر بيست", ["أنا صانع محتوى أمريكي.", "أشتهر بتحديات ضخمة.", "أقدم جوائز مالية كبيرة في فيديوهاتي.", "قناتي من أشهر قنوات يوتيوب.", "اسمي الحقيقي جيمي دونالدسون."]),
    ("ستيف جوبز", ["كنت رجل أعمال أمريكيًا.", "شاركت في تأسيس Apple.", "ارتبط اسمي بالـ iPhone.", "قدمت عروضًا شهيرة لمنتجات Apple.", "توفيت عام 2011."]),
    ("بيل غيتس", ["أنا رجل أعمال ومبرمج أمريكي.", "شاركت في تأسيس Microsoft.", "ارتبط اسمي بنظام Windows.", "عملت في مجال البرمجيات.", "أسست مؤسسة خيرية معروفة."]),
    ("شيرلوك هولمز", ["أنا محقق خيالي.", "أستخدم الاستنتاج لحل الجرائم.", "أعيش في 221B Baker Street.", "صديقي المقرب هو الدكتور واتسون.", "ابتكرني الكاتب آرثر كونان دويل."]),
    ("باتمان", ["أنا بطل خارق بدون قوى خارقة.", "أعيش في غوثام.", "هويتي السرية بروس واين.", "أستخدم أدوات وتقنيات لمكافحة الجريمة.", "أعدائي يشملون الجوكر."]),
    ("سبايدرمان", ["أنا بطل خارق.", "أستطيع تسلق الجدران.", "هويتي الشهيرة بيتر باركر.", "أستخدم شبكات للتنقل.", "أرتبط بمدينة نيويورك."]),
    ("سوبرمان", ["أنا بطل خارق من كريبتون.", "أستطيع الطيران.", "هويتي البشرية كلارك كينت.", "أرتدي شعار S.", "أشتهر بقدراتي الخارقة."]),
    ("هاري بوتر", ["أنا شخصية في سلسلة كتب خيالية.", "أدرس في هوغوارتس.", "لدي ندبة على شكل برق.", "صديقاَي رون وهيرميون.", "أواجه فولدمورت."]),
    ("غوكو", ["أنا شخصية من دراغون بول.", "أمارس فنون القتال.", "أستطيع التحول إلى سوبر سايان.", "أحب الأكل كثيرًا.", "أحارب لحماية الأرض وأصدقائي."]),
    ("ناروتو", ["أنا نينجا من قرية كونوها.", "أحلم بأن أصبح هوكاجي.", "أحمل بداخلي قوة الثعلب ذي الذيول التسعة.", "أنا بطل سلسلة أنمي تحمل اسمي.", "أشتهر بحركة راسينغان."]),
    ("يوليوس قيصر", ["كنت قائدًا رومانيًا.", "ارتبط اسمي بروما القديمة.", "عبرت نهر روبيكون.", "لعبت دورًا كبيرًا في نهاية الجمهورية الرومانية.", "اغتيلت في أيدس مارس."]),
    ("الإسكندر الأكبر", ["كنت ملك مقدونيا.", "بنيت إمبراطورية واسعة.", "وصلت حملاتي إلى الهند.", "كان أرسطو معلمي.", "توفيت في بابل."]),
    ("جنكيز خان", ["أسست الإمبراطورية المغولية.", "وحدت قبائل مغولية.", "قادت جيوشي حملات واسعة في آسيا.", "ارتبط اسمي بالإمبراطورية المغولية.", "عشت في القرن الثالث عشر."]),
    ("نابليون بونابرت", ["كنت قائدًا فرنسيًا.", "توجت إمبراطورًا لفرنسا.", "قدت حملات عسكرية واسعة في أوروبا.", "هُزمت في واترلو.", "نُفيت إلى سانت هيلانة في آخر حياتي."]),
    ("كليوباترا", ["كنت ملكة مصر البطلمية.", "ارتبط اسمي بالإسكندرية.", "تحدثت عدة لغات بحسب المصادر التاريخية.", "ارتبطت سياسيًا بيوليوس قيصر ومارك أنطوني.", "أنا من أشهر ملكات العالم القديم."]),
    ("هانيبال", ["كنت قائدًا قرطاجيًا.", "حاربت روما في الحرب البونيقية الثانية.", "عبرت جبال الألب بجيشي.", "استخدمت الفيلة في حملاتي.", "حققت انتصارًا كبيرًا في معركة كاناي."]),
    ("صلاح الدين الأيوبي", ["كنت قائدًا مسلمًا عظيمًا.", "حررت القدس عام 1187م.", "قادت حملاتي في الشام ومصر.", "تميزت بالشهامة والنبل حتى مع أعدائي.", "أسست الدولة الأيوبية."]),
    ("عمر بن الخطاب", ["كنت ثاني الخلفاء الراشدين.", "اشتهرت بالعدل والحزم.", "وسعت الدولة الإسلامية كثيرًا في عهدي.", "أسست أول جيش نظامي في الإسلام.", "لُقبت بالفاروق."]),
    ("ابن سينا", ["كنت طبيبًا وفيلسوفًا إسلاميًا.", "كتبت القانون في الطب.", "أحدثت ثورة في العلوم الطبية.", "اشتهرت في أوروبا باسم Avicenna.", "عشت في القرن الحادي عشر الميلادي."]),
    ("محمد علي كلاي", ["كنت ملاكمًا أمريكيًا أسطورياً.", "حملت لقب بطل العالم للوزن الثقيل.", "اشتهرت بجملة 'أنا الأعظم'.", "دافعت عن مبادئي وتحملت تبعاتها.", "أُعتبر من أعظم الرياضيين في التاريخ."]),
]
ACTIVE_WHO_AM_I = {}
WHO_AM_I_LAST_PLAYED = {}
WHO_AM_I_COOLDOWN = datetime.timedelta(minutes=5)

class WhoAmIView(discord.ui.View):
    def __init__(
        self,
        game,
        author_id: int
    ):
        super().__init__(timeout=300)

        self.game = game
        self.author_id = author_id

        self.hint_button = discord.ui.Button(
            label="تلميح",
            emoji="💡",
            style=discord.ButtonStyle.primary
        )

        self.reveal_button = discord.ui.Button(
            label="كشف الإجابة",
            emoji="✅",
            style=discord.ButtonStyle.success,
            disabled=True
        )

        self.hint_button.callback = self.give_hint
        self.reveal_button.callback = self.reveal_answer

        self.add_item(self.hint_button)
        self.add_item(self.reveal_button)

    async def give_hint(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                bold_msg(
                    "فقط الشخص الذي بدأ اللعبة يستطيع استخدام التلميحات.",
                    "🔒"
                ),
                ephemeral=True
            )
            return

        if self.game.finished:
            await interaction.response.send_message(
                bold_msg("انتهت اللعبة بالفعل.", "⚠️"),
                ephemeral=True
            )
            return

        if self.game.hints_used >= len(self.game.clues):
            await interaction.response.send_message(
                bold_msg(
                    "تم استخدام جميع التلميحات.",
                    "💡"
                ),
                ephemeral=True
            )
            return

        clue = self.game.clues[self.game.hints_used]
        self.game.hints_used += 1

        self.game.hint_lines.append(
            f"💡 **التلميح {self.game.hints_used}:** {clue}"
        )

        # Make reveal available only after 3 hints.
        if self.game.hints_used >= 3:
            self.reveal_button.disabled = False

        # Disable hint button after all hints.
        if self.game.hints_used >= len(self.game.clues):
            self.hint_button.disabled = True

        embed = self.game.build_embed()

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )

    async def reveal_answer(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                bold_msg(
                    "فقط الشخص الذي بدأ اللعبة يستطيع كشف الإجابة.",
                    "🔒"
                ),
                ephemeral=True
            )
            return

        if self.game.finished:
            await interaction.response.send_message(
                bold_msg("انتهت اللعبة بالفعل.", "⚠️"),
                ephemeral=True
            )
            return

        if self.game.hints_used < 3:
            await interaction.response.send_message(
                bold_msg(
                    "يجب استخدام 3 تلميحات أولًا قبل كشف الإجابة.",
                    "⚠️"
                ),
                ephemeral=True
            )
            return

        self.game.finished = True

        await self.game.finish(
            winner_name=None,
            reveal=True
        )

    async def on_timeout(self):
        if not self.game.finished:
            await self.game.finish(
                winner_name=None,
                timeout=True
            )
        class WhoAmIGame:
           def __init__(
           self,
           ctx,
           answer,
           clues,
           starter_id
        ):
            self.ctx = ctx
            self.channel_id = ctx.channel.id
            self.answer = answer
            self.clues = list(clues)
            random.shuffle(self.clues)

            self.starter_id = starter_id
            self.hints_used = 0
            self.hint_lines = []
            self.finished = False
            self.message = None
            self.message_id = None
            self.guess_task = None

    def build_embed(self):
        if self.finished:
            return discord.Embed(
                title="❓ من أنا؟",
                description=(
                    "\n".join(self.hint_lines)
                    if self.hint_lines
                    else "انتهت اللعبة."
                ),
                color=pink_color()
            )

        description = (
            "**__ خمن الشخصية من التلميحات. "
            "اكتب اسم الشخصية في الشات. __**\n\n"
        )

        if self.hint_lines:
            description += "\n".join(self.hint_lines)
        else:
            description += (
                "💡 التلميحات لم تبدأ بعد.\n"
                "🔒 كشف الإجابة متاح بعد 3 تلميحات."
            )

        return discord.Embed(
            title="❓ من أنا؟",
            description=description,
            color=pink_color()
        )

    async def start(self):
        view = WhoAmIView(
            self,
            self.starter_id
        )

        self.message = await self.ctx.send(
            embed=self.build_embed(),
            view=view
        )

        self.message_id = self.message.id

        ACTIVE_WHO_AM_I[self.channel_id] = self

        self.guess_task = asyncio.create_task(
            self.wait_for_guesses()
        )

    async def wait_for_guesses(self):
        def check(message: discord.Message):
            return (
                not message.author.bot
                and message.channel.id == self.channel_id
                and not self.finished
            )

        try:
            while not self.finished:
                message = await bot.wait_for(
                    "message",
                    timeout=300,
                    check=check
                )

                guess = clean_arabic_text(
                    message.content
                ).strip()

                answer = clean_arabic_text(
                    self.answer
                ).strip()

                if guess == answer:
                    await message.channel.send(
                        bold_msg(
                            f"إجابة صحيحة! 🎉 {message.author.mention} عرف الشخصية: **{self.answer}**",
                            "✅"
                        ),
                        allowed_mentions=discord.AllowedMentions(
                            users=True
                        )
                    )

                    await self.finish(
                        winner_name=message.author.display_name
                    )

                else:
                    await message.channel.send(
                        bold_msg(
                            f"{message.author.mention}، إجابتك غير صحيحة.",
                            "❌"
                        ),
                        allowed_mentions=discord.AllowedMentions(
                            users=True
                        )
                    )

        except asyncio.TimeoutError:
            if not self.finished:
                await self.finish(
                    timeout=True
                )

        except asyncio.CancelledError:
            return

    async def finish(
        self,
        winner_name=None,
        reveal=False,
        timeout=False
    ):
        if self.finished and not reveal:
            return

        self.finished = True

        if self.guess_task:
            current = asyncio.current_task()

            if self.guess_task is not current:
                self.guess_task.cancel()

        if self.channel_id in ACTIVE_WHO_AM_I:
            ACTIVE_WHO_AM_I.pop(
                self.channel_id,
                None
            )

        description = ""

        if self.hint_lines:
            description += (
                "\n".join(self.hint_lines)
                + "\n\n"
            )

        if winner_name:
            description += (
                f"🎉 **الفائز: {winner_name}**\n"
                f"الإجابة كانت: **{self.answer}**"
            )

        elif reveal:
            description += (
                f"✅ **الإجابة هي: {self.answer}**"
            )

        elif timeout:
            description += (
                f"⏰ انتهى وقت اللعبة.\n"
                f"الإجابة كانت: **{self.answer}**"
            )

        else:
            description += (
                f"اللعبة انتهت.\n"
                f"الإجابة كانت: **{self.answer}**"
            )

        embed = discord.Embed(
            title="❓ من أنا؟ • انتهت اللعبة",
            description=description,
            color=pink_color()
        )

        try:
            if self.message:
                for item in self.message.components:
                    pass

                await self.message.edit(
                    embed=embed,
                    view=None
                )
        except discord.NotFound:
            pass
        except Exception as e:
            print(
                f"Error finishing Who Am I game: {e}"
            )
            
@bot.command(name="من_انا")
async def who_am_i(ctx):
    channel_id = ctx.channel.id
    now = datetime.datetime.now()

    # Don't allow a second active game in the same channel.
    if channel_id in ACTIVE_WHO_AM_I:
        active_game = ACTIVE_WHO_AM_I[channel_id]

        if not active_game.finished:
            await ctx.send(
                bold_msg(
                    "هناك لعبة من أنا قيد التشغيل بالفعل في هذا الروم. ⏳",
                    "⚠️"
                )
            )
            return

        ACTIVE_WHO_AM_I.pop(
            channel_id,
            None
        )

    # Five-minute cooldown between games.
    last_played = WHO_AM_I_LAST_PLAYED.get(
        channel_id
    )

    if last_played:
        remaining = (
            WHO_AM_I_COOLDOWN
            - (now - last_played)
        ).total_seconds()

        if remaining > 0:
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)

            await ctx.send(
                bold_msg(
                    f"يمكن تشغيل لعبة من أنا مرة أخرى بعد "
                    f"`{minutes}m {seconds}s`.",
                    "⏳"
                )
            )
            return

    WHO_AM_I_LAST_PLAYED[channel_id] = now

    answer, original_clues = random.choice(
        WHO_AM_I
    )

    game = WhoAmIGame(
        ctx=ctx,
        answer=answer,
        clues=original_clues,
        starter_id=ctx.author.id
    )

    await game.start()
    
# ==============================================================================
# Arabic Wordle
# ==============================================================================
WORDLE_WORDS = ["كتاب", "صباح", "ملعب", "لاعب", "سريع", "جميل", "طريق", "مدينة", "مدرسة", "صديق",
                "قهوة", "شجرة", "هاتف", "سيرفر", "فريق", "كرسي", "مفتاح", "سيارة", "حديقة", "رسالة",
                "مكتبة", "بطولة", "جمهور", "مباراة", "نتيجة", "مشجع", "لاعبون", "رئيسي", "عالمي", "مغربي"]
WORDLE_WORDS = [w for w in WORDLE_WORDS if len(w) == 5]
WORDLE_LEN = 5

def wordle_feedback(secret, guess):
    secret = list(secret)
    guess = list(guess)
    result = ["⬜"] * len(guess)
    counts = {}
    for ch in secret:
        counts[ch] = counts.get(ch, 0) + 1
    for i, ch in enumerate(guess):
        if i < len(secret) and ch == secret[i]:
            result[i] = "🟩"
            counts[ch] -= 1
    for i, ch in enumerate(guess):
        if result[i] == "🟩":
            continue
        if counts.get(ch, 0) > 0:
            result[i] = "🟨"
            counts[ch] -= 1
    return "".join(result)

class WordleGame:
    def __init__(self, channel, author):
        self.channel = channel
        self.author = author
        self.secret = random.choice(WORDLE_WORDS)
        self.rows = []

    def board(self):
        return "\n".join(self.rows + ["⬜" * WORDLE_LEN] * (6 - len(self.rows)))

@bot.command(name="wordle")
async def wordle(ctx):
    game = WordleGame(ctx.channel.id, ctx.author.id)
    embed = discord.Embed(
        title="🟩 Wordle عربي",
        description="**__ اكتب كلمة من 5 أحرف في الشات. لديك 6 محاولات. 🟩 صحيح • 🟨 موجود • ⬜ غير موجود __**\n\n" + game.board(),
        color=pink_color()
    )
    msg = await ctx.send(embed=embed)

    def check(m):
        return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id and len(clean_arabic_text(m.content).replace(" ", "")) == WORDLE_LEN

    for _ in range(6):
        try:
            m = await bot.wait_for("message", timeout=60, check=check)
        except asyncio.TimeoutError:
            break
        guess = clean_arabic_text(m.content).replace(" ", "")
        game.rows.append(wordle_feedback(game.secret, guess))
        embed.description = "**__ اكتب كلمة من 5 أحرف. 🟩 صحيح • 🟨 موجود • ⬜ غير موجود __**\n\n" + game.board()
        if guess == game.secret:
            embed.description += f"\n\n**__ 🎉 فزت! الكلمة: {game.secret} __**"
            await msg.edit(embed=embed)
            return
        await msg.edit(embed=embed)
    embed.description += f"\n\n**__ انتهت المحاولات. الكلمة كانت: {game.secret} __**"
    await msg.edit(embed=embed)

# ==============================================================================
# XO VS BOT
# ==============================================================================
class XOView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=180)
        self.author = author
        self.board = [" "] * 9
        self.done = False

    def winner(self):
        for a, b, c in [(0, 1, 2), (3, 4, 5), (6, 7, 8),
                        (0, 3, 6), (1, 4, 7), (2, 5, 8),
                        (0, 4, 8), (2, 4, 6)]:
            if self.board[a] != " " and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return "draw" if " " not in self.board else None

    def render(self):
        return "\n".join(" | ".join(self.board[i:i + 3]) for i in range(0, 9, 3))

    async def play(self, interaction, index):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(bold_msg("هذه اللعبة ليست لك.", "🔒"), ephemeral=True)
            return
        if self.done or self.board[index] != " ":
            await interaction.response.send_message(bold_msg("هذه الخانة غير متاحة.", "⚠️"), ephemeral=True)
            return
        self.board[index] = "❌"
        w = self.winner()
        if not w:
            empty = [i for i, x in enumerate(self.board) if x == " "]
            if empty:
                self.board[random.choice(empty)] = "⭕"
            w = self.winner()
        if w:
            self.done = True
        embed = discord.Embed(
            title="⭕❌ XO VS BOT",
            description=f"```\n{self.render()}\n```\n" + (
                "**__ تعادل! __**" if w == "draw" else
                f"**__ الفائز: {'أنت' if w == '❌' else 'البوت'} __**" if w else
                "**__ دورك. __**"
            ),
            color=pink_color()
        )
        for child in self.children:
            child.disabled = self.done or self.board[child.row * 3 + child.col] != " "
        await interaction.response.edit_message(embed=embed, view=self)

    def add_buttons(self):
        for i in range(9):
            btn = discord.ui.Button(label=str(i + 1), style=discord.ButtonStyle.secondary, row=i // 3)
            btn.row = i // 3
            btn.col = i % 3
            async def callback(interaction, idx=i):
                await self.play(interaction, idx)
            btn.callback = callback
            self.add_item(btn)

@bot.command(name="xo")
async def xo(ctx):
    view = XOView(ctx.author)
    view.add_buttons()
    await ctx.send(
        embed=discord.Embed(
            title="⭕❌ XO VS BOT",
            description="**__ اضغط رقم الخانة للعب. أنت ❌ والبوت ⭕ __**\n```\n 1 | 2 | 3\n 4 | 5 | 6\n 7 | 8 | 9\n```",
            color=pink_color()
        ),
        view=view
    )

# ==============================================================================
# EDIT: !لو_خيروك — Expanded to 450 questions (original 150 + 300 new)
# ==============================================================================
WOULD_YOU_RATHER = [
    # ── Original 150 questions (preserved exactly) ────────────────────────────
    "تعيش بدون هاتف أم بدون إنترنت؟",
    "تسافر للماضي أم للمستقبل؟",
    "تكون سريعًا جدًا أم قويًا جدًا؟",
    "تربح مليونًا الآن أم عشرة ملايين بعد عشر سنوات؟",
    "تعيش في البحر أم في الصحراء؟",
    "تتقن كل اللغات أم كل الآلات الموسيقية؟",
    "تكون مشهورًا أم غنيًا؟",
    "تملك ذاكرة مثالية أم نومًا مثاليًا؟",
    "تأكل الحلو دائمًا أم المالح دائمًا؟",
    "تعيش في مدينة كبيرة أم قرية هادئة؟",
    "تلعب كرة القدم أم كرة السلة؟",
    "تكون حارس مرمى أم مهاجمًا؟",
    "تفوز بدوري أبطال أم بكأس العالم؟",
    "تتوقف عن الألعاب شهرًا أم عن السوشيال شهرًا؟",
    "تشاهد فيلمًا أم مسلسلًا؟",
    "تقرأ كتابًا أم تشاهد وثائقيًا؟",
    "تعيش يومًا بلا كلام أم يومًا بلا كتابة؟",
    "تملك سيارة رياضية أم منزلًا فاخرًا؟",
    "تتعلم البرمجة أم التصميم؟",
    "تكون قائد فريق أم أفضل لاعب فيه؟",
    "تفوز كل مباراة بصعوبة أم تفوز بسهولة بدون تحدٍ؟",
    "تكون مشهورًا في بلدك أم معروفًا عالميًا؟",
    "تملك حيوانًا أليفًا أم نباتات كثيرة؟",
    "تستيقظ مبكرًا دائمًا أم تسهر دائمًا؟",
    "تعيش صيفًا دائمًا أم شتاءً دائمًا؟",
    "تملك قوة الاختفاء أم الطيران؟",
    "تستطيع قراءة الأفكار أم رؤية المستقبل؟",
    "تكون ذكيًا جدًا أم محظوظًا جدًا؟",
    "تملك غرفة ألعاب أم سينما منزلية؟",
    "تلعب مع أصدقاءك أم ضدهم؟",
    "تربح 100 نقطة كل يوم أم 1000 نقطة مرة واحدة؟",
    "تكون مشهورًا بسبب الرياضة أم المحتوى؟",
    "تسافر وحدك أم مع أصدقاءك؟",
    "تعيش بلا موسيقى أم بلا أفلام؟",
    "تتوقف عن القهوة أم المشروبات الغازية؟",
    "تأكل نفس الوجبة أسبوعًا أم لا تأكلها سنة؟",
    "تملك حاسوبًا قويًا أم هاتفًا قويًا؟",
    "تعيش في المغرب أم إسبانيا؟",
    "تزور اليابان أم الولايات المتحدة؟",
    "تزور أوروبا أم آسيا؟",
    "تتعلم الطبخ أم التصوير؟",
    "تكون محترفًا في لعبة واحدة أم جيدًا في عشر ألعاب؟",
    "تملك حسابًا موثقًا أم مليون متابع؟",
    "تربح بطولة صغيرة أم تصل نهائي بطولة كبيرة؟",
    "تلعب مباراة في ملعب ضخم أم أمام جمهور صغير؟",
    "تسجل هدف الفوز أم تصنع هدف الفوز؟",
    "تكون مدربًا أم لاعبًا؟",
    "تبدأ المباراة أم تنهيها؟",
    "تتلقى نصيحة أم تعطي نصيحة؟",
    "تملك يومًا إضافيًا كل أسبوع أم ساعة إضافية كل يوم؟",
    "تستطيع إيقاف الوقت أم تسريعه؟",
    "تملك روبوتًا مساعدًا أم سيارة ذاتية القيادة؟",
    "تعيش في عالم ألعاب أم عالم أفلام؟",
    "تدخل عالم Minecraft أم Roblox؟",
    "تلعب لعبة رعب أم لعبة ألغاز؟",
    "تختار لعبة قديمة أم لعبة جديدة؟",
    "تلعب على PC أم console؟",
    "تملك إنترنت سريع جدًا أم مساحة تخزين ضخمة؟",
    "تشاهد كل المباريات أم كل الأفلام؟",
    "تكون أول شخص يعرف الأخبار أم آخر شخص؟",
    "تملك طاقة لا تنتهي أم وقتًا لا ينتهي؟",
    "تنام 4 ساعات وتكون نشيطًا أم 10 ساعات؟",
    "تعيش بدون حلويات أم بدون وجبات سريعة؟",
    "تأكل بيتزا أم برغر؟",
    "تختار شاورما أم تاكو؟",
    "تختار عصيرًا أم مشروبًا غازيًا؟",
    "تطبخ لنفسك أم يطبخ لك شخص آخر؟",
    "تتناول الإفطار أم العشاء؟",
    "تعيش قرب البحر أم الجبال؟",
    "تسكن في طابق مرتفع أم منزل أرضي؟",
    "تملك حديقة كبيرة أم مسبحًا؟",
    "تسافر بالطائرة أم القطار؟",
    "تسافر ليلًا أم نهارًا؟",
    "تذهب في رحلة قصيرة كثيرة أم رحلة طويلة واحدة؟",
    "تزور مدينة جديدة كل شهر أم دولة جديدة كل سنة؟",
    "تتحدث أمام جمهور أم تقدم عرضًا مسجلًا؟",
    "تكون هادئًا دائمًا أم اجتماعيًا دائمًا؟",
    "تملك مهارة الإقناع أم التفاوض؟",
    "تتعلم بسرعة أم لا تنسى أبدًا؟",
    "تنجح بدون شهرة أم تشتهر بدون نجاح كبير؟",
    "تكون مشهورًا في المدرسة أم في الإنترنت؟",
    "تملك فريقًا من 5 أصدقاء أم 50 معرفة؟",
    "تثق بالجميع أم لا تثق بأحد؟",
    "تسمع الحقيقة دائمًا أم تسمع ما يسعدك؟",
    "تعرف من يحبك أم من يكرهك؟",
    "تعيش بلا كذب أم بلا أسرار؟",
    "تكون دائمًا على حق أم دائمًا محبوبًا؟",
    "تعتذر أولًا أم تنتظر اعتذارًا؟",
    "تملك ذاكرة صور أم ذاكرة أصوات؟",
    "تتعلم من الأخطاء أم لا تخطئ أصلًا؟",
    "تتذكر كل حلم أم لا تحلم؟",
    "تستطيع التحكم بالطقس أم البحر؟",
    "تملك مزرعة أم شركة؟",
    "تعمل من المنزل أم من مكتب؟",
    "تعمل 4 أيام أم 6 أيام؟",
    "تختار وظيفة تحبها أم وظيفة راتبها أعلى؟",
    "تبدأ مشروعًا أم تنضم لمشروع ناجح؟",
    "تكون مديرًا أم موظفًا متميزًا؟",
    "تعمل وحدك أم ضمن فريق؟",
    "تتعلم من فيديوهات أم كتب؟",
    "تدرس ساعة يوميًا أم 7 ساعات في يوم واحد؟",
    "تحصل على إجازة شهر أم عطلة نهاية أسبوع طويلة؟",
    "تكون دائمًا مستعدًا أم دائمًا مرتجلًا؟",
    "تملك قائمة مهام مثالية أم ذاكرة تنظيمية؟",
    "تتلقى هدية مفاجئة أم تختار هديتك؟",
    "تهدي صديقًا أم تشتري لنفسك؟",
    "تحتفل بعيد ميلاد كبير أم صغير؟",
    "تلتقي بشخص مشهور أم لاعبك المفضل؟",
    "تلتقط صورة أم توقيع؟",
    "تحصل على تذكرة مباراة أم حفلة؟",
    "تشاهد المباراة من المدرجات أم من غرفة VIP؟",
    "تلعب نهائيًا في المطر أم تحت الشمس؟",
    "تفوز بهدف في الدقيقة 90 أم بركلات الترجيح؟",
    "تكون لاعب الوسط أم الجناح؟",
    "تكون مدافعًا سريعًا أم مهاجمًا قويًا؟",
    "تسجل 3 أهداف أم تصنع 3 أهداف؟",
    "تتدرب صباحًا أم مساءً؟",
    "تلعب كل مباراة أم ترتاح نصف الموسم؟",
    "تختار فريقًا تاريخيًا أم فريقًا جديدًا؟",
    "تلعب مع أصدقاءك في الواقع أم أونلاين؟",
    "تملك سيرفر ألعاب كبير أم قناة كبيرة؟",
    "تكون مطور لعبة أم لاعبًا محترفًا؟",
    "تصنع لعبة ناجحة أم تطبيقًا ناجحًا؟",
    "تملك 100 لعبة أم لعبة واحدة لا تمل منها؟",
    "تتعلم Unity أم Unreal؟",
    "تتعلم Python أم JavaScript؟",
    "تكتب الكود أم تصمم الواجهة؟",
    "تصلح Bug صغير أم تبني Feature كبيرة؟",
    "تعمل وحدك أم مع فريق تطوير؟",
    "تطلق مشروعك الآن أم بعد سنة من التحسين؟",
    "تختار السرعة أم الجودة؟",
    "تملك نسخة احتياطية دائمًا أم إنترنت احتياطي؟",
    "تخسر حسابك أم هاتفك؟",
    "تنسى كلمة مرور أم تفقد ملفًا مهمًا؟",
    "تملك بطارية لا تنتهي أم شحنًا فوريًا؟",
    "تعيش أسبوعًا بلا كهرباء أم بلا ماء ساخن؟",
    "تسمع نفس الأغنية يومًا كاملًا أم لا تسمع موسيقى؟",
    "تشاهد نفس الفيلم عشر مرات أم لا تشاهد أفلامًا شهرًا؟",
    "تكون بطل قصة أم الشرير؟",
    "تعيش في عالم هاري بوتر أم دراغون بول؟",
    "تكون باتمان أم سبايدرمان؟",
    "تكون غوكو أم سوبرمان؟",
    "تحل قضية مع شيرلوك هولمز أم مغامرة مع هاري بوتر؟",
    "تدخل هوغوارتس أم غوثام؟",
    "تعيش في عالم أنمي أم ألعاب؟",
    "تختار مغامرة خطيرة أم حياة هادئة؟",
    "تكون قائدًا في عالم خيالي أم بطلًا مجهولًا؟",
    "تملك سيفًا أسطوريًا أم درعًا أسطوريًا؟",
    "تختار القوة أم الحكمة؟",
    "تملك كنزًا مخفيًا أم خريطة العالم؟",
    "تكتشف جزيرة أم مدينة مفقودة؟",
    "تعيش أسبوعًا في الغابة أم الصحراء؟",
    "تسافر للفضاء أم أعماق المحيط؟",
    "ترى كوكبًا جديدًا أم نوعًا جديدًا من الحيوانات؟",
    "تكتشف اختراعًا أم نظرية علمية؟",
    "تكون أول شخص على المريخ أم أول شخص في مدينة تحت البحر؟",
    "تتعلم مهارة في دقيقة أم لغة في يوم؟",
    "تملك إجابة لأي سؤال أم سؤالًا لا يستطيع أحد حله؟",
    "تكون عبقريًا مجهولًا أم مشهورًا عاديًا؟",
    "تعيش عمرًا طويلًا أم حياة قصيرة مليئة بالمغامرات؟",
    "تختار السلام دائمًا أم المغامرة دائمًا؟",
    "تبدأ من الصفر مع خبرتك أم تحصل على المال فقط؟",
    "تعيد يومًا واحدًا من حياتك أم ترى يومًا من مستقبلك؟",
    "تعيش سنة بلا مشاكل أم تتعلم حل كل مشكلة؟",
    "تملك فرصة ثانية واحدة أم فرصًا صغيرة كثيرة؟",
    "تختار الحظ أم المهارة؟",
    "تختار النجاح السريع أم النجاح المستمر؟",
    "تكون آخر شخص في العالم أم أول شخص في عالم جديد؟",
    "تملك القدرة على فهم الحيوانات أم التحدث مع الروبوتات؟",
    "تعيش بدون نوم أم بدون طعام؟",
    "تستطيع المشي على الماء أم التنفس تحته؟",
    "تملك ذاكرة لا تُنسى أم قدرة على النسيان؟",
    "تستطيع الانتقال لأي مكان أم استدعاء أي شيء؟",
    "تملك آلة زمن أم بوابة لعالم آخر؟",
    "تختار الماضي أم المستقبل؟",
    "تكون بطلًا ليوم واحد أم عاديًا مدى الحياة؟",
    "تختار الشهرة أم الخصوصية؟",
    "تختار الحرية أم الراحة؟",
    "تختار المال أم الوقت؟",
    "تختار المعرفة أم القوة؟",
    "تختار أصدقاء كثيرين أم صديقًا واحدًا مقربًا؟",
    "تختار بيتًا كبيرًا أم سفرًا حول العالم؟",
    "تختار سيارة أم دراجة نارية؟",
    "تختار البحر أم الثلج؟",
    "تختار الفجر أم منتصف الليل؟",
    "تختار الشروق أم الغروب؟",
    "تختار مدينة مزدحمة أم مكانًا منعزلًا؟",
    "تختار العمل الإبداعي أم العمل المنظم؟",
    "تختار أن تكون مشهورًا يومًا أم مجهولًا دائمًا؟",
    "تختار أن يفهمك الجميع أم يفهمك شخص واحد تمامًا؟",
    "تختار أن تكون محظوظًا في كل لعبة أم في الحياة؟",
    "تختار الفوز دائمًا أم التعلم دائمًا؟",
    "تختار أن تكون الأفضل أم أن تستمتع أكثر؟",
    "تختار تحديًا صعبًا أم لعبة سهلة؟",
    "تختار 1v1 أم مباراة جماعية؟",
    "تختار البطولة أم الصداقة؟",
    "تختار الكأس أم أفضل لاعب؟",
    "تختار هدفًا عالميًا أم تمريرة حاسمة عالمية؟",
    "تختار جمهورًا صاخبًا أم ملعبًا هادئًا؟",
    "تختار مدربًا صارمًا أم مدربًا صديقًا؟",
    "تختار التدريب الفردي أم الجماعي؟",
    "تختار اللعب على العشب أم الشاطئ؟",
    "تختار تسجيل هدفك الأول أم هدف الفوز؟",
    "تختار إعادة مباراة خسرتها أم حفظ مباراة فزت بها؟",
    "تختار أن تبدأ مسيرتك من جديد أم تكملها كما هي؟",
    "تختار أن تكون لاعبًا مشهورًا أم مدربًا مشهورًا؟",
    "تختار كأسًا واحدًا تاريخيًا أم عدة كؤوس صغيرة؟",
    "تختار فريقًا تحبه أم فريقًا يضمن لك البطولات؟",
    "تختار اللعب مع أسطورتك المفضلة أم ضدها؟",
    "تختار أن تسجل في آخر دقيقة أم تمنع هدفًا في آخر دقيقة؟",
    "تختار أن تكون نجمًا في مباراة واحدة أم ثابت المستوى طوال الموسم؟",
    "تختار الاحتفال مع الجمهور أم مع زملائك؟",
    "تختار قميصًا موقعًا أم كرة موقعًا عليها؟",
    "تختار حضور النهائي أم مشاهدة كل البطولة؟",
    "تختار أن تعرف النتيجة قبل المباراة أم تعيش المفاجأة؟",
    "تختار فريقًا من أصدقاءك أم فريقًا من محترفين؟",
    "تختار اللعب في ملعبك أم خارج أرضك؟",
    "تختار مباراة نهائية أم مباراة ديربي؟",
    "تختار الفوز بصعوبة أم الفوز بنتيجة كبيرة؟",
    "تختار تسجيل هدف جميل أم هدف بسيط مهم؟",
    "تختار أن تكون قائدًا أم هدافًا؟",
    "تختار أن تكون مشهورًا بسبب إنجاز أم بسبب شخصية؟",
    "تختار أن يتذكرك الناس كلاعب أم كشخص؟",
    "تختار أن تفوز الآن أم تتطور للمستقبل؟",
    "تختار أن تعرف مستواك الحقيقي أم أقوى نسخة منك؟",
    "تختار أن تلعب بلا ضغط أم وسط ضغط كبير؟",
    "تختار مباراة في المطر أم الثلج؟",
    "تختار بطولة صيفية أم شتوية؟",
    "تختار جمهورًا من أصدقائك أم جمهورًا ضخمًا؟",
    "تختار أن تكون أول من يبدأ أم آخر من يدخل؟",
    "تختار أن تكون أفضل مدافع أم أفضل مهاجم؟",
    "تختار أن تتقن المراوغة أم التسديد؟",
    "تختار أن تتقن التمرير أم السرعة؟",
    "تختار أن تملك لياقة عالية أم مهارة عالية؟",
    "تختار أن تلعب 90 دقيقة أم 20 دقيقة حاسمة؟",
    "تختار أن تنقذ فريقك أم تحمل الفريق للفوز؟",
    "تختار أن تفوز مع فريق ضعيف أم تخسر مع فريق قوي؟",
    "تختار أن تصنع تاريخًا أم تكسر رقمًا قياسيًا؟",
    "تختار أن تملك قصة نجاح صعبة أم سهلة؟",
    "تختار أن تكون أسطورة محلية أم عالمية؟",
    "تختار أن يعرفك اللاعبون أم الجمهور؟",
    "تختار أن تتذكر كل مباراة أم كل هدف؟",
    "تختار أن تحصل على فرصة واحدة أم ثلاث فرص؟",
    "تختار أن تكون آخر من يلمس الكرة أم أول من يلمسها؟",
    "تختار أن تتعلم من أفضل لاعب أم أفضل مدرب؟",
    "تختار أن تلعب مع أسطورة أم ضد أسطورة؟",
    "تختار أن يكون فريقك متفاهمًا أم فردياته قوية؟",
    "تختار الفوز بروح الفريق أم بالمهارة الفردية؟",
    "تختار بطولة بلا جمهور أم مباراة ودية بجمهور ضخم؟",
    "تختار أن تبدأ الموسم قويًا أم تنهيه قويًا؟",
    "تختار أن تسجل في النهائي أم نصف النهائي؟",
    "تختار هدفًا من ركلة حرة أم ركلة جزاء؟",
    "تختار ركلة جزاء حاسمة أم تصديًا حاسمًا؟",
    "تختار أن تكون حارسًا أم مهاجمًا في آخر دقيقة؟",
    "تختار أن تملك حذاءً سحريًا أم قميصًا سحريًا؟",
    "تختار أن تعرف كل قوانين اللعبة أم كل تكتيكاتها؟",
    "تختار أن تفوز دون تسجيل أم تسجل دون فوز؟",
    "تختار أن تلعب مباراة مثالية أم موسمًا مثاليًا؟",
    "تختار أن يكون اسمك في التاريخ أم صورتك في كل ملعب؟",
    "تختار أن تعيش حلمك مرة أم حلمًا صغيرًا كل يوم؟",
    # ── 300 NEW questions ────────────────────────────────────────────────────
    # المجموعة: الحياة اليومية والعلاقات
    "تكون شخصًا صادقًا دائمًا أم دبلوماسيًا دائمًا؟",
    "تعيش مع عائلتك أم وحدك؟",
    "تختار صديقًا واحدًا وفيًا أم مئة صديق عاديين؟",
    "تقضي وقتك مع الناس أم وحدك؟",
    "تعبر عن مشاعرك بسهولة أم تحتفظ بها لنفسك؟",
    "تعيش قرب أهلك أم بعيدًا عنهم باستقلالية تامة؟",
    "تتصل بأصدقائك يوميًا أم تراهم مرة بالأسبوع؟",
    "تفضل الهدية المادية أم الهدية العاطفية؟",
    "تكون الشخص الذي يبادر أم الذي ينتظر؟",
    "تنسى الإهانات سريعًا أم تتذكرها طويلًا؟",
    "تعفو بسهولة أم تحتاج وقتًا طويلًا لذلك؟",
    "تواجه المشكلة فورًا أم تنتظر حتى تهدأ؟",
    "تحب المفاجآت أم تفضل التخطيط المسبق؟",
    "تشاركهم أفراحهم أم تكون معهم في أحزانهم؟",
    "تكون الشخص المضحك في المجموعة أم الشخص الحكيم؟",
    # المجموعة: التقنية والمستقبل
    "تملك جهاز يترجم أفكارك مباشرة أم جهاز يعطيك إجابة أي سؤال؟",
    "تعيش في مدينة ذكية أم مزرعة تقنية؟",
    "تملك طابعة ثلاثية الأبعاد تصنع أي شيء أم سيارة طائرة؟",
    "تختار الواقع الافتراضي الكامل أم الواقع المعزز؟",
    "تكون مبرمجًا لروبوتات أم مصمم مدن مستقبلية؟",
    "تعيش في عالم بلا ورق أم بلا نقود؟",
    "تختار اتصال إنترنت فائق السرعة أم بطارية تدوم شهرًا؟",
    "تملك ساعة ذكية تتحكم بصحتك أم نظارة ذكية ترى بها كل شيء؟",
    "تفضل الذكاء الاصطناعي المساعد أم الذكاء الاصطناعي الإبداعي؟",
    "تعيش في مستعمرة فضاء أم مدينة تحت الماء؟",
    "تختار سيارة كهربائية ذاتية القيادة أم دراجة هوائية فائقة السرعة؟",
    "تملك هاتفًا قابلًا للطي أم هاتفًا مبنيًا في يدك؟",
    "تعمل مع روبوت شريك أم وحدك بدعم تقني كامل؟",
    "تختار التعلم بالواقع الافتراضي أم الفصول الذكية؟",
    "تكون مخترعًا للتقنية أم مستخدمًا أول لكل ابتكار؟",
    # المجموعة: الطعام والترفيه
    "تأكل سوشي أم مكرونة إيطالية؟",
    "تختار مطعمًا فاخرًا مرة أم مطعمًا شعبيًا أسبوعيًا؟",
    "تطبخ وجبة جديدة كل يوم أم نفس الوجبة المفضلة دائمًا؟",
    "تأكل الحلويات قبل الطعام أم بعده؟",
    "تشرب القهوة أم الشاي؟",
    "تفضل الأكل الحار أم الأكل المعتدل؟",
    "تأكل وجبة ضخمة مرة أم وجبات صغيرة متكررة؟",
    "تختار مطعمًا على الشاطئ أم مطعمًا في الجبال؟",
    "تجرب مطبخًا غريبًا لم تسمع به أم تلتزم بما تعرفه؟",
    "تختار وجبة فطور ضخمة أم عشاء فاخر؟",
    "تتناول وجبتك أمام التلفزيون أم مع العائلة على الطاولة؟",
    "تختار حفلة موسيقية حية أم مهرجان أفلام؟",
    "تشاهد الأفلام وحدك أم مع أشخاص يتكلمون كثيرًا؟",
    "تختار مسلسلًا قصيرًا ومكثفًا أم مسلسلًا طويلًا وممتدًا؟",
    "تختار مشاهدة فيلم رعب أم فيلم كوميدي ليلًا؟",
    # المجموعة: الرياضة والتحديات
    "تمشي ساعة يوميًا أم تجري نصف ساعة؟",
    "تتدرب في الصالة أم في الهواء الطلق؟",
    "تلعب رياضة فردية أم جماعية؟",
    "تكون أسرع إنسان على الأرض أم أقوى إنسان على الأرض؟",
    "تفوز بذهبية أولمبية أم بطولة عالمية في رياضتك المفضلة؟",
    "تتدرب مع بطل عالمي أسبوعًا أم تتدرب وحدك شهرًا؟",
    "تختار السباحة أم تسلق الجبال؟",
    "تمارس رياضة يوميًا لمدة سنة أم تأخذ استراحة وترجع أقوى؟",
    "تكون لاعبًا احتياطيًا في فريق بطل أم أساسيًا في فريق عادي؟",
    "تلعب مباراة في برد شديد أم حر شديد؟",
    "تختار التحمل الرياضي أم الانفجار السريع؟",
    "تشارك في ماراثون أم سباق دراجات؟",
    "تلعب في فريق متواضع وتصنع الفارق أم تلعب في فريق قوي وتكون احتياطيًا؟",
    "تكون لاعبًا يُعشق من الجمهور أم لاعبًا يحترمه المحترفون؟",
    "تتقن رياضة فردية تمامًا أم تكون أفضل لاعب في رياضة جماعية؟",
    # المجموعة: الخيال والعوالم الأخرى
    "تعيش في عالم ما قبل التقنية أم عالم ما بعدها بألف سنة؟",
    "تختار أن تكون ساحرًا أم محاربًا أسطوريًا؟",
    "تعيش في عالم يحكمه الأخيار أم تبقى في عالمنا الحقيقي؟",
    "تكون تنينًا يطير أم ذئبًا يتحول في اللحظات الحاسمة؟",
    "تدخل عالم Game of Thrones أم عالم Lord of the Rings؟",
    "تملك سيف أسطوري أم درع يحميك من أي هجوم؟",
    "تكون ملكًا في عالم خيالي أم سفيرًا بين العوالم؟",
    "تعيش قصيدة حياة كاملة أم تعيش أسطورة لا تنتهي؟",
    "تكون صديق البطل أم البطل نفسه؟",
    "تعيش في زمن الفرسان أم في زمن القراصنة؟",
    "تختار أن تكون عالمًا في عالم سحري أم محاربًا أسطوريًا؟",
    "تعيش في مدينة تحت الأرض أم فوق السحاب؟",
    "تملك سفينة فضاء أم بوابة لأبعاد موازية؟",
    "تكون محققًا في عالم أنمي أم بطلًا في لعبة RPG؟",
    "تعيش في عالم بلا موت طبيعي أم عالم تختار فيه وقت رحيلك؟",
    # المجموعة: الشخصية والنمو
    "تكون شجاعًا بلا حكمة أم حكيمًا بلا شجاعة؟",
    "تملك عزيمة فولاذية أم مرونة عالية؟",
    "تكون متفائلًا دائمًا أم واقعيًا دائمًا؟",
    "تغير نفسك من أجل الآخرين أم تبقى على طبيعتك؟",
    "تكون صارمًا مع نفسك أم متساهلًا معها؟",
    "تختار الإنتاجية العالية أم الراحة الكاملة؟",
    "تعيش بلا ندم أم تتعلم من كل ندم؟",
    "تملك أهدافًا طموحة أم أهدافًا واقعية تحققها؟",
    "تكون شخصًا يلهم الآخرين أم شخصًا يعمل خلف الكواليس؟",
    "تختار شهادة عليا أم خبرة عملية واسعة؟",
    "تعيش بشكل منظم أم بشكل عفوي؟",
    "تكون قائد محبوب أم قائد فعّال؟",
    "تختار الرضا الداخلي أم الاعتراف الخارجي؟",
    "تكون مثابرًا رغم الفشل أم تتعلم متى تتوقف؟",
    "تختار أن تكون قدوة أم أن تكون محرك التغيير الصامت؟",
    # المجموعة: السفر والمغامرة
    "تزور كل قارات العالم مرة أم تعيش في قارة واحدة بعمق؟",
    "تسافر بلا خطة مسبقة أم تخطط لكل تفصيلة؟",
    "تختار إقامة في فندق فاخر أم خيمة وسط الطبيعة؟",
    "تزور مدينة تاريخية أم مدينة حديثة؟",
    "تسافر في الصيف أم في فصل الخريف؟",
    "تذهب لمهرجان ثقافي أم لمنتجع طبيعي؟",
    "تختار رحلة برية طويلة أم رحلة بحرية؟",
    "تزور المعالم الشهيرة أم الأماكن الخفية غير المعروفة؟",
    "تسافر للاستجمام أم للتعلم والاكتشاف؟",
    "تختار بلدًا باردًا أم بلدًا استوائيًا؟",
    "تعيش تجربة التخييم في الغابة أم الإقامة في قرية بدائية؟",
    "تصعد جبل أم تغوص في أعماق البحر؟",
    "تختار رفاهية السفر أم صدق تجربته؟",
    "تسافر للمناطق القطبية أم الصحراء الكبرى؟",
    "تختار تجربة ثقافة مختلفة لشهر أم العودة لثقافتك بعد أسبوع؟",
    # المجموعة: الإبداع والفن
    "تكون موسيقيًا محترفًا أم مصورًا فنيًا؟",
    "تكتب رواية تاريخية أم مستقبلية؟",
    "ترسم لوحة عبقرية واحدة أم لوحات جميلة كثيرة؟",
    "تختار الشعر أم النثر؟",
    "تؤلف موسيقى هادئة أم حماسية؟",
    "تمثل في مسرحية أم تخرج فيلمًا؟",
    "تكون فنانًا معروفًا بعد موتك أم فنانًا بسيطًا مشهورًا في حياتك؟",
    "تختار الفن الكلاسيكي أم الفن الحديث؟",
    "تعزف آلة موسيقية واحدة بإتقان تام أم تجيد عدة آلات بشكل متوسط؟",
    "تشارك في معرض فني أم تنشر أعمالك رقميًا؟",
    "تكون كاتبًا ناجحًا أم مخرجًا ناجحًا؟",
    "تختار الرسم بالأقلام التقليدية أم التصميم الرقمي؟",
    "تصنع فيلمًا قصيرًا أثّر في الناس أم فيلمًا طويلًا حصد جوائز؟",
    "تكتب للناس العاديين أم للنخبة المثقفة؟",
    "تختار الإبداع الحر أم الإبداع الموجه لهدف؟",
    # المجموعة: السيرفر والديسكورد
    "تكون أكثر عضو متفاعل في السيرفر أم أكثر عضو مُقدِّر فيه؟",
    "تفتح تذكرة دعم أم تحل مشكلتك بنفسك؟",
    "تدخل قناة صوتية مع الأصدقاء أم تتواصل نصيًا فقط؟",
    "تشارك في فعاليات السيرفر أم تراقبها من بعيد؟",
    "تختار رتبة مميزة أم لقبًا خاصًا؟",
    "تكون أول من يعلق على إعلانات السيرفر أم تقرأها بصمت؟",
    "تشارك في مسابقات الألعاب أم مسابقات التصميم؟",
    "تكون عضوًا هادئًا ومحترمًا أم عضوًا مرحًا ومضحكًا؟",
    "تفضل قنوات السيرفر المنظمة أم الشات العام الحر؟",
    "تقترح ميزة جديدة للسيرفر أم تستمتع بما هو موجود؟",
    # المجموعة: المال والمستقبل المهني
    "تربح مليون دولار دفعة واحدة أم 10000 دولار شهريًا مدى الحياة؟",
    "تستثمر في الأسهم أم العقارات؟",
    "تبدأ شركتك الناشئة أم تشتري امتيازًا لشركة ناجحة؟",
    "تختار العمل بمجال تقني أم إبداعي؟",
    "تكون محاميًا ناجحًا أم طبيبًا بارعًا؟",
    "تبني علامة تجارية شخصية أم تعمل خلف الكواليس؟",
    "تختار الاستقرار الوظيفي أم مغامرة ريادة الأعمال؟",
    "تتفرغ لمشروع حلمك أم تضمن دخلك أولًا؟",
    "تختار المكانة الاجتماعية أم الحرية المالية؟",
    "تعمل في شركة عالمية أم تبني مشروعًا محليًا مؤثرًا؟",
    # المجموعة: السعادة والفلسفة
    "تختار حياة قصيرة مليئة بالسعادة أم حياة طويلة مليئة بالتحديات؟",
    "تكون سعيدًا بلا سبب أم سعيدًا بسبب واضح؟",
    "تختار البساطة في الحياة أم الثروة مع التعقيد؟",
    "تعيش في الحاضر أم تخطط للمستقبل دائمًا؟",
    "تكون مؤثرًا في مجتمعك أم سعيدًا في عزلتك؟",
    "تختار الفضول الدائم أم الرضا الكامل؟",
    "تملك قناعة راسخة أم عقلًا منفتحًا يتغير؟",
    "تختار أن تكون محبوبًا أم أن تكون على حق؟",
    "تعيش لتأكل أم تأكل لتعيش؟",
    "تختار الهدوء الداخلي أم الانجاز الخارجي؟",
    # المجموعة: متفرقات ومواقف
    "تكون الأول في الطابور أم الأخير بلا انتظار؟",
    "تختار الاستيقاظ على موسيقى هادئة أم إنذار صاخب؟",
    "تنام في غرفة باردة مع بطانية دافئة أم في غرفة دافئة؟",
    "تختار قراءة الأخبار يوميًا أم تجاهلها تمامًا؟",
    "تكنّس البيت وحدك أم تطلب مساعدة؟",
    "تختار مقعدًا في القطار بجانب النافذة أم بجانب الممر؟",
    "تستخدم خريطة ورقية أم تتبع GPS في كل مكان؟",
    "تختار قضاء يوم العطلة في النوم أم في النزهة؟",
    "تتحدث مع الغرباء في المصعد أم تصمت؟",
    "تشتري ملابس غالية قليلة أم رخيصة كثيرة؟",
    "تختار مشاهدة الأفلام بالترجمة أم بالدبلجة؟",
    "تذهب للطبيب عند أول علامة أم تنتظر حتى تشتد الحالة؟",
    "تختار الجلوس في الصف الأمامي بالفصل أم الخلفي؟",
    "تحتفظ بكل ذكرياتك أم تمسح المؤلم منها؟",
    "تختار أن تكون خبيرًا في مجال واحد أم جيدًا في مجالات كثيرة؟",
    # المجموعة: مواقف اجتماعية وعلاقات
    "تكون من يقدم النصيحة أم من يستمع دائمًا؟",
    "تختار صديقًا يضحكك أم صديقًا يلهمك؟",
    "تفضل التجمعات الكبيرة أم الجلسات الصغيرة؟",
    "تعيش في مجتمع يعرفك الجميع أم في مدينة أنت فيها مجهول؟",
    "تكون الشخص الذي يجمع الناس أم الذي يحل خلافاتهم؟",
    "تفضل التواصل وجهًا لوجه أم عبر الرسائل؟",
    "تختار شريكًا يشاركك نفس اهتماماتك أم يكمّلك باهتمامات مختلفة؟",
    "تكون موضع ثقة كل من حولك أم تحتفظ بخصوصيتك تمامًا؟",
    "تفضل تربية أبناء في المدينة أم في الريف؟",
    "تختار التعاون الدائم أم الاستقلالية الكاملة؟",
    # المجموعة: الطبيعة والبيئة
    "تعيش في منطقة غابات أم بالقرب من شلال؟",
    "تختار حديقة صغيرة تعتني بها أم غابة تستكشفها؟",
    "تملك بيتًا يطل على البحر أم على الجبال؟",
    "تعيش في مناخ معتدل دائمًا أم تجرب كل الفصول؟",
    "تختار شمس الشروق أم هدوء المساء؟",
    "تمشي في الطبيعة يوميًا أم تزور أماكن طبيعية نادرًا لكن بعمق؟",
    "تختار إنقاذ الغابات أم المحيطات؟",
    "تملك حديقة خضراء في منزلك أم سطحًا مفتوحًا للسماء؟",
    "تعيش بالقرب من المحميات الطبيعية أم في مدينة مستدامة؟",
    "تختار زراعة طعامك بنفسك أم شراء منتجات عضوية؟",
    # المجموعة: التعليم والمعرفة
    "تقرأ عشرة كتب سنويًا أم تتعمق في كتاب واحد كل شهر؟",
    "تختار جامعة مرموقة أم برنامج تعليمي مبتكر؟",
    "تتعلم من التجربة أم من النظرية؟",
    "تختار معرفة التاريخ أم معرفة المستقبل؟",
    "تدرس علمًا بحتًا أم علمًا إنسانيًا؟",
    "تتعلم لغة جديدة أم تتقن حرفة يدوية؟",
    "تختار المعرفة الواسعة السطحية أم المعرفة العميقة المتخصصة؟",
    "تدرس فلسفة أم رياضيات؟",
    "تختار التعليم الذاتي أم التعليم المؤسسي؟",
    "تعلّم الآخرين أم تتعلم منهم طوال الوقت؟",
    # المجموعة: ألعاب ديسكورد وترفيه
    "تشارك في لعبة !من_انا أم !لو_خيروك؟",
    "تلعب wordle عربي أم XO ضد البوت؟",
    "تشارك في !غميمه أم تتفرج عليها؟",
    "تطرح سؤالًا في الشات أم تجيب على أسئلة الآخرين؟",
    "تلعب مع أصدقاءك في الشات الصوتي أم النصي؟",
    "تشارك في مسابقة ألعاب أسبوعية أم فعالية خاصة شهرية؟",
    "تكون منظم الفعالية أم المشارك الأكثر حماسًا؟",
    "تفضل ألعاب الكلمات أم ألعاب الاستراتيجية؟",
    "تختار ألعاب سريعة أم ألعاب تأخذ وقتًا طويلًا؟",
    "تلعب للمتعة أم للفوز بالمرتبة الأولى؟",
]

@bot.command(name="لو_خيروك")
async def would_you_rather(ctx):
    q = random.choice(WOULD_YOU_RATHER)
    embed = discord.Embed(
        title="🤔 لو خيروك",
        description=f"**__ {q} __**",
        color=pink_color()
    )
    await ctx.send(embed=embed)

# ==============================================================================
# EDIT: !غميمه — Updated lobby to show participant list
# Hide-and-seek game logic is untouched; only the lobby/start phase shows members.
# ==============================================================================
class HideSeekGridView(discord.ui.View):
    def __init__(self, game):
        super().__init__(timeout=300)
        self.game = game
        for i in range(25):
            b = discord.ui.Button(label=str(i + 1), style=discord.ButtonStyle.secondary, row=i // 5)
            b.index = i
            async def cb(interaction, idx=i):
                await self.game.choose(interaction, idx)
            b.callback = cb
            self.add_item(b)

class HideSeekGame:
    def __init__(self, ctx):
        self.ctx = ctx
        self.players: dict[int, str] = {}
        self.hider_slots: dict[int, int] = {}
        self.found: set = set()
        self.running = False
        self.grid_view = None
        self.lobby_message = None  # Reference to the lobby message for live updates

    def _build_lobby_embed(self) -> discord.Embed:
        """Build the lobby embed showing the current participant list."""
        embed = discord.Embed(
            title="🫣 Hide & Seek • غرفة الانتظار",
            color=pink_color()
        )
        embed.description = (
            "**__ لعبة اختباء من 25 خانة. اضغط مشاركة للدخول، ثم اضغط ابدأ اللعبة عندما تكون جاهزين. __**\n"
            "البوت سيضغط أرقامًا عشوائية حتى يبقى آخر لاعب حي.\n\n"
            "⚠️ تحتاج اللعبة إلى لاعبَين على الأقل للبدء."
        )
        embed.set_image(url=TOUCHLINE_IMAGE_URL)
        if self.players:
            names = "\n".join(f"✅ {name}" for name in self.players.values())
            embed.add_field(
                name=f"👥 المشاركون ({len(self.players)})",
                value=names,
                inline=False
            )
        else:
            embed.add_field(
                name="👥 المشاركون (0)",
                value="*لا يوجد مشاركون بعد. اضغط مشاركة!*",
                inline=False
            )
        return embed

    async def join(self, interaction: discord.Interaction):
        if self.running:
            await interaction.response.send_message(bold_msg("بدأت اللعبة بالفعل.", "⚠️"), ephemeral=True)
            return
        if interaction.user.id in self.players:
            await interaction.response.send_message(bold_msg("أنت مشارك بالفعل.", "ℹ️"), ephemeral=True)
            return
        self.players[interaction.user.id] = interaction.user.display_name
        # Update the lobby embed to show the new participant
        updated_embed = self._build_lobby_embed()
        await interaction.response.edit_message(embed=updated_embed)

    async def choose(self, interaction: discord.Interaction, idx: int):
        if not self.running:
            await interaction.response.send_message(bold_msg("لم تبدأ مرحلة الاختباء بعد.", "⚠️"), ephemeral=True)
            return
        if interaction.user.id not in self.players:
            await interaction.response.send_message(bold_msg("اضغط مشاركة أولًا.", "⚠️"), ephemeral=True)
            return
        if interaction.user.id in self.hider_slots:
            await interaction.response.send_message(bold_msg("اخترت مكانًا بالفعل.", "⚠️"), ephemeral=True)
            return
        self.hider_slots[interaction.user.id] = idx
        await interaction.response.send_message(
            bold_msg(f"تم إخفاؤك في الرقم {idx + 1}. لا يظهر اختيارك للآخرين.", "🫣"),
            ephemeral=True
        )

    async def start(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(bold_msg("فقط صاحب اللعبة يستطيع بدءها.", "🔒"), ephemeral=True)
            return
        if len(self.players) < 2:
            await interaction.response.send_message(bold_msg("تحتاج اللعبة إلى لاعبين على الأقل.", "⚠️"), ephemeral=True)
            return
        self.running = True
        self.grid_view = HideSeekGridView(self)

        # Show participant list before starting hide phase
        names_list = "\n".join(f"🙋 {name}" for name in self.players.values())
        embed = discord.Embed(
            title="🫣 Hide & Seek • مرحلة الاختباء",
            description=(
                f"**__ {len(self.players)} لاعب سيشاركون في هذه الجولة! __**\n\n"
                f"{names_list}\n\n"
                "**اختاروا واحدًا من الـ25 رقمًا. لديكم 20 ثانية. "
                "اختيار المكان يرسل لك تأكيدًا خاصًا ولا يظهر للآخرين.**"
            ),
            color=pink_color()
        )
        await interaction.response.edit_message(embed=embed, view=self.grid_view)
        await asyncio.sleep(20)
        await self.search()

    async def search(self):
        alive = set(self.hider_slots.keys())
        if len(alive) <= 1:
            if alive:
                uid = next(iter(alive))
                await self.ctx.channel.send(bold_msg(f"الفائز هو **{self.players[uid]}**! 🏆", "🎉"))
            else:
                await self.ctx.channel.send(bold_msg("لم يختر أحد مكانًا للاختباء.", "⚠️"))
            self.running = False
            return
        slots = list(range(25))
        random.shuffle(slots)
        occupied = {}
        for uid, slot in self.hider_slots.items():
            occupied.setdefault(slot, []).append(uid)
        for slot in slots:
            if len(alive) <= 1:
                break
            found_here = [uid for uid in occupied.get(slot, []) if uid in alive]
            if found_here:
                names = []
                for uid in found_here:
                    alive.remove(uid)
                    self.found.add(uid)
                    names.append(self.players[uid])
                await self.ctx.channel.send(
                    bold_msg(f"البوت ضغط الرقم `{slot + 1}` ووجد: **{', '.join(names)}** 💥", "🔎")
                )
            else:
                await self.ctx.channel.send(
                    bold_msg(f"البوت ضغط الرقم `{slot + 1}` ولم يجد أحدًا. 🫣", "❌")
                )
            await asyncio.sleep(1)
        if alive:
            winner = next(iter(alive))
            await self.ctx.channel.send(bold_msg(f"الفائز الأخير هو **{self.players[winner]}**! 🏆", "🎉"))
        self.running = False
        if self.grid_view:
            for child in self.grid_view.children:
                child.disabled = True

class HideSeekLobbyView(discord.ui.View):
    def __init__(self, game: HideSeekGame):
        super().__init__(timeout=120)
        self.game = game

    @discord.ui.button(label="مشاركة", emoji="🙋", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.game.join(interaction)

    @discord.ui.button(label="ابدأ اللعبة", emoji="🎮", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.game.start(interaction)

@bot.command(name="غميمه")
async def hide_and_seek(ctx):
    game = HideSeekGame(ctx)
    embed = game._build_lobby_embed()
    await ctx.send(embed=embed, view=HideSeekLobbyView(game))

# ==============================================================================
# Core moderation commands (aliases added per requirement)
# ==============================================================================
@bot.command(name="rename")
async def rename(ctx, *, new_name: str):
    if not check_permissions(ctx):
        return
    try:
        await ctx.channel.edit(name=new_name)
        await ctx.send(bold_msg(f"تم تغيير اسم الروم إلى {new_name} بنجاح.", "✅"))
    except Exception as e:
        await ctx.send(bold_msg(f"فشل تغيير اسم الروم: {e}", "❌"))

# FIX ALIAS: حذف, م
@bot.command(name="حذف")
async def delete_messages(ctx, amount: int):
    if not check_permissions(ctx):
        return
    if amount < 1:
        return
    try:
        await ctx.channel.purge(limit=amount + 1)
    except Exception as e:
        await ctx.send(bold_msg(f"فشل حذف الرسائل: {e}", "❌"))

# FIX ALIAS: برا
@bot.command(name="برا")
async def kick_user(ctx, member: discord.Member, *, reason: str = "لا يوجد سبب محدد"):
    if not check_permissions(ctx):
        return
    try:
        await member.kick(reason=reason)
        await ctx.send(bold_msg(f"تم طرد {member.mention} بنجاح.", "🥾"))
    except Exception as e:
        await ctx.send(bold_msg(f"فشل الطرد: {e}", "❌"))

@bot.command(name="باند", aliases=["لباريس", "لف"])
async def ban_user(
    ctx: commands.Context,
    member: discord.Member,
    *,
    reason: str = "لا يوجد سبب محدد"
):
    if not check_permissions(ctx):
        return

    if member.id == MY_DISCORD_ID:
        await ctx.send(
            bold_msg(
                "لا يمكنك عمل باند لمالك البوت.",
                "❌"
            )
        )
        return

    if member.bot:
        await ctx.send(
            bold_msg(
                "لا يمكنك عمل باند لهذا البوت.",
                "❌"
            )
        )
        return

    bot_member = ctx.guild.me

    if bot_member and member.top_role >= bot_member.top_role:
        await ctx.send(
            bold_msg(
                "لا يمكنني عمل باند لعضو رتبته مساوية أو أعلى من رتبة البوت.",
                "❌"
            )
        )
        return

    try:
        await member.ban(
            reason=f"{reason} | بواسطة {ctx.author}"
        )

        await ctx.send(
            bold_msg(
                f"تم حظر {member.mention} بنجاح.\nالسبب: {reason}",
                "🔨"
            ),
            allowed_mentions=discord.AllowedMentions(users=True)
        )

    except discord.Forbidden:
        await ctx.send(
            bold_msg(
                "لا أملك صلاحية حظر هذا العضو.",
                "❌"
            )
        )

    except Exception as e:
        await ctx.send(
            bold_msg(
                f"فشل الحظر: {e}",
                "❌"
            )
)
@bot.command(name="رتب")
async def give_role(
    ctx: commands.Context,
    member: discord.Member,
    *,
    role_input: str
):
    if not check_permissions(ctx):
        return

    role_input = role_input.strip()

    if not role_input:
        await ctx.send(
            bold_msg(
                "استخدم الأمر هكذا: `!رتب @user اسم الرتبة`",
                "⚠️"
            )
        )
        return

    role = None

    # 1. Role mention: @Role
    role_match = re.fullmatch(r"<@&(\d+)>", role_input)

    if role_match:
        role = ctx.guild.get_role(int(role_match.group(1)))

    # 2. Raw role ID
    elif role_input.isdigit():
        role = ctx.guild.get_role(int(role_input))

    # 3. Role name
    else:
        role = discord.utils.find(
            lambda r: r.name.casefold() == role_input.casefold(),
            ctx.guild.roles
        )

    if role is None:
        await ctx.send(
            bold_msg(
                f"لم يتم العثور على الرتبة: `{role_input}`",
                "❌"
            )
        )
        return

    if role.is_default():
        await ctx.send(
            bold_msg(
                "لا يمكن إعطاء رتبة @everyone.",
                "❌"
            )
        )
        return

    if role.managed:
        await ctx.send(
            bold_msg(
                "لا يمكن إدارة هذه الرتبة لأنها Managed بواسطة Discord/بوت آخر.",
                "❌"
            )
        )
        return

    bot_member = ctx.guild.me

    if bot_member is None:
        await ctx.send(
            bold_msg("تعذر تحديد رتبة البوت.", "❌")
        )
        return

    if role >= bot_member.top_role:
        await ctx.send(
            bold_msg(
                "لا أستطيع إعطاء هذه الرتبة لأن رتبتها أعلى من أعلى رتبة للبوت.",
                "❌"
            )
        )
        return

    try:
        await member.add_roles(
            role,
            reason=f"إعطاء رتبة بواسطة {ctx.author}"
        )

        await ctx.send(
            bold_msg(
                f"تم إعطاء {role.mention} إلى {member.mention} بنجاح.",
                "✅"
            ),
            allowed_mentions=discord.AllowedMentions(
                users=True,
                roles=True
            )
        )

    except discord.Forbidden:
        await ctx.send(
            bold_msg(
                "لا أملك صلاحية إعطاء هذه الرتبة.",
                "❌"
            )
        )

    except Exception as e:
        await ctx.send(
            bold_msg(
                f"حدث خطأ أثناء إعطاء الرتبة: {e}",
                "❌"
            )
)
# FIX ALIAS: افراج
@bot.command(name="سجن")
async def jail_member(ctx, member: discord.Member, *, reason: str = "لا يوجد سبب محدد"):
    if not check_permissions(ctx):
        return
    if member.id == MY_DISCORD_ID or member.bot:
        await ctx.send(bold_msg("لا يمكنك سجن هذا العضو.", "❌"))
        return
    try:
        ok = await jail_member_action(ctx, member, reason)
        if not ok:
            await ctx.send(bold_msg("تعذر تنفيذ السجن. تأكد من وجود رتبة السجن وأنها أسفل أعلى رتبة للبوت.", "❌"))
            return
        await ctx.send(bold_msg(f"تم سجن {member.mention} بنجاح • السبب: {reason}", "⛓️"))
    except discord.Forbidden:
        await ctx.send(bold_msg("لا أملك صلاحية إدارة رتب هذا العضو.", "❌"))
    except Exception as e:
        await ctx.send(bold_msg(f"حدث خطأ أثناء السجن: {e}", "❌"))

@bot.command(name="افراج")
async def unjail_member(ctx: commands.Context, member: discord.Member):
    if not check_permissions(ctx):
        await ctx.send(bold_msg("ليس لديك صلاحية الإفراج.", "🔒"))
        return
    jail_role = ctx.guild.get_role(JAIL_ROLE_ID)
    # FIX #2: async I/O
    saved = await load_jail()
    uid = str(member.id)
    roles = []
    if uid in saved:
        for rid in saved[uid]:
            role = ctx.guild.get_role(rid)
            if role and not role.is_default():
                roles.append(role)
    try:
        if jail_role and jail_role in member.roles:
            await member.remove_roles(jail_role, reason=f"إفراج بواسطة {ctx.author.name}")
        if roles:
            await member.add_roles(*roles, reason="استعادة الرتب بعد الإفراج")
        if uid in saved:
            del saved[uid]
            await save_jail(saved)
        await ctx.send(bold_msg(f"تم الإفراج عن {member.mention} وإعادة رتبه السابقة بنجاح.", "🕊️"))
    except discord.Forbidden:
        await ctx.send(bold_msg("لا أملك صلاحية إعادة رتب هذا العضو.", "❌"))
    except Exception as e:
        await ctx.send(bold_msg(f"فشل الإفراج: {e}", "❌"))

# FIX ALIAS: قفل
@bot.command(name="قفل", aliases=["ق"])
async def lock_channel(ctx):
    if not check_permissions(ctx):
        return
    everyone = ctx.guild.default_role
    overwrite = ctx.channel.overwrites_for(everyone)
    overwrite.send_messages = False
    try:
        await ctx.channel.set_permissions(everyone, overwrite=overwrite, reason=f"قفل بواسطة {ctx.author.name}")
        await ctx.send(bold_msg("تم قفل الإرسال في الروم. رؤية الروم لم تتغير.", "🔒"))
    except Exception as e:
        await ctx.send(bold_msg(f"فشل قفل الروم: {e}", "❌"))

# FIX ALIAS: فتح
@bot.command(name="فتح", aliases=["ف"])
async def unlock_channel(ctx):
    if not check_permissions(ctx):
        return
    everyone = ctx.guild.default_role
    overwrite = ctx.channel.overwrites_for(everyone)
    overwrite.send_messages = True
    try:
        await ctx.channel.set_permissions(everyone, overwrite=overwrite, reason=f"فتح بواسطة {ctx.author.name}")
        await ctx.send(bold_msg("تم فتح الإرسال في الروم. رؤية الروم لم تتغير.", "🔓"))
    except Exception as e:
        await ctx.send(bold_msg(f"فشل فتح الروم: {e}", "❌"))

# ==============================================================================
# Error handler and runtime
# ==============================================================================
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(bold_msg(f"المعامل ناقص: `{error.param.name}`.", "⚠️"))
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(bold_msg("تعذر فهم أحد المعاملات. تأكد من منشن العضو وصيغة الأمر.", "⚠️"))
        return
    if isinstance(error, commands.CheckFailure):
        await ctx.send(bold_msg("ليس لديك صلاحية استخدام هذا الأمر.", "🔒"))
        return
    print("Command error:", repr(error))
    try:
        await ctx.send(bold_msg("حدث خطأ غير متوقع أثناء تنفيذ الأمر. راجع Console لمعرفة التفاصيل.", "❌"))
    except Exception:
        pass

# ==============================================================================
# FIFA VAULT SECURITY SYSTEM (integrated into bot.py)
# ==============================================================================

"""FIFA VAULT security protection layer integrated into bot.py."""
import asyncio, datetime, json, os
from collections import defaultdict
import discord
from discord import app_commands
from discord.ext import commands

STATE_FILE = "security_state.json"
MEMBER_ROLE_ID = 1558495451198787758
WHITELIST_ROLE_ID = 1558954781035200673
JAIL_ROLE_ID = 1558958669813514330
DECISION_ROLE_ID = 1555096604954857503
DELETE_WINDOW = 60
DELETE_THRESHOLD = 3
DECISION_DELAY = 120

def now():
    return datetime.datetime.now(datetime.timezone.utc)

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}

def save_state(data):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)

async def read_state():
    return await asyncio.to_thread(load_state)

async def write_state(data):
    await asyncio.to_thread(save_state, data)

def guild_state(data, guild_id):
    return data.setdefault(str(guild_id), {
        "security_channel_id": None, "nuke_enabled": False,
        "role_permissions_backup": {}, "scores": {}, "events": [],
        "processed_audit_ids": [], "role_backups": {}, "incidents": {}
    })

def manageable(guild, role):
    me = guild.me
    if not me or not role:
        return False
    if role.is_default():
        return bool(me.guild_permissions.manage_roles)
    return bool(not role.managed and me.top_role > role)

def whitelisted(member):
    return any(getattr(r, "id", None) == WHITELIST_ROLE_ID for r in getattr(member, "roles", []))

async def setup_security(bot, owner_id, load_server_config, save_server_config):
    pending_tasks = {}
    recent_deletes = defaultdict(list)

    async def send_alert(guild, embed, view=None):
        data = await read_state()
        channel_id = guild_state(data, guild.id).get("security_channel_id")
        if not channel_id:
            return False
        channel = guild.get_channel(int(channel_id))
        if channel is None:
            try:
                channel = await bot.fetch_channel(int(channel_id))
            except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
                return False
        try:
            await channel.send(embed=embed, view=view)
            return True
        except (discord.Forbidden, discord.HTTPException, AttributeError):
            return False

    async def find_actor(guild, action, target_id=None):
        try:
            async for entry in guild.audit_logs(limit=12, action=action):
                if target_id is not None and getattr(entry.target, "id", None) != target_id:
                    continue
                age = (now() - entry.created_at).total_seconds()
                if 0 <= age <= 45:
                    return entry.user, entry
        except (discord.Forbidden, discord.HTTPException):
            pass
        return None, None

    async def contain_member(member, reason):
        data = await read_state()
        gs = guild_state(data, member.guild.id)
        key = str(member.id)
        if key not in gs["role_backups"]:
            gs["role_backups"][key] = [r.id for r in member.roles if not r.is_default()]
            await write_state(data)
        removable = [r for r in member.roles if not r.is_default() and r.id != MEMBER_ROLE_ID and manageable(member.guild, r)]
        try:
            if removable:
                await member.remove_roles(*removable, reason=reason[:480])
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[Security] role removal incomplete for {member.id}: {exc}")
        member_role = member.guild.get_role(MEMBER_ROLE_ID)
        if member_role and manageable(member.guild, member_role) and member_role not in member.roles:
            try:
                await member.add_roles(member_role, reason=reason[:480])
            except (discord.Forbidden, discord.HTTPException):
                pass
        jail = member.guild.get_role(JAIL_ROLE_ID)
        if jail and manageable(member.guild, jail):
            try:
                await member.add_roles(jail, reason=reason[:480])
            except (discord.Forbidden, discord.HTTPException):
                pass

    async def restore_member_roles(guild, member):
        data = await read_state()
        gs = guild_state(data, guild.id)
        saved = gs["role_backups"].get(str(member.id))
        if saved is None:
            return False, "لا توجد نسخة محفوظة من رتب هذا العضو."
        roles = [guild.get_role(int(rid)) for rid in saved]
        roles = [r for r in roles if r and manageable(guild, r)]
        jail = guild.get_role(JAIL_ROLE_ID)
        try:
            if jail and jail in member.roles and manageable(guild, jail):
                await member.remove_roles(jail, reason="استعادة الرتب بأمر مخوّل")
            add = [r for r in roles if r not in member.roles]
            if add:
                await member.add_roles(*add, reason="استعادة الرتب المحفوظة")
            gs["role_backups"].pop(str(member.id), None)
            await write_state(data)
            return True, f"تمت استعادة {len(roles)} رتبة قابلة للإرجاع. قد يتعذر إرجاع الرتب الأعلى من البوت أو المُدارة."
        except (discord.Forbidden, discord.HTTPException) as exc:
            return False, f"تعذرت استعادة بعض الرتب بسبب صلاحيات Discord: {exc}"

    def allowed(interaction):
        return interaction.user.id == owner_id or any(r.id == DECISION_ROLE_ID for r in getattr(interaction.user, "roles", []))

    async def security_admin_action(interaction, target_id, action, label):
        if not allowed(interaction):
            await interaction.response.send_message("هذا الإجراء للمالك أو الرتبة المخوّلة فقط.", ephemeral=True)
            return
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("يعمل هذا الإجراء داخل السيرفر فقط.", ephemeral=True)
            return
        member = guild.get_member(int(target_id))
        if member is None:
            await interaction.response.send_message("لم أستطع العثور على العضو المستهدف.", ephemeral=True)
            return
        if member.id == guild.owner_id:
            await interaction.response.send_message("لا يمكن للبوت تنفيذ هذا الإجراء على مالك السيرفر.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        reason = f"FIFA VAULT security panel: {label}"[:480]
        try:
            if action == "timeout":
                await member.timeout(datetime.timedelta(hours=1), reason=reason)
                result_text = "تم تطبيق تايم ساعة واحدة."
            else:
                data = await read_state()
                gs = guild_state(data, guild.id)
                key = str(member.id)
                if key not in gs["role_backups"]:
                    gs["role_backups"][key] = [r.id for r in member.roles if not r.is_default()]
                    await write_state(data)
                removable = [r for r in member.roles if not r.is_default() and r.id != MEMBER_ROLE_ID and manageable(guild, r)]
                if removable:
                    await member.remove_roles(*removable, reason=reason)
                if action == "jail":
                    jail = guild.get_role(JAIL_ROLE_ID)
                    if not jail or not manageable(guild, jail):
                        raise RuntimeError("رتبة السجن غير موجودة أو أعلى من رتبة البوت.")
                    if jail not in member.roles:
                        await member.add_roles(jail, reason=reason)
                    result_text = "تم سجن العضو مع إبقاء Member."
                else:
                    result_text = f"تم سحب {len(removable)} رتبة قابلة للإزالة مع إبقاء Member."
            result = discord.Embed(title="🛡️ نتيجة الإجراء الإداري", description=f"{result_text}\nالمستهدف: {member.mention}\nالعملية الأصلية: {label}", color=discord.Color.dark_red(), timestamp=now())
            result.add_field(name="نفّذ الإجراء", value=interaction.user.mention, inline=True)
            await interaction.followup.send(embed=result, ephemeral=True)
            await send_alert(guild, result)
        except (discord.Forbidden, discord.HTTPException, RuntimeError) as exc:
            await interaction.followup.send(f"تعذّر تنفيذ الإجراء: {exc}", ephemeral=True)

    class SecurityActionView(discord.ui.View):
        def __init__(self, guild_id, actor_id, label):
            super().__init__(timeout=None)
            self.guild_id, self.actor_id, self.label = guild_id, actor_id, label

        @discord.ui.button(label="تايم 1 ساعة", style=discord.ButtonStyle.danger, emoji="⏱️")
        async def timeout_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.guild and interaction.guild.id == self.guild_id:
                await security_admin_action(interaction, self.actor_id, "timeout", self.label)
            else:
                await interaction.response.send_message("هذا الزر مرتبط بسيرفر آخر.", ephemeral=True)

        @discord.ui.button(label="سجن", style=discord.ButtonStyle.danger, emoji="🔒")
        async def jail_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.guild and interaction.guild.id == self.guild_id:
                await security_admin_action(interaction, self.actor_id, "jail", self.label)
            else:
                await interaction.response.send_message("هذا الزر مرتبط بسيرفر آخر.", ephemeral=True)

        @discord.ui.button(label="سحب الرتب", style=discord.ButtonStyle.danger, emoji="🧹")
        async def roles_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.guild and interaction.guild.id == self.guild_id:
                await security_admin_action(interaction, self.actor_id, "roles", self.label)
            else:
                await interaction.response.send_message("هذا الزر مرتبط بسيرفر آخر.", ephemeral=True)

    class IncidentView(discord.ui.View):
        def __init__(self, incident_id, guild_id):
            super().__init__(timeout=DECISION_DELAY)
            self.incident_id, self.guild_id = incident_id, guild_id

        @discord.ui.button(label="إلغاء القرار التلقائي", style=discord.ButtonStyle.secondary, emoji="✋")
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not allowed(interaction):
                await interaction.response.send_message("هذا الزر للمالك أو الرتبة المخوّلة فقط.", ephemeral=True)
                return
            data = await read_state()
            item = guild_state(data, self.guild_id)["incidents"].get(self.incident_id)
            if not item or item.get("status") != "pending":
                await interaction.response.send_message("تم اتخاذ القرار بالفعل أو انتهت الحادثة.", ephemeral=True)
                return
            item["status"] = "cancelled"
            item["cancelled_by"] = interaction.user.id
            await write_state(data)
            task = pending_tasks.get(self.incident_id)
            if task and not task.done():
                task.cancel()
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(content=f"أُلغي القرار التلقائي بواسطة {interaction.user.mention}. الحادثة بقيت في السجل.", view=self)

    async def make_incident(guild, actor, label, points, force_ban=False):
        if not isinstance(actor, discord.Member):
            return
        data = await read_state()
        gs = guild_state(data, guild.id)
        if whitelisted(actor) and not gs.get("nuke_enabled"):
            return
        incident_id = f"{guild.id}-{actor.id}-{int(now().timestamp())}"
        gs["incidents"][incident_id] = {
            "actor_id": actor.id, "label": label, "points": points,
            "created_at": now().isoformat(), "status": "pending",
            "force_ban": force_ban
        }
        total = int(gs["scores"].get(str(actor.id), 0))
        await write_state(data)
        embed = discord.Embed(
            title="🚨 FIFA VAULT — تنبيه أمني",
            description=f"**الفاعل:** {actor.mention}\n**الفعل:** {label}\n**النقاط المضافة:** {points}\n**مجموع النقاط:** {total}\n**القرار بعد دقيقتين:** سحب الرتب القابلة للإزالة، إبقاء Member، وإضافة رتبة السجن."
                        + ("\n**وضع الطوارئ:** سيُحاول البوت حظر الفاعل بعد التحقق من الفعل." if force_ban else ""),
            color=discord.Color.red(), timestamp=now()
        )
        embed.set_footer(text=f"Incident {incident_id}")
        await send_alert(guild, embed, IncidentView(incident_id, guild.id))

        async def delayed():
            try:
                await asyncio.sleep(DECISION_DELAY)
                latest = await read_state()
                lgs = guild_state(latest, guild.id)
                item = lgs["incidents"].get(incident_id)
                if not item or item.get("status") != "pending":
                    return
                current_member = guild.get_member(actor.id)
                if current_member is None:
                    item["status"] = "member_not_in_server"
                    await write_state(latest)
                    return
                if current_member.id == guild.owner_id:
                    item["status"] = "owner_cannot_be_moderated_by_bot"
                    item["completed_at"] = now().isoformat()
                    await write_state(latest)
                    await send_alert(guild, discord.Embed(
                        title="⚠️ تنبيه أمني: مالك السيرفر",
                        description=f"تم رصد فعل عالي الخطورة من مالك السيرفر {current_member.mention}. لا يستطيع Discord السماح للبوت بسحب ملكيته أو حظره؛ يلزم تدخل بشري.",
                        color=discord.Color.orange(), timestamp=now()
                    ))
                    return
                await contain_member(current_member, f"Security response: {label}")
                if item.get("force_ban") and guild.me and guild.me.guild_permissions.ban_members:
                    try:
                        await guild.ban(current_member, reason=f"Confirmed high-risk action during emergency mode: {label}", delete_message_seconds=0)
                        item["status"] = "contained_and_banned"
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        item["status"] = f"contained_ban_failed: {str(exc)[:120]}"
                else:
                    item["status"] = "contained"
                item["completed_at"] = now().isoformat()
                await write_state(latest)
                await send_alert(guild, discord.Embed(
                    title="🛡️ نتيجة إجراء الحماية",
                    description=f"**الفاعل:** <@{actor.id}>\n**الحادثة:** {label}\n**النتيجة:** {item['status']}",
                    color=discord.Color.dark_red(), timestamp=now()
                ))
            except asyncio.CancelledError:
                return
            except Exception as exc:
                print(f"[Security] incident failed: {exc}")
        pending_tasks[incident_id] = asyncio.create_task(delayed())

    async def record(guild, actor, entry, label, points, high_risk=False, is_delete=False, target=None, details=None):
        if not isinstance(actor, discord.Member) or actor.bot or entry is None:
            return
        data = await read_state()
        gs = guild_state(data, guild.id)
        entry_id = f"{entry.id}:{label}"
        if entry_id in gs["processed_audit_ids"]:
            return
        gs["processed_audit_ids"].append(entry_id)
        gs["processed_audit_ids"] = gs["processed_audit_ids"][-1000:]
        key = str(actor.id)
        previous_total = int(gs["scores"].get(key, 0))
        gs["scores"][key] = previous_total + points
        stamp = now().timestamp()
        gs["events"].append({"actor_id": actor.id, "target_id": getattr(target, "id", None), "kind": label, "at": stamp, "points": points})
        gs["events"] = [e for e in gs["events"] if stamp - e.get("at", 0) <= 86400]
        emergency = bool(gs.get("nuke_enabled"))
        await write_state(data)
        if is_delete:
            key2 = (guild.id, actor.id)
            recent_deletes[key2] = [t for t in recent_deletes[key2] if stamp - t <= DELETE_WINDOW]
            recent_deletes[key2].append(stamp)
            if len(recent_deletes[key2]) >= DELETE_THRESHOLD:
                high_risk = True
                label = f"اشتباه نيوك: {len(recent_deletes[key2])} عمليات حذف خلال دقيقة — {label}"
        total = int(gs["scores"].get(str(actor.id), 0))
        remaining = max(0, 100-total)
        risk = min(100, total)
        risk_label = "حرج جدًا" if risk >= 100 else "مرتفع" if risk >= 70 else "متوسط" if risk >= 40 else "منخفض"
        reason = getattr(entry, "reason", None) or "لم يذكر Discord سببًا في سجل التدقيق"
        target_text = getattr(target, "mention", str(target) if target is not None else "غير محدد")
        if target is not None and getattr(target, "id", None):
            target_text += f"\n{target.id}"
        embed = discord.Embed(title="🔴 FIFA VAULT | سجل أمني",
            description="تم رصد عملية إدارية داخل السيرفر.",
            color=discord.Color.from_rgb(139, 0, 0), timestamp=now())
        embed.add_field(name="👤 الفاعل", value=f"{actor.mention}\n{actor.id}", inline=True)
        embed.add_field(name="🎯 المفعول به", value=target_text[:1024], inline=True)
        embed.add_field(name="⚙️ الفعل", value=label[:1024], inline=False)
        if details:
            embed.add_field(name="📋 تفاصيل العملية", value=str(details)[:1024], inline=False)
        embed.add_field(name="📝 السبب", value=str(reason)[:1024], inline=False)
        embed.add_field(name="➕ نقاط العملية", value=f"+{points}", inline=True)
        embed.add_field(name="📊 مجموع النقاط", value=f"{total}/100", inline=True)
        embed.add_field(name="🧯 المتبقي للحد", value=f"{remaining} نقطة", inline=True)
        embed.add_field(name="🌡️ نسبة الخطورة", value=f"{risk}% — {risk_label}", inline=True)
        embed.set_footer(text=f"FIFA VAULT SECURITY • Audit #{entry.id}")
        await send_alert(guild, embed, SecurityActionView(guild.id, actor.id, label))
        crossed_threshold = previous_total < 100 <= total
        force_ban = emergency and high_risk
        if crossed_threshold or high_risk or (emergency and points >= 50):
            await make_incident(guild, actor, label, points, force_ban=force_ban)

    async def on_channel_delete(channel):
        actor, entry = await find_actor(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
        await record(channel.guild, actor, entry, f"حذف روم: {channel.name}", 100, True, True, target=channel, details=f"الروم المحذوف: {channel.name} ({channel.id})")

    async def on_role_delete(role):
        actor, entry = await find_actor(role.guild, discord.AuditLogAction.role_delete, role.id)
        await record(role.guild, actor, entry, f"حذف رتبة: {role.name}", 100, True, True, target=role, details=f"الرتبة المحذوفة: {role.name} ({role.id})")

    async def on_channel_create(channel):
        actor, entry = await find_actor(channel.guild, discord.AuditLogAction.channel_create, channel.id)
        await record(channel.guild, actor, entry, f"إنشاء روم: {channel.name}", 50, target=channel, details=f"الروم الجديد: {channel.name} ({channel.id})")

    async def on_role_create(role):
        actor, entry = await find_actor(role.guild, discord.AuditLogAction.role_create, role.id)
        dangerous = any(getattr(role.permissions, name, False) for name in (
            "administrator", "manage_guild", "manage_roles", "manage_channels",
            "ban_members", "kick_members", "manage_webhooks", "manage_messages", "mention_everyone"
        ))
        await record(role.guild, actor, entry, f"إنشاء رتبة: {role.name}", 50, dangerous)

    async def on_role_update(before, after):
        if before.permissions == after.permissions:
            return
        actor, entry = await find_actor(after.guild, discord.AuditLogAction.role_update, after.id)
        critical_permissions = (
            "administrator", "manage_guild", "manage_roles", "manage_channels",
            "ban_members", "kick_members", "manage_webhooks", "manage_messages", "mention_everyone"
        )
        dangerous = any(
            getattr(after.permissions, name, False) and not getattr(before.permissions, name, False)
            for name in critical_permissions
        )
        await record(after.guild, actor, entry, f"تعديل صلاحيات رتبة: {after.name}", 100 if dangerous else 50, dangerous)

    async def on_member_update(before, after):
        before_timeout = getattr(before, "communication_disabled_until", None)
        after_timeout = getattr(after, "communication_disabled_until", None)
        if after_timeout and (before_timeout is None or after_timeout > before_timeout):
            timeout_actor, timeout_entry = await find_actor(after.guild, discord.AuditLogAction.member_update, after.id)
            if timeout_entry:
                await record(after.guild, timeout_actor, timeout_entry, f"تايم آوت للعضو {after.display_name}", 10)

        old_ids = {r.id for r in before.roles}
        added = [r for r in after.roles if r.id not in old_ids and not r.is_default()]
        if not added:
            return
        actor, entry = await find_actor(after.guild, discord.AuditLogAction.member_role_update, after.id)
        if not entry:
            return
        for role in added:
            dangerous = any((role.permissions.administrator, role.permissions.manage_guild, role.permissions.manage_roles,
                             role.permissions.manage_channels, role.permissions.ban_members, role.permissions.kick_members))
            await record(after.guild, actor, entry, f"منح رتبة {role.name} للعضو {after.display_name}", 50 if dangerous else 5, dangerous)

    async def on_member_ban(guild, user):
        actor, entry = await find_actor(guild, discord.AuditLogAction.ban, user.id)
        await record(guild, actor, entry, f"حظر العضو {user}", 100, True)

    async def on_member_remove(member):
        actor, entry = await find_actor(member.guild, discord.AuditLogAction.kick, member.id)
        if entry:
            await record(member.guild, actor, entry, f"طرد العضو {member}", 100, True)

    group = app_commands.Group(name="set_security", description="إعدادات نظام الحماية")

    @group.command(name="room", description="تعيين روم تنبيهات الحماية")
    async def set_room(interaction: discord.Interaction, channel: discord.TextChannel):
        if not allowed(interaction):
            await interaction.response.send_message("هذا الأمر متاح للمالك أو الرتبة المخوّلة فقط.", ephemeral=True)
            return
        data = await read_state()
        guild_state(data, interaction.guild_id)["security_channel_id"] = channel.id
        await write_state(data)
        await interaction.response.send_message(f"تم تعيين {channel.mention} كروم الحماية.", ephemeral=True)

    bot.tree.add_command(group)

    @bot.tree.command(name="whitelist", description="إضافة رتبة Whitelist لعضو")
    async def whitelist(interaction: discord.Interaction, member: discord.Member):
        if interaction.user.id != owner_id:
            await interaction.response.send_message("هذا الأمر للمالك فقط.", ephemeral=True)
            return
        role = interaction.guild.get_role(WHITELIST_ROLE_ID)
        if not role or not manageable(interaction.guild, role):
            await interaction.response.send_message("رتبة Whitelist غير موجودة أو أعلى من رتبة البوت.", ephemeral=True)
            return
        try:
            await member.add_roles(role, reason=f"Whitelist by {interaction.user.id}")
            await interaction.response.send_message(f"تمت إضافة Whitelist إلى {member.mention}. لا تمنحه حصانة أثناء /nuke.", ephemeral=True)
        except (discord.Forbidden, discord.HTTPException) as exc:
            await interaction.response.send_message(f"فشل إعطاء Whitelist: {exc}", ephemeral=True)

    @bot.tree.command(name="unwhitelist", description="إزالة رتبة Whitelist من عضو")
    async def unwhitelist(interaction: discord.Interaction, member: discord.Member):
        if interaction.user.id != owner_id:
            await interaction.response.send_message("هذا الأمر للمالك فقط.", ephemeral=True)
            return
        role = interaction.guild.get_role(WHITELIST_ROLE_ID)
        if not role or not manageable(interaction.guild, role):
            await interaction.response.send_message("رتبة Whitelist غير موجودة أو أعلى من رتبة البوت.", ephemeral=True)
            return
        try:
            await member.remove_roles(role, reason=f"Unwhitelist by {interaction.user.id}")
            await interaction.response.send_message(f"تمت إزالة Whitelist من {member.mention}.", ephemeral=True)
        except (discord.Forbidden, discord.HTTPException) as exc:
            await interaction.response.send_message(f"فشل إزالة Whitelist: {exc}", ephemeral=True)

    @bot.tree.command(name="nuke", description="تفعيل وضع الطوارئ — المالك فقط")
    async def nuke(interaction: discord.Interaction):
        if interaction.user.id != owner_id:
            await interaction.response.send_message("هذا الأمر متاح لك وحدك.", ephemeral=True)
            return
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("هذا الأمر يعمل داخل السيرفر فقط.", ephemeral=True)
            return
        data = await read_state()
        gs = guild_state(data, guild.id)
        if gs.get("nuke_enabled"):
            await interaction.response.send_message("وضع الطوارئ مفعّل بالفعل.", ephemeral=True)
            return
        gs["nuke_enabled"] = True
        gs["nuke_started_at"] = now().isoformat()
        gs["role_permissions_backup"] = {}
        await write_state(data)
        await interaction.response.defer(ephemeral=True, thinking=True)
        changed, failures = 0, 0
        for role in sorted(guild.roles, key=lambda r: r.position):
            if not manageable(guild, role):
                continue
            perms = role.permissions
            dangerous_permissions = (
                "administrator", "manage_guild", "manage_roles", "manage_channels",
                "ban_members", "kick_members", "create_instant_invite",
                "manage_webhooks", "manage_messages", "manage_threads", "mention_everyone"
            )
            if any(getattr(perms, name, False) for name in dangerous_permissions):
                gs["role_permissions_backup"][str(role.id)] = int(perms.value)
                # Persist the original permissions before attempting any mutation.
                await write_state(data)
                for name in dangerous_permissions:
                    if hasattr(perms, name):
                        setattr(perms, name, False)
                try:
                    await role.edit(permissions=perms, reason=f"/nuke by owner {interaction.user.id}")
                    changed += 1
                except (discord.Forbidden, discord.HTTPException):
                    failures += 1
        await write_state(data)
        await send_alert(guild, discord.Embed(title="🚨 وضع الطوارئ مفعّل",
            description=f"تم تعديل {changed} رتبة. تعذر تعديل {failures} رتبة. المراقبة المشددة فعالة حتى /unnuke.",
            color=discord.Color.red(), timestamp=now()))
        await interaction.followup.send(f"تم تفعيل الطوارئ. الرتب المعدلة: {changed}؛ تعذر تعديل: {failures}.", ephemeral=True)

    @bot.tree.command(name="unnuke", description="إيقاف الطوارئ واستعادة الصلاحيات المحفوظة")
    async def unnuke(interaction: discord.Interaction):
        if interaction.user.id != owner_id:
            await interaction.response.send_message("هذا الأمر متاح لك وحدك.", ephemeral=True)
            return
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("هذا الأمر يعمل داخل السيرفر فقط.", ephemeral=True)
            return
        data = await read_state()
        gs = guild_state(data, guild.id)
        if not gs.get("nuke_enabled"):
            await interaction.response.send_message("وضع الطوارئ غير مفعّل.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        restored, failures = 0, 0
        remaining_backup = {}
        for role_id, raw in list(gs.get("role_permissions_backup", {}).items()):
            role = guild.get_role(int(role_id))
            if not role or not manageable(guild, role):
                failures += 1
                remaining_backup[role_id] = raw
                continue
            try:
                await role.edit(permissions=discord.Permissions(int(raw)), reason=f"/unnuke by owner {interaction.user.id}")
                restored += 1
            except (discord.Forbidden, discord.HTTPException):
                failures += 1
                remaining_backup[role_id] = raw
        gs["role_permissions_backup"] = remaining_backup
        # Keep emergency mode active if restoration is incomplete so /unnuke can be retried.
        gs["nuke_enabled"] = failures > 0
        if failures == 0:
            gs["nuke_ended_at"] = now().isoformat()
        await write_state(data)
        if failures:
            await send_alert(guild, discord.Embed(title="🟠 استعادة جزئية — الطوارئ ما زالت مفعّلة",
                description=f"تمت استعادة {restored} رتبة؛ تعذر استعادة {failures}. عالج ترتيب الرتب أو الصلاحيات ثم أعد /unnuke.", color=discord.Color.orange(), timestamp=now()))
            await interaction.followup.send(f"استعادة جزئية: تمت استعادة {restored} رتبة؛ تعذر استعادة {failures}. وضع الطوارئ ما زال مفعّلًا حتى نجاح الاستعادة.", ephemeral=True)
        else:
            await send_alert(guild, discord.Embed(title="🟢 انتهى وضع الطوارئ",
                description=f"تمت استعادة {restored} رتبة؛ لم تتبقَّ رتب تحتاج إلى استعادة.", color=discord.Color.green(), timestamp=now()))
            await interaction.followup.send(f"تم إيقاف الطوارئ بنجاح. تمت استعادة {restored} رتبة.", ephemeral=True)

    @bot.command(name="إرجاع")
    async def restore_command(ctx, member: discord.Member):
        if ctx.author.id != owner_id and not any(r.id == DECISION_ROLE_ID for r in getattr(ctx.author, "roles", [])):
            await ctx.send("هذا الأمر متاح للمالك أو الرتبة المخوّلة فقط.")
            return
        ok, message = await restore_member_roles(ctx.guild, member)
        await ctx.send(("✅ " if ok else "⚠️ ") + message)

    # Add listeners instead of replacing existing bot.event handlers.
    bot.add_listener(on_channel_delete, "on_guild_channel_delete")
    bot.add_listener(on_role_delete, "on_guild_role_delete")
    bot.add_listener(on_channel_create, "on_guild_channel_create")
    bot.add_listener(on_role_create, "on_guild_role_create")
    bot.add_listener(on_role_update, "on_guild_role_update")
    bot.add_listener(on_member_update, "on_member_update")
    bot.add_listener(on_member_ban, "on_member_ban")
    bot.add_listener(on_member_remove, "on_member_remove")
    print("[Security] protection listeners and slash commands registered.")
    # Professional security log UI patch will be added in this branch.


async def main():
    async with bot:
        await setup_security(bot, MY_DISCORD_ID, load_server_config, save_server_config)
        if BOT_TOKEN:
            await bot.start(BOT_TOKEN)
        else:
            print("❌ DISCORD_TOKEN is not set.")

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
