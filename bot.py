#!/usr/bin/env python3
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import sys
import io
from datetime import datetime, timezone, timedelta
from typing import List, Dict

# ========== إصلاح مشكلة audioop في Python 3.13 ==========
os.environ["DISCORD_INSTANCE_NO_VOICE"] = "true"
try:
    import audioop
except ImportError:
    try:
        import audioop_lts as audioop
        print("✅ تم استخدام audioop-lts كبديل.")
    except ImportError:
        print("⚠️ audioop غير متاح، سيتم تعطيل ميزات الصوت.")

# ========== متغيرات البيئة ==========
TOKEN = os.getenv("DISCORD_TOKEN")
ALLOWED_GUILD_ID = int(os.getenv("ALLOWED_GUILD_ID", "0"))

if not TOKEN:
    print("❌ DISCORD_TOKEN غير موجود", file=sys.stderr)
    sys.exit(1)
if ALLOWED_GUILD_ID == 0:
    print("❌ ALLOWED_GUILD_ID غير موجود", file=sys.stderr)
    sys.exit(1)

# ========== إعداد النوايا ==========
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ========== هوية البوت ==========
BOT_NAME      = "Protocol Zero"
BOT_VER       = "v2.0"
BOT_IMAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.jpg")

# ── تحميل صورة البوت في الذاكرة عند التشغيل ──
_bot_img: bytes | None = None

def _load_bot_image() -> None:
    global _bot_img
    try:
        with open(BOT_IMAGE_PATH, "rb") as f:
            _bot_img = f.read()
        print(f"✅ صورة البوت محملة ({len(_bot_img):,} bytes)")
    except FileNotFoundError:
        print(f"⚠️ bot.jpg غير موجودة في: {BOT_IMAGE_PATH}")
    except Exception as ex:
        print(f"⚠️ فشل تحميل bot.jpg: {ex}")

def bot_file() -> discord.File | None:
    """يُرجع discord.File جديد من الذاكرة في كل مرة (مطلوب لأن ديسكورد يقرأه مرة واحدة)"""
    if _bot_img is None:
        return None
    return discord.File(io.BytesIO(_bot_img), filename="bot.jpg")

# ========== نظام الألوان الموحّد ==========
class C:
    SUCCESS = 0x57F287   # أخضر
    ERROR   = 0xED4245   # أحمر
    WARNING = 0xFEE75C   # أصفر
    INFO    = 0x5865F2   # أزرق بنفسجي
    NUKE    = 0xFF2222   # أحمر ناري
    SAVE    = 0x00B0F4   # أزرق فاتح
    PURGE   = 0xEB459E   # وردي

# ========== دوال Embed المساعدة ==========

def _footer() -> str:
    return f"⚡ {BOT_NAME} {BOT_VER}"

def _ts() -> datetime:
    return datetime.utcnow()

def _apply_thumbnail(e: discord.Embed) -> discord.Embed:
    if _bot_img is not None:
        e.set_thumbnail(url="attachment://bot.jpg")
    return e

def embed_success(title: str, desc: str = "", fields: list = None) -> discord.Embed:
    e = discord.Embed(title=f"✅  {title}", description=desc, color=C.SUCCESS, timestamp=_ts())
    if fields:
        for name, value, inline in fields:
            e.add_field(name=name, value=value, inline=inline)
    e.set_footer(text=_footer())
    return _apply_thumbnail(e)

def embed_error(title: str, desc: str = "") -> discord.Embed:
    e = discord.Embed(title=f"❌  {title}", description=desc, color=C.ERROR, timestamp=_ts())
    e.set_footer(text=_footer())
    return _apply_thumbnail(e)

def embed_warning(title: str, desc: str = "") -> discord.Embed:
    e = discord.Embed(title=f"⚠️  {title}", description=desc, color=C.WARNING, timestamp=_ts())
    e.set_footer(text=_footer())
    return _apply_thumbnail(e)

def embed_info(title: str, desc: str = "", color: int = C.INFO, fields: list = None) -> discord.Embed:
    e = discord.Embed(title=title, description=desc, color=color, timestamp=_ts())
    if fields:
        for name, value, inline in fields:
            e.add_field(name=name, value=value, inline=inline)
    e.set_footer(text=_footer())
    return _apply_thumbnail(e)

