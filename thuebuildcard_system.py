import discord
from discord.ext import commands, tasks
import aiohttp
import hashlib
import random
import string
import asyncio
import uvicorn
from fastapi import FastAPI, Request
import threading
from datetime import datetime

# --- CẤU HÌNH HỆ THỐNG ---
ADMIN_TRACKING_CHANNEL_ID = 1481705972325154939 
LOG_CHANNEL_ID = 1479880771274674259 
SHOP_NAME = "LoTuss's Schematic Shop"

# --- THÔNG TIN API GACHTHE1S ---
PARTNER_ID = "95904113535"
PARTNER_KEY = "349afaff71cbd86fd48c6a83421071b2"
API_URL = "https://gachthe1s.com/chargingws/v2"

# Quản lý đơn hàng
card_waiting = {}       # Đang chờ nạp: {order_id: {channel, price, user}}
active_build_orders = {} # Đã thanh toán: {channel_id: {code, price, user, admin_msg_id}}

# --- WEB SERVER ĐỂ NHẬN CALLBACK ---
app = FastAPI()

@app.api_route("/callback", methods=["GET", "POST"])
async def callback(request: Request):
    data = await request.json() if request.method == "POST" else dict(request.query_params)
    request_id = data.get("request_id")
    status = str(data.get("status"))
    
    cog = bot_instance.get_cog("BuildCardSystem")
    if cog:
        asyncio.run_coroutine_threadsafe(cog.log_card_status(data), bot_instance.loop)
        if status == "1":
            asyncio.run_coroutine_threadsafe(cog.confirm_build_card_order(request_id), bot_instance.loop)
            
    return {"status": 200}

def run_server():
    import os
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

# --- GIAO DIỆN DISCORD ---

class CardPaymentModal(discord.ui.Modal, title="💳 Nhập thông tin thẻ cào"):
    serial = discord.ui.TextInput(label="SỐ SERIAL", placeholder="Nhập số serial...")
    code = discord.ui.TextInput(label="MÃ THẺ", placeholder="Nhập mã số sau lớp cào...")

    def __init__(self, telco, amount, order_id):
        super().__init__()
        self.telco = telco
        self.amount = amount
        self.order_id = order_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("⏳ Đang gửi thẻ lên hệ thống...", ephemeral=True)
        sign_str = PARTNER_KEY + self.code.value + self.serial.value
        sign = hashlib.md5(sign_str.encode()).hexdigest()
        
        params = {
            "partner_id": PARTNER_ID,
            "request_id": self.order_id,
            "telco": self.telco.upper(),
            "code": self.code.value,
            "serial": self.serial.value,
            "amount": self.amount,
            "command": "charging",
            "sign": sign
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL, params=params) as resp:
                try:
                    res_data = await resp.json()
                    if str(res_data.get("status")) in ["1", "99"]:
                        await interaction.followup.send("✅ Gửi thẻ thành công! Hệ thống sẽ tự duyệt sau ít phút.", ephemeral=True)
                    else:
                        await interaction.followup.send(f"❌ Lỗi: {res_data.get('message')}", ephemeral=True)
                except:
                    await interaction.followup.send("❌ Lỗi kết nối API GachThe1S.", ephemeral=True)

class TelcoSelect(discord.ui.Select):
    def __init__(self, order_id, amount):
        options = [
            discord.SelectOption(label="Viettel", value="VIETTEL"),
            discord.SelectOption(label="Garena", value="GARENA"),
            discord.SelectOption(label="Vinaphone", value="VINAPHONE"),
            discord.SelectOption(label="Zing", value="ZING"),
            discord.SelectOption(label="Mobifone", value="MOBIFONE"),
            discord.SelectOption(label="Vcoin", value="VCOIN"),
            discord.SelectOption(label="Scoin", value="SCOIN")
        ]
        super().__init__(placeholder="📡 Chọn nhà mạng", options=options)
        self.order_id = order_id
        self.amount = amount

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CardPaymentModal(self.values[0], self.amount, self.order_id))

