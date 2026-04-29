#!/usr/bin/env python3
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import sys
from datetime import datetime
from typing import List, Dict

# ------------------- متغيرات البيئة -------------------
TOKEN = os.getenv("DISCORD_TOKEN")
ALLOWED_GUILD_ID = int(os.getenv("ALLOWED_GUILD_ID", "0"))

if not TOKEN:
    print("❌ DISCORD_TOKEN غير موجود", file=sys.stderr)
    sys.exit(1)
if ALLOWED_GUILD_ID == 0:
    print("❌ ALLOWED_GUILD_ID غير موجود", file=sys.stderr)
    sys.exit(1)

# ------------------- إعداد النوايا -------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------- دوال مساعدة -------------------
def generate_html(messages: List[Dict], channel_name: str) -> str:
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>#{channel_name}</title>
<style>
    body {{ background: #1e1f22; color: #dbdee1; font-family: Arial; padding: 20px; }}
    .msg {{ background: #2b2d31; margin: 8px 0; padding: 10px; border-radius: 8px; }}
    .author {{ color: #fff; font-weight: bold; }}
    .time {{ color: #aaa; font-size: 12px; }}
</style>
</head>
<body><h1>#{channel_name}</h1><hr>
"""
    for m in messages:
        html += f'<div class="msg"><div class="author">{m["author"]} <span class="time">{m["time"]}</span></div><div>{m["content"]}</div></div>'
    html += "</body></html>"
    return html

# ------------------- الأوامر العادية -------------------
@bot.event
async def on_ready():
    print(f"✅ شغال: {bot.user}")
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

# أمر المزامنة (لتفعيل الأوامر المائلة)
@bot.command(name="sync")
@commands.has_permissions(manage_messages=True)
async def sync_commands(ctx):
    await ctx.defer()
    await ctx.send("🔄 جاري تسجيل الأوامر...")
    try:
        guild = discord.Object(id=ctx.guild.id)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        cmd_names = [cmd.name for cmd in synced]
        await ctx.send(f"✅ تم تسجيل {len(synced)} أمر: {', '.join(cmd_names)}\nأعد تشغيل ديسكورد الآن.")
    except Exception as e:
        await ctx.send(f"❌ فشل: {e}")

# ------------------- الأوامر المائلة -------------------
@bot.tree.command(name="save", description="أرشفة الروم الحالي (HTML)")
async def slash_save(interaction: discord.Interaction):
    if interaction.guild.id != ALLOWED_GUILD_ID:
        return await interaction.response.send_message("❌ غير مصرح", ephemeral=True)
    await interaction.response.defer(thinking=True)
    await interaction.edit_original_response(content="📀 جاري جمع الرسائل...")
    msgs = []
    async for msg in interaction.channel.history(limit=None):
        msgs.append({
            'author': msg.author.display_name,
            'content': msg.clean_content or "[وسائط]",
            'time': msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
        if len(msgs) % 500 == 0:
            await interaction.edit_original_response(content=f"📀 جمعت {len(msgs)}...")
    await interaction.edit_original_response(content="📄 توليد HTML...")
    html = generate_html(msgs, interaction.channel.name)
    fn = f"archive_{interaction.channel.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(fn, 'w', encoding='utf-8') as f:
        f.write(html)
    await interaction.edit_original_response(content="📤 إرسال...")
    try:
        await interaction.user.send(file=discord.File(fn))
        await interaction.edit_original_response(content=f"✅ تم إرسال {len(msgs)} رسالة")
    except Exception as e:
        await interaction.edit_original_response(content=f"❌ فشل: {e}")
    finally:
        if os.path.exists(fn):
            os.remove(fn)

@bot.tree.command(name="purge", description="مسح رسائل من الروم الحالي")
@app_commands.describe(limit="العدد (1-2000)")
async def slash_purge(interaction: discord.Interaction, limit: int = 100):
    if interaction.guild.id != ALLOWED_GUILD_ID:
        return await interaction.response.send_message("❌ غير مصرح", ephemeral=True)
    limit = min(max(1, limit), 2000)
    await interaction.response.defer(thinking=True)
    await interaction.edit_original_response(content=f"🧹 جاري مسح {limit}...")
    try:
        deleted = await interaction.channel.purge(limit=limit)
        await interaction.edit_original_response(content=f"✅ حذف {len(deleted)}")
    except Exception as e:
        await interaction.edit_original_response(content=f"❌ {str(e)[:200]}")

@bot.tree.command(name="nuke", description="⚠️ مسح كل الرومات (آخر 2000 لكل روم)")
async def slash_nuke(interaction: discord.Interaction):
    if interaction.guild.id != ALLOWED_GUILD_ID:
        return await interaction.response.send_message("❌ غير مصرح", ephemeral=True)
    if not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message("❌ تحتاج صلاحية", ephemeral=True)
    
    class Confirm(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=30)
            self.confirmed = False
        @discord.ui.button(label="💣 تأكيد", style=discord.ButtonStyle.danger)
        async def confirm(self, btn: discord.Interaction, button):
            self.confirmed = True
            self.stop()
            await btn.response.edit_message(content="✅ بدء المسح...", view=None)
        @discord.ui.button(label="❌ إلغاء", style=discord.ButtonStyle.secondary)
        async def cancel(self, btn, button):
            self.stop()
            await btn.response.edit_message(content="❌ ألغي", view=None)
    
    view = Confirm()
    await interaction.response.send_message("⚠️ تحذير: سيمسح آخر 2000 رسالة من كل روم.\nتأكيد؟", view=view, ephemeral=True)
    await view.wait()
    if not view.confirmed:
        return
    await interaction.edit_original_response(content="💣 جاري المسح...")
    total = 0
    channels = [c for c in interaction.guild.channels if isinstance(c, discord.TextChannel)]
    for i, ch in enumerate(channels):
        try:
            deleted = await ch.purge(limit=2000)
            total += len(deleted)
            await interaction.edit_original_response(content=f"💣 {ch.name}: {len(deleted)} ({i+1}/{len(channels)})")
            await asyncio.sleep(1)
        except:
            pass
    await interaction.edit_original_response(content=f"✅ حذف {total} رسالة")
    await interaction.user.send(f"تقرير nuke: {total} رسالة")

# ------------------- خادم الويب لـ Render -------------------
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# ------------------- التشغيل -------------------
if __name__ == "__main__":
    keep_alive()
    try:
        bot.run(TOKEN, reconnect=True)
    except Exception as e:
        print(f"💥 خطأ فادح: {e}", file=sys.stderr)
        sys.exit(1)