def progress_bar(current: int, total: int, length: int = 14) -> str:
    """يولّد شريط تقدم مرئي  ████████░░░░ 65%"""
    if total == 0:
        return f"`{'░' * length}` 0%"
    filled  = int(length * current / total)
    bar     = "█" * filled + "░" * (length - filled)
    percent = int(100 * current / total)
    return f"`{bar}` **{percent}%**"

def _files() -> dict:
    """kwargs مناسبة لـ send() — تضيف الصورة إذا كانت محملة"""
    f = bot_file()
    return {"file": f} if f else {}

def _atts() -> dict:
    """kwargs مناسبة لـ edit_original_response() / message.edit()"""
    f = bot_file()
    return {"attachments": [f]} if f else {}

# ========== توليد HTML بشكل واجهة ديسكورد ==========

def generate_html(messages: List[Dict], channel_name: str, guild_name: str = "") -> str:
    AVATAR_COLORS = [
        "#5865F2","#57F287","#FEE75C","#EB459E",
        "#ED4245","#00B0F4","#FF7B00","#9B59B6"
    ]

    def avatar_color(name: str) -> str:
        return AVATAR_COLORS[sum(ord(c) for c in name) % len(AVATAR_COLORS)]

    def initials(name: str) -> str:
        parts = name.split()
        return (parts[0][0] + parts[1][0]).upper() if len(parts) >= 2 else name[:2].upper()

    def safe(text: str) -> str:
        return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))

    body_html = ""
    prev_author = None

    for m in messages:
        is_new = m["author"] != prev_author
        prev_author = m["author"]
        color = avatar_color(m["author"])
        init  = initials(m["author"])
        text  = safe(m["content"])
        time_full  = m["time"]
        time_short = m["time"][11:16]       # HH:MM

        if is_new:
            body_html += f"""
      <div class="grp">
        <div class="av" style="background:{color}" title="{safe(m['author'])}">{init}</div>
        <div class="grp-body">
          <div class="grp-head">
            <span class="uname" style="color:{color}">{safe(m['author'])}</span>
            <span class="ts" title="{time_full}">{time_full}</span>
          </div>
          <div class="line">{text}</div>
        </div>
      </div>"""
        else:
            body_html += f"""
      <div class="cont">
        <span class="ts-s" title="{time_full}">{time_short}</span>
        <div class="line">{text}</div>
      </div>"""

    total_msgs = len(messages)
    generated  = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>#{channel_name} · {guild_name}</title>
  <style>
    /* ─── Reset ─── */
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    /* ─── Root ─── */
    :root{{
      --bg0:#1e1f22; --bg1:#2b2d31; --bg2:#313338;
      --text:#dbdee1; --muted:#80848e; --border:#3f4147;
      --accent:#5865f2; --green:#57f287; --pink:#eb459e;
    }}
    html{{scroll-behavior:smooth}}
    body{{background:var(--bg0);color:var(--text);
          font-family:'Segoe UI',system-ui,sans-serif;font-size:15px;line-height:1.55}}

    /* ─── Top bar ─── */
    .topbar{{
      position:sticky;top:0;z-index:100;
      background:var(--bg1);border-bottom:1px solid var(--border);
      display:flex;align-items:center;gap:12px;padding:14px 24px;
    }}
    .topbar-hash{{color:var(--muted);font-size:22px;font-weight:700;line-height:1}}
    .topbar-name{{font-weight:700;font-size:16px;color:#f2f3f5}}
    .topbar-sep{{width:1px;height:20px;background:var(--border);margin:0 4px}}
    .topbar-guild{{color:var(--muted);font-size:13px}}
    .topbar-badge{{
      margin-left:auto;background:var(--accent);color:#fff;
      font-size:11px;font-weight:700;padding:3px 10px;border-radius:12px;
      letter-spacing:.4px;text-transform:uppercase;
    }}

    /* ─── Banner ─── */
    .banner{{
      background:linear-gradient(135deg,#5865F2 0%,#EB459E 60%,#FEE75C 100%);
      padding:10px 24px;font-size:12px;color:rgba(255,255,255,.9);
      display:flex;justify-content:space-between;align-items:center;
      font-weight:600;letter-spacing:.3px;
    }}
    .banner span{{opacity:.75}}

    /* ─── Stats bar ─── */
    .stats{{
      background:var(--bg1);border-bottom:1px solid var(--border);
      display:flex;gap:24px;padding:10px 24px;font-size:12px;color:var(--muted);
    }}
    .stat-item strong{{color:var(--text);font-size:14px;display:block}}

    /* ─── Scroll ─── */
    .scroller{{max-width:900px;margin:0 auto;padding:16px 12px 40px}}

    /* ─── Message group ─── */
    .grp{{
      display:flex;gap:16px;padding:6px 12px;
      border-radius:6px;margin-top:18px;transition:background .1s;
    }}
    .grp:hover{{background:var(--bg2)}}

    /* ─── Avatar ─── */
    .av{{
      width:40px;height:40px;border-radius:50%;flex-shrink:0;
      display:flex;align-items:center;justify-content:center;
      font-size:13px;font-weight:800;color:#fff;margin-top:2px;
      cursor:default;user-select:none;
    }}

    /* ─── Group body ─── */
    .grp-body{{flex:1;min-width:0}}
    .grp-head{{display:flex;align-items:baseline;gap:8px;margin-bottom:3px}}
    .uname{{font-weight:700;font-size:15px}}
    .ts{{color:var(--muted);font-size:11px}}

    /* ─── Continuation ─── */
    .cont{{
      display:flex;gap:8px;padding:2px 12px 2px 68px;
      border-radius:6px;transition:background .1s;
    }}
    .cont:hover{{background:var(--bg2)}}
    .ts-s{{color:var(--muted);font-size:10px;min-width:38px;padding-top:4px;flex-shrink:0}}

    /* ─── Message text ─── */
    .line{{color:var(--text);word-break:break-word;white-space:pre-wrap}}
    .line:empty::after{{content:"[media]";color:var(--muted);font-style:italic}}

    /* ─── Footer ─── */
    .foot{{
      text-align:center;padding:28px;color:var(--muted);font-size:12px;
      border-top:1px solid var(--border);margin-top:24px;
    }}
    .foot strong{{color:var(--accent)}}

    /* ─── Scrollbar ─── */
    ::-webkit-scrollbar{{width:8px}}
    ::-webkit-scrollbar-track{{background:var(--bg0)}}
    ::-webkit-scrollbar-thumb{{background:var(--border);border-radius:4px}}
    ::-webkit-scrollbar-thumb:hover{{background:#5a5d65}}
  </style>
</head>
<body>

<!-- Top Bar -->
<div class="topbar">
  <span class="topbar-hash">#</span>
  <span class="topbar-name">{channel_name}</span>
  <div class="topbar-sep"></div>
  <span class="topbar-guild">{guild_name}</span>
  <span class="topbar-badge">⚡ Protocol Zero Archive</span>
</div>

<!-- Banner -->
<div class="banner">
  <span>⚡ Protocol Zero · Channel Archive</span>
  <span>Generated: {generated}</span>
</div>

<!-- Stats -->
<div class="stats">
  <div class="stat-item"><strong>{total_msgs:,}</strong>messages archived</div>
  <div class="stat-item"><strong>#{channel_name}</strong>channel</div>
  <div class="stat-item"><strong>{guild_name}</strong>server</div>
</div>

<!-- Messages -->
<div class="scroller">
{body_html}
</div>

<!-- Footer -->
<div class="foot">
  <strong>Protocol Zero</strong> {BOT_VER} &nbsp;·&nbsp;
  Archive of <strong>#{channel_name}</strong> &nbsp;·&nbsp;
  {total_msgs:,} messages &nbsp;·&nbsp; {generated}
</div>

</body>
</html>"""

# ========== الأحداث ==========

@bot.event
async def on_ready():
    _load_bot_image()
    print(f"✅ {BOT_NAME} شغال: {bot.user}")
    print(f"🚀 متصل بـ {len(bot.guilds)} سيرفر")
    target = discord.utils.get(bot.guilds, id=ALLOWED_GUILD_ID)
    if target:
        print(f"✅ السيرفر المخصص: {target.name}")
    else:
        print(f"⚠️ السيرفر {ALLOWED_GUILD_ID} غير موجود")

@bot.event
async def on_guild_join(guild):
    if guild.id != ALLOWED_GUILD_ID:
        await guild.leave()
        print(f"🚫 غادرت {guild.name} (غير مصرح)")

# ========== أوامر الإدارة ==========

@bot.command(name="clear")
@commands.has_permissions(administrator=True)
async def clear_commands(ctx):
    await ctx.send(embed=embed_info("🗑️  مسح الأوامر", "جاري مسح كل الأوامر المكررة..."), **_files())
    try:
        guild = discord.Object(id=ctx.guild.id)
        bot.tree.clear_commands(guild=guild)
        await bot.tree.sync(guild=guild)
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()
        await ctx.send(embed=embed_success(
            "تم المسح",
            "كل الأوامر حُذفت.\nاكتب `!sync` لتسجيلها من جديد."
        ), **_files())
    except Exception as e:
        await ctx.send(embed=embed_error("فشل المسح", str(e)), **_files())

@bot.command(name="sync")
@commands.has_permissions(administrator=True)
async def sync_commands(ctx):
    await ctx.send(embed=embed_info("🔄  مزامنة", "جاري تسجيل الأوامر..."), **_files())
    try:
        guild = discord.Object(id=ctx.guild.id)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        names  = ", ".join(f"`/{c.name}`" for c in synced)
        await ctx.send(embed=embed_success(
            f"تم تسجيل {len(synced)} أمر",
            f"{names}\n\nأعد تشغيل ديسكورد إذا ما ظهرت."
        ), **_files())
    except Exception as e:
        await ctx.send(embed=embed_error("فشل المزامنة", str(e)), **_files())

# ========== الأوامر المائلة ==========

# ─────────────── /save ───────────────
@bot.tree.command(name="save", description="أرشفة الروم الحالي كملف HTML")
async def slash_save(interaction: discord.Interaction):
    if interaction.guild.id != ALLOWED_GUILD_ID:
        return await interaction.response.send_message(
            embed=embed_error("غير مصرح"), ephemeral=True, **_files()
        )

    await interaction.response.defer(thinking=True)

    # ── مرحلة الجمع ──
    e = embed_info(
        "💾  جاري الأرشفة",
        f"**الروم:** `#{interaction.channel.name}`\n\n"
        f"{progress_bar(0, 1)}\n`جاري جمع الرسائل...`",
        color=C.SAVE
    )
    await interaction.edit_original_response(embed=e, **_atts())

    msgs = []
    async for msg in interaction.channel.history(limit=None):
        msgs.append({
            'author':  msg.author.display_name,
            'content': msg.clean_content or "[وسائط]",
            'time':    msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
        if len(msgs) % 500 == 0:
            e.description = (
                f"**الروم:** `#{interaction.channel.name}`\n\n"
                f"{progress_bar(len(msgs), len(msgs) + 1)}\n"
                f"`جُمعت {len(msgs):,} رسالة...`"
            )
            await interaction.edit_original_response(embed=e, **_atts())

    # ── مرحلة توليد HTML ──
    total = len(msgs)
    e.description = (
        f"**الروم:** `#{interaction.channel.name}`\n\n"
        f"{progress_bar(1, 2)}\n`توليد ملف HTML...`"
    )
    await interaction.edit_original_response(embed=e, **_atts())

    html = generate_html(msgs, interaction.channel.name, interaction.guild.name)
    fn   = f"/tmp/pz_archive_{interaction.channel.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(fn, 'w', encoding='utf-8') as f:
        f.write(html)

    # ── مرحلة الإرسال ──
    e.description = (
        f"**الروم:** `#{interaction.channel.name}`\n\n"
        f"{progress_bar(2, 2)}\n`إرسال الملف...`"
    )
    await interaction.edit_original_response(embed=e, **_atts())

    try:
        await interaction.user.send(file=discord.File(fn))
        await interaction.edit_original_response(embed=embed_success(
            "أرشفة مكتملة",
            f"تم إرسال الملف إلى رسائلك الخاصة.",
            fields=[
                ("📁 الروم",   f"`#{interaction.channel.name}`",  True),
                ("💬 الرسائل", f"`{total:,}`",                    True),
                ("📩 الوجهة",  "رسائلك الخاصة",                   True),
            ]
        ), **_atts())
    except discord.Forbidden:
        await interaction.edit_original_response(embed=embed_error(
            "فشل الإرسال",
            "تأكد أن رسائلك الخاصة مفتوحة ثم حاول مجدداً."
        ), **_atts())
    except Exception as ex:
        await interaction.edit_original_response(embed=embed_error("خطأ", str(ex)[:300]), **_atts())
    finally:
        if os.path.exists(fn):
            os.remove(fn)

# ─────────────── /purge ───────────────
@bot.tree.command(name="purge", description="مسح رسائل من الروم الحالي")
@app_commands.describe(limit="العدد (1 - 2000)")
async def slash_purge(interaction: discord.Interaction, limit: int = 100):
    if interaction.guild.id != ALLOWED_GUILD_ID:
        return await interaction.response.send_message(
            embed=embed_error("غير مصرح"), ephemeral=True, **_files()
        )

    limit = min(max(1, limit), 2000)
    await interaction.response.defer(thinking=True)

    e = embed_info(
        "🧹  تنظيف",
        f"**الروم:** `#{interaction.channel.name}`\n\n"
        f"{progress_bar(0, limit)}\n`جاري مسح {limit:,} رسالة...`",
        color=C.PURGE
    )
    await interaction.edit_original_response(embed=e, **_atts())

    try:
        deleted = await interaction.channel.purge(limit=limit)
        await interaction.edit_original_response(embed=embed_success(
            "تنظيف مكتمل",
            f"{progress_bar(len(deleted), limit)}",
            fields=[
                ("🧹 الروم",    f"`#{interaction.channel.name}`", True),
                ("🗑️ المحذوف", f"`{len(deleted):,}` رسالة",       True),
            ]
        ), **_atts())
    except Exception as ex:
        await interaction.edit_original_response(embed=embed_error("فشل المسح", str(ex)[:300]), **_atts())

# ─────────────── /nuke ───────────────
@bot.tree.command(name="nuke", description="⚠️ مسح كل الرومات (آخر 2000 لكل روم)")
async def slash_nuke(interaction: discord.Interaction):
    if interaction.guild.id != ALLOWED_GUILD_ID:
        return await interaction.response.send_message(
            embed=embed_error("غير مصرح"), ephemeral=True, **_files()
        )
    if not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message(
            embed=embed_error("صلاحيات غير كافية", "تحتاج صلاحية `Manage Messages`."),
            ephemeral=True, **_files()
        )

    # ── نافذة التأكيد ──
    class ConfirmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=30)
            self.confirmed = False

        @discord.ui.button(label="💣  تأكيد التنفيذ", style=discord.ButtonStyle.danger)
        async def confirm(self, btn: discord.Interaction, button: discord.ui.Button):
            self.confirmed = True
            self.stop()
            await btn.response.edit_message(
                embed=embed_warning("تم التأكيد", "جاري تشغيل البروتوكول..."),
                view=None, **_atts()
            )

        @discord.ui.button(label="إلغاء", style=discord.ButtonStyle.secondary)
        async def cancel(self, btn: discord.Interaction, button: discord.ui.Button):
            self.stop()
            await btn.response.edit_message(
                embed=embed_info("⛔  تم الإلغاء", "لم يُحذف شيء.", color=C.INFO),
                view=None, **_atts()
            )

    view = ConfirmView()
    confirm_embed = embed_warning(
        "⚠️  تحذير — Nuke Protocol",
        "سيتم **مسح آخر 2000 رسالة** من كل روم نصي في السيرفر.\n\n"
        "هذا الإجراء **لا يمكن التراجع عنه**."
    )
    confirm_embed.add_field(name="السيرفر", value=f"`{interaction.guild.name}`", inline=True)
    confirm_embed.add_field(name="المُنفِّذ", value=interaction.user.mention, inline=True)

    await interaction.response.send_message(embed=confirm_embed, view=view, ephemeral=True, **_files())
    await view.wait()

    if not view.confirmed:
        return

    # ── رسالة عامة يشوفها الكل (تُحذف مع الروم لاحقاً) ──
    origin_channel = interaction.channel
    channels = [c for c in interaction.guild.channels if isinstance(c, discord.TextChannel)]
    total_ch = len(channels)

    public_embed = discord.Embed(
        title="⚡  PROTOCOL ZERO — NUKE INITIATED",
        description=(
            f"**المُنفِّذ:** {interaction.user.mention}\n"
            f"**السيرفر:** `{interaction.guild.name}`\n\n"
            f"{progress_bar(0, total_ch)}\n"
            f"`جاري مسح الرومات... 0 / {total_ch}`"
        ),
        color=C.NUKE,
        timestamp=_ts()
    )
    public_embed.set_footer(text=_footer())
    if _bot_img:
        public_embed.set_thumbnail(url="attachment://bot.jpg")

    try:
        public_msg = await origin_channel.send(embed=public_embed, **_files())
    except Exception:
        public_msg = None

    # ── المسح الفعلي ──
    total_deleted = 0
    other_channels = [c for c in channels if c.id != origin_channel.id]
    done = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=13, hours=23)

    for idx, ch in enumerate(other_channels, start=1):
        try:
            # هل في رسالة واحدة على الأقل أحدث من 14 يوم؟
            has_recent = False
            async for _ in ch.history(limit=1, after=cutoff):
                has_recent = True
                break

            if not has_recent:
                continue  # فاضي أو رسائله كلها قديمة → تخطّ فوري

            deleted = await ch.purge(
                limit=2000,
                check=lambda m: m.created_at >= cutoff
            )
            total_deleted += len(deleted)
            done += 1

            if public_msg:
                public_embed.description = (
                    f"**المُنفِّذ:** {interaction.user.mention}\n"
                    f"**السيرفر:** `{interaction.guild.name}`\n\n"
                    f"{progress_bar(done, len(other_channels))}\n"
                    f"`#{ch.name}` — حُذفت `{len(deleted):,}` رسالة\n"
                    f"`{done} روم منظّف`"
                )
                try:
                    await public_msg.edit(embed=public_embed, **_atts())
                except Exception:
                    pass

            await asyncio.sleep(0.8)
        except Exception:
            pass

    # ── مسح الروم الأصلي (يُحذف معه الرسالة العامة) ──
    try:
        await origin_channel.purge(limit=2000)
    except Exception:
        pass

    # ── رسالة الإنجاز النهائية ──
    final_embed = discord.Embed(
        title="✅  NUKE COMPLETE — Protocol Zero",
        color=C.SUCCESS,
        timestamp=_ts()
    )
    final_embed.description = (
        f"```\n"
        f"  ██████╗ ██████╗  ██████╗ ████████╗ ██████╗  ██████╗ ██████╗ ██╗\n"
        f"  ██╔══██╗██╔══██╗██╔═══██╗╚══██╔══╝██╔═══██╗██╔════╝██╔═══██╗██║\n"
        f"  ██████╔╝██████╔╝██║   ██║   ██║   ██║   ██║██║     ██║   ██║██║\n"
        f"  ██╔═══╝ ██╔══██╗██║   ██║   ██║   ██║   ██║██║     ██║   ██║██║\n"
        f"  ██║     ██║  ██║╚██████╔╝   ██║   ╚██████╔╝╚██████╗╚██████╔╝███████╗\n"
        f"  ╚═╝     ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝  ╚═════╝ ╚═════╝ ╚══════╝\n"
        f"```"
    )
    final_embed.add_field(name="💬  الرسائل المحذوفة", value=f"`{total_deleted:,}`",       inline=True)
    final_embed.add_field(name="📂  الرومات",          value=f"`{total_ch}`",              inline=True)
    final_embed.add_field(name="👤  المُنفِّذ",         value=interaction.user.mention,     inline=True)
    final_embed.add_field(name="🖥️  السيرفر",          value=f"`{interaction.guild.name}`", inline=False)
    final_embed.set_footer(text=_footer())
    if _bot_img:
        final_embed.set_thumbnail(url="attachment://bot.jpg")

    await origin_channel.send(embed=final_embed, **_files())

    # تقرير خاص للمُنفِّذ
    try:
        report = embed_success(
            "تقرير Nuke",
            f"تمت عملية المسح بنجاح.",
            fields=[
                ("💬 محذوف",  f"`{total_deleted:,}` رسالة", True),
                ("📂 رومات",  f"`{total_ch}`",               True),
                ("🕐 التوقيت", f"`{_ts().strftime('%Y-%m-%d %H:%M UTC')}`", False),
            ]
        )
        await interaction.user.send(embed=report, **_files())
    except Exception:
        pass

# ========== خادم الويب ==========
from flask import Flask, jsonify
from threading import Thread

web_app = Flask('')

@web_app.route('/')
def home():
    return f"⚡ {BOT_NAME} is alive!", 200

@web_app.route('/ping')
def ping():
    return jsonify({
        "status": "ok",
        "bot":    str(bot.user) if bot.user else "starting...",
        "guilds": len(bot.guilds),
        "time":   datetime.utcnow().isoformat()
    }), 200

def run_web():
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    Thread(target=run_web, daemon=True).start()

# ========== التشغيل ==========
if __name__ == "__main__":
    keep_alive()
    try:
        bot.run(TOKEN, reconnect=True)
    except Exception as e:
        print(f"💥 {BOT_NAME} خطأ: {e}", file=sys.stderr)
        sys.exit(1)
