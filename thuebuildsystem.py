import discord
from discord.ext import commands
import asyncio
import sqlite3
import os
import random
import string
import urllib.parse
from datetime import datetime

# --- CẤU HÌNH ID ---
BANK_CHANNEL_ID = 1479440469120389221         
PAYMENT_LOG_CHANNEL_ID = 1481239066115571885   
ADMIN_TRACKING_CHANNEL_ID = 1481705972325154939 
FEEDBACK_CHANNEL_MENTION = "<#1481245879607492769>"

bank_waiting = {}

def init_db():
    conn = sqlite3.connect('build_orders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS waiting_builds 
                 (code TEXT PRIMARY KEY, channel_id INTEGER, product TEXT, price INTEGER, user_id INTEGER, status INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def db_update_status(code, status):
    conn = sqlite3.connect('build_orders.db')
    conn.execute("UPDATE waiting_builds SET status = ? WHERE code = ?", (status, code))
    conn.commit()
    conn.close()

init_db()

class BuildPaymentView(discord.ui.View):
    def __init__(self, price, order_code, customer_name):
        super().__init__(timeout=None)
        self.price = price
        self.code = order_code
        # Cập nhật nội dung chuyển khoản viết liền không dấu
        self.info = f"BUILD{order_code.split('-')[1]}" 

    @discord.ui.button(label="💳 CHUYỂN KHOẢN", style=discord.ButtonStyle.green)
    async def bank(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        button.label = "ĐÃ HIỆN MÃ QR"
        await interaction.message.edit(view=self)

        safe_info = urllib.parse.quote(self.info)
        qr_url = f"https://img.vietqr.io/image/MB-0764495919-compact2.png?amount={self.price}&addInfo={safe_info}"
        
        embed = discord.Embed(
            title="💳 THANH TOÁN CHUYỂN KHOẢN",
            description=(
                f"🏗️ **Sản phẩm:** `Thuê Build`\n"
                f"💰 **Số tiền:** **{self.price:,} VND**\n"
                f"📝 **Nội dung:** `{self.info}`\n\n"
                f"📌 *Vui lòng quét mã QR bên dưới để thanh toán.*"
            ),
            color=0xF1C40F
        )
        embed.set_image(url=qr_url)
        embed.set_footer(text="Hệ thống sẽ tự động xác nhận sau khi nhận được tiền.")
        await interaction.response.send_message(embed=embed, ephemeral=False)

class BuildSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="thuebuild")
    @commands.has_permissions(administrator=True)
    async def thuebuild(self, ctx, price: int):
        channel_name = ctx.channel.name
        random_id = ''.join(random.choices(string.digits, k=4))
        order_code = f"BUILD-{random_id}"
        
        customer_name = channel_name.split('-')[1] if '-' in channel_name else channel_name
        
        target_user = None
        for m in ctx.channel.members:
            if not m.bot and not m.guild_permissions.administrator:
                target_user = m; break
        
        if not target_user: target_user = ctx.author

        bank_waiting[order_code] = {"channel": ctx.channel.id, "price": price, "user": target_user.id}
        
        conn = sqlite3.connect('build_orders.db')
        conn.execute("INSERT OR REPLACE INTO waiting_builds VALUES (?, ?, ?, ?, ?, ?)", 
                     (order_code, ctx.channel.id, f"Thuê Build ({customer_name})", price, target_user.id, 0))
        conn.commit()
        conn.close()

        embed = discord.Embed(
            title="🏗️ XÁC NHẬN THUÊ BUILD",
            description=f"Chào {target_user.mention}! Admin đã tạo đơn thuê build cho bạn.\n\n"
                        f"🆔 **Mã đơn:** `{order_code}`\n"
                        f"👤 **Khách hàng:** `{customer_name}`\n"
                        f"💰 **Giá tiền:** `{price:,} VND` \n"
                        f"📝 **Nội dung CK:** `BUILD{random_id}`",
            color=0x3498DB
        )
        await ctx.send(content=target_user.mention, embed=embed, view=BuildPaymentView(price, order_code, customer_name))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.channel.id != BANK_CHANNEL_ID: return
        
        # Xử lý tin nhắn ngân hàng: Xóa hết khoảng trắng và ký tự đặc biệt
        content = message.content.upper().replace(" ", "").replace("-", "").replace("#", "")
        
        matched_code = None
        for code in list(bank_waiting.keys()):
            # So sánh với mã đã xóa dấu gạch ngang (BUILD8064)
            clean_code = code.upper().replace("-", "")
            if clean_code in content:
                matched_code = code
                break
        
        if matched_code:
            data = bank_waiting[matched_code]
            channel = self.bot.get_channel(data["channel"])
            
            embed_success = discord.Embed(
                title="🎉 THANH TOÁN THÀNH CÔNG (TỰ ĐỘNG)",
                description="Hệ thống đã xác nhận giao dịch qua biến động số dư!",
                color=0x2ECC71
            )
            embed_success.add_field(name="💰 Số tiền", value=f"{data['price']:,} VND")
            embed_success.add_field(name="🆔 Mã đơn", value=matched_code)
            embed_success.add_field(name="📥 Ghi chú", value="Admin đã nhận được tiền và đang bắt đầu build. Vui lòng đợi nhé!", inline=False)
            
            if channel: await channel.send(content=f"<@{data['user']}>", embed=embed_success)
            
            admin_ch = self.bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
            if admin_ch:
                time_now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                embed_admin = discord.Embed(title="👷 ĐƠN THUÊ BUILD MỚI", color=0xE67E22)
                embed_admin.add_field(name="👤 Khách", value=f"<@{data['user']}>", inline=True)
                embed_admin.add_field(name="💰 Giá", value=f"`{data['price']:,} VND`", inline=True)
                embed_admin.add_field(name="🆔 Mã đơn", value=f"`{matched_code}`", inline=True)
                embed_admin.add_field(name="📍 Kênh", value=f"<#{data['channel']}>", inline=True)
                embed_admin.add_field(name="🔗 Link", value=f"[Bay tới kênh](https://discord.com/channels/{message.guild.id}/{data['channel']})", inline=True)
                await admin_ch.send(embed=embed_admin)

            db_update_status(matched_code, 1)
            del bank_waiting[matched_code]
            await message.add_reaction("✅")

    @commands.command(name="dabank")
    @commands.has_permissions(administrator=True)
    async def dabank(self, ctx, code: str):
        code = code.upper()
        if code in bank_waiting:
            data = bank_waiting[code]
            channel = self.bot.get_channel(data["channel"])
            embed_success = discord.Embed(title="🎉 THANH TOÁN THÀNH CÔNG (ADMIN DUYỆT)", color=0x2ECC71)
            embed_success.add_field(name="💰 Số tiền", value=f"{data['price']:,} VND")
            embed_success.add_field(name="🆔 Mã đơn", value=code)
            embed_success.add_field(name="📥 Ghi chú", value="Admin đã nhận được tiền và đang bắt đầu build. Vui lòng đợi nhé!", inline=False)
            if channel: await channel.send(content=f"<@{data['user']}>", embed=embed_success)
            db_update_status(code, 1)
            del bank_waiting[code]
            await ctx.send(f"✅ Đã duyệt đơn `{code}`")

    @commands.command(name="xong")
    @commands.has_permissions(administrator=True)
    async def xong(self, ctx):
        conn = sqlite3.connect('build_orders.db')
        row = conn.execute("SELECT code, user_id FROM waiting_builds WHERE channel_id = ? AND status = 1", (ctx.channel.id,)).fetchone()
        if row:
            order_code, user_id = row
            embed_done = discord.Embed(title="✅ DỰ ÁN HOÀN TẤT!", description=f"Đơn thuê build **{order_code}** đã hoàn thành!\nCảm ơn <@{user_id}> đã ủng hộ shop.", color=0x2ECC71)
            await ctx.send(content=f"<@{user_id}>", embed=embed_done)
            db_update_status(order_code, 2)
            conn.close()
        else:
            await ctx.send("❌ Đơn chưa thanh toán hoặc không tồn tại!", delete_after=5)

async def setup(bot):
    await bot.add_cog(BuildSystem(bot))
