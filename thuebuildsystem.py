import discord
from discord.ext import commands
import asyncio
import random
import string
import urllib.parse
from datetime import datetime

# --- CẤU HÌNH ID (LOU IS KIỂM TRA KỸ TẠI ĐÂY) ---
BANK_CHANNEL_ID = 1479440469120389221         # Kênh nhận tin nhắn biến động số dư
ADMIN_TRACKING_CHANNEL_ID = 1481705972325154939 # Kênh báo cho Admin khi có người trả tiền

# Lưu trữ đơn đang chờ trong bộ nhớ tạm (RAM)
bank_waiting = {}

class BuildPaymentView(discord.ui.View):
    def __init__(self, price, order_code, bot):
        super().__init__(timeout=None)
        self.price = price
        self.code = order_code
        self.bot = bot
        # Nội dung chuyển khoản viết liền: BUILDxxxx
        self.info = f"BUILD{order_code.split('-')[1]}" 

    @discord.ui.button(label="💳 CHUYỂN KHOẢN", style=discord.ButtonStyle.green)
    async def bank(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        button.label = "ĐÃ HIỆN MÃ QR"
        await interaction.message.edit(view=self)

        safe_info = urllib.parse.quote(self.info)
        qr_url = f"https://img.vietqr.io/image/MB-0764495919-compact2.png?amount={self.price}&addInfo={safe_info}"
        
        # --- LOGIC ĐẾM NGƯỢC TỪNG GIÂY ---
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
        embed.set_footer(text="Hệ thống sẽ tự động xác nhận sau khi nhận được tiền.")
        
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        while seconds_left > 0:
            # Nếu đơn đã được duyệt thành công thì dừng đếm
            if self.code not in bank_waiting:
                return

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
                break # Thoát nếu tin nhắn bị xóa thủ công

        # Xử lý khi hết thời gian 5 phút mà chưa thanh toán
        if self.code in bank_waiting:
            del bank_waiting[self.code]
            timeout_embed = discord.Embed(
                title="❌ MÃ THANH TOÁN HẾT HẠN", 
                description="Đơn hàng đã bị hủy tự động sau 5 phút. Vui lòng tạo đơn mới.", 
                color=0xFF0000
            )
            await msg.edit(embed=timeout_embed)

class BuildSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="thuebuild")
    @commands.has_permissions(administrator=True)
    async def thuebuild(self, ctx, price: int):
        random_id = ''.join(random.choices(string.digits, k=4))
        order_code = f"BUILD-{random_id}"
        
        # Tìm khách hàng trong kênh (người không phải bot/admin)
        target_user = next((m for m in ctx.channel.members if not m.bot and not m.guild_permissions.administrator), ctx.author)

        # Lưu thông tin vào RAM
        bank_waiting[order_code] = {"channel": ctx.channel.id, "price": price, "user": target_user.id}
        
        embed = discord.Embed(
            title="🏗️ XÁC NHẬN THUÊ BUILD",
            description=f"Chào {target_user.mention}! Admin đã tạo đơn thuê build cho bạn.\n\n"
                        f"🆔 **Mã đơn:** `{order_code}`\n"
                        f"💰 **Giá tiền:** `{price:,} VND`",
            color=0x3498DB
        )
        await ctx.send(content=target_user.mention, embed=embed, view=BuildPaymentView(price, order_code, self.bot))

    @commands.Cog.listener()
    async def on_message(self, message):
        # 1. Chỉ quét tin nhắn tại kênh biến động số dư chuẩn
        if message.author.bot or message.channel.id != BANK_CHANNEL_ID: 
            return
        
        # 2. Xóa sạch dấu cách/gạch ngang/dấu thăng để so khớp chuẩn BUILDxxxx
        bank_msg = message.content.upper().replace(" ", "").replace("-", "").replace("#", "")
        
        matched_code = None
        for code in list(bank_waiting.keys()):
            # Chuyển BUILD-8102 thành BUILD8102 để tìm trong nội dung bank
            clean_waiting_code = code.replace("-", "").upper()
            if clean_waiting_code in bank_msg:
                matched_code = code
                break
        
        if matched_code:
            data = bank_waiting[matched_code]
            channel = self.bot.get_channel(data["channel"])
            
            # Xóa đơn khỏi danh sách chờ để dừng đếm ngược ngay lập tức
            del bank_waiting[matched_code]
            
            # Gửi thông báo thành công cho khách hàng
            embed_ok = discord.Embed(title="🎉 THANH TOÁN THÀNH CÔNG (TỰ ĐỘNG)", color=0x2ECC71)
            embed_ok.add_field(name="💰 Số tiền", value=f"{data['price']:,} VND")
            embed_ok.add_field(name="🆔 Mã đơn", value=matched_code)
            embed_ok.add_field(name="📥 Ghi chú", value="Hệ thống đã xác nhận tiền. Admin sẽ bắt đầu build sớm nhất!", inline=False)
            
            if channel: 
                await channel.send(content=f"<@{data['user']}>", embed=embed_ok)
            
            # Gửi thông báo cho Admin
            admin_ch = self.bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
            if admin_ch:
                embed_ad = discord.Embed(title="👷 ĐƠN THUÊ BUILD MỚI", color=0xE67E22)
                embed_ad.add_field(name="Khách hàng", value=f"<@{data['user']}>", inline=True)
                embed_ad.add_field(name="🆔 Mã đơn", value=f"`{matched_code}`", inline=True)
                embed_ad.add_field(name="📍 Kênh Ticket", value=f"<#{data['channel']}>", inline=True)
                await admin_ch.send(embed=embed_ad)

            await message.add_reaction("✅")

async def setup(bot):
    await bot.add_cog(BuildSystem(bot))
