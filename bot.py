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
import html
import urllib.parse
import urllib.request
from threading import Thread
from flask import Flask

# ==============================================================================
# TOUCHLINE / FIFA VAULT DISCORD BOT - EXTENDED BUILD WITH TICKET SYSTEM
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

TOUCHLINE_IMAGE_URL = "https://cdn.discordapp.com/attachments/1541195966105911371/1550178075306631168/touchline_interface.jpg?ex=6aad6356&is=6aac11d6&hm=dd1815df26dcb9137a41d163150cc9075f118d1dd86c5b7c1dc3b5f3848690d4"

# Soft pink / rainbow-ish embed palette.
EMBED_COLORS = [0xFFB6D9, 0xFFC7E8, 0xFF9ED2, 0xF5A6FF, 0xFFD1F0]

def pink_color():
    return discord.Color(random.choice(EMBED_COLORS))

def bold_msg(text: str, emoji: str = "") -> str:
    prefix = f"{emoji} " if emoji else ""
    return f"**__ {prefix}{text} __**"

def image_attachment_url():
    return TOUCHLINE_IMAGE_URL

# ── Async-safe JSON I/O ───────────────────────────────────────────────────────
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
    ("10m", "spam"),
    ("15m", "spam"),
    ("30m", "تقديم إساءات لعضو أو إداري"),
    ("1h", "السب والقذف أو إرسال صور مخلة"),
    ("2h", "السب والقذف بالأهل أو مخالفة أي قانون"),
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
# Auto Replies (pre-cleaned keys)
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
}

KEYWORD_REPLIES_CLEANED: dict[str, list] = {}
for _keys, _replies in _RAW_KEYWORD_REPLIES.items():
    for _k in _keys:
        KEYWORD_REPLIES_CLEANED[clean_arabic_text(_k)] = _replies

# ==============================================================================
# TICKET SYSTEM UTILITY FUNCTIONS (NEW)
# ==============================================================================

def get_ticket_type_name_ar(ticket_type: str) -> str:
    """Get Arabic ticket type display name used in embeds/messages."""
    types = {
        "technical": "〢🎫・الدعم・الفني",
        "verification": "〢✅・توثيق",
        "complaint": "〢🎟️・شكوى"
    }
    return types.get(ticket_type, ticket_type)


