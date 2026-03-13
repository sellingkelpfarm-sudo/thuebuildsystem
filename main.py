import discord
from discord.ext import commands
import aiohttp
import hashlib
import os
import sqlite3
import asyncio
from fastapi import FastAPI, Request
import uvicorn
import threading
from datetime import datetime

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PARTNER_ID = "95904113535"
PARTNER_KEY = "349afaff71cbd86fd48c6a83421071b2"
API_URL = "https://gachthe1s.com/chargingws/v2"
SHOP_NAME = "LoTuss's Schematic Shop"

app = FastAPI()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

def init_db():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                  (request_id TEXT PRIMARY KEY, channel_id INTEGER, product TEXT, user_id INTEGER, amount INTEGER, status TEXT)''')
    conn.commit()
    conn.close()

def get_order(request_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE request_id = ?", (request_id,))
    row = c.fetchone()
    conn.close()
    if row: return {"request_id": row[0], "channel": row[1], "product": row[2], "user_id": row[3], "amount": row[4]}
    return None

init_db()

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
    if str(data.get("status", "")) == "1":
        order = get_order(request_id)
        if order:
            cog = bot.get_cog("BuildCardSystem")
            if cog: bot.loop.create_task(cog.process_auto_success(order))
    return {"status": 1}

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
    serial = discord.ui.TextInput(label="SERIAL", placeholder="Nhập số seri...")
    code = discord.ui.TextInput(label="MÃ THẺ", placeholder="Nhập mã thẻ...")

    def __init__(self, telco, amount, order_id):
        super().__init__()
        self.telco, self.amount, self.order_id = telco, amount, order_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("⏳ Đang gửi thẻ...", ephemeral=True)
        sign = hashlib.md5((PARTNER_KEY + self.code.value + self.serial.value).encode()).hexdigest()
        params = {"partner_id": PARTNER_ID, "request_id": self.order_id, "telco": self.telco, "code": self.code.value, "serial": self.serial.value, "amount": self.amount, "command": "charging", "sign": sign}
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL, params=params) as resp:
                result = await resp.json()
                msg = "✅ Đã nhận thẻ! Đang chờ duyệt." if str(result.get("status")) in ["1", "99"] else f"❌ Lỗi: {result.get('message')}"
                await interaction.followup.send(msg, ephemeral=True)

if __name__ == "__main__":
    threading.Thread(target=lambda: uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080))), daemon=True).start()
    async def run():
        await bot.load_extension("thuebuildcard_system")
        await bot.start(TOKEN)
    asyncio.run(run())
