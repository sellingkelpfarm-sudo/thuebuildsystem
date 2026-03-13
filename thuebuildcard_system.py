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
import sqlite3
import time
from datetime import datetime, timedelta

# --- CẤU HÌNH ---
TOKEN = os.getenv("TOKEN")
PARTNER_ID = "86935102540"
PARTNER_KEY = "c63d72291473a68fcbb23261491a103f"
API_URL = "https://gachthe1s.com/chargingws/v2"

CATEGORY_NAME = "orders-card"
LOG_CHANNEL_ID = 1479880771274674259
HISTORY_CHANNEL_ID = 1481239066115571885 
WARRANTY_ROLE_ID = 1479550698982215852  
SHOP_NAME = "LoTuss's Schematic Shop"
FEEDBACK_CHANNEL_MENTION = "<#1481245879607492769>"

# --- DATABASE LOGIC (Giữ nguyên của LouIs) ---
def init_db():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (request_id TEXT PRIMARY KEY, channel_id INTEGER, product TEXT, link TEXT, 
                  user_id INTEGER, amount INTEGER, user_name TEXT, serial TEXT, code TEXT, telco TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS warranty 
                 (user_id INTEGER, guild_id INTEGER, expiry_timestamp REAL)''')
    conn.commit()
    conn.close()

def save_order(request_id, channel_id, product, link, user_id, amount, user_name):
    conn = sqlite3.connect('orders.db')
    conn.execute("INSERT OR REPLACE INTO orders (request_id, channel_id, product, link, user_id, amount, user_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (request_id, channel_id, product, link, user_id, amount, user_name))
    conn.commit()
    conn.close()

def get_order(request_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE request_id = ?", (request_id,))
    row = c.fetchone()
    conn.close()
    return {"request_id": row[0], "channel": row[1], "product": row[2], "link": row[3], "user_id": row[4], "amount": row[5], "user_name": row[6]} if row else None

def delete_order(request_id):
    conn = sqlite3.connect('orders.db')
    conn.execute("DELETE FROM orders WHERE request_id = ?", (request_id,))
    conn.commit()
    conn.close()

init_db()

# --- BOT SETUP ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
app = FastAPI()
user_ticket_count = {}
MAX_TICKETS_PER_USER = 3

# --- UI COMPONENTS (Giao diện mới) ---
class CardModal(discord.ui.Modal, title="💳 NHẬP THÔNG TIN THẺ CÀO"):
    serial = discord.ui.TextInput(label="SERIAL", placeholder="Nhập số seri thẻ...", min_length=10)
    code = discord.ui.TextInput(label="MÃ THẺ", placeholder="Nhập mã số sau lớp bạc...", min_length=10)

    def __init__(self, telco, amount, order_id):
        super().__init__()
        self.telco, self.amount, self.order_id = telco, amount, order_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("📡 Đang gửi thẻ lên hệ thống...", ephemeral=True)
        sign = hashlib.md5((PARTNER_KEY + self.code.value + self.serial.value).encode()).hexdigest()
        params = {
            "partner_id": PARTNER_ID, "request_id": self.order_id, "telco": self.telco.upper(),
            "code": self.code.value, "serial": self.serial.value, "amount": self.amount,
            "command": "charging", "sign": sign
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL, params=params) as resp:
                result = await resp.json() if resp.status == 200 else {"status": "0"}
        
        if str(result.get("status")) in ["1", "99"]:
            await interaction.followup.send(f"✅ Gửi thẻ thành công! Đang đợi duyệt đơn `{self.order_id}`.", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Lỗi: {result.get('message', 'Thẻ không hợp lệ')}", ephemeral=True)

class TelcoSelect(discord.ui.Select):
    def __init__(self, order_id, amount):
        options = [
            discord.SelectOption(label="Viettel (8%)", value="Viettel", emoji="🔴"),
            discord.SelectOption(label="Garena (11%)", value="Garena", emoji="🎮"),
            discord.SelectOption(label="Vinaphone (8%)", value="Vinaphone", emoji="🔵"),
            discord.SelectOption(label="Zing (12%)", value="Zing", emoji="🟢"),
            discord.SelectOption(label="Mobifone (16%)", value="Mobifone", emoji="🟡"),
            discord.SelectOption(label="Vcoin (8%)", value="Vcoin", emoji="💎"),
            discord.SelectOption(label="Scoin (28%)", value="Scoin", emoji="💳")
        ]
        super().__init__(placeholder="📡 Chọn nhà mạng nạp thẻ", options=options)
        self.order_id, self.amount = order_id, amount

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CardModal(self.values[0], self.amount, self.order_id))

class OrderView(discord.ui.View):
    def __init__(self, order_id, amount):
        super().__init__(timeout=None)
        self.order_id, self.amount = order_id, amount

    @discord.ui.button(label="💳 NẠP CARD", style=discord.ButtonStyle.green, emoji="💰")
    async def nap(self, interaction: discord.Interaction, button):
        view = discord.ui.View().add_item(TelcoSelect(self.order_id, self.amount))
        await interaction.response.send_message(content="**Hãy chọn đúng nhà mạng bên dưới:**", view=view, ephemeral=True)

    @discord.ui.button(label="❌ HỦY ĐƠN", style=discord.ButtonStyle.red, emoji="🗑️")
    async def cancel(self, interaction: discord.Interaction, button):
        user_id = interaction.user.id
        if user_id in user_ticket_count: user_ticket_count[user_id] = max(0, user_ticket_count[user_id]-1)
        delete_order(self.order_id)
        await interaction.response.send_message("⏳ Kênh sẽ bị xoá sau 3 giây.")
        await asyncio.sleep(3)
        await interaction.channel.delete()

# --- COMMANDS ---
@bot.command()
@commands.has_permissions(administrator=True)
async def sellcard(ctx, amount: int, link: str):
    await ctx.message.delete()
    product = ctx.channel.name.replace("-", " ").upper()
    embed = discord.Embed(
        title="🛒 THANH TOÁN BẰNG THẺ CÀO",
        description=f"📦 **Tên hàng:** `{product}`\n💰 **Giá:** `{amount:,} VND`\n\n👇 **Nhấn nút bên dưới để tạo đơn thanh toán**",
        color=0x3498DB
    )
    embed.set_author(name=SHOP_NAME)
    embed.set_footer(text=f"Dịch vụ cung cấp bởi {SHOP_NAME}")
    await ctx.send(embed=embed, view=BuyButton(product, amount, link))

class BuyButton(discord.ui.View):
    def __init__(self, product, amount, link):
        super().__init__(timeout=None)
        self.product, self.amount, self.link = product, amount, link

    @discord.ui.button(label="🛒 MUA NGAY", style=discord.ButtonStyle.green)
    async def buy(self, interaction: discord.Interaction, button):
        user_id = interaction.user.id
        if user_ticket_count.get(user_id, 0) >= MAX_TICKETS_PER_USER:
            return await interaction.response.send_message("🚫 Bạn đã mở quá nhiều đơn hàng.", ephemeral=True)
        
        code = ''.join(random.choices(string.digits, k=5))
        category = discord.utils.get(interaction.guild.categories, name=CATEGORY_NAME)
        overwrites = {interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False), interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True), interaction.guild.me: discord.PermissionOverwrite(view_channel=True)}
        
        channel = await interaction.guild.create_text_channel(name=f"card-{code}-{interaction.user.name}", category=category, overwrites=overwrites)
        save_order(code, channel.id, self.product, self.link, user_id, self.amount, interaction.user.name)
        user_ticket_count[user_id] = user_ticket_count.get(user_id, 0) + 1
        
        embed = discord.Embed(title=f"💳 {SHOP_NAME} - XÁC NHẬN ĐƠN", color=0xF1C40F, timestamp=datetime.now())
        embed.add_field(name="📦 Tên hàng", value=f"`{self.product}`", inline=True)
        embed.add_field(name="💰 Số tiền", value=f"**{self.amount:,} VND**", inline=True)
        embed.add_field(name="🆔 Mã đơn", value=f"`{code}`", inline=False)
        embed.add_field(name="🛡️ Lưu ý", value="• Chọn đúng nhà mạng và mệnh giá.\n• Sai mệnh giá hệ thống không hoàn tiền.", inline=False)
        
        await channel.send(content=interaction.user.mention, embed=embed, view=OrderView(code, self.amount))
        await interaction.response.send_message(f"✅ Đã tạo đơn tại: {channel.mention}", ephemeral=True)

# --- CALLBACK & AUTO TASKS (Giữ nguyên logic của LouIs) ---
@app.api_route("/callback", methods=["GET", "POST"])
async def callback(request: Request):
    # Logic xử lý callback như code cũ của bạn để duyệt đơn tự động
    # Bao gồm: check status == 1, add_role, gửi DM, ghi History...
    # (Để tiết kiệm không gian tôi tóm lược lại phần này, LouIs giữ nguyên phần xử lý callback cũ nhé)
    return {"status": 1, "message": "success"}

# --- KHỞI CHẠY ---
def start_bot(): bot.run(TOKEN)
threading.Thread(target=start_bot, daemon=True).start()
if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))