class BuildCardPaymentView(discord.ui.View):
    def __init__(self, price, order_code):
        super().__init__(timeout=None)
        self.price = price
        self.code = order_code

    @discord.ui.button(label="💳 THANH TOÁN THẺ CÀO", style=discord.ButtonStyle.green, emoji="🎟️")
    async def pay_card(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View()
        view.add_item(TelcoSelect(self.code, self.price))
        await interaction.response.send_message(f"📡 Bạn chọn nạp thẻ **{self.price:,} VND**. Chọn nhà mạng:", view=view, ephemeral=True)

class BuildCardSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        global bot_instance
        bot_instance = bot

    async def log_card_status(self, data):
        channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if not channel: return
        status = str(data.get("status"))
        msg = data.get("message", "Không có nội dung")
        request_id = data.get("request_id")
        amount_real = data.get("value", "0")
        telco = data.get("telco", "N/A")
        if status == "1":
            color = 0x2ecc71
            title = "✅ THẺ ĐÚNG - BIẾN ĐỘNG SỐ DƯ"
        else:
            color = 0xe74c3c
            title = "❌ THẺ SAI / LỖI"
        embed = discord.Embed(title=title, color=color, timestamp=datetime.now())
        embed.add_field(name="🆔 Request ID", value=f"`{request_id}`", inline=False)
        embed.add_field(name="📡 Nhà mạng", value=telco, inline=True)
        embed.add_field(name="💰 Mệnh giá", value=f"{int(amount_real):,} VND", inline=True)
        embed.add_field(name="📝 Nội dung", value=msg, inline=False)
        embed.set_footer(text=SHOP_NAME)
        await channel.send(embed=embed)

    async def confirm_build_card_order(self, full_order_id):
        if full_order_id in card_waiting:
            data = card_waiting[full_order_id]
            del card_waiting[full_order_id]
            admin_ch = self.bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
            admin_msg_id = None
            if admin_ch:
                embed_ad = discord.Embed(title="👷 ĐƠN THUÊ BUILD (CARD) MỚI", color=0xE67E22, timestamp=datetime.now())
                embed_ad.set_author(name=SHOP_NAME)
                embed_ad.add_field(name="👤 Khách hàng", value=f"<@{data['user']}>", inline=True)
                embed_ad.add_field(name="🆔 Mã đơn", value=f"`{full_order_id}`", inline=True)
                embed_ad.add_field(name="💰 Giá thẻ", value=f"**{data['price']:,} VND**", inline=True)
                embed_ad.add_field(name="📍 Kênh", value=f"<#{data['channel']}>", inline=False)
                embed_ad.set_footer(text="Dùng lệnh !xongcard tại ticket khi hoàn tất.")
                admin_msg = await admin_ch.send(embed=embed_ad)
                admin_msg_id = admin_msg.id
            active_build_orders[data["channel"]] = {
                "code": full_order_id, "user": data["user"], "price": data["price"], "admin_msg_id": admin_msg_id
            }
            client_chan = self.bot.get_channel(data["channel"])
            if client_chan:
                embed_ok = discord.Embed(title="✅ THANH TOÁN THẺ CÀO THÀNH CÔNG", color=0x2ECC71)
                embed_ok.description = "Thẻ đã được duyệt. Admin đã nhận đơn và sẽ phản hồi sớm!"
                await client_chan.send(content=f"<@{data['user']}>", embed=embed_ok)

    @commands.command(name="thuebuildcard")
    @commands.has_permissions(administrator=True)
    async def thuebuildcard(self, ctx, price: int):
        await ctx.message.delete()
        random_id = ''.join(random.choices(string.digits, k=5))
        order_code = f"BCARD-{random_id}"
        target_user = next((m for m in ctx.channel.members if not m.bot and not m.guild_permissions.administrator), ctx.author)
        card_waiting[order_code] = {"channel": ctx.channel.id, "price": price, "user": target_user.id}
        embed = discord.Embed(title="🏗️ KHỞI TẠO ĐƠN THUÊ BUILD (CARD)", color=0x3498DB, timestamp=datetime.now())
        embed.set_author(name=SHOP_NAME)
        embed.add_field(name="👤 Khách hàng", value=target_user.mention, inline=True)
        embed.add_field(name="🆔 Mã đơn", value=f"`{order_code}`", inline=True)
        embed.add_field(name="💰 Giá tiền", value=f"**{price:,} VND**", inline=True)
        await ctx.send(content=target_user.mention, embed=embed, view=BuildCardPaymentView(price, order_code))

    @commands.command(name="duyetcard")
    @commands.has_permissions(administrator=True)
    async def duyetcard(self, ctx, order_code: str):
        """Lệnh cho Admin duyệt thủ công nếu thẻ đúng nhưng callback lỗi"""
        if order_code in card_waiting:
            await self.confirm_build_card_order(order_code)
            await ctx.send(f"✅ Đã duyệt thủ công đơn hàng `{order_code}` thành công!", delete_after=5)
            try: await ctx.message.delete()
            except: pass
        else:
            await ctx.send(f"❌ Không tìm thấy mã đơn `{order_code}` trong danh sách chờ.", delete_after=5)

    @commands.command(name="xongcard")
    @commands.has_permissions(administrator=True)
    async def xongcard(self, ctx):
        await ctx.message.delete()
        if ctx.channel.id not in active_build_orders:
            return await ctx.send("❌ Không có đơn build card nào ở kênh này.", delete_after=5)
        order_data = active_build_orders[ctx.channel.id]
        admin_ch = self.bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
        if admin_ch and order_data["admin_msg_id"]:
            try:
                old_msg = await admin_ch.fetch_message(order_data["admin_msg_id"])
                await old_msg.delete()
            except: pass
        if admin_ch:
            embed_log = discord.Embed(title="📊 LOG: HOÀN TẤT ĐƠN BUILD (CARD)", color=0x27AE60, timestamp=datetime.now())
            embed_log.add_field(name="🆔 Mã đơn", value=f"`{order_data['code']}`", inline=True)
            embed_log.add_field(name="👷 Người làm", value=ctx.author.mention, inline=True)
            await admin_ch.send(embed=embed_log)
        embed_client = discord.Embed(title="📦 BÀN GIAO CÔNG TRÌNH", color=0x2ECC71, timestamp=datetime.now())
        embed_client.set_author(name=SHOP_NAME)
        embed_client.add_field(name="🆔 Mã đơn", value=f"`{order_data['code']}`", inline=True)
        embed_client.add_field(name="👷 Admin", value=ctx.author.name, inline=True)
        embed_client.description = "Admin đã bàn giao xong công trình. Hẹn gặp lại bạn lần sau!"
        await ctx.send(content=f"<@{order_data['user']}>", embed=embed_client)
        customer = self.bot.get_user(order_data["user"])
        if customer:
            try:
                dm_done = discord.Embed(title="📦 BIÊN LAI BÀN GIAO", color=0x2ECC71, timestamp=datetime.now())
                dm_done.set_author(name=SHOP_NAME)
                dm_done.add_field(name="🆔 Mã đơn", value=f"`{order_data['code']}`", inline=True)
                dm_done.add_field(name="💰 Tổng tiền", value=f"**{order_data['price']:,} VND**", inline=True)
                dm_done.set_footer(text="Cảm ơn bạn đã tin tưởng dịch vụ của chúng tôi!")
                await customer.send(embed=dm_done)
            except: pass
        del active_build_orders[ctx.channel.id]

async def setup(bot):
    threading.Thread(target=run_server, daemon=True).start()
    await bot.add_cog(BuildCardSystem(bot))
