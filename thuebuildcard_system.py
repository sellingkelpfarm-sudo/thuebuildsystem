import discord
from discord.ext import commands
import aiohttp
import hashlib
import random
import string
import asyncio
from fastapi import FastAPI, Request
import os
import sqlite3
from datetime import datetime

# --- CẤU HÌNH ---
PARTNER_ID = "86935102540"
PARTNER_KEY = "c63d72291473a68fcbb23261491a103f"
API_URL = "https://gachthe1s.com/chargingws/v2"
SHOP_NAME = "LoTuss's Schematic Shop"
CATEGORY_NAME = "orders-card"
HISTORY_CHANNEL_ID = 1481239066115571885 

app = FastAPI()

# --- DATABASE LOGIC ---
def init_db():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (request_id TEXT PRIMARY KEY, channel_id INTEGER, product TEXT, 
                  user_id INTEGER, amount INTEGER, user_name TEXT)''')
    conn.commit()
    conn.close()

def save_order(request_id, channel_id, product, user_id, amount, user_name):
    conn = sqlite3.connect('orders.db')
    conn.execute("INSERT OR REPLACE INTO orders (request_id, channel_id, product, user_id, amount, user_name) VALUES (?, ?, ?, ?, ?, ?)",
              (request_id, channel_id, product, user_id, amount, user_name))
    conn.commit()
    conn.close()

def get_order(request_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE request_id = ?", (request_id,))
    row = c.fetchone()
    conn.close()
    return {"request_id": row[0], "channel_id": row[1], "product": row[2], "user_id": row[3], "amount": row[4], "user_name": row[5]} if row else None

def delete_order(request_id):
    conn = sqlite3.connect('orders.db')
    conn.execute("DELETE FROM orders WHERE request_id = ?", (request_id,))
    conn.commit()
    conn.close()

init_db()

# --- UI COMPONENTS ---
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
            await interaction.followup.send(f"✅ Gửi thẻ thành công! Đang đợi duyệt đơn `CARD-{self.order_id}`.", ephemeral=True)
            
            embed_ok = discord.Embed(title="✅ ĐÃ NHẬN THẺ", color=0x2ECC71)
            embed_ok.add_field(name="💰 Mệnh giá", value=f"`{self.amount:,} VND`", inline=True)
            embed_ok.add_field(name="🆔 Mã đơn", value=f"`CARD-{self.order_id}`", inline=True)
            embed_ok.description = "Hệ thống đã nhận thông tin thẻ của bạn. Admin đang kiểm tra, vui lòng chờ trong giây lát!"
            embed_ok.set_footer(text=f"Cảm ơn bạn đã lựa chọn {SHOP_NAME}")
            await interaction.channel.send(content=interaction.user.mention, embed=embed_ok)
        else:
            await interaction.followup.send(f"❌ Lỗi: {result.get('message', 'Thẻ không hợp lệ')}", ephemeral=True)

class TelcoSelect(discord.ui.Select):
    def __init__(self, order_id, amount):
        options = [
            discord.SelectOption(label="Viettel (8%)", value="Viettel"),
            discord.SelectOption(label="Garena (11%)", value="Garena"),
            discord.SelectOption(label="Vinaphone (8%)", value="Vinaphone"),
            discord.SelectOption(label="Zing (12%)", value="Zing"),
            discord.SelectOption(label="Mobifone (16%)", value="Mobifone"),
            discord.SelectOption(label="Vcoin (8%)", value="Vcoin"),
            discord.SelectOption(label="Scoin (28%)", value="Scoin")
        ]
        super().__init__(placeholder=f"📡 Chọn nhà mạng (Mệnh giá {amount:,} VND)", options=options)
        self.order_id, self.amount = order_id, amount

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CardModal(self.values[0], self.amount, self.order_id))

class BuyButtonView(discord.ui.View):
    def __init__(self, product, amount):
        super().__init__(timeout=None)
        self.product, self.amount = product, amount

    @discord.ui.button(label="🛒 NẠP THẺ NGAY", style=discord.ButtonStyle.green, emoji="💳")
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        code = ''.join(random.choices(string.digits, k=5))
        save_order(code, interaction.channel.id, self.product, interaction.user.id, self.amount, interaction.user.name)
        
        embed = discord.Embed(title=f"💳 {SHOP_NAME} - XÁC NHẬN ĐƠN THẺ", color=0x3498DB, timestamp=datetime.now())
        embed.add_field(name="📦 Tên hàng", value=f"`{self.product}`", inline=True)
        embed.add_field(name="💰 Số tiền", value=f"**{self.amount:,} VND**", inline=True)
        embed.add_field(name="🆔 Mã đơn", value=f"`CARD-{code}`", inline=False)
        embed.set_footer(text="Vui lòng chọn đúng loại thẻ và mệnh giá.")
        
        view = discord.ui.View().add_item(TelcoSelect(code, self.amount))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class CardSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_card_orders = {}

    @commands.command(name="buildthuecard")
    @commands.has_permissions(administrator=True)
    async def buildthuecard(self, ctx, amount: int):
        await ctx.message.delete()
        product = ctx.channel.name.upper()
        embed = discord.Embed(title="🛒 THANH TOÁN QUA THẺ CÀO", description=f"📦 **Hàng:** `{product}`\n💰 **Giá:** `{amount:,} VND`", color=0x3498DB)
        embed.set_footer(text=f"Cung cấp bởi {SHOP_NAME}")
        await ctx.send(embed=embed, view=BuyButtonView(product, amount))

    @commands.command(name="dathuecard")
    @commands.has_permissions(administrator=True)
    async def dathuecard(self, ctx, request_id: str):
        await ctx.message.delete()
        clean_id = request_id.upper().replace("CARD-", "").strip()
        order = get_order(clean_id)
        if order:
            # 1. Thông báo tại Ticket
            embed_ok = discord.Embed(title="✅ THANH TOÁN THÀNH CÔNG", color=0x2ECC71)
            embed_ok.add_field(name="💰 Số tiền", value=f"`{order['amount']:,} VND`", inline=True)
            embed_ok.add_field(name="🆔 Mã đơn", value=f"`CARD-{clean_id}`", inline=True)
            embed_ok.description = "Admin đã xác nhận nhận thẻ thành công. Đơn hàng đang được thực hiện!"
            await ctx.send(content=f"<@{order['user_id']}>", embed=embed_ok)

            # 2. DMs báo cho khách
            customer = self.bot.get_user(order['user_id'])
            if customer:
                try:
                    dm_inv = discord.Embed(title="🧾 HÓA ĐƠN XÁC NHẬN NẠP THẺ", color=0x2ECC71, timestamp=datetime.now())
                    dm_inv.set_author(name=SHOP_NAME)
                    dm_inv.add_field(name="🆔 Mã hóa đơn", value=f"`CARD-{clean_id}`", inline=True)
                    dm_inv.add_field(name="💰 Tổng nạp", value=f"**{order['amount']:,} VND**", inline=True)
                    dm_inv.add_field(name="🚀 Trạng thái", value="`Đang xử lý` ✅", inline=True)
                    await customer.send(embed=dm_inv)
                except: pass

            self.active_card_orders[ctx.channel.id] = order
        else:
            await ctx.send(f"❌ Không tìm thấy mã đơn `CARD-{clean_id}`.", delete_after=5)

    @commands.command(name="xongcard")
    @commands.has_permissions(administrator=True)
    async def xongcard(self, ctx):
        await ctx.message.delete()
        if ctx.channel.id not in self.active_card_orders:
            return await ctx.send("❌ Kênh này không có đơn nạp thẻ nào đang xử lý.", delete_after=5)
        
        order_data = self.active_card_orders[ctx.channel.id]
        
        # 1. Log cho Admin
        admin_ch = self.bot.get_channel(HISTORY_CHANNEL_ID)
        if admin_ch:
            embed_log = discord.Embed(title="📊 LOG: NẠP THẺ HOÀN TẤT", color=0x27AE60, timestamp=datetime.now())
            embed_log.add_field(name="🆔 Mã đơn", value=f"`CARD-{order_data['request_id']}`", inline=True)
            embed_log.add_field(name="👷 Người duyệt", value=ctx.author.mention, inline=True)
            embed_log.add_field(name="💵 Tổng tiền", value=f"**{order_data['amount']:,} VND**", inline=False)
            await admin_ch.send(embed=embed_log)

        # 2. Thông báo Ticket
        embed_client = discord.Embed(title="🎊 ĐƠN HÀNG ĐÃ HOÀN TẤT!", color=0x00FFFF)
        embed_client.description = "Admin đã bàn giao xong. Cảm ơn bạn đã tin tưởng dịch vụ!"
        embed_client.set_footer(text=f"Cảm ơn bạn đã lựa chọn {SHOP_NAME}")
        await ctx.send(content=f"<@{order_data['user_id']}>", embed=embed_client)

        # 3. Biên lai DM
        customer = self.bot.get_user(order_data["user_id"])
        if customer:
            try:
                dm_done = discord.Embed(title="📦 BIÊN LAI HOÀN TẤT", color=0x2ECC71, timestamp=datetime.now())
                dm_done.add_field(name="🆔 Mã đơn", value=f"`CARD-{order_data['request_id']}`", inline=True)
                dm_done.add_field(name="💰 Tổng tiền", value=f"**{order_data['amount']:,} VND**", inline=True)
                dm_done.set_footer(text="Cảm ơn bạn đã tin tưởng chúng tôi!")
                await customer.send(embed=dm_done)
            except: pass

        delete_order(order_data['request_id'])
        del self.active_card_orders[ctx.channel.id]

# --- CALLBACK ---
@app.api_route("/callback", methods=["GET", "POST"])
async def callback(request: Request):
    return {"status": 1, "message": "success"}

async def setup(bot):
    await bot.add_cog(CardSystem(bot))
