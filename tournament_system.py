import asyncio
import datetime
import json
import os
import random
import re
import discord
from discord import app_commands
from discord.ext import commands

FILE = "tournament_data.json"
COLOR = 0xF5D451
ADMIN_ROLES = {1550882056408666132, 1555096604954857503}
COUNTS = {4, 8, 12, 16}


async def load_all():
    def read():
        try:
            with open(FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}
    return await asyncio.to_thread(read)


async def save_all(data):
    def write():
        with open(FILE + ".tmp", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(FILE + ".tmp", FILE)
    await asyncio.to_thread(write)


def state_for(data, guild_id):
    return data.setdefault(str(guild_id), {"active": None, "history": []})


def embed(title, description=""):
    e = discord.Embed(title=title, description=description, color=discord.Color(COLOR),
                      timestamp=discord.utils.utcnow())
    e.set_footer(text="🏆 FIFA VAULT • TOURNAMENT CENTER")
    return e


def safe_name(value):
    return discord.utils.escape_markdown(str(value or "فريق محذوف"))


def current_round(t):
    i = int(t.get("current_round", 0))
    return t["rounds"][i] if 0 <= i < len(t.get("rounds", [])) else None


def make_match(a, b, rnd, group=None):
    return {"match_id": f"{rnd}-{random.randrange(100000, 999999)}",
            "team1_id": int(a["role_id"]), "team2_id": int(b["role_id"]),
            "team1_name": a["name"], "team2_name": b["name"],
            "round_index": rnd, "group": group, "status": "pending"}


def stage_name(match_count):
    return {8: "ثمن النهائي", 4: "ربع النهائي", 2: "نصف النهائي", 1: "النهائي"}.get(match_count, "الأدوار الإقصائية")


def round_robin(teams):
    pool = list(teams)
    random.shuffle(pool)
    if len(pool) % 2:
        pool.append(None)
    result = []
    for _ in range(len(pool) - 1):
        pairs = []
        for i in range(len(pool) // 2):
            a, b = pool[i], pool[-1-i]
            if a is not None and b is not None:
                pairs.append((a, b))
        random.shuffle(pairs)
        result.append(pairs)
        pool = [pool[0], pool[-1], *pool[1:-1]]
    return result


def pair_teams(teams, avoid_same_group=False):
    items = list(teams)
    random.shuffle(items)
    if not avoid_same_group:
        return [(items[i], items[i+1]) for i in range(0, len(items), 2)]

    def solve(rest):
        if not rest:
            return []
        first = rest[0]
        options = list(range(1, len(rest)))
        random.shuffle(options)
        for i in options:
            other = rest[i]
            if first.get("group") == other.get("group"):
                continue
            remaining = rest[1:i] + rest[i+1:]
            tail = solve(remaining)
            if tail is not None:
                return [(first, other)] + tail
        return None
    solved = solve(items)
    if solved is not None:
        return solved
    random.shuffle(items)
    return [(items[i], items[i+1]) for i in range(0, len(items), 2)]


def build_ko(teams, idx, avoid_same_group=False):
    pairs = pair_teams(teams, avoid_same_group)
    return {"name": stage_name(len(pairs)), "group_stage": False,
            "matches": [make_match(a, b, idx) for a, b in pairs]}


def round_done(rnd):
    return bool(rnd and rnd.get("matches")) and all(m.get("status") == "completed" for m in rnd["matches"])


def standings(t):
    result = {}
    for group, teams in t.get("groups", {}).items():
        rows = {}
        for team in teams:
            rows[int(team["role_id"])] = {"team": team, "played": 0, "wins": 0, "draws": 0,
                "losses": 0, "gf": 0, "ga": 0, "points": 0, "group": group}
        for rnd in t.get("rounds", []):
            if not rnd.get("group_stage"):
                continue
            for m in rnd["matches"]:
                if m.get("group") != group or m.get("status") != "completed":
                    continue
                a, b = int(m["team1_id"]), int(m["team2_id"])
                if a not in rows or b not in rows:
                    continue
                sa, sb = int(m["score1"]), int(m["score2"])
                x, y = rows[a], rows[b]
                x["played"] += 1; y["played"] += 1
                x["gf"] += sa; x["ga"] += sb
                y["gf"] += sb; y["ga"] += sa
                if sa > sb:
                    x["wins"] += 1; x["points"] += 3; y["losses"] += 1
                elif sb > sa:
                    y["wins"] += 1; y["points"] += 3; x["losses"] += 1
                else:
                    x["draws"] += 1; y["draws"] += 1; x["points"] += 1; y["points"] += 1
        tie = {k: random.random() for k in rows}
        ordered = list(rows.values())
        ordered.sort(key=lambda r: (-r["points"], -(r["gf"]-r["ga"]), -r["gf"], tie[int(r["team"]["role_id"])]))
        result[group] = ordered
    return result


def qualifiers(t):
    tables = standings(t)
    count = int(t["team_count"])
    if count == 4:
        return [tables["A"][0]["team"], tables["A"][1]["team"]]
    selected = [tables[g][i]["team"] for i in range(2) for g in sorted(tables)]
    if count == 12:
        thirds = [tables[g][2] for g in sorted(tables)]
        thirds.sort(key=lambda r: (-r["points"], -(r["gf"]-r["ga"]), -r["gf"], random.random()))
        selected.extend(r["team"] for r in thirds[:2])
    return selected


def advance(t):
    rnd = current_round(t)
    if not round_done(rnd):
        return None
    if rnd.get("group_stage"):
        next_group = next((i for i, r in enumerate(t["rounds"])
                           if r.get("group_stage") and i > int(t["current_round"])), None)
        if next_group is not None:
            t["current_round"] = next_group
            return f"بدأت {t['rounds'][next_group]['name']}."
        selected = qualifiers(t)
        idx = len(t["rounds"])
        nxt = build_ko(selected, idx, avoid_same_group=int(t["team_count"]) != 4)
        t["rounds"].append(nxt)
        t["current_round"] = idx
        return f"انتهت المجموعات وبدأ {nxt['name']}."
    winners = []
    for m in rnd["matches"]:
        if int(m["score1"]) == int(m["score2"]):
            return "لا يمكن إنهاء دور إقصائي بنتيجة تعادل."
        winner_id = int(m["team1_id"] if int(m["score1"]) > int(m["score2"]) else m["team2_id"])
        winners.append({"role_id": winner_id, "name": m["team1_name"] if winner_id == int(m["team1_id"]) else m["team2_name"]})
    if len(winners) == 1:
        final = rnd["matches"][0]
        winner = winners[0]
        loser_id = int(final["team2_id"] if winner["role_id"] == int(final["team1_id"]) else final["team1_id"])
        loser_name = final["team2_name"] if loser_id == int(final["team2_id"]) else final["team1_name"]
        t["status"] = "completed"
        t["champion"] = winner
        t["runner_up"] = {"role_id": loser_id, "name": loser_name}
        t["completed_at"] = discord.utils.utcnow().isoformat()
        return f"🏆 انتهت البطولة! البطل: {safe_name(winner['name'])}."
    idx = len(t["rounds"])
    nxt = build_ko(winners, idx)
    t["rounds"].append(nxt)
    t["current_round"] = idx
    return f"تأهل الفائزون وبدأ {nxt['name']}."


def match_text(guild, m, number=None):
    a = safe_name(m.get("team1_name"))
    b = safe_name(m.get("team2_name"))
    n = f"{number}. " if number is not None else ""
    if m.get("status") == "completed":
        outcome = ""
        if not m.get("group") and int(m.get("score1", 0)) != int(m.get("score2", 0)):
            outcome = " • 🏆 " + safe_name(m.get("winner_name"))
        return f"{n}{a} **{m['score1']} — {m['score2']}** {b}{outcome}"
    return f"{n}{a} **VS** {b} • ⏳ لم تُلعب"


async def setup_tournaments(bot, owner_id, owner_role_ids):
    allowed_roles = set(owner_role_ids) | ADMIN_ROLES

    def is_admin(member):
        return member.id == owner_id or bool({r.id for r in getattr(member, "roles", [])} & allowed_roles)

    async def get_state(guild_id):
        data = await load_all()
        return data, state_for(data, guild_id)

    async def reply(interaction, title, description):
        await interaction.response.send_message(embed=embed(title, description), ephemeral=True)

    @bot.tree.command(name="إنشاء_بطولة", description="إنشاء بطولة وتحديد النظام وعدد الفرق")
    @app_commands.describe(name="اسم البطولة", format_type="نظام البطولة", team_count="عدد الفرق")
    @app_commands.choices(format_type=[
        app_commands.Choice(name="إقصائية فقط", value="knockout"),
        app_commands.Choice(name="مجموعات ثم إقصائية", value="groups_knockout")])
    @app_commands.choices(team_count=[
        app_commands.Choice(name="4 فرق", value=4), app_commands.Choice(name="8 فرق", value=8),
        app_commands.Choice(name="12 فريقًا", value=12), app_commands.Choice(name="16 فريقًا", value=16)])
    async def create(interaction: discord.Interaction, name: str, format_type: app_commands.Choice[str],
                     team_count: app_commands.Choice[int]):
        if not interaction.guild or not is_admin(interaction.user):
            await reply(interaction, "🔒 صلاحيات غير كافية", "الأمر متاح للمالك والرتبتين المصرح لهما فقط، ومن داخل السيرفر.")
            return
        name = name.strip()
        if not name or len(name) > 80:
            await reply(interaction, "⚠️ اسم غير صالح", "اكتب اسمًا من 1 إلى 80 حرفًا.")
            return
        data, state = await get_state(interaction.guild.id)
        old = state.get("active")
        if old and old.get("status") != "completed":
            await reply(interaction, "⚠️ توجد بطولة قائمة", f"أنهِ أو ألغِ البطولة الحالية أولًا: {old['name']}.")
            return
        state["active"] = {"name": name, "format": format_type.value, "team_count": int(team_count.value),
            "status": "registration", "created_by": interaction.user.id, "created_at": discord.utils.utcnow().isoformat(),
            "teams": [], "groups": {}, "rounds": [], "current_round": 0}
        await save_all(data)
        mode = "إقصائية فقط" if format_type.value == "knockout" else "مجموعات ثم إقصائية"
        await reply(interaction, "🏆 تم إنشاء البطولة", f"**{name}**\nالنظام: **{mode}**\nعدد الفرق: **{team_count.value}**\n"
            f"سجل الفرق بأمر /تسجيل_فريق_بطولة، ثم استخدم /بدء_البطولة لخلط القرعة.")

    @bot.tree.command(name="تسجيل_فريق_بطولة", description="تسجيل رتبة فريق في البطولة الحالية")
    async def register(interaction: discord.Interaction, team_role: discord.Role):
        if not interaction.guild or not is_admin(interaction.user):
            await reply(interaction, "🔒 صلاحيات غير كافية", "تسجيل الفرق متاح للمالك والرتبتين المصرح لهما فقط.")
            return
        data, state = await get_state(interaction.guild.id); t = state.get("active")
        if not t or t["status"] != "registration":
            await reply(interaction, "⚠️ لا يوجد تسجيل مفتوح", "أنشئ بطولة أولًا أو انتهى التسجيل.")
            return
        if len(t["teams"]) >= int(t["team_count"]):
            await reply(interaction, "⚠️ اكتمل العدد", "وصلت البطولة إلى عدد الفرق المحدد.")
            return
        if any(int(x["role_id"]) == team_role.id for x in t["teams"]):
            await reply(interaction, "⚠️ الفريق مسجل مسبقًا", f"{team_role.mention} مسجل بالفعل.")
            return
        t["teams"].append({"role_id": team_role.id, "name": team_role.name})
        await save_all(data)
        await reply(interaction, "✅ تم تسجيل الفريق", f"{team_role.mention}\nالمسجلون: **{len(t['teams'])}/{t['team_count']}**.")

    @bot.tree.command(name="إزالة_فريق_بطولة", description="إزالة فريق قبل بدء البطولة")
    async def remove_team(interaction: discord.Interaction, team_role: discord.Role):
        if not interaction.guild or not is_admin(interaction.user):
            await reply(interaction, "🔒 صلاحيات غير كافية", "الأمر متاح للمالك والرتبتين المصرح لهما فقط.")
            return
        data, state = await get_state(interaction.guild.id); t = state.get("active")
        if not t or t["status"] != "registration":
            await reply(interaction, "⚠️ لا يمكن الإزالة الآن", "إزالة الفرق متاحة قبل بدء البطولة فقط.")
            return
        before = len(t["teams"])
        t["teams"] = [x for x in t["teams"] if int(x["role_id"]) != team_role.id]
        if before == len(t["teams"]):
            await reply(interaction, "⚠️ الفريق غير مسجل", "الرتبة ليست ضمن البطولة الحالية.")
            return
        await save_all(data)
        await reply(interaction, "🗑️ تمت الإزالة", f"تمت إزالة {team_role.mention}. المتبقي {len(t['teams'])}/{t['team_count']}.")

    @bot.tree.command(name="تبديل_الفرق", description="استبدال فريق منسحب بفريق بديل قبل بدء البطولة")
    @app_commands.describe(old_team="الفريق المسجل الذي انسحب", new_team="رتبة الفريق البديل")
    async def swap_teams(interaction: discord.Interaction, old_team: discord.Role, new_team: discord.Role):
        if not interaction.guild or not is_admin(interaction.user):
            await reply(interaction, "🔒 صلاحيات غير كافية", "الأمر متاح للمالك والرتبتين المصرح لهما فقط.")
            return
        data, state = await get_state(interaction.guild.id); t = state.get("active")
        if not t or t["status"] != "registration":
            await reply(interaction, "⚠️ لا يمكن التبديل الآن", "التبديل متاح قبل بدء البطولة حتى لا تتغير نتائج ومواجهات قائمة.")
            return
        idx = next((i for i, x in enumerate(t["teams"]) if int(x["role_id"]) == old_team.id), None)
        if idx is None or any(int(x["role_id"]) == new_team.id for x in t["teams"]) or old_team.id == new_team.id:
            await reply(interaction, "⚠️ تعذر التبديل", "تأكد أن الفريق القديم مسجل وأن الفريق البديل مختلف وغير مسجل.")
            return
        t["teams"][idx] = {"role_id": new_team.id, "name": new_team.name}
        await save_all(data)
        await reply(interaction, "🔁 تم تبديل الفريق", f"تم استبدال {old_team.mention} بـ {new_team.mention}.")

    @bot.tree.command(name="بدء_البطولة", description="بدء البطولة وإنشاء القرعة عشوائيًا")
    async def start(interaction: discord.Interaction):
        if not interaction.guild or not is_admin(interaction.user):
            await reply(interaction, "🔒 صلاحيات غير كافية", "الأمر متاح للمالك والرتبتين المصرح لهما فقط.")
            return
        data, state = await get_state(interaction.guild.id); t = state.get("active")
        if not t or t["status"] != "registration":
            await reply(interaction, "⚠️ لا توجد بطولة جاهزة", "أنشئ بطولة وسجل الفرق أولًا.")
            return
        if len(t["teams"]) != int(t["team_count"]):
            await reply(interaction, "⚠️ عدد الفرق غير مكتمل", f"المسجل: {len(t['teams'])}/{t['team_count']}.")
            return
        teams = list(t["teams"]); random.shuffle(teams)
        t["status"] = "active"; t["started_at"] = discord.utils.utcnow().isoformat()
        if t["format"] == "knockout":
            t["rounds"] = [build_ko(teams, 0)]; t["current_round"] = 0
            desc = "تم خلط الفرق عشوائيًا وإنشاء مواجهات " + t["rounds"][0]["name"] + "."
        else:
            n = int(t["team_count"]); group_count = {4: 1, 8: 2, 12: 3, 16: 4}[n]
            names = [chr(65+i) for i in range(group_count)]
            t["groups"] = {g: [] for g in names}
            for i, team in enumerate(teams):
                t["groups"][names[i % group_count]].append(team)
            schedules = {g: round_robin(v) for g, v in t["groups"].items()}
            t["rounds"] = []
            for r in range(max(len(x) for x in schedules.values())):
                matches = []
                for g in names:
                    if r < len(schedules[g]):
                        matches.extend(make_match(a, b, r, g) for a, b in schedules[g][r])
                random.shuffle(matches)
                t["rounds"].append({"name": f"الجولة {r+1} • المجموعات", "group_stage": True, "matches": matches})
            t["current_round"] = 0
            desc = {4: "مجموعة واحدة؛ الأول والثاني إلى النهائي.",
                    8: "مجموعتان؛ الأول والثاني من كل مجموعة إلى نصف النهائي.",
                    12: "ثلاث مجموعات؛ الأول والثاني من كل مجموعة وأفضل فريقين بالمركز الثالث إلى ربع النهائي.",
                    16: "أربع مجموعات؛ الأول والثاني من كل مجموعة إلى ربع النهائي."}[n]
            desc = "تم توزيع الفرق عشوائيًا. " + desc
        await save_all(data)
        await interaction.response.send_message(embed=embed("🚀 بدأت البطولة • " + t["name"],
            desc + "\nاستخدم موجهات لعرض الجولة الحالية، ومواجهات_البطولة لتصفح كل المباريات."))

    @bot.command(name="تسجيل_نتيجة")
    async def record(ctx, team1: discord.Role = None, score: str = None, team2: discord.Role = None):
        if not ctx.guild:
            return
        if not is_admin(ctx.author):
            await ctx.send(embed=embed("🔒 صلاحيات غير كافية", "تسجيل نتائج البطولة متاح للمالك والرتبتين المصرح لهما فقط.")); return
        if team1 is None or score is None or team2 is None:
            await ctx.send(embed=embed("⚠️ صيغة النتيجة", "استخدم: تسجيل_نتيجة @الفريق1 7-6 @الفريق2")); return
        parsed = re.fullmatch(r"\s*(\d{1,2})\s*[-–:]\s*(\d{1,2})\s*", score)
        if not parsed or team1.id == team2.id:
            await ctx.send(embed=embed("⚠️ نتيجة غير صحيحة", "استخدم تسجيل_نتيجة @الفريق1 7-6 @الفريق2 مع فريقين مختلفين.")); return
        sa, sb = int(parsed.group(1)), int(parsed.group(2))
        data = await load_all(); state = state_for(data, ctx.guild.id); t = state.get("active")
        if not t or t.get("status") != "active":
            await ctx.send(embed=embed("⚠️ لا توجد بطولة جارية", "أنشئ بطولة وابدأها أولًا.")); return
        rnd = current_round(t)
        if not rnd:
            await ctx.send(embed=embed("⚠️ لا توجد جولة نشطة", "لا توجد جولة حالية.")); return
        m = next((x for x in rnd["matches"] if {int(x["team1_id"]), int(x["team2_id"])} == {team1.id, team2.id}), None)
        if not m:
            await ctx.send(embed=embed("⚠️ المواجهة غير موجودة", f"الفريقان ليسا ضمن {rnd['name']}. استخدم أمر موجهات.")); return
        if m.get("status") == "completed":
            await ctx.send(embed=embed("⚠️ النتيجة مسجلة", "هذه المواجهة تم اعتماد نتيجتها مسبقًا.")); return
        if not rnd.get("group_stage") and sa == sb:
            await ctx.send(embed=embed("⚠️ تعادل غير مسموح", "مباريات الإقصائيات تحتاج فائزًا. أدخل نتيجة الحسم بعد ركلات الترجيح.")); return
        if int(m["team1_id"]) == team1.id:
            m["score1"], m["score2"] = sa, sb
        else:
            m["score1"], m["score2"] = sb, sa
        m["status"] = "completed"; m["recorded_by"] = ctx.author.id
        m["recorded_at"] = discord.utils.utcnow().isoformat()
        if int(m["score1"]) != int(m["score2"]):
            m["winner_name"] = m["team1_name"] if int(m["score1"]) > int(m["score2"]) else m["team2_name"]
        transition = advance(t)
        if t.get("status") == "completed":
            state.setdefault("history", []).append({
                "name": t["name"], "format": t["format"], "team_count": t["team_count"],
                "champion": t["champion"], "runner_up": t["runner_up"],
                "created_at": t.get("created_at"), "completed_at": t.get("completed_at"),
                "teams": t["teams"], "rounds": t["rounds"]})
        await save_all(data)
        desc = f"{safe_name(m['team1_name'])} **{m['score1']} — {m['score2']}** {safe_name(m['team2_name'])}"
        if m.get("winner_name"):
            desc += "\n🏆 الفائز: " + safe_name(m["winner_name"])
        if transition:
            desc += "\n\n" + transition
        nxt = current_round(t)
        if nxt and t.get("status") == "active":
            desc += "\n\nالجولة الحالية: **" + nxt["name"] + "**. استخدم موجهات لعرضها."
        await ctx.send(embed=embed("✅ تم اعتماد نتيجة البطولة", desc))

    @bot.command(name="موجهات")
    async def fixtures(ctx):
        if not ctx.guild: return
        data = await load_all(); t = state_for(data, ctx.guild.id).get("active")
        if not t:
            await ctx.send(embed=embed("📭 لا توجد بطولة", "لا توجد بطولة حالية.")); return
        rnd = current_round(t)
        if not rnd:
            desc = "🏆 انتهت البطولة." if t.get("status") == "completed" else "لم تبدأ البطولة بعد."
            await ctx.send(embed=embed("📋 " + t["name"], desc)); return
        lines = [match_text(ctx.guild, m, i+1) for i, m in enumerate(rnd["matches"])]
        await ctx.send(embed=embed("📋 " + t["name"] + " • " + rnd["name"], "\n".join(lines)[:4000]))

    class MatchesView(discord.ui.View):
        def __init__(self, guild, t, user_id):
            super().__init__(timeout=300)
            self.guild = guild; self.t = t; self.user_id = user_id; self.page = 0; self.per_page = 5
            self.items = [(r["name"], m) for r in t.get("rounds", []) for m in r.get("matches", [])]
            self.max_page = max(1, (len(self.items)+self.per_page-1)//self.per_page)
            self.prev.disabled = True; self.next.disabled = self.max_page <= 1

        async def interaction_check(self, interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("🔒 الأزرار مخصصة للشخص الذي طلب عرض المواجهات.", ephemeral=True)
                return False
            return True

        def make_embed(self):
            start = self.page*self.per_page
            subset = self.items[start:start+self.per_page]
            lines = [f"**{stage}**\n{match_text(self.guild, m, start+i+1)}" for i, (stage, m) in enumerate(subset)]
            e = embed("🗂️ " + self.t["name"] + " • سجل المواجهات", "\n\n".join(lines)[:4000] or "لم تُنشأ مواجهات بعد.")
            e.set_footer(text=f"FIFA VAULT • صفحة {self.page+1}/{self.max_page} • {len(self.items)} مواجهة")
            return e

        def sync(self):
            self.prev.disabled = self.page <= 0
            self.next.disabled = self.page >= self.max_page-1

        @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.page -= 1; self.sync()
            await interaction.response.edit_message(embed=self.make_embed(), view=self)

        @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.page += 1; self.sync()
            await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @bot.command(name="مواجهات_البطولة")
    async def all_fixtures(ctx):
        if not ctx.guild: return
        data = await load_all(); t = state_for(data, ctx.guild.id).get("active")
        if not t:
            await ctx.send(embed=embed("📭 لا توجد بطولة", "لا توجد بطولة حالية.")); return
        view = MatchesView(ctx.guild, t, ctx.author.id)
        await ctx.send(embed=view.make_embed(), view=view)

    @bot.tree.command(name="سجل_الأبطال", description="عرض سجل أبطال البطولات السابقة")
    async def champions(interaction: discord.Interaction):
        if not interaction.guild:
            await reply(interaction, "⚠️ داخل السيرفر فقط", "استخدم الأمر داخل السيرفر."); return
        data, state = await get_state(interaction.guild.id)
        history = list(reversed(state.get("history", [])))
        lines = []
        for i, h in enumerate(history[:15], 1):
            champ = h.get("champion") or {}; runner = h.get("runner_up") or {}
            lines.append(f"**{i}. {safe_name(h.get('name'))}**\n🥇 البطل: **{safe_name(champ.get('name'))}**\n🥈 الوصيف: **{safe_name(runner.get('name'))}**")
        await interaction.response.send_message(embed=embed("🏆 سجل أبطال FIFA VAULT", "\n\n".join(lines) or "لا توجد بطولات منتهية بعد."))

    @bot.tree.command(name="حالة_البطولة", description="عرض حالة البطولة الحالية")
    async def status(interaction: discord.Interaction):
        if not interaction.guild:
            await reply(interaction, "⚠️ داخل السيرفر فقط", "استخدم الأمر داخل السيرفر."); return
        data, state = await get_state(interaction.guild.id); t = state.get("active")
        if not t:
            await interaction.response.send_message(embed=embed("📭 لا توجد بطولة", "أنشئ بطولة لبدء التسجيل.")); return
        rnd = current_round(t)
        status_text = {"registration": "التسجيل مفتوح", "active": "جارية", "completed": "منتهية"}.get(t["status"], "غير معروفة")
        desc = f"**{t['name']}**\nالحالة: **{status_text}**\nالفرق: **{len(t['teams'])}/{t['team_count']}**\nالنظام: **{'إقصائية' if t['format']=='knockout' else 'مجموعات + إقصائية'}**"
        if rnd: desc += "\nالجولة: **" + rnd["name"] + "**"
        if t.get("champion"): desc += "\n🏆 البطل: **" + safe_name(t["champion"]["name"]) + "**"
        await interaction.response.send_message(embed=embed("📊 حالة البطولة", desc))

    @bot.tree.command(name="إلغاء_البطولة", description="إلغاء البطولة الحالية")
    @app_commands.describe(confirm="اكتب نعم للتأكيد")
    async def cancel(interaction: discord.Interaction, confirm: str):
        if not interaction.guild or not is_admin(interaction.user):
            await reply(interaction, "🔒 صلاحيات غير كافية", "الأمر متاح للمالك والرتبتين المصرح لهما فقط."); return
        if confirm.strip() != "نعم":
            await reply(interaction, "لم يتم الإلغاء", "اكتب نعم في خانة التأكيد لإلغاء البطولة."); return
        data, state = await get_state(interaction.guild.id); t = state.get("active")
        if not t or t.get("status") == "completed":
            await reply(interaction, "⚠️ لا توجد بطولة قابلة للإلغاء", "لا توجد بطولة غير منتهية."); return
        state["active"] = None
        await save_all(data)
        await reply(interaction, "🗑️ تم إلغاء البطولة", "أُلغيَت البطولة الحالية وسجل الأبطال السابق محفوظ.")

    print("[Tournament] Tournament commands registered.")
