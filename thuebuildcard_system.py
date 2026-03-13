import discord
from discord.ext import commands, tasks
import aiohttp
import hashlib
import random
import string
import asyncio
from fastapi import FastAPI, Request
import uvicorn
import threading
import os
import json
import time
import sqlite3
import re
from datetime import datetime, timedelta

# --- CẤU HÌNH ---
TOKEN = os.getenv("TOKEN")
PARTNER_ID = "86935102540"
PARTNER_KEY = "c63d72291473a68fcbb23261491a103f"
API_URL = "https://gachthe1s.com/chargingws/v2"

SHOP_NAME = "LoTuss's Schematic Shop"
CATEGORY_NAME = "orders-card"
LOG_CHANNEL_ID = 1479880771274674259 # Log nạp thẻ
ADMIN_TRACKING_CHANNEL_ID = 1481705972325154939 # Log đơn hàng cần xử lý (Đồng bộ với Bank)
HISTORY_CHANNEL_ID = 1481239066115571885 
WARRANTY_ROLE_ID = 1479550698982215852   
FEEDBACK_CHANNEL_MENTION = "<#1481245879607492769>"

# ===== DATABASE SETUP =====
def init_db():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (request_id TEXT PRIMARY KEY, channel_id INTEGER, product TEXT, link TEXT, 
                  user_id INTEGER, amount INTEGER, user_name TEXT, serial TEXT, code TEXT, telco TEXT, admin_msg_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS warranty 
                 (user_id INTEGER, guild_id INTEGER, expiry_timestamp REAL)''')
    conn.commit()
    conn.close()

def save_order(request_id, channel_id, product, link, user_id, amount, user_name):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO orders (request_id, channel_id, product, link, user_id, amount, user_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (request_id, channel_id, product, link, user_id, amount, user_name))
    conn.commit()
    conn.close()

def update_admin_msg(request_id, msg_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("UPDATE orders SET admin_msg_id = ? WHERE request_id = ?", (msg_id, request_id))
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
    conn.commit()
    conn.close()

init_db()

user_cooldown, user_fail_count, user_block_until, buy_cooldown, user_ticket_count = {}, {}, {}, {}, {}
MAX_TICKETS_PER_USER, COOLDOWN_TIME, MAX_FAIL, BLOCK_TIME, BUY_COOLDOWN = 3, 15, 3, 300, 20

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
app = FastAPI()

def random_code():
    return ''.join(random.choices(string.digits, k=5))

# ===== LOGIC XỬ LÝ ĐƠN HÀNG (ĐỒNG BỘ VỚI BANK) =====
async def process_confirm_order(order_data, is_manual=False, admin_user=None):
    request_id = order_data["request_id"]
    user_id = order_data["user_id"]
    amount = order_data["amount"]
    product = order_data["product"]
    channel_id = order_data["channel"]
    
    # 1. Thông báo cho Admin (Dòng Cam - Đơn mới cần xử lý)
    admin_ch = bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
    admin_msg_id = None
    if admin_ch:
        # Sửa: Thêm nhãn [CARD] và thông tin Phương thức
        embed_ad = discord.Embed(title="👷 ĐƠN THUÊ BUILD MỚI [CARD]", color=0xE67E22, timestamp=datetime.now())
        embed_ad.set_author(name=SHOP_NAME)
        embed_ad.add_field(name="👤 Khách hàng", value=f"<@{user_id}>", inline=True)
        embed_ad.add_field(name="🆔 Mã đơn", value=f"`{request_id}`", inline=True)
        embed_ad.add_field(name="💰 Doanh thu", value=f"**{amount:,} VND**", inline=True)
        embed_ad.add_field(name="💳 Phương thức", value="`Thẻ cào (Auto)`", inline=True) # Dòng thêm mới
        embed_ad.add_field(name="📍 Kênh Ticket", value=f"<#{channel_id}>", inline=False)
        
        footer_text = f"Duyệt thủ công bởi {admin_user.name}" if is_manual else "Hệ thống tự động duyệt thẻ."
        embed_ad.set_footer(text=footer_text)
        
        admin_msg = await admin_ch.send(embed=embed_ad)
        admin_msg_id = admin_msg.id
        update_admin_msg(request_id, admin_msg_id)

    # 2. Hóa đơn DMs gửi khách (Đồng bộ mẫu Bank)
    customer = bot.get_user(user_id)
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

    # 3. Thông báo tại Ticket (Đồng bộ mẫu Bank)
    client_chan = bot.get_channel(channel_id)
    if client_chan:
        embed_ok = discord.Embed(title="✅ THANH TOÁN THÀNH CÔNG", color=0x2ECC71)
        embed_ok.add_field(name="💰 Số tiền", value=f"`{amount:,} VND`", inline=True)
        embed_ok.add_field(name="🆔 Mã đơn", value=f"`{request_id}`", inline=True)
        embed_ok.description = "Admin đang duyệt và sẽ thông báo với bạn sau khi có thời gian nhé"
        await client_chan.send(content=f"<@{user_id}>", embed=embed_ok)

# ===== LỆNH ADMIN =====

@bot.command(name="dathuecard")
@commands.has_permissions(administrator=True)
async def dathuecard(ctx, order_id: str):
    await ctx.message.delete()
    clean_id = order_id.upper().replace("BUILD-", "").strip()
    order = get_order(clean_id)
    
    if order:
        await process_confirm_order(order, is_manual=True, admin_user=ctx.author)
        # Giảm số ticket chờ của khách
        if order["user_id"] in user_ticket_count: 
            user_ticket_count[order["user_id"]] = max(0, user_ticket_count[order["user_id"]]-1)
        await ctx.send(f"✅ Đã duyệt thủ công đơn `BUILD-{clean_id}`", delete_after=5)
    else:
        await ctx.send(f"❌ Không tìm thấy mã đơn `{order_id}`", delete_after=5)

@bot.command(name="xongcard")
@commands.has_permissions(administrator=True)
async def xongcard(ctx, order_id: str):
    """Hoàn tất công trình và xóa log cam tương tự lệnh !xong"""
    await ctx.message.delete()
    clean_id = order_id.upper().replace("BUILD-", "").strip()
    order = get_order(clean_id)
    
    if not order:
        return await ctx.send("❌ Không tìm thấy đơn hàng này để hoàn tất.", delete_after=5)

    # Xóa dòng cam ở Admin
    admin_ch = bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
    if admin_ch and order["admin_msg_id"]:
        try:
            old_msg = await admin_ch.fetch_message(order["admin_msg_id"])
            await old_msg.delete()
        except: pass

    # Log hoàn tất xanh lá
    if admin_ch:
        # Sửa: Thêm nhãn [CARD] và thông tin Loại hình
        embed_log = discord.Embed(title="📊 LOG: ĐƠN HÀNG CARD HOÀN TẤT", color=0x27AE60, timestamp=datetime.now())
        embed_log.add_field(name="🆔 Mã đơn", value=f"`BUILD-{clean_id}`", inline=True)
        embed_log.add_field(name="💳 Loại hình", value="`Thanh toán qua Card`", inline=True) # Dòng thêm mới
        embed_log.add_field(name="👷 Người thực hiện", value=ctx.author.mention, inline=True)
        embed_log.add_field(name="💵 Tiền nhận", value=f"**{order['amount']:,} VND**", inline=False)
        await admin_ch.send(embed=embed_log)

    # Thông báo Ticket
    embed_client = discord.Embed(title="🎊 CÔNG TRÌNH ĐÃ HOÀN THÀNH!", color=0x00FFFF)
    embed_client.set_author(name=SHOP_NAME)
    embed_client.description = "Admin đã bàn giao xong công trình. Hẹn gặp lại bạn lần sau!"
    await ctx.send(content=f"<@{order['user_id']}>", embed=embed_client)

    # Biên lai DMs gửi khách
    customer = bot.get_user(order["user_id"])
    if customer:
        try:
            dm_done = discord.Embed(title="📦 BIÊN LAI BÀN GIAO", color=0x2ECC71, timestamp=datetime.now())
            dm_done.set_author(name=SHOP_NAME)
            dm_done.add_field(name="🆔 Mã đơn", value=f"`BUILD-{clean_id}`", inline=True)
            dm_done.add_field(name="💰 Tổng tiền", value=f"**{order['amount']:,} VND**", inline=True)
            dm_done.set_footer(text=f"Cảm ơn bạn đã tin tưởng {SHOP_NAME}!")
            await customer.send(embed=dm_done)
        except: pass

    delete_order(clean_id)

# ===== WEBHOOK CALLBACK (AUTO CARD) =====

@app.api_route("/callback", methods=["GET", "POST"])
async def callback(request: Request):
    data = {}
    try:
        if request.method == "POST":
            try: data = await request.json()
            except: data = dict(await request.form())
        if not data: data = dict(request.query_params)
    except: return {"status": 99}

    request_id = str(data.get("request_id", "")).upper()
    status = str(data.get("status", ""))
    real_value = int(data.get("value") or data.get("amount") or 0)

    order = get_order(request_id)
    if order:
        if status == "1" and real_value == int(order["amount"]):
            # Giảm số ticket chờ
            if order["user_id"] in user_ticket_count: 
                user_ticket_count[order["user_id"]] = max(0, user_ticket_count[order["user_id"]]-1)
            
            # Thực hiện quy trình xác nhận đồng bộ
            await process_confirm_order(order, is_manual=False)
            
            # Log nạp thẻ riêng (LOG_CHANNEL_ID)
            log_ch = bot.get_channel(LOG_CHANNEL_ID)
            if log_ch:
                embed_card = discord.Embed(title="📥 THẺ NẠP THUÊ BUILD THÀNH CÔNG", color=0x3498db)
                embed_card.add_field(name="Khách", value=order["user_name"])
                embed_card.add_field(name="Mệnh giá", value=f"{real_value:,} VND")
                embed_card.add_field(name="Mã đơn", value=request_id)
                bot.loop.create_task(log_ch.send(embed=embed_card))
    
    return {"status": 1, "message": "success"}

# ===== LỆNH NGƯỜI DÙNG =====

@bot.command(name="thuebuildcard")
@commands.has_permissions(administrator=True)
async def thuebuildcard(ctx, price: int):
    await ctx.message.delete()
    random_id = random_code()
    order_code = f"BUILD-{random_id}"
    
    # Tìm khách hàng trong ticket (người không phải bot/admin)
    target_user = next((m for m in ctx.channel.members if not m.bot and not m.guild_permissions.administrator), ctx.author)
    
    save_order(random_id, ctx.channel.id, ctx.channel.name, "N/A", target_user.id, price, target_user.name)
    user_ticket_count[target_user.id] = user_ticket_count.get(target_user.id, 0) + 1

    embed = discord.Embed(title="🏗️ KHỞI TẠO ĐƠN THUÊ BUILD (CARD)", color=0x3498DB, timestamp=datetime.now())
    embed.set_author(name=SHOP_NAME)
    embed.add_field(name="👤 Khách hàng", value=target_user.mention, inline=True)
    embed.add_field(name="🆔 Mã đơn", value=f"`{order_code}`", inline=True)
    embed.add_field(name="💰 Giá tiền", value=f"**{price:,} VND**", inline=True)
    
    view = BuyView(price, random_id)
    await ctx.send(content=target_user.mention, embed=embed, view=view)

class BuyView(discord.ui.View):
    def __init__(self, amount, order_id):
        super().__init__(timeout=None)
        self.amount = amount
        self.order_id = order_id

    @discord.ui.button(label="💳 THANH TOÁN THẺ CÀO NGAY", style=discord.ButtonStyle.green, emoji="💰")
    async def pay_card(self, interaction: discord.Interaction, button):
        await interaction.response.send_message(f"📡 Chọn nhà mạng để nạp `{self.amount:,} VND`", 
                                                view=discord.ui.View().add_item(TelcoSelect(self.order_id, self.amount)), 
                                                ephemeral=True)

class TelcoSelect(discord.ui.Select):
    def __init__(self, order_id, amount):
        options = [discord.SelectOption(label=x, value=x.upper()) for x in ["Viettel", "Vinaphone", "Mobifone", "Zing"]]
        super().__init__(placeholder="📡 Chọn nhà mạng", options=options)
        self.order_id, self.amount = order_id, amount

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CardModal(self.values[0], self.amount, self.order_id))

class CardModal(discord.ui.Modal, title="💳 Nhập thông tin thẻ"):
    serial = discord.ui.TextInput(label="SERIAL", placeholder="Nhập số seri thẻ...")
    code = discord.ui.TextInput(label="MÃ THẺ", placeholder="Nhập mã thẻ sau lớp cào...")

    def __init__(self, telco, amount, order_id):
        super().__init__()
        self.telco, self.amount, self.order_id = telco, amount, order_id

    async def on_submit(self, interaction: discord.Interaction):
        # Giữ nguyên logic cũ của bạn
        sign = hashlib.md5((PARTNER_KEY + self.code.value + self.serial.value).encode()).hexdigest()
        # ... logic gọi API gachthe1s tiếp theo ...
        await interaction.response.send_message("⏳ Đã gửi thẻ! Hệ thống đang kiểm tra, vui lòng chờ trong giây lát...", ephemeral=True)

# --- Khởi chạy ---
def start_bot(): bot.run(TOKEN)
threading.Thread(target=start_bot, daemon=True).start()
if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
