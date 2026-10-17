import asyncio
import datetime
import json
import os
import re
import discord
from discord import app_commands
from discord.ext import commands

LEAGUE_FILE = "league_data.json"
LEAGUE_COLOR = 0xF5D451
PINK_COLOR = 0xFF9ED2
LEAGUE_OPERATOR_ROLE_ID = 1550882056408666132


async def load_data():
    def read():
        try:
            with open(LEAGUE_FILE, "r", encoding="utf-8") as stream:
                data = json.load(stream)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}
    return await asyncio.to_thread(read)


async def save_data(data):
    def write():
        temp = LEAGUE_FILE + ".tmp"
        with open(temp, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.replace(temp, LEAGUE_FILE)
    await asyncio.to_thread(write)


def guild_data(data, guild_id):
    return data.setdefault(str(guild_id), {"teams": [], "matches": [], "next_team_id": 1})


def team_for_role(state, role_id):
    return next((t for t in state.get("teams", []) if int(t.get("role_id", 0)) == int(role_id)), None)


def team_name(guild, team):
    role = guild.get_role(int(team.get("role_id", 0)))
    return role.name if role else str(team.get("name") or "فريق محذوف")


def stats_for(state):
    active_ids = {int(t["team_id"]) for t in state.get("teams", [])}
    stats = {tid: {"played": 0, "wins": 0, "draws": 0, "losses": 0, "gf": 0, "ga": 0, "points": 0} for tid in active_ids}
    for match in state.get("matches", []):
        try:
            a, b = int(match["team1_id"]), int(match["team2_id"])
            sa, sb = int(match["score1"]), int(match["score2"])
        except (KeyError, TypeError, ValueError):
            continue
        # Historical matches remain visible, but deleted teams no longer affect the table.
        if a not in active_ids or b not in active_ids:
            continue
        x, y = stats[a], stats[b]
        x["played"] += 1
        y["played"] += 1
        x["gf"] += sa
        x["ga"] += sb
        y["gf"] += sb
        y["ga"] += sa
        if sa > sb:
            x["wins"] += 1
            x["points"] += 3
            y["losses"] += 1
        elif sb > sa:
            y["wins"] += 1
            y["points"] += 3
            x["losses"] += 1
        else:
            x["draws"] += 1
            y["draws"] += 1
            x["points"] += 1
            y["points"] += 1
    return stats


def base_embed(title, description=None):
    embed = discord.Embed(title=title, description=description, color=discord.Color(LEAGUE_COLOR), timestamp=discord.utils.utcnow())
    embed.set_footer(text="🏆 FIFA VAULT • OFFICIAL LEAGUE SYSTEM")
    return embed


async def setup_league(bot, owner_id, owner_role_ids):
    owner_roles = set(owner_role_ids) | {1550882056408666132, 1555096604954857503}

    def is_owner_admin(member):
        return getattr(member, "id", None) == owner_id or bool(
            {r.id for r in getattr(member, "roles", [])} & owner_roles
        )

    def can_add_score(member):
        return is_owner_admin(member) or any(
            getattr(r, "id", None) == LEAGUE_OPERATOR_ROLE_ID
            for r in getattr(member, "roles", [])
        )

    def add_role(state, role):
        old = team_for_role(state, role.id)
        if old:
            return False, old
        number = int(state.get("next_team_id", 1))
        state["next_team_id"] = number + 1
        team = {"team_id": number, "role_id": role.id, "name": role.name, "created_at": discord.utils.utcnow().isoformat()}
        state.setdefault("teams", []).append(team)
        return True, team

    async def send_admin(interaction, title, description):
        await interaction.response.send_message(embed=base_embed(title, description), ephemeral=True)

    @bot.command(name="جدول")
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def league_table(ctx):
        if ctx.guild is None:
            return
        data = await load_data()
        state = guild_data(data, ctx.guild.id)
        stats = stats_for(state)
        teams = list(state.get("teams", []))
        teams.sort(key=lambda t: (-stats[int(t["team_id"])]["points"],
                                  -(stats[int(t["team_id"])]["gf"] - stats[int(t["team_id"])]["ga"]),
                                  -stats[int(t["team_id"])]["gf"], int(t["team_id"])))
        embed = base_embed("🏆・**__جدول الترتيب • FIFA VAULT__**")
        if not teams:
            embed.description = "━━━━━━━━━━━━━━━━━━━━\n📭 **__لا توجد فرق مسجلة حتى الآن__**\n\nتستطيع الإدارة إضافة الفرق من أوامر الدوري.\n━━━━━━━━━━━━━━━━━━━━"
            await ctx.send(embed=embed)
            return
        lines = ["**__TEAM__**　│　**__POINTS__**　│　**__MATCHES__**　│　**__GOALS FOR / AGAINST__**",
                 "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        for position, team in enumerate(teams[:30], start=1):
            s = stats[int(team["team_id"])]
            name = discord.utils.escape_markdown(team_name(ctx.guild, team)).replace("|", "¦")
            gd = s["gf"] - s["ga"]
            lines.append(f"{medals.get(position, '🏅')} **__#{team['team_id']} {name}__**\n　🟡 **{s['points']} pts**　│　⚽ {s['wins']}W {s['draws']}D {s['losses']}L　│　🥅 {s['gf']}:{s['ga']} ({gd:+d})")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
        if len(teams) > 30:
            lines.append(f"… وهناك **{len(teams) - 30}** فريقًا إضافيًا.")
        embed.description = ("📊 **__POINTS　 MATCHES　 GOALS FOR / AGAINST__**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines))[:4000]
        embed.add_field(name="📘 **__طريقة الترتيب__**", value="النقاط أولًا، ثم فارق الأهداف، ثم الأهداف المسجلة. **رقم # الفريق ثابت ولا يمثل مركزه الحالي.**", inline=False)
        embed.set_footer(text=f"🏆 FIFA VAULT • {len(teams)} TEAMS • W=فوز | D=تعادل | L=خسارة")
        await ctx.send(embed=embed)

    @bot.command(name="نتيجة")
    async def league_result(ctx, team1: discord.Role = None, score: str = None, team2: discord.Role = None):
        if ctx.guild is None:
            return
        if not can_add_score(ctx.author):
            await ctx.send(embed=base_embed("🔒・**__صلاحيات غير كافية__**", "هذا الأمر مخصص للأونرات المصرح لهم ورتبة إدارة الدوري."))
            return
        if team1 is None or score is None or team2 is None:
            await ctx.send(embed=base_embed("⚠️・**__صيغة النتيجة__**", "استخدم: **__نتيجة @الفريق1 6-0 @الفريق2__**"))
            return
        parsed = re.fullmatch(r"\s*(\d{1,2})\s*[-–:]\s*(\d{1,2})\s*", score)
        if not parsed:
            await ctx.send(embed=base_embed("⚠️・**__نتيجة غير صحيحة__**", "استخدم الصيغة: **__نتيجة @الفريق1 6-0 @الفريق2__**"))
            return
        sa, sb = int(parsed.group(1)), int(parsed.group(2))
        if team1.id == team2.id:
            await ctx.send(embed=base_embed("⚠️・**__الفريق نفسه__**", "منشن رتبتين مختلفتين للفريقين."))
            return
        data = await load_data()
        state = guild_data(data, ctx.guild.id)
        a, b = team_for_role(state, team1.id), team_for_role(state, team2.id)
        if not a or not b:
            missing = team1.name if not a else team2.name
            await ctx.send(embed=base_embed("⚠️・**__فريق غير مسجل__**", f"الفريق **{discord.utils.escape_markdown(missing)}** غير مسجل في الدوري."))
            return
        match = {"match_id": len(state.setdefault("matches", [])) + 1,
                 "team1_id": int(a["team_id"]), "team2_id": int(b["team_id"]),
                 "team1_role_id": team1.id, "team2_role_id": team2.id,
                 "team1_name": team1.name, "team2_name": team2.name,
                 "score1": sa, "score2": sb, "recorded_by": ctx.author.id,
                 "recorded_at": discord.utils.utcnow().isoformat()}
        state["matches"].append(match)
        await save_data(data)
        first = discord.utils.escape_markdown(team1.name)
        second = discord.utils.escape_markdown(team2.name)
        if sa > sb:
            outcome, pa, pb = f"🏆 **__الفائز: {first}__**", 3, 0
        elif sb > sa:
            outcome, pa, pb = f"🏆 **__الفائز: {second}__**", 0, 3
        else:
            outcome, pa, pb = "🤝 **__انتهت المباراة بالتعادل__**", 1, 1
        embed = base_embed("⚽・**__تم اعتماد نتيجة المباراة__**",
            f"**__{first}__**　**{sa} — {sb}**　**__{second}__**\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🥅 **الأهداف:** {first} سجل {sa} • {second} سجل {sb}\n"
            f"📈 **النقاط:** {first} **+{pa}**　│　{second} **+{pb}**\n\n{outcome}\n"
            "✅ تم تحديث جدول الترتيب والإحصائيات تلقائيًا.")
        embed.add_field(name="🧾 **__تفاصيل التسجيل__**", value=f"👤 المسؤول: {ctx.author.mention}\n🕒 <t:{int(discord.utils.utcnow().timestamp())}:R>", inline=False)
        embed.set_footer(text="🏆 FIFA VAULT • MATCH CENTER")
        await ctx.send(embed=embed)

    @bot.command(name="نتائج", aliases=["نتايج"])
    async def league_recent_results(ctx):
        if ctx.guild is None:
            return
        data = await load_data()
        state = guild_data(data, ctx.guild.id)
        matches = list(reversed(state.get("matches", [])))[:5]
        embed = base_embed("⚽・**__آخر 5 نتائج • FIFA VAULT__**")
        if not matches:
            embed.description = "━━━━━━━━━━━━━━━━━━━━\n📭 **__لا توجد مباريات مسجلة حتى الآن__**\n━━━━━━━━━━━━━━━━━━━━"
        else:
            lines = []
            for i, m in enumerate(matches, start=1):
                a = discord.utils.escape_markdown(str(m.get("team1_name", "فريق محذوف")))
                b = discord.utils.escape_markdown(str(m.get("team2_name", "فريق محذوف")))
                sa, sb = int(m.get("score1", 0)), int(m.get("score2", 0))
                outcome = f"🏆 فوز **{a}**" if sa > sb else f"🏆 فوز **{b}**" if sb > sa else "🤝 تعادل"
                lines.append(f"**__{i}. {a}　{sa} — {sb}　{b}__**\n　{outcome}　•　👤 <@{m.get('recorded_by')}>\n━━━━━━━━━━━━━━━━━━━━")
            embed.description = "\n".join(lines)[:4000]
        embed.set_footer(text="FIFA VAULT • MATCH HISTORY • الأحدث أولًا")
        await ctx.send(embed=embed)

    @bot.tree.command(name="اضافة_الفرق", description="إضافة رتبة نادي إلى جدول الدوري")
    @app_commands.describe(team_role="اختر رتبة النادي التي تريد تسجيلها")
    async def add_team(interaction: discord.Interaction, team_role: discord.Role):
        if interaction.guild is None:
            await send_admin(interaction, "⚠️・**__هذا الأمر داخل السيرفر فقط__**", "افتح الأمر من داخل السيرفر.")
            return
        if not can_add_score(interaction.user):
            await send_admin(interaction, "🔒・**__صلاحيات غير كافية__**", "هذا الأمر مخصص للإدارة المصرح لها بإضافة الفرق.")
            return
        data = await load_data()
        state = guild_data(data, interaction.guild.id)
        added, team = add_role(state, team_role)
        if not added:
            await send_admin(interaction, "⚠️・**__الفريق مسجل مسبقًا__**", f"رتبة {team_role.mention} مسجلة بالمعرّف الثابت **#{team['team_id']}**.")
            return
        await save_data(data)
        await send_admin(interaction, "🛡️・**__تم تسجيل فريق جديد__**", f"━━━━━━━━━━━━━━━━━━━━\n🎽 **الفريق:** {team_role.mention}\n🔢 **المعرّف الثابت:** **#{team['team_id']}**\n📊 جاهز لتسجيل المباريات\n━━━━━━━━━━━━━━━━━━━━")

    @bot.tree.command(name="إزالة_فريق", description="إزالة فريق من الجدول مع الاحتفاظ بسجل مبارياته")
    @app_commands.describe(team_role="اختر رتبة الفريق الذي تريد إزالته")
    async def remove_team(interaction: discord.Interaction, team_role: discord.Role):
        if interaction.guild is None:
            await send_admin(interaction, "⚠️・**__هذا الأمر داخل السيرفر فقط__**", "افتح الأمر من داخل السيرفر.")
            return
        if not is_owner_admin(interaction.user):
            await send_admin(interaction, "🔒・**__صلاحيات غير كافية__**", "إزالة الفرق متاحة للأونرات المصرح لهم فقط.")
            return
        data = await load_data()
        state = guild_data(data, interaction.guild.id)
        team = team_for_role(state, team_role.id)
        if not team:
            await send_admin(interaction, "⚠️・**__الفريق غير مسجل__**", f"رتبة {team_role.mention} ليست ضمن فرق الدوري الحالية.")
            return
        state["teams"] = [t for t in state.get("teams", []) if int(t["team_id"]) != int(team["team_id"])]
        await save_data(data)
        await send_admin(interaction, "🗑️・**__تمت إزالة الفريق__**", f"━━━━━━━━━━━━━━━━━━━━\n🎽 **الفريق:** {discord.utils.escape_markdown(team_role.name)} (#{team['team_id']})\n✅ أُزيل من الجدول الحالي.\n🗂️ سجل مبارياته السابقة محفوظ ولن يؤثر في النقاط الحالية.\n━━━━━━━━━━━━━━━━━━━━")

    class ResetView(discord.ui.View):
        def __init__(self, guild_id):
            super().__init__(timeout=60)
            self.guild_id = int(guild_id)

        async def interaction_check(self, interaction):
            if interaction.guild_id != self.guild_id or not is_owner_admin(interaction.user):
                await interaction.response.send_message("🔒 هذا التأكيد مخصص للأونرات المصرح لهم داخل السيرفر نفسه.", ephemeral=True)
                return False
            return True

        @discord.ui.button(label="تأكيد التصفير", emoji="⚠️", style=discord.ButtonStyle.danger)
        async def confirm(self, interaction, button):
            data = await load_data()
            data[str(self.guild_id)] = {"teams": [], "matches": [], "next_team_id": 1}
            await save_data(data)
            self.stop()
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(embed=base_embed("✅・**__تم تصفير الدوري بالكامل__**", "🗑️ تمت إزالة جميع الفرق والنتائج والإحصائيات.\n🔢 سيبدأ الترقيم من #1 عند إضافة الفرق من جديد."), view=self)

        @discord.ui.button(label="إلغاء", emoji="✖️", style=discord.ButtonStyle.secondary)
        async def cancel(self, interaction, button):
            self.stop()
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(embed=base_embed("↩️・**__تم إلغاء التصفير__**", "لم يتم تغيير أي بيانات في الدوري."), view=self)

    @bot.tree.command(name="reset_league", description="تصفير الدوري بالكامل بعد تأكيد الأونرات")
    async def reset_league(interaction: discord.Interaction):
        if interaction.guild is None:
            await send_admin(interaction, "⚠️・**__هذا الأمر داخل السيرفر فقط__**", "افتح الأمر من داخل السيرفر.")
            return
        if not is_owner_admin(interaction.user):
            await send_admin(interaction, "🔒・**__صلاحيات غير كافية__**", "تصفير الدوري متاح للأونرات المصرح لهم فقط.")
            return
        await interaction.response.send_message(
            embed=base_embed("⚠️・**__تأكيد تصفير الدوري__**", "━━━━━━━━━━━━━━━━━━━━\nسيتم حذف جميع الفرق والنتائج والإحصائيات.\n\n**__لا يمكن التراجع بعد التأكيد.__**\n━━━━━━━━━━━━━━━━━━━━"),
            view=ResetView(interaction.guild.id), ephemeral=True
        )

    @bot.tree.command(name="اضافة_افرقة", description="إضافة ما يصل إلى 10 فرق دفعة واحدة")
    @app_commands.describe(
        team1="الفريق الأول (اختياري)", team2="الفريق الثاني (اختياري)",
        team3="الفريق الثالث (اختياري)", team4="الفريق الرابع (اختياري)",
        team5="الفريق الخامس (اختياري)", team6="الفريق السادس (اختياري)",
        team7="الفريق السابع (اختياري)", team8="الفريق الثامن (اختياري)",
        team9="الفريق التاسع (اختياري)", team10="الفريق العاشر (اختياري)"
    )
    async def add_many(interaction: discord.Interaction, team1: discord.Role = None, team2: discord.Role = None,
                       team3: discord.Role = None, team4: discord.Role = None, team5: discord.Role = None,
                       team6: discord.Role = None, team7: discord.Role = None, team8: discord.Role = None,
                       team9: discord.Role = None, team10: discord.Role = None):
        if interaction.guild is None:
            await send_admin(interaction, "⚠️・**__هذا الأمر داخل السيرفر فقط__**", "افتح الأمر من داخل السيرفر.")
            return
        if not can_add_score(interaction.user):
            await send_admin(interaction, "🔒・**__صلاحيات غير كافية__**", "إضافة الفرق متاحة للإدارة المصرح لها فقط.")
            return
        roles = [r for r in (team1, team2, team3, team4, team5, team6, team7, team8, team9, team10) if r]
        if not roles:
            await send_admin(interaction, "⚠️・**__لم تختر أي فرق__**", "اختر رتبة واحدة على الأقل.")
            return
        data = await load_data()
        state = guild_data(data, interaction.guild.id)
        added, skipped, seen = [], [], set()
        for role in roles:
            if role.id in seen:
                skipped.append(f"↪️ {role.mention} — مكرر في الطلب")
                continue
            seen.add(role.id)
            ok, team = add_role(state, role)
            if ok:
                added.append(f"✅ **#{team['team_id']}** — {role.mention}")
            else:
                skipped.append(f"↪️ {role.mention} — مسجل مسبقًا (#{team['team_id']})")
        await save_data(data)
        description = ("━━━━━━━━━━━━━━━━━━━━\n🟢 **__تمت الإضافة: " + str(len(added)) + "__**\n" +
                       ("\n".join(added) if added else "لا توجد فرق جديدة.") +
                       "\n\n🟡 **__تم التجاوز: " + str(len(skipped)) + "__**\n" +
                       ("\n".join(skipped) if skipped else "لا توجد فرق متجاوزة.") + "\n━━━━━━━━━━━━━━━━━━━━")
        await send_admin(interaction, "📋・**__إضافة عدة فرق__**", description[:4000])

    print("[League] Prefix and slash commands registered.")