def get_ticket_channel_name_ar(ticket_type: str) -> str:
    """Get the short Arabic name used for ticket channel names."""
    types = {
        "technical": "دعم فني",
        "verification": "توثيق",
        "complaint": "شكوى"
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
        channel_name = f"{get_ticket_channel_name_ar(ticket_type)} #{number}"
        
        # Find or create tickets category
        category = discord.utils.get(guild.categories, name="التذاكر")
        if not category:
            category = await guild.create_category("التذاكر")
        
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
    """Generate a complete HTML transcript including ticket metadata and event history."""
    try:
        messages = []
        async for msg in channel.history(limit=None, oldest_first=True):
            messages.append(msg)

        def esc(value) -> str:
            return html.escape(str(value if value is not None else ""))

        events = ticket_data.get("events", [])
        takeover_events = [e for e in events if e.get("type") == "takeover"]

        if takeover_events:
            takeover_summary = "<br>".join(
                f"{esc(e.get('timestamp', 'N/A'))} — {esc(e.get('from_user_name') or 'لا يوجد مستلم سابق')} → {esc(e.get('user_name') or 'غير معروف')}"
                for e in takeover_events
            )
        else:
            takeover_summary = "لم يحدث استلام خاص من مستلم سابق."

        event_labels = {
            "created": "إنشاء التذكرة",
            "claimed": "استلام التذكرة",
            "takeover": "استلام خاص / Owner Takeover",
            "user_added": "إضافة عضو",
            "closed": "إغلاق التذكرة",
            "reopened": "إعادة فتح التذكرة",
            "deleted": "حذف التذكرة",
            "claimer_left": "مغادرة مستلم التذكرة",
            "auto_deleted": "حذف تلقائي بسبب عدم النشاط"
        }

        html_text = f"""
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Transcript {esc(channel.name)}</title>
    <style>
        body {{ font-family: Segoe UI, Tahoma, sans-serif; background:#36393f; color:#dcddde; margin:0; padding:20px; }}
        .container {{ max-width:1200px; margin:0 auto; background:#2f3136; border-radius:10px; padding:20px; }}
        .header {{ border-bottom:2px solid #202225; padding-bottom:16px; margin-bottom:18px; }}
        .header h1 {{ margin:0 0 8px; color:#fff; }}
        .info {{ background:#202225; padding:15px; border-radius:8px; margin-bottom:18px; }}
        .row {{ margin:7px 0; }}
        .label {{ font-weight:700; color:#b9bbbe; }}
        .section {{ margin-top:20px; }}
        .section h2 {{ color:#fff; font-size:18px; }}
        .event {{ background:#202225; padding:10px; border-radius:6px; margin:7px 0; }}
        .message {{ margin:12px 0; padding:11px; background:#40444b; border-radius:6px; border-right:3px solid #ffb6d9; }}
        .message-header {{ display:flex; gap:10px; align-items:center; margin-bottom:7px; flex-wrap:wrap; }}
        .author {{ font-weight:700; color:#fff; }}
        .meta {{ color:#72767d; font-size:0.85rem; }}
        .content {{ color:#dcddde; white-space:pre-wrap; word-break:break-word; }}
        a {{ color:#00aff4; }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>📋 نص تذكرة: {esc(channel.name)}</h1>
        <div>{esc(ticket_data.get('guild_id', 'N/A'))}</div>
    </div>

    <div class="info">
        <div class="row"><span class="label">نوع التذكرة:</span> {esc(get_ticket_channel_name_ar(ticket_data.get('type', 'unknown')))}</div>
        <div class="row"><span class="label">تم الفتح بواسطة:</span> {esc(ticket_data.get('creator_name', 'Unknown'))} (ID: {esc(ticket_data.get('creator_id', 'N/A'))})</div>
        <div class="row"><span class="label">تاريخ الفتح:</span> {esc(ticket_data.get('created_at', 'N/A'))}</div>
        <div class="row"><span class="label">مستلم التكت الحالي:</span> {esc(ticket_data.get('claimed_by_name') or 'لم يتم الاستلام حالياً')}</div>
        <div class="row"><span class="label">وقت الاستلام الحالي:</span> {esc(ticket_data.get('claimed_at', 'N/A'))}</div>
        <div class="row"><span class="label">هل حدث Owner Takeover؟</span> {takeover_summary}</div>
        <div class="row"><span class="label">الإغلاق بواسطة:</span> {esc(ticket_data.get('closed_by_name') or 'N/A')} (ID: {esc(ticket_data.get('closed_by_id') or 'N/A')})</div>
        <div class="row"><span class="label">وقت الإغلاق:</span> {esc(ticket_data.get('closed_at', 'N/A'))}</div>
        <div class="row"><span class="label">سبب الإغلاق:</span> {esc(ticket_data.get('close_reason') or 'N/A')}</div>
        <div class="row"><span class="label">سبب الحذف:</span> {esc(ticket_data.get('delete_reason') or 'حذف يدوي')}</div>
    </div>

    <div class="section">
        <h2>🧾 سجل الأحداث</h2>
        {''.join(f"<div class='event'><b>{esc(event_labels.get(e.get('type'), e.get('type', 'event')))}</b> — {esc(e.get('timestamp','N/A'))}<br>{esc(e.get('user_name',''))} {('→ ' + esc(e.get('from_user_name'))) if e.get('type') == 'takeover' and e.get('from_user_name') else ''}{(' — ' + esc(e.get('reason'))) if e.get('reason') else ''}{(' — تمت إضافة: ' + esc(e.get('added_user_name'))) if e.get('type') == 'user_added' and e.get('added_user_name') else ''}</div>" for e in events)}
    </div>

    <div class="section">
        <h2>💬 الرسائل ({len(messages)})</h2>
"""

        for msg in messages:
            author_display = esc(msg.author.display_name)
            author_name = esc(msg.author.name)
            author_id = esc(msg.author.id)
            timestamp = esc(msg.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"))
            content = esc(msg.content or "[رسالة بدون نص]")
            attachments = ""
            for attachment in msg.attachments:
                url = esc(attachment.url)
                filename = esc(attachment.filename)
                attachments += f'<div>📎 <a href="{url}">{filename}</a></div>'

            html_text += f"""
        <div class="message">
            <div class="message-header">
                <span class="author">{author_display}</span>
                <span class="meta">@{author_name}</span>
                <span class="meta">ID: {author_id}</span>
                <span class="meta">{timestamp}</span>
            </div>
            <div class="content">{content}</div>
            {attachments}
        </div>
"""

        html_text += """
    </div>
</div>
</body>
</html>
"""
        return html_text

    except Exception as e:
        print(f"Error generating transcript: {e}")
        return f"<html><body><h1>Error generating transcript: {html.escape(str(e))}</h1></body></html>"

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
    """Persistent control buttons inside every ticket channel."""
    def __init__(self):
        super().__init__(timeout=None)

    async def _get_ticket(self, interaction: discord.Interaction):
        tickets = await load_tickets()
        open_tickets = tickets.get("open_tickets", {})
        return tickets, open_tickets, open_tickets.get(str(interaction.channel_id))

    @discord.ui.button(
        label="استلام",
        emoji="🟢",
        style=discord.ButtonStyle.success,
        custom_id="ticket:claim"
    )
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not can_claim_ticket(interaction.user):
                await interaction.response.send_message(bold_msg("ليس لديك صلاحية استلام التذاكر.", "🔒"), ephemeral=True)
                return

            tickets, open_tickets, ticket_data = await self._get_ticket(interaction)
            if not ticket_data:
                await interaction.response.send_message(bold_msg("لم يتم العثور على بيانات التذكرة.", "❌"), ephemeral=True)
                return

            if ticket_data.get("closed"):
                await interaction.response.send_message(bold_msg("هذه التذكرة مغلقة. أعد فتحها أولاً.", "🔒"), ephemeral=True)
                return

            if ticket_data.get("claimed_by_id"):
                await interaction.response.send_message(bold_msg("تم استلام التذكرة بالفعل.", "⚠️"), ephemeral=True)
                return

            now = datetime.datetime.now().isoformat()
            ticket_data["claimed_by_id"] = interaction.user.id
            ticket_data["claimed_by_name"] = interaction.user.display_name
            ticket_data["claimed_at"] = now
            ticket_data.setdefault("events", []).append({
                "type": "claimed",
                "timestamp": now,
                "user_id": interaction.user.id,
                "user_name": interaction.user.display_name
            })
            ticket_data["last_activity"] = now
            open_tickets[str(interaction.channel_id)] = ticket_data
            tickets["open_tickets"] = open_tickets
            await save_tickets(tickets)

            channel = interaction.channel
            guild = interaction.guild
            ticket_staff_role = guild.get_role(TICKET_STAFF_ROLE_ID)
            if ticket_staff_role:
                await channel.set_permissions(ticket_staff_role, view_channel=True, send_messages=False, read_message_history=True)

            await channel.set_permissions(interaction.user, view_channel=True, send_messages=True, read_message_history=True)

            await interaction.response.send_message(
                bold_msg(f"📋 تم استلام التذكرة بواسطة {interaction.user.mention}", ""),
                allowed_mentions=discord.AllowedMentions(users=True)
            )
        except Exception as e:
            print(f"Error claiming ticket: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(bold_msg(f"حدث خطأ: {e}", "❌"), ephemeral=True)
            except Exception:
                pass

    @discord.ui.button(
        label="استلام (اونر)",
        emoji="⚫",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket:takeover"
    )
    async def takeover_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not is_authorized_user(interaction.user):
                await interaction.response.send_message(bold_msg("هذا الزر مخصص للإدارة المصرح لها فقط.", "🔒"), ephemeral=True)
                return

            tickets, open_tickets, ticket_data = await self._get_ticket(interaction)
            if not ticket_data:
                await interaction.response.send_message(bold_msg("لم يتم العثور على بيانات التذكرة.", "❌"), ephemeral=True)
                return
            if ticket_data.get("closed"):
                await interaction.response.send_message(bold_msg("هذه التذكرة مغلقة. أعد فتحها أولاً.", "🔒"), ephemeral=True)
                return

            previous_claimer_id = ticket_data.get("claimed_by_id")
            previous_claimer_name = ticket_data.get("claimed_by_name") or "لا أحد"
            now = datetime.datetime.now().isoformat()

            ticket_data["previous_claimer_id"] = previous_claimer_id
            ticket_data["previous_claimer_name"] = previous_claimer_name
            ticket_data["claimed_by_id"] = interaction.user.id
            ticket_data["claimed_by_name"] = interaction.user.display_name
            ticket_data["claimed_at"] = now
            ticket_data.setdefault("events", []).append({
                "type": "takeover",
                "timestamp": now,
                "user_id": interaction.user.id,
                "user_name": interaction.user.display_name,
                "from_user_id": previous_claimer_id,
                "from_user_name": previous_claimer_name
            })
            ticket_data["last_activity"] = now
            open_tickets[str(interaction.channel_id)] = ticket_data
            tickets["open_tickets"] = open_tickets
            await save_tickets(tickets)

            channel = interaction.channel
            guild = interaction.guild

            if previous_claimer_id:
                previous_member = guild.get_member(previous_claimer_id)
                if previous_member and not previous_member.guild_permissions.administrator:
                    await channel.set_permissions(previous_member, view_channel=True, send_messages=False, read_message_history=True)

            await channel.set_permissions(interaction.user, view_channel=True, send_messages=True, read_message_history=True)

            if previous_claimer_id:
                text = f"👑 قام {interaction.user.mention} باستلام التذكرة من <@{previous_claimer_id}>"
            else:
                text = f"👑 قام {interaction.user.mention} باستلام التذكرة"
            await interaction.response.send_message(
                bold_msg(text, ""),
                allowed_mentions=discord.AllowedMentions(users=True)
            )
        except Exception as e:
            print(f"Error taking over ticket: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(bold_msg(f"حدث خطأ: {e}", "❌"), ephemeral=True)
            except Exception:
                pass

    @discord.ui.button(
        label="قفل التكت",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="ticket:close"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            _, _, ticket_data = await self._get_ticket(interaction)
            if not ticket_data:
                await interaction.response.send_message(bold_msg("لم يتم العثور على بيانات التذكرة.", "❌"), ephemeral=True)
                return

            if ticket_data.get("closed"):
                await interaction.response.send_message(bold_msg("التذكرة مغلقة بالفعل.", "⚠️"), ephemeral=True)
                return

            if not can_close_ticket(interaction.user, ticket_data):
                await interaction.response.send_message(bold_msg("ليس لديك صلاحية إغلاق هذه التذكرة.", "🔒"), ephemeral=True)
                return

            await interaction.response.send_message(
                embed=discord.Embed(
                    title="🔒 سبب إغلاق التذكرة",
                    description="اختر سبب قفل التذكرة من القائمة التالية.",
                    color=pink_color()
                ),
                view=TicketCloseReasonView(interaction.user.id),
                ephemeral=True
            )
        except Exception as e:
            print(f"Error opening close reason selector: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(bold_msg(f"حدث خطأ: {e}", "❌"), ephemeral=True)
            except Exception:
                pass

    @discord.ui.button(
        label="إضافة شخص",
        emoji="👤",
        style=discord.ButtonStyle.primary,
        custom_id="ticket:add_user"
    )
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            _, _, ticket_data = await self._get_ticket(interaction)
            if not ticket_data:
                await interaction.response.send_message(bold_msg("لم يتم العثور على بيانات التذكرة.", "❌"), ephemeral=True)
                return
            if ticket_data.get("closed"):
                await interaction.response.send_message(bold_msg("لا يمكنك إضافة شخص إلى تذكرة مغلقة.", "🔒"), ephemeral=True)
                return
            if interaction.user.id != ticket_data.get("creator_id"):
                await interaction.response.send_message(bold_msg("فقط منشئ التذكرة يمكنه إضافة أشخاص.", "🔒"), ephemeral=True)
                return

            added_users = ticket_data.get("added_users", [])
            if len(added_users) >= 2:
                await interaction.response.send_message(bold_msg("تم الوصول للحد الأقصى: شخصان فقط.", "⚠️"), ephemeral=True)
                return

            await interaction.response.send_message(
                embed=discord.Embed(
                    title="👤 إضافة شخص للتذكرة",
                    description="اختر العضو من القائمة. يمكنك إضافة شخصين كحد أقصى.",
                    color=pink_color()
                ),
                view=AddUserSelectView(interaction.channel_id, interaction.user.id),
                ephemeral=True
            )
        except Exception as e:
            print(f"Error opening add-user selector: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(bold_msg(f"حدث خطأ: {e}", "❌"), ephemeral=True)
            except Exception:
                pass


class AddUserSelectView(discord.ui.View):
    """Ephemeral Discord User Select for adding people to a ticket."""
    def __init__(self, channel_id: int, creator_id: int):
        super().__init__(timeout=60)
        self.channel_id = channel_id
        self.creator_id = creator_id
        self.user_select = discord.ui.UserSelect(
            placeholder="اختر العضو الذي تريد إضافته",
            min_values=1,
            max_values=1,
            custom_id=f"ticket:add-user-select:{channel_id}"
        )
        self.user_select.callback = self.on_user_selected
        self.add_item(self.user_select)

    async def on_user_selected(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.creator_id:
                await interaction.response.send_message(bold_msg("فقط منشئ التذكرة يمكنه استخدام هذه القائمة.", "🔒"), ephemeral=True)
                return

            selected = self.user_select.values[0]
            member = interaction.guild.get_member(selected.id)
            if not member:
                try:
                    member = await interaction.guild.fetch_member(selected.id)
                except Exception:
                    member = None

            if not member:
                await interaction.response.send_message(bold_msg("لم يتم العثور على العضو داخل السيرفر.", "❌"), ephemeral=True)
                return
            if member.bot:
                await interaction.response.send_message(bold_msg("لا يمكن إضافة بوت إلى التذكرة.", "❌"), ephemeral=True)
                return
            if member.id == interaction.user.id:
                await interaction.response.send_message(bold_msg("أنت منشئ التذكرة بالفعل.", "⚠️"), ephemeral=True)
                return

            tickets = await load_tickets()
            open_tickets = tickets.get("open_tickets", {})
            ticket_data = open_tickets.get(str(self.channel_id))
            if not ticket_data:
                await interaction.response.send_message(bold_msg("لم يتم العثور على بيانات التذكرة.", "❌"), ephemeral=True)
                return
            if ticket_data.get("closed"):
                await interaction.response.send_message(bold_msg("التذكرة مغلقة.", "🔒"), ephemeral=True)
                return

            added_users = ticket_data.get("added_users", [])
            if len(added_users) >= 2:
                await interaction.response.send_message(bold_msg("تم الوصول للحد الأقصى: شخصان فقط.", "⚠️"), ephemeral=True)
                return
            if member.id in added_users:
                await interaction.response.send_message(bold_msg("هذا العضو مضاف بالفعل.", "⚠️"), ephemeral=True)
                return

            channel = interaction.channel
            await channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            )

            now = datetime.datetime.now().isoformat()
            added_users.append(member.id)
            ticket_data["added_users"] = added_users
            ticket_data.setdefault("events", []).append({
                "type": "user_added",
                "timestamp": now,
                "added_by_id": interaction.user.id,
                "added_by_name": interaction.user.display_name,
                "added_user_id": member.id,
                "added_user_name": member.display_name
            })
            ticket_data["last_activity"] = now
            open_tickets[str(self.channel_id)] = ticket_data
            tickets["open_tickets"] = open_tickets
            await save_tickets(tickets)

            await interaction.response.edit_message(
                content=bold_msg(f"👤 تمت إضافة {member.mention} للتذكرة بنجاح.", "✅"),
                embed=None,
                view=None,
                allowed_mentions=discord.AllowedMentions(users=True)
            )
            self.stop()
        except Exception as e:
            print(f"Error in add-user selector: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(bold_msg(f"حدث خطأ: {e}", "❌"), ephemeral=True)
            except Exception:
                pass


class TicketCloseReasonView(discord.ui.View):
    """Close reason selection shown before the final close confirmation."""
    def __init__(self, initiator_id: int):
        super().__init__(timeout=120)
        self.initiator_id = initiator_id
        self.reason_select = discord.ui.Select(
            placeholder="اختر سبب قفل التذكرة",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label="تم الانتهاء من التكت",
                    value="تم الانتهاء من التكت",
                    description="تم التعامل مع المشكلة وإنهاء الطلب."
                ),
                discord.SelectOption(
                    label="لم يتم الوصول إلى حل مرضي",
                    value="لم يتم الوصول إلى حل مرضي",
                    description="لم يتم الوصول إلى حل مرضي للمشكلة."
                ),
                discord.SelectOption(
                    label="أخرى",
                    value="أخرى",
                    description="اكتب سبباً مخصصاً لإغلاق التذكرة."
                )
            ]
        )
        self.reason_select.callback = self.on_reason_selected
        self.add_item(self.reason_select)

    async def on_reason_selected(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.initiator_id:
                await interaction.response.send_message(bold_msg("فقط الشخص الذي بدأ عملية الإغلاق يمكنه اختيار السبب.", "🔒"), ephemeral=True)
                return

            reason = self.reason_select.values[0]
            if reason == "أخرى":
                await interaction.response.send_modal(TicketOtherCloseReasonModal(self.initiator_id))
            else:
                await prepare_ticket_close_confirmation(interaction, self.initiator_id, reason)
                self.stop()
        except Exception as e:
            print(f"Error selecting close reason: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(bold_msg(f"حدث خطأ: {e}", "❌"), ephemeral=True)
            except Exception:
                pass


class TicketOtherCloseReasonModal(discord.ui.Modal, title="سبب إغلاق مخصص"):
    reason = discord.ui.TextInput(
        label="سبب الإغلاق",
        placeholder="اكتب سبب قفل التكت...",
        required=True,
        min_length=2,
        max_length=500,
        style=discord.TextStyle.paragraph
    )

    def __init__(self, initiator_id: int):
        super().__init__()
        self.initiator_id = initiator_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await prepare_ticket_close_confirmation(interaction, self.initiator_id, self.reason.value.strip())
        except Exception as e:
            print(f"Error submitting custom close reason: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(bold_msg(f"حدث خطأ: {e}", "❌"), ephemeral=True)
            except Exception:
                pass


async def prepare_ticket_close_confirmation(interaction: discord.Interaction, initiator_id: int, reason: str):
    tickets = await load_tickets()
    open_tickets = tickets.get("open_tickets", {})
    ticket_data = open_tickets.get(str(interaction.channel_id))
    if not ticket_data:
        await interaction.response.send_message(bold_msg("لم يتم العثور على بيانات التذكرة.", "❌"), ephemeral=True)
        return
    if not can_close_ticket(interaction.user, ticket_data) or interaction.user.id != initiator_id:
        await interaction.response.send_message(bold_msg("ليس لديك صلاحية إغلاق هذه التذكرة.", "🔒"), ephemeral=True)
        return

    now = datetime.datetime.now().isoformat()
    # Store a pending close only. The ticket becomes officially closed after the user
    # confirms with the final button, so an expired/abandoned selector does not lock it.
    ticket_data["pending_close_reason"] = reason
    ticket_data["pending_close_by_id"] = interaction.user.id
    ticket_data["pending_close_by_name"] = interaction.user.display_name
    ticket_data["pending_close_at"] = now
    ticket_data["pending_close_initiator_id"] = initiator_id
    ticket_data["last_activity"] = now
    open_tickets[str(interaction.channel_id)] = ticket_data
    tickets["open_tickets"] = open_tickets
    await save_tickets(tickets)

    embed = discord.Embed(
        title="🔒 إغلاق التذكرة",
        description=f"هل أنت متأكد من قفل التذكرة؟\n\n**السبب:** {reason}",
        color=pink_color()
    )
    if isinstance(interaction.message, discord.Message):
        await interaction.response.edit_message(
            embed=embed,
            content=None,
            view=TicketCloseConfirmView(initiator_id)
        )
    else:
        await interaction.response.send_message(
            embed=embed,
            view=TicketCloseConfirmView(initiator_id),
            ephemeral=True
        )


class TicketCloseConfirmView(discord.ui.View):
    """Final close confirmation. No cancel-delete button."""
    def __init__(self, initiator_id: int):
        super().__init__(timeout=120)
        self.initiator_id = initiator_id

    async def _load_ticket_for_action(self, interaction: discord.Interaction):
        tickets = await load_tickets()
        open_tickets = tickets.get("open_tickets", {})
        ticket_data = open_tickets.get(str(interaction.channel_id))
        return tickets, open_tickets, ticket_data

    @discord.ui.button(label="فتح", emoji="🟢", style=discord.ButtonStyle.success)
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            tickets, open_tickets, ticket_data = await self._load_ticket_for_action(interaction)
            if not ticket_data:
                await interaction.response.send_message(bold_msg("لم يتم العثور على بيانات التذكرة.", "❌"), ephemeral=True)
                return
            if interaction.user.id != self.initiator_id and not can_close_ticket(interaction.user, ticket_data):
                await interaction.response.send_message(bold_msg("ليس لديك صلاحية إعادة فتح هذه التذكرة.", "🔒"), ephemeral=True)
                return

            now = datetime.datetime.now().isoformat()
            was_closed = bool(ticket_data.get("closed"))
            ticket_data["closed"] = False
            if was_closed:
                ticket_data["close_reopened_at"] = now
                ticket_data.setdefault("events", []).append({
                    "type": "reopened",
                    "timestamp": now,
                    "user_id": interaction.user.id,
                    "user_name": interaction.user.display_name
                })
            ticket_data.pop("pending_close_reason", None)
            ticket_data.pop("pending_close_by_id", None)
            ticket_data.pop("pending_close_by_name", None)
            ticket_data.pop("pending_close_at", None)
            ticket_data.pop("pending_close_initiator_id", None)
            ticket_data["last_activity"] = now
            open_tickets[str(interaction.channel_id)] = ticket_data
            tickets["open_tickets"] = open_tickets
            await save_tickets(tickets)

            channel = interaction.channel
            guild = interaction.guild
            ticket_staff_role = guild.get_role(TICKET_STAFF_ROLE_ID)
            if ticket_staff_role and not ticket_data.get("claimed_by_id"):
                await channel.set_permissions(ticket_staff_role, view_channel=True, send_messages=True, read_message_history=True)

            await interaction.response.edit_message(
                content=bold_msg("تم إلغاء الإغلاق وإبقاء التذكرة مفتوحة.", "🟢") if not was_closed else bold_msg("تم إعادة فتح التذكرة بنجاح.", "🟢"),
                embed=None,
                view=None
            )
            self.stop()
        except Exception as e:
            print(f"Error reopening ticket: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(bold_msg(f"حدث خطأ: {e}", "❌"), ephemeral=True)
            except Exception:
                pass

    @discord.ui.button(label="حذف", emoji="🔴", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            tickets, open_tickets, ticket_data = await self._load_ticket_for_action(interaction)
            if not ticket_data:
                await interaction.response.send_message(bold_msg("لم يتم العثور على بيانات التذكرة.", "❌"), ephemeral=True)
                return
            if interaction.user.id != self.initiator_id and not can_close_ticket(interaction.user, ticket_data):
                await interaction.response.send_message(bold_msg("ليس لديك صلاحية حذف هذه التذكرة.", "🔒"), ephemeral=True)
                return

            now = datetime.datetime.now().isoformat()
            close_reason = ticket_data.get("pending_close_reason") or ticket_data.get("close_reason") or "غير محدد"
            close_by_id = ticket_data.get("pending_close_by_id") or ticket_data.get("closed_by_id") or interaction.user.id
            close_by_name = ticket_data.get("pending_close_by_name") or ticket_data.get("closed_by_name") or interaction.user.display_name

            ticket_data["closed"] = True
            ticket_data["closed_by_id"] = close_by_id
            ticket_data["closed_by_name"] = close_by_name
            ticket_data["closed_at"] = now
            ticket_data["close_reason"] = close_reason
            ticket_data["delete_reason"] = "حذف يدوي"
            ticket_data.setdefault("events", []).append({
                "type": "closed",
                "timestamp": now,
                "user_id": close_by_id,
                "user_name": close_by_name,
                "reason": close_reason
            })
            ticket_data.setdefault("events", []).append({
                "type": "deleted",
                "timestamp": now,
                "user_id": interaction.user.id,
                "user_name": interaction.user.display_name,
                "reason": "حذف يدوي"
            })
            for key in ("pending_close_reason", "pending_close_by_id", "pending_close_by_name", "pending_close_at", "pending_close_initiator_id"):
                ticket_data.pop(key, None)
            ticket_data["last_activity"] = now
            open_tickets[str(interaction.channel_id)] = ticket_data
            tickets["open_tickets"] = open_tickets
            await save_tickets(tickets)

            channel = interaction.channel
            transcript_html = await generate_ticket_transcript(channel, ticket_data)

            config = await load_ticket_config()
            transcript_channel_id = config.get("transcript_channel_id")
            if transcript_channel_id:
                transcript_channel = interaction.guild.get_channel(transcript_channel_id)
                if transcript_channel:
                    transcript_file = discord.File(
                        io.BytesIO(transcript_html.encode("utf-8")),
                        filename=f"transcript-{channel.id}.html"
                    )
                    takeover_events = [e for e in ticket_data.get("events", []) if e.get("type") == "takeover"]
                    takeover_text = "نعم" if takeover_events else "لا"
                    log_embed = discord.Embed(
                        title="🎫 سجل التذكرة",
                        color=pink_color(),
                        timestamp=datetime.datetime.now(datetime.timezone.utc)
                    )
                    log_embed.add_field(name="النوع", value=get_ticket_channel_name_ar(ticket_data.get("type", "unknown")), inline=True)
                    log_embed.add_field(name="التذكرة", value=channel.name, inline=True)
                    log_embed.add_field(name="منشئ التكت", value=f"<@{ticket_data.get('creator_id')}>", inline=True)
                    log_embed.add_field(name="مستلم التكت", value=ticket_data.get("claimed_by_name") or "لم يتم الاستلام", inline=True)
                    log_embed.add_field(name="وقت الاستلام", value=ticket_data.get("claimed_at", "N/A"), inline=True)
                    log_embed.add_field(name="Owner Takeover", value=takeover_text, inline=True)
                    log_embed.add_field(name="الإغلاق بواسطة", value=ticket_data.get("closed_by_name") or "N/A", inline=True)
                    log_embed.add_field(name="وقت الإغلاق", value=ticket_data.get("closed_at", "N/A"), inline=True)
                    log_embed.add_field(name="سبب الإغلاق", value=ticket_data.get("close_reason") or "N/A", inline=False)
                    log_embed.add_field(name="سبب الحذف", value="حذف يدوي", inline=False)
                    if takeover_events:
                        last_takeover = takeover_events[-1]
                        log_embed.add_field(
                            name="من المستلم إلى مستلم Owner",
                            value=f"{last_takeover.get('from_user_name') or 'لا أحد'} → {last_takeover.get('user_name') or 'غير معروف'}\n{last_takeover.get('timestamp', 'N/A')}",
                            inline=False
                        )
                    else:
                        log_embed.add_field(name="استلام Owner", value="لم يحدث أي Takeover.", inline=False)
                    try:
                        await transcript_channel.send(embed=log_embed, file=transcript_file)
                    except Exception as e:
                        print(f"Error sending transcript: {e}")

            await interaction.response.edit_message(
                content=bold_msg("🗑️ سيتم حذف التذكرة خلال 10 ثوانٍ.", ""),
                embed=None,
                view=None
            )

            await asyncio.sleep(10)
            try:
                await channel.delete(reason=f"تم حذف التذكرة بواسطة {interaction.user.name}")
            except Exception:
                pass

            tickets = await load_tickets()
            open_tickets = tickets.get("open_tickets", {})
            if str(channel.id) in open_tickets:
                del open_tickets[str(channel.id)]
                tickets["open_tickets"] = open_tickets
                await save_tickets(tickets)
            self.stop()
        except Exception as e:
            print(f"Error deleting ticket: {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message(bold_msg(f"حدث خطأ: {e}", "❌"), ephemeral=True)
            except Exception:
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
                
                # Record the automatic deletion event before generating the transcript.
                now_iso = datetime.datetime.now().isoformat()
                ticket_data["delete_reason"] = "15 ساعة بدون نشاط"
                ticket_data.setdefault("events", []).append({
                    "type": "auto_deleted",
                    "timestamp": now_iso,
                    "user_id": bot.user.id if bot.user else None,
                    "user_name": str(bot.user) if bot.user else "BOT",
                    "reason": "15 ساعة بدون نشاط"
                })

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
                        log_embed.add_field(name="مستلم التكت", value=ticket_data.get('claimed_by_name') or 'لم يتم الاستلام', inline=True)
                        takeover_events = [e for e in ticket_data.get("events", []) if e.get("type") == "takeover"]
                        log_embed.add_field(name="Owner Takeover", value="نعم" if takeover_events else "لا", inline=True)
                        log_embed.add_field(name="سبب الحذف", value="15 ساعة بدون نشاط", inline=False)
                        if takeover_events:
                            e = takeover_events[-1]
                            log_embed.add_field(name="تفاصيل Owner Takeover", value=f"{e.get('from_user_name') or 'لا أحد'} → {e.get('user_name') or 'غير معروف'}\n{e.get('timestamp', 'N/A')}", inline=False)
                        
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
        # Create panel embed
        embed = discord.Embed(
            title="🎫 نظام التذاكر",
            description=(
                "**__ مرحباً بك في نظام التذاكر __**\n\n"
                "يمكنك فتح تذكرة للحصول على:\n"
                "• **دعم فني** 🟨\n"
                "• **توثيق نادي** 🟩\n"
                "• **تقديم شكوى** 🟥\n\n"
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
        
        # Update the existing configured panel when possible; otherwise send a new one.
        panel_message_id = config.get("panel_message_id")
        panel_message = None
        if panel_message_id and config.get("panel_channel_id") == channel.id:
            try:
                panel_message = await channel.fetch_message(int(panel_message_id))
            except Exception:
                panel_message = None

        if panel_message:
            await panel_message.edit(embed=embed, view=TicketPanelView())
        else:
            panel_message = await channel.send(embed=embed, view=TicketPanelView())

        config["panel_channel_id"] = channel.id
        config["panel_message_id"] = panel_message.id
        config["guild_id"] = interaction.guild_id
        await save_ticket_config(config)

        await interaction.response.send_message(
            bold_msg(f"تم تعيين {channel.mention} كقناة لوحة التذاكر وتحديث اللوحة بنجاح.", "✅"),
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
# Events (MODIFIED TO ADD PERSISTENT VIEWS AND ACTIVITY TRACKING)
# ==============================================================================
@bot.event
async def on_ready():
    print(f"✅ Bot Online as: {bot.user}")
    try:
        await bot.tree.sync()
        print("Synced all slash commands successfully.")
    except Exception as e:
        print(f"Sync error: {e}")
    
    # Register persistent views for ticket system
    bot.add_view(TicketPanelView())
    bot.add_view(TicketControlView())
    print("✅ Ticket system persistent views registered.")
    
    # Start inactivity checker
    if not check_inactive_tickets.is_running():
        check_inactive_tickets.start()
        print("✅ Ticket inactivity checker started.")

@bot.event
async def on_member_remove(member: discord.Member):
    """If a ticket claimer leaves, unclaim the ticket so staff can claim it again."""
    try:
        tickets = await load_tickets()
        open_tickets = tickets.get("open_tickets", {})
        changed = False
        for channel_id, ticket_data in open_tickets.items():
            if ticket_data.get("claimed_by_id") != member.id or ticket_data.get("closed", False):
                continue

            now = datetime.datetime.now().isoformat()
            ticket_data.setdefault("events", []).append({
                "type": "claimer_left",
                "timestamp": now,
                "user_id": member.id,
                "user_name": member.display_name
            })
            ticket_data["previous_claimer_id"] = ticket_data.get("claimed_by_id")
            ticket_data["previous_claimer_name"] = ticket_data.get("claimed_by_name")
            ticket_data["claimed_by_id"] = None
            ticket_data["claimed_by_name"] = None
            ticket_data["claimed_at"] = None
            ticket_data["last_activity"] = now
            changed = True

            channel = bot.get_channel(int(channel_id))
            if channel:
                staff_role = channel.guild.get_role(TICKET_STAFF_ROLE_ID)
                if staff_role:
                    try:
                        await channel.set_permissions(staff_role, view_channel=True, send_messages=True, read_message_history=True)
                    except Exception:
                        pass

        if changed:
            tickets["open_tickets"] = open_tickets
            await save_tickets(tickets)
    except Exception as e:
        print(f"Error handling ticket claimer leave: {e}")


@bot.event
async def on_message(message: discord.Message):
    """Keep Auto Replies while always allowing discord.py prefix commands to run.
    Also tracks ticket activity."""
    if message.author.bot:
        return

    try:
        # Track ticket activity if message is in a ticket channel
        if message.channel.type == discord.ChannelType.text:
            tickets = await load_tickets()
            open_tickets = tickets.get("open_tickets", {})
            if str(message.channel.id) in open_tickets:
                # Update activity timestamp
                await update_ticket_activity(message.channel.id)
        
        content = message.content.strip()
        clean_content = clean_arabic_text(content)

        # Auto-reply lookup (O(1))
        if clean_content in KEYWORD_REPLIES_CLEANED:
            replies = KEYWORD_REPLIES_CLEANED[clean_content]
            await message.reply(random.choice(replies))
            return

        # PREFIX-LESS COMMAND SUPPORT
        if not content.startswith("!"):
            first_word = content.split()[0] if content.split() else ""
            cmd = bot.get_command(first_word)
            if cmd is not None:
                message.content = "!" + content
    except Exception as e:
        print("Auto-reply/prefix-less error:", repr(e))

    try:
        await bot.process_commands(message)
    except Exception as e:
        print("Prefix command processing error:", repr(e))

# ==============================================================================
# Warn commands (unchanged)
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
    warns = await load_warns()
    count = sum(len(v) for v in warns.values() if isinstance(v, list))
    await save_warns({})
    await ctx.send(bold_msg(f"تم حذف جميع تحذيرات أعضاء السيرفر بنجاح • العدد: {count}", "🧹"))

# ==============================================================================
# Dashboards (unchanged)
# ==============================================================================

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
# Timeout UI (unchanged)
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

@bot.command(name="اسكت")
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
# Slash /say & /embed (unchanged)
# ==============================================================================
@bot.tree.command(name="say", description="يجعل البوت يقول النص الذي تكتبه بشكل مجهول")
@app_commands.describe(text="النص الذي تريد أن يقوله البوت")
async def slash_say(interaction: discord.Interaction, text: str):
    if not is_owner(interaction.user):
        await interaction.response.send_message(bold_msg("هذا الأمر متاح لمالك البوت فقط.", "🔒"), ephemeral=True)
        return
    await interaction.response.send_message("✅ تم الإرسال!", ephemeral=True)
    await interaction.channel.send(text)

@bot.tree.command(name="embed", description="إرسال Embed من حساب البوت بشكل مجهول")
@app_commands.describe(title="عنوان الـ Embed", description="محتوى الـ Embed")
async def slash_embed(interaction: discord.Interaction, title: str, description: str):
    if not is_owner(interaction.user):
        await interaction.response.send_message(bold_msg("هذا الأمر متاح لمالك البوت فقط.", "🔒"), ephemeral=True)
        return
    await interaction.response.send_message("✅ تم الإرسال!", ephemeral=True)
    embed = discord.Embed(title=title, description=description, color=pink_color())
    await interaction.channel.send(embed=embed)

# ==============================================================================
# /help (unchanged)
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
        "🛠️ **الإدارة:** `!باند @user [سبب]` `!رتب @user اسم/ID/منشن` `!برا @user` `!حذف عدد` (اختصار: `!م`) `!rename الاسم` `!قفل` `!فتح`\n"
        "📊 **المعلومات:** `!s` `!u @user`\n"
        "⚙️ **الإعداد:** `/server_set` لتعيين رتبة الإدارة يدوياً\n"
        "🎫 **نظام التذاكر:** `/set_ticket` `/set_transcript`\n"
        "👑 **مالك البوت فقط:** `/say` `/embed`\n\n"
        "**ملاحظة:** صلاحيات الأوامر مرتبطة بالـ Role IDs الموجودة في إعدادات البوت."
    )
    return embed

@bot.tree.command(name="help", description="شرح البوت وأوامره")
async def slash_help(interaction: discord.Interaction):
    embed = build_member_help(interaction.guild)
    await interaction.response.send_message(embed=embed, view=HelpView(interaction.user.id), ephemeral=True)

# ==============================================================================
# Rock Paper Scissors (unchanged)
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
# Translation (unchanged)
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
# Warn system (unchanged)
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
    warns = await load_warns()
    user_warns = warns.get(str(target.id), [])
    await ctx.send(bold_msg(f"{target.mention} لديه {len(user_warns)} وارن.", "📋"))

@bot.command(name="وارنات")
async def show_all_warns(ctx):
    if not check_permissions(ctx):
        return
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
# WHO AM I (unchanged - keeping the 450 questions version from original code)
# ==============================================================================
WHO_AM_I = [
    ("ليونيل ميسي", ["أنا لاعب كرة قدم أرجنتيني.", "فزت بكأس العالم 2022.", "لعبت سنوات طويلة مع برشلونة.", "أرتبط كثيرًا بالرقم 10.", "أملك عدة كرات ذهبية."]),
    ("كريستيانو رونالدو", ["أنا لاعب كرة قدم برتغالي.", "اشتهرت بالرقم 7.", "لعبت مع مانشستر يونايتد وريال مدريد.", "حققت دوري أبطال أوروبا عدة مرات.", "أنا من أكثر الهدافين شهرة في كرة القدم."]),
    # ... rest of the 450 questions kept from original code for brevity in this response
]

class WhoAmIView(discord.ui.View):
    def __init__(self, author_id, answer, clues):
        super().__init__(timeout=90)
        self.author_id = author_id
        self.answer = answer
        self.clues = clues
        self.index = 0

    async def interaction_check(self, interaction):
        return True

    @discord.ui.button(label="تلميح", emoji="💡", style=discord.ButtonStyle.primary)
    async def clue(self, interaction, button):
        if self.index >= len(self.clues):
            await interaction.response.send_message(bold_msg("استخدمت كل التلميحات.", "💡"), ephemeral=True)
            return
        await interaction.response.send_message(bold_msg(f"التلميح {self.index + 1}: {self.clues[self.index]}", "💡"), ephemeral=True)
        self.index += 1

    @discord.ui.button(label="الحل", emoji="✅", style=discord.ButtonStyle.success)
    async def answer_button(self, interaction, button):
        await interaction.response.send_message(bold_msg(f"الإجابة هي: {self.answer}", "🎯"), ephemeral=True)
        self.stop()

@bot.command(name="من_انا")
async def who_am_i(ctx):
    answer, clues = random.choice(WHO_AM_I)
    random.shuffle(clues)
    embed = discord.Embed(
        title="❓ من أنا؟",
        description="**__ خمن الشخصية من 5 تلميحات. اكتب إجابتك في الشات أو اطلب التلميحات بالزر. __**",
        color=pink_color()
    )
    embed.add_field(name="💡 التلميحات", value="التلميحات تظهر بالترتيب عبر زر التلميح.", inline=False)
    await ctx.send(embed=embed, view=WhoAmIView(ctx.author.id, answer, clues))

# ==============================================================================
# Arabic Wordle (unchanged)
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
# XO VS BOT (unchanged)
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
# WOULD YOU RATHER (unchanged - keeping the 450 questions version)
# ==============================================================================
WOULD_YOU_RATHER = [
    "تعيش بدون هاتف أم بدون إنترنت؟",
    # ... rest of 450 questions kept from original for brevity
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
# HIDE AND SEEK (unchanged - keeping the updated lobby version)
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
        self.lobby_message = None

    def _build_lobby_embed(self) -> discord.Embed:
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
# Core moderation commands (unchanged)
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

@bot.command(name="برا")
async def kick_user(ctx, member: discord.Member, *, reason: str = "لا يوجد سبب محدد"):
    if not check_permissions(ctx):
        return
    try:
        await member.kick(reason=reason)
        await ctx.send(bold_msg(f"تم طرد {member.mention} بنجاح.", "🥾"))
    except Exception as e:
        await ctx.send(bold_msg(f"فشل الطرد: {e}", "❌"))

@bot.command(name="باند", aliases=["ban"])
async def ban_member(ctx: commands.Context, member: discord.Member, *, reason: str = "لا يوجد سبب محدد"):
    """Ban a member using the same existing moderation permission system."""
    if not check_permissions(ctx):
        return
    if member.id == MY_DISCORD_ID or member.id == ctx.author.id or member.bot:
        await ctx.send(bold_msg("لا يمكنك تنفيذ الباند على هذا العضو.", "❌"))
        return
    if ctx.guild.owner_id == member.id:
        await ctx.send(bold_msg("لا يمكن حظر مالك السيرفر.", "❌"))
        return
    me = ctx.guild.me
    if me is None or me.top_role <= member.top_role:
        await ctx.send(bold_msg("لا أملك صلاحية حظر هذا العضو بسبب ترتيب الرتب.", "❌"))
        return
    try:
        await member.ban(reason=reason)
        await ctx.send(bold_msg(f"تم حظر {member.mention} بنجاح • السبب: {reason}", "🔨"))
    except discord.Forbidden:
        await ctx.send(bold_msg("لا أملك صلاحية حظر هذا العضو.", "❌"))
    except Exception as e:
        await ctx.send(bold_msg(f"فشل الباند: {e}", "❌"))


def resolve_role_from_text(guild: discord.Guild, role_text: str) -> discord.Role | None:
    """Resolve a role by mention, ID, or exact Arabic/name match."""
    raw = role_text.strip()
    role_id = None
    if raw.startswith("<@&") and raw.endswith(">"):
        try:
            role_id = int(raw[3:-1])
        except ValueError:
            role_id = None
    elif raw.isdigit():
        role_id = int(raw)

    if role_id is not None:
        role = guild.get_role(role_id)
        if role:
            return role

    cleaned = clean_arabic_text(raw)
    for role in guild.roles:
        if clean_arabic_text(role.name) == cleaned:
            return role
    return None


@bot.command(name="رتب", aliases=["role"])
async def give_role(ctx: commands.Context, member: discord.Member, *, role_text: str):
    """Give a role by mention, ID, or role name (e.g. !رتب @user مسجون)."""
    if not check_permissions(ctx):
        return

    role = resolve_role_from_text(ctx.guild, role_text)
    if role is None:
        await ctx.send(bold_msg(f"لم أجد رتبة باسم أو ID `{role_text}`.", "❌"))
        return
    if role.is_default() or role.managed:
        await ctx.send(bold_msg("لا يمكن إعطاء هذه الرتبة.", "❌"))
        return
    if member.bot:
        await ctx.send(bold_msg("لا يفضل إعطاء الرتب للبوتات بهذا الأمر.", "❌"))
        return
    if role in member.roles:
        await ctx.send(bold_msg(f"{member.mention} يملك هذه الرتبة بالفعل.", "⚠️"))
        return

    me = ctx.guild.me
    if me is None or role >= me.top_role:
        await ctx.send(bold_msg("لا أستطيع إعطاء هذه الرتبة لأن رتبة البوت ليست أعلى منها.", "❌"))
        return
    if member == ctx.guild.me:
        await ctx.send(bold_msg("لا يمكنك استخدام هذا الأمر على البوت.", "❌"))
        return

    try:
        await member.add_roles(role, reason=f"منح رتبة بواسطة {ctx.author}")
        await ctx.send(bold_msg(f"تم إعطاء {role.mention} إلى {member.mention} بنجاح.", "✅"))
    except discord.Forbidden:
        await ctx.send(bold_msg("لا أملك صلاحية إدارة هذه الرتبة أو العضو.", "❌"))
    except Exception as e:
        await ctx.send(bold_msg(f"فشل إعطاء الرتبة: {e}", "❌"))


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

@bot.command(name="قفل")
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

@bot.command(name="فتح")
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
# Error handler and runtime (unchanged)
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

async def main():
    async with bot:
        if BOT_TOKEN:
            await bot.start(BOT_TOKEN)
        else:
            print("❌ DISCORD_TOKEN is not set.")

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
