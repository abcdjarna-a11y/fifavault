"""FIFA VAULT security protection layer; kept separate to preserve bot.py."""
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
    return bool(me and role and not role.is_default() and not role.managed and me.top_role > role)

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
        if not isinstance(actor, discord.Member) or actor.id == guild.owner_id:
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

    async def record(guild, actor, entry, label, points, high_risk=False, is_delete=False):
        if not isinstance(actor, discord.Member) or actor.bot or entry is None:
            return
        data = await read_state()
        gs = guild_state(data, guild.id)
        entry_id = str(entry.id)
        if entry_id in gs["processed_audit_ids"]:
            return
        gs["processed_audit_ids"].append(entry_id)
        gs["processed_audit_ids"] = gs["processed_audit_ids"][-500:]
        key = str(actor.id)
        gs["scores"][key] = int(gs["scores"].get(key, 0)) + points
        stamp = now().timestamp()
        gs["events"].append({"actor_id": actor.id, "kind": label, "at": stamp, "points": points})
        gs["events"] = [e for e in gs["events"] if stamp - e.get("at", 0) <= 86400]
        emergency = bool(gs.get("nuke_enabled"))
        await write_state(data)
        if is_delete:
            key2 = (guild.id, actor.id)
            recent_deletes[key2] = [t for t in recent_deletes[key2] if stamp - t <= DELETE_WINDOW]
            recent_deletes[key2].append(stamp)
            if len(recent_deletes[key2]) >= DELETE_THRESHOLD:
                high_risk = True
                label = f"اشتباه نيوك: {len(recent_deletes[key2])} عمليات حذف خلال دقيقة"
        # In emergency mode, high-risk confirmed actions become automatic-ban incidents.
        force_ban = emergency and high_risk
        total = int(gs["scores"].get(str(actor.id), 0))
        if total >= 100 or high_risk or (emergency and points >= 50):
            await make_incident(guild, actor, label, points, force_ban=force_ban)

    async def on_channel_delete(channel):
        actor, entry = await find_actor(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
        await record(channel.guild, actor, entry, f"حذف روم: {channel.name}", 100, True, True)

    async def on_role_delete(role):
        actor, entry = await find_actor(role.guild, discord.AuditLogAction.role_delete, role.id)
        await record(role.guild, actor, entry, f"حذف رتبة: {role.name}", 100, True, True)

    async def on_channel_create(channel):
        actor, entry = await find_actor(channel.guild, discord.AuditLogAction.channel_create, channel.id)
        await record(channel.guild, actor, entry, f"إنشاء روم: {channel.name}", 50)

    async def on_role_create(role):
        actor, entry = await find_actor(role.guild, discord.AuditLogAction.role_create, role.id)
        await record(role.guild, actor, entry, f"إنشاء رتبة: {role.name}", 50, role.permissions.administrator)

    async def on_role_update(before, after):
        if before.permissions == after.permissions:
            return
        actor, entry = await find_actor(after.guild, discord.AuditLogAction.role_update, after.id)
        dangerous = after.permissions.administrator and not before.permissions.administrator
        await record(after.guild, actor, entry, f"تعديل صلاحيات رتبة: {after.name}", 100 if dangerous else 50, dangerous)

    async def on_member_update(before, after):
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
            if perms.administrator or perms.create_instant_invite:
                gs["role_permissions_backup"][str(role.id)] = int(perms.value)
                perms.administrator = False
                perms.create_instant_invite = False
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
        for role_id, raw in list(gs.get("role_permissions_backup", {}).items()):
            role = guild.get_role(int(role_id))
            if not role or not manageable(guild, role):
                failures += 1
                continue
            try:
                await role.edit(permissions=discord.Permissions(int(raw)), reason=f"/unnuke by owner {interaction.user.id}")
                restored += 1
            except (discord.Forbidden, discord.HTTPException):
                failures += 1
        gs["nuke_enabled"] = False
        gs["nuke_ended_at"] = now().isoformat()
        gs["role_permissions_backup"] = {}
        await write_state(data)
        await send_alert(guild, discord.Embed(title="🟢 انتهى وضع الطوارئ",
            description=f"تمت استعادة {restored} رتبة؛ تعذر استعادة {failures}.", color=discord.Color.green(), timestamp=now()))
        await interaction.followup.send(f"تم إيقاف الطوارئ. تمت استعادة {restored} رتبة؛ تعذر استعادة {failures}.", ephemeral=True)

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
