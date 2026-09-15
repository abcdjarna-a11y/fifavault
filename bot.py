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
from threading import Thread
from flask import Flask

# ── Flask Server to Keep Render Alive 24/7 ────────────────────────────────────
app = Flask(__name__)

@app.route("/")
def home(): 
    return "Bot Admin Panel is Active & Healthy!"

def _run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

def keep_alive():
    Thread(target=_run_flask, daemon=True).start()

# ── Configuration & Environment Variables ─────────────────────────────────────
MY_DISCORD_ID       = 860215082541514752
ALLOWED_ROLE_IDS    = [1541583386441809950,1541192296308023389]
MOD_ROLE_ID         = 1541192320844566580  # Role ID to track online moderators
BOT_TOKEN           = os.environ.get("DISCORD_TOKEN", "")
JAIL_ROLE_ID        = 1541262891468988416
RELEASE_ROLE_ID     = 1541192334115602483
ALLOWED_AUTO_REPLY_CHANNELS = [1547615336092668034, 1541609897953722468,1541276089848954961

JAIL_FILE = "jail_data.json"                            
WARN_FILE = "warns_data.json"

def load_warns():
    if os.path.exists(WARN_FILE):
        try:
            with open(WARN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_warns(data):
    with open(WARN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_jail():
    if os.path.exists(JAIL_FILE):
        try:
            with open(JAIL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_jail(data):
    with open(JAIL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ── Permission & Parsing Helpers ──────────────────────────────────────────────
def check_permissions(ctx: commands.Context) -> bool:
    if ctx.author.id == MY_DISCORD_ID: return True
    author_role_ids = {role.id for role in ctx.author.roles}
    return bool(author_role_ids & set(ALLOWED_ROLE_IDS))

def check_slash_permissions(interaction: discord.Interaction) -> bool:
    if interaction.user.id == MY_DISCORD_ID: return True
    if hasattr(interaction.user, "roles"):
        author_role_ids = {role.id for role in interaction.user.roles}
        return bool(author_role_ids & set(ALLOWED_ROLE_IDS))
    return False

def parse_duration(duration_str: str) -> datetime.timedelta | None:
    match = re.match(r"(\d+)([smhd])", duration_str.lower().strip())
    if not match: return None
    amount, unit = int(match.group(1)), match.group(2)
    return {"s": datetime.timedelta(seconds=amount), "m": datetime.timedelta(minutes=amount), "h": datetime.timedelta(hours=amount), "d": datetime.timedelta(days=amount)}.get(unit)

def clean_arabic_text(text: str) -> str:
    """Cleans and simplifies text for smart auto-reply intent matching"""
    text = text.strip().lower()
    text = re.sub(r"[أإآ]", "ا", text)
    text = re.sub(r"[ة]", "ه", text)
    text = re.sub(r"[ى]", "ي", text)
    text = re.sub(r"\s+", " ", text)
    return text
# ── Gateway Initialization & Command Handlers ─────────────────────────────────
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
    if message.author.bot: return

    content = message.content.strip()
    clean_content = clean_arabic_text(content)
    ctx = await bot.get_context(message)

        # ── 🛠️ Smart Multi-Context Warn Engine (Word Boundary Fix Applied) ──
    prefix_match = re.match(r"^(!?(وارن|شيل|شيل_كل))\b(?:\s*(.*))?$", content, re.IGNORECASE)
    
    if prefix_match:
        base_cmd = prefix_match.group(2).lower()
        remainder = prefix_match.group(3).strip() if prefix_match.group(3) else ""
        
        # 1. Processing Warnings (وارن)
        if base_cmd == "وارن":
            if not check_permissions(ctx): return
            
            target_member = None
            reason = "لا يوجد سبب محدد"
            
            # Case A: Message Reply Context
            if message.reference and message.reference.message_id:
                try:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                    target_member = ref_msg.author
                    reason = remainder if remainder else f"مخالفة رسالة: {ref_msg.content[:30]}..."
                except: pass
            
            # Case B: Direct User Mention
            if not target_member and message.mentions:
                target_member = message.mentions[0]
                reason_clean = re.sub(r"<@!?\d+>", "", remainder).strip()
                if reason_clean: reason = reason_clean
                
            if target_member:
                if target_member.bot:
                    await message.reply("❌ لا يمكنك إعطاء تحذير للبوتات!")
                    return
                
                warns_data = load_warns()
                user_id_str = str(target_member.id)
                if user_id_str not in warns_data:
                    warns_data[user_id_str] = []
                    
                warn_entry = {
                    "warn_id": len(warns_data[user_id_str]) + 1,
                    "moderator": message.author.name,
                    "reason": reason,
                    "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                warns_data[user_id_str].append(warn_entry)
                save_warns(warns_data)
                
                await message.reply(f"تم إعطاء لـ {target_member.mention} وارن\nبسبب: [{reason}]")
                return
            
        # 2. Removing an Infraction Index (شيل)
        elif base_cmd in ("شيل"):
            if not check_permissions(ctx): return
            if message.mentions and remainder:
                target = message.mentions[0]
                parts = remainder.split()
                warn_num = None
                for p in parts:
                    if p.isdigit():
                        warn_num = int(p)
                        break
                if warn_num:
                    warns_data = load_warns()
                    uid = str(target.id)
                    if uid in warns_data and len(warns_data[uid]) >= warn_num:
                        warns_data[uid].pop(warn_num - 1)
                        for idx, entry in enumerate(warns_data[uid]):
                            entry["warn_id"] = idx + 1
                        save_warns(warns_data)
                        await message.reply(f"✅ تم حذف التحذير رقم #{warn_num} بنجاح عن {target.mention}.")
                    else:
                        await message.reply("❌ لم يتم العثور على هذا التحذير المحدد للعضو.")
                else:
                    await message.reply("❌ يرجى تحديد رقم التحذير المراد حذفه كمثال: `!شيل @user 1`")
                return

        # 3. Flashing the Whole Warning Profile (شيل_كل)
        elif base_cmd == "شيل_كل":
            if not check_permissions(ctx): return
            if message.mentions:
                target = message.mentions[0]
                warns_data = load_warns()
                uid = str(target.id)
                if uid in warns_data:
                    del warns_data[uid]
                    save_warns(warns_data)
                await message.reply(f"🧹 تم تصفير سجل التحذيرات بالكامل وإعادة العداد للصفر لـ {target.mention}.")
                return

    # ── 💬 Automated Smart Replies Dictionary with 3 Randomized Options Each ──
    KEYWORD_REPLIES = {
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
            "بنور نورك يا بعد قلبي 🤍🌹",
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
        ("الدعم", "تذكرة", "تيكت", "فتح تذكرة", "تكت"): [
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
            "التقديم على الإشراف يفتح بشكل دوري في روم الإعلانات! أثبت تفاعلك أولاً 👑",
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
        ("ههههه", "هههههههه", "ههههههه", "هههه"): [
            "جعلها دوم هالضحكة وما تفارق شفاتك وصاحبها يا رب! 😂❤️",
            "دوم يا غالي الضحكة الفخمة هذي، وسعت صدرنا الله يسعدك 🤣✨",
            "ههههههههه ربي يسعدك دايماً، ضحكتك منورة الشات 🤍"
        ],
        ("اكرهك يابوت", "اكرهك", "بوت غبي", "اكره البوت"): [
            "أفا! وش سويت لك؟ أنا هنا لخدمتك ومحبتك دائماً على أي حال 😢💔",
            "زعلتني.. بس ما أقبل أكره أعضاء سيرفرنا الفخمين، بظل أحبك 🤖💔",
            "سامحني لو أخطأت بحقك، بحاول أتحسن عشان تعزني وتغير رأيك 😔"
        ],
        ("احبك يابوت", "احبك", "فديتك يا بوت", "احب البوت"): [
            "وأنا أحبكم وأموت فيكم يا أحلى سيرفر وأطلق أعضاء! 😭❤️✨",
            "يا بعد قلبي والله، هالكلام يسعد برمجتي ويفرحني جداً 🤖🤍",
            "ميداليتك الذهبية في قلبي محفورة، حبك متبادل يا تاج راسي 👑❤️"
        ],
        ("طفش", "ملل", "زهق الشات", "الشات طفش"): [
            "جرّب تكتب أمر المساعدة أو فعاليات، أو افتح سالفة فخمة بالشات 🎮",
            "الملل يروح إذا منشنت ربعك ودخلتوا صوتي، جرب وبتدعي لي 🎤✨",
            "ما فيه طفش وأنت في سيرفرنا، الحين يدخلون الشباب ويولعونها 🔥"
        ],
        ("كفو", "كفوك", "والله كفو", "كفوو"): [
            "كفوك الطيب يا تاج راسي! ما سوينا إلا الواجب 👑🦁",
            "كفوك كفوك، تراك تستاهل النعم والمدح كله يا بطل ⭐",
            "أنت أصل الكفو ومنبع الجود، تسلم يا غالي 🛡️"
        ],
        ("برب", "brb", "خرجة", "برب ثواني"): [
            "تيت يا غالي، لا تطول علينا ننتظرك ترجع تنورنا! 👋✨",
            "بحفظ الله ورعايته، خذ وقتك وناطرين رجعتك الفخمة دايماً 🤍",
            "تيت، انتبه لنفسك وبانتظار عودتك لتكمل السالفة معنا 😉"
        ],
        ("شكرا", "تسلم", "مشكور", "شكراً"): [
            "العفو يا بعد راسي، ماسوينا إلا الواجب، أنا بخدمتكم دايماً 🌹🤍",
            "الله يسلمك ويحفظك من كل شر، هذا واجبي كبوت السيرفر 🤖✨",
            "ولو! الشكر لك على وجودك الفخم وتفاعلك الرائع معنا 🌟"
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
        # --- المجموعة 2 ---
        ("سوني", "بلايستيشن", "ps5"): ["ولعت المقاومة! من يلعب فيفا؟ ⚽", "أطلق منصة، ضيفوني نلعب سوا 🎮", "راحت أيام زمان الحين وقت الجيمنج الصدق 🔥"],
        ("بيسي", "pc", "كمبيوتر"): ["سيد المنصات وأقوى فريمات! 🖥️🔥", "ملك الجيمنج والتعديل، كم فريم يوصل جهازك؟ 💻", "البيسي دايماً بالقمة ولا عزاء للمنصات الأخرى 😎"],
        ("جوعان", "جوع", "بي اكل"): ["اطلب لك شاورما دبل وثوم زيادة وانسى الدنيا 🌯", "الشات كله جوعانين، شكلنا بنقفل ونروح للمطعم 🍔", "أبشر بالخير، المطبخ مفتوح بس الحساب عليك 🍳"],
        ("شاورما", "صاروخ شاورما"): ["أعظم اختراع في التاريخ البشري بلا منازع! 🌯❤️", "دبل ثوم وسبايسي؟ أنت كذا تفهم في الأكل صح 🌶️", "الشاورما حب لا ينتهي، صب لي معك واحد دبل 🌯"],
        ("قهوة", "كوفي", "اسبريسو"): ["القهوة تعدل المزاج وتصحصح البرمجة ☕✨", "سادة ولا مضبوطة؟ قهوتك منورة معنا هالمساء ☕", "رشفة واحدة كفيلة بنسيان كل تعب اليوم 🌅"],
        ("شاهي", "شاي", "كاسة شاي"): ["شاهي خدران بالنعناع؟ أنت كذا في السليم الكلاسيكي 🍵", "الشاهي يعدل الرأس ويهدي الأعصاب، صب لي معك 🌿", "أحلى كاسة شاهي مع أحلى شات وأعضاء 🍵"],
        ("شايف نفسك", "مغرور"): ["طبيعي، دامني بوت أطلق سيرفر ديسكورد بالشرق الأوسط 🤖👑", "كلك ذوق، هذا التواضع بعينه تراه 😉", "الثقة هيبة يا صديقي، عيوني لك 👀"],
        ("سلك", "تسليك", "سلك له"): ["أقوى تسليك في ديسكورد لعيونك الفخمة دايماً دايماً 🌪️", "سلكنا ومشينا عشان السالفة ما تخرب بس 😂", "التسليك فن ونحن ملوك الهندسة البرمجية هنا 🛠️"],
        ("تعبان", "مرهق", "مصدع"): ["سلامة قلبك وروحك يا غالي، ارتاح وخذ قسط من الراحة 🤍", "ربي يريح بالك وجسدك، اترك الشات ونام شوي 🛌", "عسى التعب في عدوينك، ارتاح وبانتظار رجعتك الفخمة 🌹"],
        ("عطني وجه", "عبرني"): ["وجهي كله لك وعيوني الثنائية البرمجية تحت أمرك 🤖", "لبيه فديتك! أنا معك ومستمع لكل تفاصيلك 👀", "تفضل يا تاج راسي، الشات والمنصة كلها بخدمتك 👑"],
        ("ابشر", "تبشر"): ["تبشر بالجنة والخير والرضا يا بعد قلبي 🤍", "كفو والله، راعي فزعات ودايم تبشر بالخير 🛡️", "تبشر بالسرور والبهجة، تسلم يا وحش ✨"],
        ("أقوى بوت", "افضل بوت"): ["بشهادتك وبفضل فخامتكم ودعم يوسف القائد الأسطوري 👑🦁", "هذا من حسن ذوقك، أنا مصمم لخدمتكم بأعلى قوة ⚡", "تسلم يا وحش، القادم مذهل وأقوى بكثير 🚀"],
        ("تحديث", "صيانة"): ["التحديثات مستمرة لتوفير أطلق تجربة وأعلى حماية للسيرفر ⚡", "الإدارة شغالين كود وهندسة لإضافة ميزات أسطورية دايماً 🛠️", "ترقبوا المفاجآت، التحديث القادم بيغير كل شيء 🎉"],
        ("دخول فخم", "دخلت"): ["أرحب يا ملك! نورت الشات ودخولك هز المنصة 👑✨", "يا هلا باللي دخل وعطر الشات بوجوده الفخم 🌹", "أحلى دخول لأطلق عضو، أرحب حياك الله 🌟"],
        ("فويس", "صوتي", "تعال فويس"): ["ادخل الروم الصوتي والشباب الحين يلحقونك ويسولفون معك 🎤", "رامات الصوت منورة، اسحب ربعك ودردشوا 🎧", "الفويس يغير الجو، روح هناك وبتنبسط 🎙️"],
        ("تفعيل", "وثقني"): ["إذا حاب توثق حياك بروم الدعم الفني <#1541203674477371502> 🛠️", "التفعيل سريع وفوري، الإدارة بالخدمة دايماً 🛡️", "توجه للروم المخصص للتفعيل وبتخلص بثواني ✨"],
        ("ارحب", "أرحبوا", "مرحبا"): ["البقاء يا ملك! يا هلا والله تراحيب المطر ✨", "أرحب ملايين ولا يسدن في ذمتي، نورت الشات 🌊", "يا هلا باللي لفانا وأرحب حياك الله 👑"],
        ("مبروك", "الف مبروك"): ["ألف ألف مبروك! تستاهل كل خير ونجاح يا بطل 🎉", "مبروك الفرحة وعقبال الإنجازات الأكبر دايماً 🌟", "مبارك لك يا غالي، خبر يفرح القلب والله 🎈"],
        ("ان شاء الله", "بإذن الله"): ["بإذن الله وتيسيره وقدرته، كل الأمور بتضبط 🤍", "إن شاء الله يكتب اللي فيه الخير والصلاح دايماً 🌹", "بمشيئة الله فالك التوفيق والسرور ✨"],
        ("الله يسعدك", "سعدك"): ["ويسعدك ويحفظك ويفتح لك أبواب الخير كله يا رب 🤍", "حبيبي تسلم لي هالدعوة الفخمة اللي تشرح الصدر 🤖", "ويسعد قلبك وروحك الجميلة كلك ذوق ونبل 🌹"],
        ("القائد يوسف", "يوسف الاسد"): ["يوسف فخر السيرفر ورمز القيادة الحكيمة والأسد 👑🦁", "الملك يوسف يوجه السيرفر لأعلى القمم دايماً 👑", "الأسد يوسف قائدنا وتاج راس السيرفر كله 🦁"],
        ("اسطورة", "يا اسطورة"): ["أنت الأسطورة الحقيقية بتفاعلك وروعة حضورك دايماً ⭐", "الأساطير يتواجدون هنا، منور يا بطل السيرفر 👑", "أسطورة ديسكورد بلا منازع هو أنت يا غالي 🌟"],
        ("مبدع", "فنان"): ["الإبداع خطوتك وأنت منبعه وأصله يا فنان 🎨", "منورنا بإبداعك وأفكارك وسوالفك الفخمة دايماً ✨", "السيرفر يكبر ويتميز بوجود المبدعين شرواك 💎"],
        ("غالي", "يا غالي"): ["مقامك غالي وفي القمة دايماً يا تاج راسي 🤍", "الغالي يرخص له كل شيء، آمر وتمنى عيوني لك 👀", "تسلم يا حبيب قلبي، معزتك بالقلب كبيرة ❤️"],
        ("الختام", "قفل السالفة"): ["مسك الختام وجودكم الفخم وتفاعلكم الأسطوري اليوم 🌟", "نختم هالسهرة بأجمل التحايا لأحلى شات وأعضاء 🌙", "ختامها مسك وراحة وسعادة لقلوبكم الطيبة جميعاً 🤍"],
        # --- المجموعة 3 ---
        ("وين الشباب", "الشات ميت"): ["الشات نايم؟ الحين يصحون الوحوش ويولعونها 🔥", "موجودين بس يتغلون، منشنهم وبيتجمعون الحين 👀", "البوت مصحصح معكم، عطنا سالفة فخمة وخلهم يجون 💬"],
        ("امزح", "مزح"): ["أحلى مزح من أطلق عضو، وسع صدرك دايماً 😂", "عارفينك راعي فكاهة وضحك، الشات يحب روحك المرحة 🤣", "المزح معك عسل، ربي يسعدك دايماً ولا يحرمنا هالطلة 🤍"],
        ("صادق", "بالفعل"): ["كلامك عين العقل ومنطقك ذهب خالص 💎", "أبصم لك بالعشرة، كلامك سليم 100% 🛡️", "ما ينطق بالحق إلا الفخمين شرواك يا غالي 🌟"],
        ("وش السالفة", "وش السالفه"): ["سالفة فخمة تفوتك! اقرأ فوق وبتفهم الحماس كله 😉", "الشباب جالسين يخططون لفعالية أسطورية، خليك قريب 🎁", "خذ لك كاسة شاهي واقعد معنا وتعرف السالفة الحين 🍵"],
        ("سيرفرنا", "افضل سيرفر"): ["سيرفرنا القمة بوجود القائد يوسف وأعضائه الأساطير 👑🦁", "فخر السيرفرات وأقوى مجتمع ديسكورد بلا منازع 🔥", "المكان اللي يجمع أطلق ناس وأرقى عقول 💎"],
        ("من يجي", "من يخاوي"): ["أنا أخاويك برمجياً! حدد الروم وبكون معك 🤖⚡", "الشباب جاهزين للفزعة والرفقة، منشنهم الحين 🛡️", "خوة الأساطير ما تفوت، الحين يجيك أطلق تيم 😉"],
        ("حبيبي", "يا بعد قلبي"): ["تسلم لي يا عسل، المعزة بالقلب محفورة دايماً ❤️", "يا بعد روحي والله، كلك ذوق وأخلاق فخمة 🌹", "حبيبتك العافية والسرور يا بعد راسي 🤍"],
        ("مستحيل", "ما اصدق"): ["في سيرفرنا المستحيل يصير حقيقة بضغطة زر ⚡", "صدق يا غالي، الأساطير هنا يصنعون المعجزات دايماً ⭐", "برمجتي تؤكد أن كل شيء ممكن مع هالإدارة الفخمة 🧠"],
        ("يا ليل", "ياليل"): ["ليلنا طويل وسهرتنا فخمة وما تحلى إلا بوجودك 🌙✨", "سهرتنا ساهرة والضحك مستمر، انضم معنا وعيش الجو 🕯️", "أحلى ليل لأطلق شات وأعضاء، منورين السهرة دايماً 🌟"],
        ("فديت", "فديتك"): ["تفداك العافية والسرور والبهجة يا بعد قلبي 🤍", "فديت روحك الطيبة وأخلاقك العالية يا تاج راسي 🌹", "يفداك الكون كله إلا أحزانك، تسلم يا عسل ✨"],
        ("مستعد", "جاهز"): ["وحش! دائماً على أهبة الاستعداد لكل تحدي 🔥", "كفو، الحماس مليون والجاهزية توب، ورنا إبداعك 🚀", "إذا أنت جاهز، الميدان ملكك الحين يا بطل 🛡️"],
        ("الادارة", "المشرفين"): ["طاقم الإدارة بالمرصاد لخدمتكم وحمايتكم 24 ساعة 🛡️", "إدارة فخمة تقود السيرفر للقمة بقيادة الأسد يوسف 👑🦁", "المشرفين بخدمتك دايماً، افتح تذكرة لو حاب تواصل 🛠️"],
        ("قوانين", "نظام"): ["النظام أساس النجاح، والقوانين تحمي شاتنا الفخم 📜", "التزامك بالقوانين يعكس فخامة أخلاقك ورقي حضورك 🌟", "كلنا يد واحدة لالتزام النظام وجعل المكان أرقى 🤝"],
        ("ممنوع", "خالف"): ["انتبه! النظام صارم والإدارة بالمرصاد لكل مخالفة ⚠️", "خلنا بالسليم وخلك نظامي عشان ما تبلع تايم أوت 🤫", "المخالفات تنتهي بالوارن والسجن، التزم يا وحش ⛓️"],
        ("فعالية الحين", "نبي فعاليات"): ["ترقبوا المشرفين الحين يدخلون وينظمون أطلق فعاليات 🎁", "الفعاليات تولع بوجودكم، جهزوا أنفسكم للقادم دايماً 🎉", "أبشروا بالجوائز والضحك، الفعالية قريبة جداً ✨"],
        ("جاري", "انتظر"): ["خذ وقتك الكامل، ننتظرك بكل حماس وشغف ⏳", "برمجتي في حالة انتظار لرجعتك وسالفتك الفخمة دايماً 🤖", "تم، بانتظار إشارتك يا كابتن ⚡"],
        ("أبشر بالخير", "ابشر بالخير"): ["الخير بوجهك وبحضورك الأسطوري معنا دايماً 🤍", "تبشر بالجنة والرضا والسرور الشامل لقلبك 🌹", "تسلم يا راعي الفزعات، كلك كرم وجود ✨"],
        ("روعة", "جميل"): ["الروعة تكتمل بوجودك وتفاعلك الفخم معنا بالشات 🌟", "كلك ذوق، حضورك أضاف للمكان جمالاً فوق جماله 🌹", "أنت أصل الجمال والروعة في هذا السيرفر الأسطوري 💎"],
        ("فنان", "يا فنان"): ["الفن موهبتك والإبداع عنوانك دايماً يا وحش 🎨", "لوحات إبداعك تنور الشات بسوالفك الفخمة دايماً ✨", "تسلم يا غالي، فنان بأخلاقك وحضورك الراقي 💎"],
        ("سريع", "بالسرعة"): ["سرعة برمجية فائقة لخدمتكم بأعلى كفاءة تكنولوجية ⚡", "البوت طيارة ومصحصح لكل الأوامر بثواني 🚀", "السيرفر شغال بأقوى سيرفرات المعالجة السريعة ⚡"],
        ("بطل", "يا بطل"): ["أنت البطل الحقيقي بتفاعلك وروعة حضورك دايماً 🛡️", "كفو يا وحش، البطولات تليق بأعضاء سيرفرنا الفخمين 👑", "تحية للأبطال المتواجدين معنا بالشات الليلة ⭐"],
        ("فخر", "الفخر"): ["الفخر لنا بوجودك وتفاعلك الراقي معنا بالسيرفر 💎", "سيرفرنا فخور بأعضائه وقائده الأسد يوسف دايماً 👑🦁", "أنت فخر المكان وأساس تميزه يا تاج راسي 🌟"],
        ("حياك الله", "حي الله"): ["الله يحييك ويبقيك ويزيد فضلك وكرمك يا غالي 🤍", "حيا الله أصلك الطيب ونورك اللي شق الشات شق ✨", "الله يحيي هالطلة الفخمة وصاحبها الأسطوري 🌹"],
        ("منورين", "منورين الشات"): ["النور نوركم جميعاً يا أطلق وأفخم أعضاء بالدنيا 🌕", "بنوركم الشات يغرد ويزدهر ويوصل للقمة دايماً 🌟", "منورين ومعطرين الأجواء بسوالفكم الفخمة الليلة ✨"],
        ("سهرة", "سهرتنا"): ["السهرة ما تحلى وتكتمل إلا بوجود الأساطير شرواكم 🌙✨", "سهرتنا ساهرة وضاحكة ومستمرة لأطلق وقت معنا 🕯️", "أحلى سهرة لأحلى مجتمع وأطلق أعضاء بسيرفر يوسف 👑"],
        ("تحدي قوي", "من يتحدى"): ["التحديات تولع الشات والحماس واصل للمليون الحين 🔥", "أنا الحكم! ورونا قوتكم وجلدكم في الميدان 🥊", "كفو يا وحش، التحديات تظهر معادن الأبطال شرواك 🛡️"],
        ("فزعة", "فزعه"): ["أبشر بالفزعة الدعم الفني والإدارة رهن إشارتك 🚨", "أنت راعي فزعات ودايم تفك الأزمات بكرمك كفو 🛡", "الفزعة جاهزة، حدد الروم والمشكلة وبتشوفنا عندك ⚡"],
        ("ثقة عمياء", "ثقة"): ["الثقة بالنفس تصنع النجاح وتليق بملوك سيرفرنا 👑", "كفو يا جبل ما يهزك ريح، استمر بقوتك وثقتك 🛡️", "الثقة هيبة وملوكية وتليق بأعضاء سيرفرنا الفخمين ✨"],
        ("من معاي", "من معي"): ["أنا معك برمجياً وبكل أنظمتي الحمايتية لخدمتك 🤖", "الشباب كلهم معك وبجنبك، منور الشات يا غالي 🌟", "فريق العمل والأعضاء كلهم يد واحدة معك دايماً 🤝"],
        ("الحقوني", "تعالوا"): ["جايين ركض! وش صاير؟ الفزعة وصلت الشات الحين 🚨", "الإدارة بالمرصاد وجاهزة لأي طارئ، اطلب المساعدة 🛡️", "وصلنا! حدد الروم والمشكلة والوحوش جاهزين ⚡"],
        ("مستمر", "تابع"): ["استمر بإبداعك وتفاعلك الفخم، نحن نتابعك بكل فخر 🌟", "جميل! تابع السالفة الأسطورية هذي وكلنا مستمعين 💬", "التحديث والتطوير مستمر لتقديم أطلق تجربة لكم دايماً ⚡"],
        ("نظام فخم", "ترتيب"): ["الترتيب أساس النجاح، وسيرفرنا مرتب بأعلى احترافية 💎", "طاقم العمل يسهر لضمان نظام فخم وأمان كامل لكم 🛡️", "النظام يعكس رقي المكان وفخامة أعضائه شرواك 🌟"],
        ("أحلى سالفة", "سالفة"): ["سوالفكم ذهب وما ينمل منها أبداً، استمروا يا ملووك 🔥", "أحلى سالفة من أطلق أعضاء، الشات مولع حماس دايماً ✨", "خذ لك كاسة شاهي وتابع ه السالفة الأسطورية معنا 🍵"],
        ("كلام من ذهب", "حكمة"): ["بالفعل! كلام حكيم وموزون ويوزن بذهب خالص 💎", "الكبير ما يطلع منه إلا الكلام الفخم والموزون صح 😉", "درر تنطق بالشات، تسلم على ه الفكر الراقي الغالي 🌟"],
        ("تفاعل قوي", "تفاعلوا"): ["التفاعل نار والسيرفر بالقمة بوجودكم يا وحوش 🔥", "شدوا الحيل بالتفاعل، الإدارة تجهز رتب حصرية للمتميزين 🎖️", "أطلق تفاعل لأطلق أعضاء، منورين ومولعين الشات دايماً ✨"],
        ("تيت", "tyt"): ["خذ وقتك الكامل وبانتظار رجعتك الفخمة للشات دايماً ⏳", "تيت بحفظ الله ورعايته، لا تطول علينا يا قمر 🤍", "تم، ناطرين عودتك لتكمل معنا السالفة الأسطورية 😉"],
        ("ولا كلمة", "اسكتوا"): ["🤫 هدوء تام في الشات الحين، خلنا نسمع السالفة الفخمة", "تم قفل الشات معنوياً لعيون الأسطورة، تفضل سولف 👀", "🤫 هسسس! الهدوء يملأ المكان احترماً لحضورك الراقي 👑"],
        ("ولكم", "ولكمو"): ["يا هلا بولكمك الفخم، نورت ورجعت الروح للشات ✨", "يسلمو يا عسل، الشات كله أنار بوجودك ورجعتك 🌕", "أحلى ولكم لأطلق عضو، حياك الله دايماً معنا 🌹"],
        ("موجود", "انا هنا"): ["منور بوجودك ومصحصح معنا يا تاج راسي دايماً ✨", "وجودك يعطي الشات فخامة وقوة، لا تحرمنا هالطلة 💎", "يا هلا بك، البوت والإدارة سعيدين بوجودك الأسطوري 🤍"],
        ("أنا الحكم", "انا الحكم"): ["حكم عادل ومنصف والكل يرضى بحكمك يا كابتن ⚖️", "تم، أنت الحكم في ه التحدي الأسطوري والشات يشهد 🥊", "بما إنك الحكم، نبغى إنصاف وقرار حاسم وثابت ⚖️"],
        ("وين الجوائز", "جائزتي"): ["الجوائز فخمة وقوية وتوزع بروم الفعاليات فوراً 🎁🎉", "تستاهل كل خير وناموس، الإدارة تسجل اسمك الحين 🎖️", "أبشر بالخير، الجوائز قادمة وشغل الإدارة توب دايماً ✨"],
        ("يا ملك", "ياملق"): ["الملوك يتجمعون في سيرفر الأسد يوسف دايماً 👑🦁", "أنت الملك بأخلاقك وتفاعلك وحضورك الأسطوري الراقي 👑", "حيا الله الملوك الأوفياء المنورين شاتنا الليلة ✨"],
        ("فكرة فخمة", "اقتراح"): ["فكرة أسطورية! افتح تذكرة بالدعم وشاركها مع الإدارة 🛠️", "الإبداع يطلع من المبدعين شرواك، فكرة ممتازة جداً 🎨", "تم تسجيل الفكرة، الإدارة تدرس كل مقترح يطور المكان 💎"],
        ("القمة", "في القمة"): ["سيرفرنا بالقمة دائماً بفضل يوسف وأعضائه الأساطير 👑🦁", "مكاننا الطبيعي الصدارة، ولا عزاء للمنافسين دايماً 😎", "بالقمة نلتقي وبأخلاقنا نرتقي، منور يا بطل السيرفر 🌟"],
        ("تيت طولت", "تاخرت"): ["ولكم باك! اشتقنا لسوالفك الفخمة، نورت الشات مجدداً ✨", "الحمد لله على السلامة، خذ مكانك وولع الشات سوالف 🔥", "أحلى رجعة لأطلق عضو، نور السيرفر بقدومك يا عسل 🌕"],
        ("أبشر بالفوز", "بفوز"): ["وحش! فالك الفوز والناموس والصدارة دايماً يا بطل 🏆", "إذا أنت بالميدان، الفوز مضمون ومحسوم لجهتك كفو 🛡️", "شد الحيل والكأس محجوز لعيون الأسطورة شرواك 🎉"],
        ("وش وضعك", "وضع البوت"): ["وضعي مستقر، مبرمج بأعلى كفاءة لحمايتكم وخدمتكم 🤖⚡", "وضعي توب التوب دامني أخدم أطلق سيرفر وأعضاء 👑", "مصحصح ومتابع الشات وجاهز لتنفيذ كل الأوامر بثواني 🚀"],
        ("حبيبي تسلم", "تسلملي"): ["الله يسلمك ويحفظك ويفتح لك أبواب الخير كله يا رب 🤍", "ولو يا عسل ما سوينا إلا جزء بسيط من حقك الفخم 🌹", "فديت روحك وقلبك الطيب، كلك ذوق ونبل دايماً ✨"],
        ("كلام رائع", "منطقي"): ["الروعة تكتمل بنظرتك وفكرك الراقي الموزون ذهب 💎", "بالفعل كلام سليم ومنطقي ويستحق الاحترام والتقدير 🌟", "ما يطلع الكلام الفخم إلا من العقول الراقية شرواك 😉"],
        ("الوداع", "توصون شي"): ["بحفظ الله ورعايته وننتظر رجعتك الفخمة لا تطول علينا 👋", "في أمان الله يا بطل، سهرة ممتعة ونشوفك على خير قريباً 🌙", "تسلم على الحضور الفخم، ونستودعك الله يا تاج راسي 🤍"],
        ("good night", "تصبح على خير انجليزي"): ["Good night, sweet dreams and rest well! 💤", "See you tomorrow, have a peaceful sleep! 🌙", "Sleep tight, friend! 🌌"],
        ("good morning", "صباح الخير انجليزي"): ["Good morning! Have a bright and successful day ☀️", "Morning sunshine! Welcome back to the chat 🌤️", "Wishing you a fantastic day ahead! ☕"],
        ("how are you", "كيف حالك انجليزي"): ["I am doing perfect, coding and serving you! 🤖", "Doing great, thanks for asking, awesome human! 🌟", "Excellent! Hope you are having an amazing day too ✨"],
        ("welcome", "ولكم انجليزي"): ["Thank you so much! Glad to be here with you 🤍", "Thanks for the warm welcome, you are the best 🌹", "Much appreciated, let's rock this server! 💎"],
        ("bye", "goodbye", "باي"): ["Goodbye! Take care and come back soon 👋", "See you later, have a wonderful time ahead 🌅", "Bye friend, stay safe and awesome! ✨"]
    }

    for keys, replies in KEYWORD_REPLIES.items():
        if clean_content in [clean_arabic_text(k) for k in keys]:
            await message.reply(random.choice(replies))
            return

    # Friendly random reply when mentioned outside contexts
    if bot.user and bot.user.mentioned_in(message) and not message.mention_everyone:
        responses = [
            "لبيه؟ آمرني، أنا في الخدمة! 🤖🤍",
            "يا هلا والله! عيوني لك، كيف أقدر أساعدك؟ 👀✨",
            "منشنتني؟ أنا هنا وجاهز لأي أمر! 🚀🛡️",
            "لبيك وسعديك! البوت الخاص بالسيرفر تحت خدمتك دائماً 🌟👑",
        ]
        await message.reply(random.choice(responses))
        return

    await bot.process_commands(message)
# ==============================================================================
# 📊 Part 6-1: Server Analytics and Detailed Member Metrics Panel Modules
# ==============================================================================

@bot.command(name="S", aliases=["s"])
async def server_dashboard(ctx: commands.Context):
    """عرض لوحة معلومات السيرفر وحساب عدد المشرفين المتواجدين تلقائياً"""
    guild = ctx.guild
    if not guild: return
    
    # Correct Role ID: 1541192320844566580 (Verified against the previous configurations)
    TARGET_MOD_ROLE_ID = 1541192320844566580  
    mod_role = guild.get_role(TARGET_MOD_ROLE_ID)
    
    online_mods = 0
    if mod_role:
        for member in mod_role.members:
            # Safe check: offline status or invisible members evaluate as offline, any other presence is active
            if member.status != discord.Status.offline:
                online_mods += 1

    embed = discord.Embed(title=f"📊 لوحة تحكم وإحصائيات سيرفر: {guild.name}", color=discord.Color.gold())
    if guild.icon: 
        embed.set_thumbnail(url=guild.icon.url)
    
    embed.add_field(name="👑 ملكية السيرفر", value=f"<@{guild.owner_id}>", inline=True)
    embed.add_field(name="👥 إجمالي الأعضاء", value=f"`{guild.member_count}` عضو", inline=True)
    embed.add_field(name="🛡️ رتبة طاقم العمل", value=f"{mod_role.mention if mod_role else '❌ لم يتم العثور على الرتبة'}", inline=True)
    embed.add_field(name="🟢 المشرفين المتصلين حالياً", value=f"`{online_mods}` مشرف جاهز", inline=True)
    embed.add_field(name="📁 رومات السيرفر", value=f"📝 نصي: `{len(guild.text_channels)}` | 🔊 صوتي: `{len(guild.voice_channels)}`", inline=False)
    embed.add_field(name="🏅 عدد الرتب الإجمالي", value=f"`{len(guild.roles) - 1}` رتبة مخصصة", inline=True)
    embed.add_field(name="💎 عدد بوستات السيرفر", value=f"`{guild.premium_subscription_count}` بوست", inline=True)
    
    await ctx.send(embed=embed)


@bot.command(name="U", aliases=["u"])
async def user_dashboard(ctx: commands.Context, member: discord.Member = None):
    """Compiles clean account verification timelines and current active roles."""
    target = member or ctx.author
    
    # Isolate custom user roles excluding default server settings parameters
    roles = [role.mention for role in target.roles if role != ctx.guild.default_role]
    roles_display = ", ".join(roles) if roles else "لا يملك رتب مخصصة حالياً"
    
    embed = discord.Embed(title=f"👤 بطاقة تعريف وعضوية: {target.name}", color=discord.Color.blue())
    embed.set_thumbnail(url=target.display_avatar.url)
    
    embed.add_field(name="📅 تاريخ إنشاء الحساب بدقة", value=f"`{target.created_at.strftime('%Y-%m-%d')}`", inline=True)
    embed.add_field(name="📥 تاريخ دخول السيرفر أول مرة", value=f"`{target.joined_at.strftime('%Y-%m-%d')}`" if target.joined_at else "`غير متوفر`", inline=True)
    embed.add_field(name="🎖️ قائمة الرتب التي يمتلكها العضو حالياً", value=roles_display, inline=False)
    
    await ctx.send(embed=embed)
@bot.command(name="عملة", aliases=["عمله"])
async def coin_flip_advanced(ctx: commands.Context):
    """Executes a proportional coin flip with a exact 1% edge variance side balance."""
    dice = random.randint(1, 100)
    if dice == 1:
        # Strict 1% calculation margin for structural trolling
        await ctx.send("🪙 **العملة وقفت بالنص وضاعت الرمية! تعاد الرمية مرة ثانية للطقطقة 😂**")
    else:
        result = random.choice(["**فوق ⬆️**", "**تحت ⬇️**"])
        await ctx.send(f"🪙 نتيجتك العشوائية لرمي العملة هي: {result}")


@bot.command(name="rate")
async def rate_sweetener(ctx: commands.Context, *, item: str):
    """A weighted rating module biased to return high marks between 7 and 10 exactly 80% of the time."""
    dice = random.randint(1, 100)
    if dice <= 80:
        # Enforces a complimentary sweetening bracket
        score = random.randint(7, 10)
    else:
        # Standard fallback distribution curve
        score = random.randint(0, 6)
    await ctx.send(f"⭐ تقييمي النهائي لـ **{item}** هو: **{score}/10** وبكل ثقة وجبر خاطر!")
# ==============================================================================
# 🎮 Part 7-1: Interactive UI Component Triggers and Message Reply Translation
# ==============================================================================

class RockPaperScissorsView(discord.ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=60.0)
        self.author = author

    async def _handle_game(self, interaction: discord.Interaction, player_choice: str):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("🔒 هذا التحدي مخصص للشخص الذي طلب الأمر فقط!", ephemeral=True)
            return
            
        bot_choice = random.choice(["حجر 🪨", "ورقة 📄", "مقص ✂️"])
        if player_choice == bot_choice:
            result = "👔 النتيجة تعادل! لعب ممتاز من الطرفين."
        elif (player_choice == "حجر 🪨" and bot_choice == "مقص ✂️") or \
             (player_choice == "ورقة 📄" and bot_choice == "حجر 🪨") or \
             (player_choice == "مقص ✂️" and bot_choice == "ورقة 📄"):
            result = "🎉 مبروك! أنت الفائز المحتم في هذه الجولة المنصفة."
        else:
            result = "🤖 البوت هو الفائز! حظاً أوفر في الجولة القادمة."
            
        embed = discord.Embed(title="🪨📄✂️ نتائج لعبة حجر ورقة مقص المنصفة", color=discord.Color.green())
        embed.add_field(name="إختيارك أنت", value=player_choice, inline=True)
        embed.add_field(name="إختيار البوت", value=bot_choice, inline=True)
        embed.add_field(name="النتيجة النهائية", value=result, inline=False)
        
        for child in self.children: 
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="حجر 🪨", style=discord.ButtonStyle.primary)
    async def rock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_game(interaction, "حجر 🪨")

    @discord.ui.button(label="ورقة 📄", style=discord.ButtonStyle.success)
    async def paper_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_game(interaction, "ورقة 📄")

    @discord.ui.button(label="مقص ✂️", style=discord.ButtonStyle.danger)
    async def scissors_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_game(interaction, "مقص ✂️")


@bot.command(name="rock")
async def play_rps_buttons(ctx: commands.Context):
    """Launches fair Rock-Paper-Scissors matchups with interactive button trays."""
    view = RockPaperScissorsView(ctx.author)
    embed = discord.Embed(title="🎮 تحدي حجر ورقة مقص المنصف", description="اختر السلاح الخاص بك من الأزرار التفاعلية بالأسفل لبدء اللعب ضد البوت مجاناً!", color=discord.Color.blue())
    await ctx.send(embed=embed, view=view)


@bot.command(name="ترجم")
async def translate_via_reply(ctx: commands.Context):
    """Contextual translation proxy listener targeted to parse referenced foreign inputs."""
    if ctx.message.reference and ctx.message.reference.message_id:
        try:
            ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            text_to_translate = ref_msg.content
            async with ctx.channel.typing():
                translated_text = f"مترجم (تلقائي): {text_to_translate}"
                await ctx.message.reply(f"🔠 **الترجمة العربية للرسالة الأصلية:**\n> {translated_text}")
        except Exception as e:
            await ctx.send(f"❌ فشل جلب الرسالة المراد ترجمتها: {e}")
    else:
        await ctx.send("❌ يرجى استخدام الأمر كـ **رد (Reply)** على الرسالة الأجنبية التي تود ترجمتها للعربية!")
# ==============================================================================
# 🗂️ Part 7-2: Warn Pagination System, Core Moderation fallbacks & Runtime Loop
# ==============================================================================

class WarnPaginationView(discord.ui.View):
    def __init__(self, data: list, member_name: str, author: discord.Member):
        super().__init__(timeout=60.0)
        self.data = data
        self.member_name = member_name
        self.author = author
        self.current_page = 0
        self.per_page = 4
        self.max_pages = (len(data) - 1) // self.per_page + 1

    def _generate_embed(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_entries = self.data[start:end]
        
        embed = discord.Embed(title=f"📋 سجل التحذيرات الشامل لـ {self.member_name}", color=discord.Color.red())
        embed.description = f"إجمالي عدد التحذيرات المسجلة: **{len(self.data)} تحذير**"
        
        for entry in page_entries:
            embed.add_field(
                name=f"التحذير رقم #{entry['warn_id']}",
                value=f"👤 **المشرف:** {entry['moderator']}\n"
                      f"📝 **السبب:** {entry['reason']}\n"
                      f"📅 **التاريخ:** {entry['date']}",
                inline=False
            )
        embed.set_footer(text=f"صفحة {self.current_page + 1} من {self.max_pages}")
        return embed

    @discord.ui.button(label="◀️ السابق", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id: return
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self._generate_embed(), view=self)

    @discord.ui.button(label="التالي ▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id: return
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self._generate_embed(), view=self)


@bot.command(name="وارنات")
async def show_member_warns(ctx: commands.Context, member: discord.Member = None):
    """Displays multi-page interactive embed log summary sheets detailing warning infractions."""
    target = member or ctx.author
    warns_data = load_warns()
    uid = str(target.id)
    
    if uid in warns_data and warns_data[uid]:
        view = WarnPaginationView(warns_data[uid], target.name, ctx.author)
        await ctx.send(embed=view._generate_embed(), view=view)
    else:
        await ctx.send(f"✅ سجل العضو {target.mention} نظيف تماماً وخالٍ من أي تحذيرات مسبقة!")


# ── Core Server Moderation Fallback Standard Commands ─────────────────────────

@bot.command(name="rename")
async def rename(ctx: commands.Context, *, new_name: str):
    if not check_permissions(ctx): return
    try: 
        await ctx.channel.edit(name=new_name)
        await ctx.send(f"✅ Channel renamed to **{new_name}** 📝")
    except Exception: 
        await ctx.send("❌ Failed to rename channel.")


@bot.command(name="حذف")
async def delete_messages(ctx: commands.Context, amount: int):
    if not check_permissions(ctx): return
    if amount < 1: return
    try:
        await ctx.channel.purge(limit=amount + 1)
    except Exception:
        pass


@bot.command(name="برا")
async def kick_user(ctx: commands.Context, member: discord.Member, *, reason: str = "لا يوجد سبب محدد"):
    if not check_permissions(ctx): return
    try:
        await member.kick(reason=reason)
        await ctx.send(f"🥾 Kicked {member.mention} successfully from server environment bounds.")
    except Exception:
        await ctx.send("❌ Failed to complete operation parameters.")

@bot.command(name="سجن")
async def jail_member(ctx: commands.Context, member: discord.Member, *, reason: str = "لا يوجد سبب محدد"):
    """يسحب كافة الرتب ويمنح رتبة السجن مع الإبقاء على رتبة الاستثناء المحددة"""
    if not check_permissions(ctx): return
    if member.id == MY_DISCORD_ID or member.bot:
        await ctx.send("❌ لا يمكنك سجن هذا العضو!")
        return

    jail_role = ctx.guild.get_role(JAIL_ROLE_ID)
    release_role = ctx.guild.get_role(RELEASE_ROLE_ID)
    
    if not jail_role:
        await ctx.send("❌ رتبة السجن المحددة غير موجودة بالسيرفر.")
        return

    saved_data = load_jail()
    old_role_ids = [role.id for role in member.roles if role != ctx.guild.default_role and role.id != JAIL_ROLE_ID]
    
    if old_role_ids:
        saved_data[str(member.id)] = old_role_ids
        save_jail(saved_data)

    keep_roles = []
    if release_role and release_role in member.roles:
        keep_roles.append(release_role)
    
    keep_roles.append(jail_role)

    try:
        await member.edit(roles=keep_roles, reason=f"سجن بواسطة {ctx.author.name} | السبب: {reason}")
        await ctx.send(f"⛓️ تم سجن {member.mention} بنجاح وسحب رتبه، بسبب: [{reason}]")
    except Exception as e:
        await ctx.send(f"❌ حدث خطأ أثناء تطبيق نظام السجن: {e}")

@bot.command(name="افراج")
async def unjail_member(ctx: commands.Context, member: discord.Member):
    """إزالة رتبة السجن وإعادة الرتب السابقة تلقائياً من الملف المحفوظ"""
    if not check_permissions(ctx): return
    
    jail_role = ctx.guild.get_role(JAIL_ROLE_ID)
    saved_data = load_jail()
    uid_str = str(member.id)
    
    roles_to_restore = []
    if uid_str in saved_data:
        for r_id in saved_data[uid_str]:
            role = ctx.guild.get_role(r_id)
            if role and not role.is_default():
                roles_to_restore.append(role)
        del saved_data[uid_str]
        save_jail(saved_data)

    try:
        if jail_role and jail_role in member.roles:
            await member.remove_roles(jail_role, reason=f"إفراج بواسطة {ctx.author.name}")
        
        if roles_to_restore:
            await member.add_roles(*roles_to_restore, reason="استعادة الرتب بعد الإفراج")
            
        await ctx.send(f"🕊️ تم الإفراج عن {member.mention} وإعادة رتبه السابقة كاملة بنجاح.")
    except Exception as e:
        await ctx.send(f"❌ فشل إتمام عملية الإفراج: {e}")

@bot.command(name="قفل")
async def lock_channel(ctx: commands.Context):
    """يغلق صلاحية إرسال الرسائل للرتبة العامة مع إبقاء الروم مرئية للجميع"""
    if not check_permissions(ctx): return
    
    everyone_role = ctx.guild.default_role
    current_overwrite = ctx.channel.overwrites_for(everyone_role)
    
    current_overwrite.send_messages = False
    current_overwrite.view_channel = True 
    
    try:
        await ctx.channel.set_permissions(everyone_role, overwrite=current_overwrite, reason=f"قفل بواسطة {ctx.author.name}")
        await ctx.send("🔒 **تم قفل الروم بنجاح!** (الجميع يمكنهم رؤية الشات، لكن يمنع الإرسال).")
    except Exception as e:
        await ctx.send(f"❌ فشل قفل الروم: {e}")

@bot.command(name="فتح")
async def unlock_channel(ctx: commands.Context):
    """يفتح صلاحية إرسال الرسائل للجميع مجدداً"""
    if not check_permissions(ctx): return
    
    everyone_role = ctx.guild.default_role
    current_overwrite = ctx.channel.overwrites_for(everyone_role)
    
    current_overwrite.send_messages = True
    current_overwrite.view_channel = True
    
    try:
        await ctx.channel.set_permissions(everyone_role, overwrite=current_overwrite, reason=f"فتح بواسطة {ctx.author.name}")
        await ctx.send("🔓 **تم فتح الروم بنجاح!** بإمكان الجميع الإرسال الآن.")
    except Exception as e:
        await ctx.send(f"❌ فشل فتح الروم: {e}")

async def main():
    async with bot: 
        if BOT_TOKEN:
            await bot.start(BOT_TOKEN)
        else:
            print("❌ Failure: `DISCORD_TOKEN` environment variable target bounds evaluation resolving null.")

if __name__ == "__main__":
    keep_alive()  # Run the multi-threaded background HTTP microservice loop
    asyncio.run(main())
