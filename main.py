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
# Partner ID khớp với ảnh của bạn: 95904113535
TOKEN = os.getenv("TOKEN")
PARTNER_ID = "95904113535" 
PARTNER_KEY = "349afaff71cbd86fd48c6a83421071b2"
API_URL = "https://gachthe1s.com/chargingws/v2"

SHOP_NAME = "LoTuss's Schematic Shop"
CATEGORY_NAME = "orders-card"
LOG_CHANNEL_ID = 1479880771274674259
HISTORY_CHANNEL_ID = 1481239066115571885 
WARRANTY_ROLE_ID = 1479550698982215852  
FEEDBACK_CHANNEL_MENTION = "<#1481245879607492769>"

# --- DATABASE ---
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
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO orders (request_id, channel_id, product, link, user_id, amount, user_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (request_id, channel_id, product, link, user_id, amount, user_name))
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
                "user_id": row[4], "amount": row[5], "user_name": row[6]}
    return None

def delete_order(request_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("DELETE FROM orders WHERE request_id = ?", (request_id,))
    conn.commit()
    conn.close()

init_db()

# --- BOT SETUP ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
app = FastAPI()
user_ticket_count = {}

# --- WEBHOOK CALLBACK (QUAN TRỌNG) ---
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
    receive = int(data.get("received") or data.get("receive") or 0)

    order = get_order(request_id)
    if order:
        # Gửi log biến động vào Discord
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(title="💳 THÔNG BÁO THẺ", color=0x3498db)
            embed.add_field(name="Mã đơn", value=request_id)
            embed.add_field(name="Trạng thái", value="Thành công" if status == "1" else f"Lỗi ({status})")
            embed.add_field(name="Thực nhận", value=f"{receive:,} VND")
            bot.loop.create_task(log_channel.send(embed=embed))

        # Nếu thẻ thành công -> Tự động duyệt đơn
        if status == "1":
            bot.loop.create_task(process_success_order(order))
            
    return {"status": 1, "message": "success"}

async def process_success_order(order):
    user_id = order["user_id"]
    channel = bot.get_channel(order["channel"])
    history_channel = bot.get_channel(HISTORY_CHANNEL_ID)

    # 1. Thông báo trong ticket
    if channel:
        embed = discord.Embed(title="🎉 THANH TOÁN THÀNH CÔNG", color=0x2ecc71)
        embed.description = f"📦 **Hàng:** {order['product']}\n💰 **Tiền:** {order['amount']:,} VND\n🔗 **Link:** {order['link']}"
        await channel.send(content=f"<@{user_id}>", embed=embed)

    # 2. Ghi lịch sử
    if history_channel:
        await history_channel.send(f"✅ <@{user_id}> đã mua **{order['product']}** thành công!")

    # 3. Xóa đơn
    delete_order(order["request_id"])

# --- CÁC LỆNH BOT ---
@bot.event
async def on_ready():
    print(f"✅ Bot {bot.user} đã sẵn sàng!")

@bot.command()
async def sellcard(ctx, amount: int, link: str):
    embed = discord.Embed(title="🛒 MUA HÀNG QUA THẺ CÀO", color=discord.Color.blue())
    embed.description = f"📦 **Sản phẩm:** {ctx.channel.name}\n💰 **Giá:** {amount:,} VND"
    # Bạn có thể thêm BuyView của bạn vào đây
    await ctx.send(embed=embed)

# --- CHẠY HỆ THỐNG ---
def run_bot():
    bot.run(TOKEN)

if __name__ == "__main__":
    # Chạy Bot trong một luồng riêng
    threading.Thread(target=run_bot, daemon=True).start()
    # Chạy FastAPI trên Port 8080 (Khớp với ảnh Railway của bạn)
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
