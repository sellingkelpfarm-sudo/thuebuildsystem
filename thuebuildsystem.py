import discord
from discord.ext import commands
import asyncio
import random
import string
import urllib.parse
import re

# --- CẤU HÌNH ID ---
BANK_CHANNEL_ID = 1479440469120389221         
ADMIN_TRACKING_CHANNEL_ID = 1481705972325154939 

# Lưu trữ đơn đang chờ trong RAM (giữ đơn tạm thời khi bot đang chạy)
bank_waiting = {}

class BuildPaymentView(discord.ui.View):
    def __init__(self, price, order_code, bot):
        super().__init__(timeout=None)
        self.price = price
        self.code = order_code # Ví dụ: BUILD-08102
        self.bot = bot
        # Nội dung chuyển khoản gọn sạch: BUILD08102
        self.info = order_code.replace("-", "").upper()

    @discord.ui.button(label="💳 CHUYỂN KHOẢN", style=discord.ButtonStyle.green)
    async def bank(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        button.label = "ĐÃ HIỆN MÃ QR"
        await interaction.message.edit(view=self)

        safe_info = urllib.parse.quote(self.info)
        qr_url = f"https://img.vietqr.io/image/MB-0764495919-compact2.png?amount={self.price}&addInfo={safe_info}"
        
        # --- ĐẾM NGƯỢC 5 PHÚT TỪNG GIÂY ---
        seconds_left = 300 
        embed = discord.Embed(
            title="💳 THANH TOÁN CHUYỂN KHOẢN",
            description=(
                f"🏗️ **Sản phẩm:** `Thuê Build`\n"
                f"💰 **Số tiền:** **{self.price:,} VND**\n"
                f"📝 **Nội dung:** `{self.info}`\n\n"
                f"⏳ **Thời gian còn lại:** `05:00`"
            ),
            color=0xF1C40F
        )
        embed.set_image(url=qr_url)
        embed.set_footer(text="Hệ thống sẽ xác nhận tự động sau khi nhận tiền.")
        
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        while seconds_left > 0:
            if self.code not in bank_waiting: 
                return # Đơn đã được duyệt, thoát vòng lặp ngay

            await asyncio.sleep(1)
            seconds_left -= 1
            mins, secs = divmod(seconds_left, 60)
            
            new_embed = embed.copy()
            new_embed.description = (
                f"🏗️ **Sản phẩm:** `Thuê Build`\n"
                f"💰 **Số tiền:** **{self.price:,} VND**\n"
                f"📝 **Nội dung:** `{self.info}`\n\n"
                f"⏳ **Thời gian còn lại:** `{mins:02d}:{secs:02d}`"
            )
            try:
                await msg.edit(embed=new_embed)
            except: 
                break

        if self.code in bank_waiting:
            del bank_waiting[self.code]
            timeout_embed = discord.Embed(title="❌ HẾT HẠN", description="Mã thanh toán đã hết hạn 5 phút.", color=0xFF0000)
            await msg.edit(embed=timeout_embed)

class BuildSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="thuebuild")
    @commands.has_permissions(administrator=True)
    async def thuebuild(self, ctx, price: int):
        # 1. Tạo mã 5 con số như bạn yêu cầu
        random_id = ''.join(random.choices(string.digits, k=5))
        order_code = f"BUILD-{random_id}"
        
        target_user = next((m for m in ctx.channel.members if not m.bot and not m.guild_permissions.administrator), ctx.author)
        bank_waiting[order_code] = {"channel": ctx.channel.id, "price": price, "user": target_user.id}
        
        embed = discord.Embed(title="🏗️ XÁC NHẬN THUÊ BUILD", color=0x3498DB)
        embed.description = f"Chào {target_user.mention}! Đơn hàng của bạn đã sẵn sàng."
        embed.add_field(name="🆔 Mã đơn (5 số)", value=f"`{order_code}`", inline=False)
        embed.add_field(name="💰 Giá tiền", value=f"`{price:,} VND`", inline=False)
        
        await ctx.send(content=target_user.mention, embed=embed, view=BuildPaymentView(price, order_code, self.bot))

    @commands.Cog.listener()
    async def on_message(self, message):
        # Kiểm tra ID kênh ngân hàng
        if message.channel.id != BANK_CHANNEL_ID: return
        
        # Làm sạch tin nhắn để quét
        content = message.content.upper().replace(" ", "").replace("-", "").replace("#", "")
        
        # 2. Tìm mã BUILD + 5 con số trong tin nhắn
        match = re.search(r"BUILD(\d{5})", content)
        if not match: return

        found_num = match.group(1)
        full_waiting_code = f"BUILD-{found_num}"

        if full_waiting_code in bank_waiting:
            data = bank_waiting[full_waiting_code]
            channel = self.bot.get_channel(data["channel"])
            
            # Xóa khỏi danh sách chờ để dừng đếm ngược
            del bank_waiting[full_waiting_code] 
            
            # Gửi thông báo thành công cho khách
            embed_ok = discord.Embed(title="🎉 THANH TOÁN THÀNH CÔNG (TỰ ĐỘNG)", color=0x2ECC71)
            embed_ok.description = "Hệ thống đã xác nhận giao dịch thành công!"
            embed_ok.add_field(name="💰 Số tiền", value=f"{data['price']:,} VND", inline=True)
            embed_ok.add_field(name="🆔 Mã đơn", value=found_num, inline=True)
            embed_ok.add_field(name="📥 Ghi chú", value="Admin đã nhận được tiền và đang chuẩn bị build.", inline=False)
            
            if channel: await channel.send(content=f"<@{data['user']}>", embed=embed_ok)
            
            # Báo cho Admin
            admin_ch = self.bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
            if admin_ch:
                embed_ad = discord.Embed(title="👷 ĐƠN THUÊ BUILD MỚI", color=0xE67E22)
                embed_ad.add_field(name="Mã đơn", value=f"`{found_num}`")
                embed_ad.add_field(name="Kênh Ticket", value=f"<#{data['channel']}>")
                await admin_ch.send(embed=embed_ad)

            await message.add_reaction("✅")

async def setup(bot):
    await bot.add_cog(BuildSystem(bot))
