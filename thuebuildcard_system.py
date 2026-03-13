import discord
from discord.ext import commands, tasks
import aiohttp
import hashlib
import random
import string
import asyncio
import os
import json
import time
import sqlite3
import re
from datetime import datetime, timedelta
from fastapi import Request

# Import app và bot từ file chính
from main import app, bot 

# --- CẤU HÌNH (GIỮ NGUYÊN) ---
PARTNER_ID = "95904113535"
PARTNER_KEY = "349afaff71cbd86fd48c6a83421071b2"
API_URL = "https://gachthe1s.com/chargingws/v2"

SHOP_NAME = "LoTuss's Schematic Shop"
CATEGORY_NAME = "orders-card"
LOG_CHANNEL_ID = 1479880771274674259
ADMIN_TRACKING_CHANNEL_ID = 1481705972325154939 
HISTORY_CHANNEL_ID = 1481239066115571885 
WARRANTY_ROLE_ID = 1479550698982215852    
FEEDBACK_CHANNEL_MENTION = "<#1481245879607492769>"

# Cấu hình chống spam giống bot (1).py
COOLDOWN_TIME = 30
MAX_FAIL = 3
user_cooldown = {}
user_fail_count = {}
user_block_until = {}

# ===== DATABASE SETUP (GIỮ NGUYÊN) =====
def init_db():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                  (request_id TEXT PRIMARY KEY, channel_id INTEGER, product TEXT, link TEXT, 
                   user_id INTEGER, amount INTEGER, user_name TEXT, serial TEXT, code TEXT, telco TEXT, admin_msg_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS card_attempts 
                  (request_id TEXT PRIMARY KEY, attempts INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def save_order(request_id, channel_id, product, link, user_id, amount, user_name):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO orders (request_id, channel_id, product, link, user_id, amount, user_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (request_id, channel_id, product, link, user_id, amount, user_name))
    c.execute("INSERT OR REPLACE INTO card_attempts (request_id, attempts) VALUES (?, 0)", (request_id,))
    conn.commit()
    conn.close()

def get_order(request_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE request_id = ?", (request_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"request_id": row[0], "channel": row[1], "product": row[2], "link": row[3], 
                "user_id": row[4], "amount": row[5], "user_name": row[6], "admin_msg_id": row[10]}
    return None

def delete_order(request_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("DELETE FROM orders WHERE request_id = ?", (request_id,))
    c.execute("DELETE FROM card_attempts WHERE request_id = ?", (request_id,))
    conn.commit()
    conn.close()

init_db()

# --- LOGIC GỬI THẺ (THEO BOT (1).PY) ---
async def send_card(telco, amount, serial, code, request_id):
    sign = hashlib.md5((PARTNER_KEY + code + serial).encode()).hexdigest()
    params = {
        "partner_id": PARTNER_ID,
        "request_id": request_id,
        "telco": telco.upper(),
        "code": code,
        "serial": serial,
        "amount": amount,
        "command": "charging",
        "sign": sign
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL, params=params) as resp:
            try: return await resp.json()
            except: return {"status": "0", "message": "Lỗi kết nối API"}

# --- WEBHOOK HANDLER (NGOÀI COG ĐỂ TRÁNH LỖI 404) ---
@app.api_route("/callback", methods=["GET", "POST"])
async def callback_handler(request: Request):
    data = {}
    try:
        if request.method == "POST":
            try: data = await request.json()
            except: data = dict(await request.form())
        if not data: data = dict(request.query_params)
    except: return {"status": 99}

    request_id = str(data.get("request_id", "")).upper()
    status = str(data.get("status", ""))
    
    order = get_order(request_id)
    if order:
        if status == "1":
            cog = bot.get_cog("BuildCardSystem")
            if cog:
                bot.loop.create_task(cog.process_confirm_order(order, is_manual=False))
    return {"status": 1, "message": "success"}

# ===== COG CLASS =====
class BuildCardSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def random_code(self):
        return ''.join(random.choices(string.digits, k=5))

    async def process_confirm_order(self, order_data, is_manual=False, admin_user=None):
        request_id = order_data["request_id"]
        user_id = order_data["user_id"]
        amount = order_data["amount"]
        channel_id = order_data["channel"]
        
        admin_ch = self.bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
        if admin_ch:
            embed_ad = discord.Embed(title="👷 ĐƠN THUÊ BUILD MỚI [CARD]", color=0xE67E22, timestamp=datetime.now())
            embed_ad.set_author(name=SHOP_NAME)
            embed_ad.add_field(name="👤 Khách hàng", value=f"<@{user_id}>", inline=True)
            embed_ad.add_field(name="🆔 Mã đơn", value=f"`{request_id}`", inline=True)
            embed_ad.add_field(name="💰 Doanh thu", value=f"**{amount:,} VND**", inline=True)
            embed_ad.add_field(name="💳 Phương thức", value="`Thẻ cào (Auto)`", inline=True)
            embed_ad.add_field(name="📍 Kênh Ticket", value=f"<#{channel_id}>", inline=False)
            footer_text = f"Duyệt thủ công bởi {admin_user.name if admin_user else 'Admin'}" if is_manual else "Hệ thống tự động duyệt thẻ."
            embed_ad.set_footer(text=footer_text)
            admin_msg = await admin_ch.send(embed=embed_ad)
            update_admin_msg(request_id, admin_msg.id)

        customer = self.bot.get_user(user_id)
        if customer:
            try:
                dm_inv = discord.Embed(title="🧾 HÓA ĐƠN XÁC NHẬN DỊCH VỤ", color=0x2ECC71, timestamp=datetime.now())
                dm_inv.set_author(name=SHOP_NAME)
                dm_inv.add_field(name="🆔 Mã hóa đơn", value=f"`BUILD-{request_id}`", inline=True)
                dm_inv.add_field(name="💰 Tổng thanh toán", value=f"**{amount:,} VND**", inline=True)
                dm_inv.add_field(name="🚀 Trạng thái", value="`Đang xử lý` ✅", inline=True)
                dm_inv.set_footer(text="Hệ thống sẽ thông báo khi công trình hoàn tất.")
                await customer.send(embed=dm_inv)
            except: pass

        client_chan = self.bot.get_channel(channel_id)
        if client_chan:
            embed_ok = discord.Embed(title="✅ THANH TOÁN THÀNH CÔNG", color=0x2ECC71)
            embed_ok.add_field(name="💰 Số tiền", value=f"`{amount:,} VND`", inline=True)
            embed_ok.add_field(name="🆔 Mã đơn", value=f"`{request_id}`", inline=True)
            embed_ok.description = "Admin đang duyệt và sẽ thông báo với bạn sau khi có thời gian nhé"
            await client_chan.send(content=f"<@{user_id}>", embed=embed_ok)

    @commands.command(name="thuebuildcard")
    @commands.has_permissions(administrator=True)
    async def thuebuildcard(self, ctx, price: int):
        await ctx.message.delete()
        random_id = self.random_code()
        order_code = f"BUILD-{random_id}"
        target_user = next((m for m in ctx.channel.members if not m.bot and not m.guild_permissions.administrator), ctx.author)
        save_order(random_id, ctx.channel.id, ctx.channel.name, "N/A", target_user.id, price, target_user.name)

        embed = discord.Embed(title="🏗️ KHỞI TẠO ĐƠN THUÊ BUILD (CARD)", color=0x3498DB, timestamp=datetime.now())
        embed.set_author(name=SHOP_NAME)
        embed.add_field(name="👤 Khách hàng", value=target_user.mention, inline=True)
        embed.add_field(name="🆔 Mã đơn", value=f"`{order_code}`", inline=True)
        embed.add_field(name="💰 Giá tiền", value=f"**{price:,} VND**", inline=True)
        view = BuyView(price, random_id)
        await ctx.send(content=target_user.mention, embed=embed, view=view)

    @commands.command(name="dathuecard")
    @commands.has_permissions(administrator=True)
    async def dathuecard(self, ctx, order_id: str):
        await ctx.message.delete()
        clean_id = order_id.upper().replace("BUILD-", "").strip()
        order = get_order(clean_id)
        if order:
            await self.process_confirm_order(order, is_manual=True, admin_user=ctx.author)
            await ctx.send(f"✅ Đã duyệt thủ công đơn `BUILD-{clean_id}`", delete_after=5)
        else:
            await ctx.send(f"❌ Không tìm thấy mã đơn `{order_id}`", delete_after=5)

    @commands.command(name="xongcard")
    @commands.has_permissions(administrator=True)
    async def xongcard(self, ctx, order_id: str):
        await ctx.message.delete()
        clean_id = order_id.upper().replace("BUILD-", "").strip()
        order = get_order(clean_id)
        if not order: return await ctx.send("❌ Không tìm thấy đơn hàng.", delete_after=5)

        admin_ch = self.bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
        if admin_ch and order["admin_msg_id"]:
            try:
                old_msg = await admin_ch.fetch_message(order["admin_msg_id"])
                await old_msg.delete()
            except: pass

        if admin_ch:
            embed_log = discord.Embed(title="📊 LOG: ĐƠN HÀNG CARD HOÀN TẤT", color=0x27AE60, timestamp=datetime.now())
            embed_log.add_field(name="🆔 Mã đơn", value=f"`BUILD-{clean_id}`", inline=True)
            embed_log.add_field(name="💳 Loại hình", value="`Thanh toán qua Card`", inline=True)
            embed_log.add_field(name="👷 Người thực hiện", value=ctx.author.mention, inline=True)
            embed_log.add_field(name="💵 Tiền nhận", value=f"**{order['amount']:,} VND**", inline=False)
            await admin_ch.send(embed=embed_log)

        embed_client = discord.Embed(title="🎊 CÔNG TRÌNH ĐÃ HOÀN THÀNH!", color=0x00FFFF)
        embed_client.set_author(name=SHOP_NAME)
        embed_client.description = "Admin đã bàn giao xong công trình. Hẹn gặp lại bạn lần sau!"
        await ctx.send(content=f"<@{order['user_id']}>", embed=embed_client)
        delete_order(clean_id)

# ===== VIEW & MODAL =====
class BuyView(discord.ui.View):
    def __init__(self, amount, order_id):
        super().__init__(timeout=None)
        self.amount, self.order_id = amount, order_id

    @discord.ui.button(label="💳 THANH TOÁN THẺ CÀO NGAY", style=discord.ButtonStyle.green, emoji="💰")
    async def pay_card(self, interaction: discord.Interaction, button):
        view = discord.ui.View()
        view.add_item(TelcoSelect(self.order_id, self.amount))
        await interaction.response.send_message(f"📡 Chọn nhà mạng nạp `{self.amount:,} VND`", view=view, ephemeral=True)

class TelcoSelect(discord.ui.Select):
    def __init__(self, order_id, amount):
        options = [discord.SelectOption(label=x, value=x.upper()) for x in ["Viettel", "Vinaphone", "Mobifone", "Vcoin", "Scoin", "Zing"]]
        super().__init__(placeholder="📡 Chọn nhà mạng", options=options)
        self.order_id, self.amount = order_id, amount

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CardModal(self.values[0], self.amount, self.order_id))

class CardModal(discord.ui.Modal, title="💳 Nhập thông tin thẻ"):
    serial = discord.ui.TextInput(label="SERIAL", placeholder="Nhập số seri thẻ...")
    code = discord.ui.TextInput(label="MÃ THẺ", placeholder="Nhập mã thẻ...")

    def __init__(self, telco, amount, order_id):
        super().__init__()
        self.telco, self.amount, self.order_id = telco, amount, order_id

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        now = time.time()

        # Logic chặn/cooldown từ bot (1).py
        if user_id in user_block_until and now < user_block_until[user_id]:
            return await interaction.response.send_message(f"🚫 Bạn đang bị chặn nạp thẻ trong {int(user_block_until[user_id]-now)}s", ephemeral=True)
        if user_id in user_cooldown and now - user_cooldown[user_id] < COOLDOWN_TIME:
            return await interaction.response.send_message(f"⏳ Vui lòng chờ {int(COOLDOWN_TIME-(now-user_cooldown[user_id]))}s", ephemeral=True)
        
        user_cooldown[user_id] = now
        await interaction.response.send_message("⏳ Đang gửi thẻ...", ephemeral=True)
        
        result = await send_card(self.telco, self.amount, self.serial.value, self.code.value, self.order_id)
        
        if str(result.get("status")) in ["1", "99"]:
            await interaction.followup.send("✅ Đã nhận thẻ thành công, vui lòng chờ hệ thống kiểm tra.", ephemeral=True)
            user_fail_count[user_id] = 0
        else:
            fails = user_fail_count.get(user_id, 0) + 1
            user_fail_count[user_id] = fails
            if fails >= MAX_FAIL:
                user_block_until[user_id] = now + 300 # Chặn 5 phút
                await interaction.followup.send("❌ Sai quá nhiều lần! Bạn bị chặn 5 phút.", ephemeral=True)
            else:
                msg = result.get("message", "Thẻ không hợp lệ")
                await interaction.followup.send(f"❌ Lỗi: {msg}. Thử lại sau {COOLDOWN_TIME}s.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(BuildCardSystem(bot))
