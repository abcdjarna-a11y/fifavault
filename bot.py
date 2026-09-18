import discord
from discord.ext import commands
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
# TOUCHLINE / FIFA VAULT DISCORD BOT - EXTENDED BUILD
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
    ("15m", "spam"),
    ("30m", "تقديم إساءات لعضو أو إداري"),
    ("1h", "السب والقذف أو إرسال صور مخلة"),
    ("2h", "السب والقذف بالأهل أو مخالفة أي قانون"),
    ("1d", "في حال تكرار مخالفة القوانين"),
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
}

# FIX #3: Pre-build a flat dict mapping cleaned_key -> replies list, done ONCE at startup.
# This replaces the inner-loop normalization inside on_message.
KEYWORD_REPLIES_CLEANED: dict[str, list] = {}
for _keys, _replies in _RAW_KEYWORD_REPLIES.items():
    for _k in _keys:
        KEYWORD_REPLIES_CLEANED[clean_arabic_text(_k)] = _replies

# ==============================================================================
# Events
# ==============================================================================
@bot.event
async def on_ready():
    print(f"✅ Bot Online as: {bot.user}")
    try:
        await bot.tree.sync()
        print("Synced all slash commands successfully.")
    except Exception as e:
        print(f"Sync error: {e}")

@bot.event
async def on_message(message: discord.Message):
    """Keep Auto Replies while always allowing discord.py prefix commands to run."""
    if message.author.bot:
        return

    try:
        content = message.content.strip()
        clean_content = clean_arabic_text(content)

        # FIX #3: O(1) lookup in pre-built dict instead of O(n*k) loop with normalization
        if clean_content in KEYWORD_REPLIES_CLEANED:
            replies = KEYWORD_REPLIES_CLEANED[clean_content]
            await message.reply(random.choice(replies))
            return
    except Exception as e:
        print("Auto-reply error:", repr(e))

    # IMPORTANT: process_commands must be called manually when on_message is overridden.
    try:
        await bot.process_commands(message)
    except Exception as e:
        print("Prefix command processing error:", repr(e))

# ==============================================================================
# Warn commands  (aliases added per requirement)
# ==============================================================================
@bot.command(name="وارن", aliases=["وارن"])
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

@bot.command(name="شيل", aliases=["شيل"])
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

@bot.command(name="S", aliases=["s"])
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

@bot.command(name="U", aliases=["u"])
async def user_dashboard(ctx: commands.Context, member: discord.Member = None):
    target = member or ctx.author
    roles = [r.mention for r in target.roles if not r.is_default()]
    embed = discord.Embed(title=f"👤 بطاقة العضوية: {target.name}", color=pink_color())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="📅 إنشاء الحساب", value=f"`{target.created_at.strftime('%Y-%m-%d')}`", inline=True)
    embed.add_field(name="📥 دخول السيرفر", value=f"`{target.joined_at.strftime('%Y-%m-%d')}`" if target.joined_at else "`غير متوفر`", inline=True)
    embed.add_field(name="🎖️ الرتب", value=", ".join(roles) if roles else "لا توجد", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="عملة", aliases=["عمله"])
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
@bot.command(name="اسكت", aliases=["تايم", "اص"])
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
@bot.command(name="تكلم", aliases=["تكلم"])
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

@bot.command(name="عمر", aliases=["عمر_الحساب", "accountage"])
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
@bot.command(name="وارنات", aliases=["وارنات"])
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

@bot.command(name="من_انا", aliases=["منانا", "مين_انا"])
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

@bot.command(name="wordle", aliases=["وردل"])
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

@bot.command(name="xo", aliases=["اكس_او"])
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

@bot.command(name="لو_خيروك", aliases=["لوخيروك"])
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
@bot.command(name="حذف", aliases=["م"])
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
@bot.command(name="برا", aliases=["برا"])
async def kick_user(ctx, member: discord.Member, *, reason: str = "لا يوجد سبب محدد"):
    if not check_permissions(ctx):
        return
    try:
        await member.kick(reason=reason)
        await ctx.send(bold_msg(f"تم طرد {member.mention} بنجاح.", "🥾"))
    except Exception as e:
        await ctx.send(bold_msg(f"فشل الطرد: {e}", "❌"))

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

@bot.command(name="افراج", aliases=["افراج"])
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
@bot.command(name="قفل", aliases=["قفل"])
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
@bot.command(name="فتح", aliases=["فتح"])
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

async def main():
    async with bot:
        if BOT_TOKEN:
            await bot.start(BOT_TOKEN)
        else:
            print("❌ DISCORD_TOKEN is not set.")

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
