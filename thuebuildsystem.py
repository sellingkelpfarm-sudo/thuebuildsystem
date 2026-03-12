import discord
from discord.ext import commands
import asyncio
import random
import string
import urllib.parse
import re  # Sử dụng Regex để quét mã đơn cực nhạy

# --- CẤU HÌNH ID ---
BANK_CHANNEL_ID = 1479440469120389221         
ADMIN_TRACKING_CHANNEL_ID = 1481705972325154939 

# Lưu trữ đơn đang chờ trong RAM
bank_waiting = {}

class BuildPaymentView(discord.ui.View):
    def __init__(self, price, order_code, bot):
        super().__init__(timeout=None)
        self.price = price
        self.code = order_code # Ví dụ: BUILD-2649
        self.bot = bot
        self.info = f"BUILD{order_code.split('-')[1]}" # Nội dung QR: BUILD2649

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
        embed.set_footer(text="Hệ thống tự động xác nhận sau khi nhận biến động số dư.")
        
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        while seconds_left > 0:
            if self.code not in bank_waiting: return # Dừng đếm nếu đã trả tiền

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
            try: await msg.edit(embed=new_embed)
            except: break

        if self.code in bank_waiting:
            del bank_waiting[self.code]
            await msg.edit(content="❌ Đơn hàng đã hết hạn thanh toán.", embed=None)

class BuildSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="thuebuild")
    @commands.has_permissions(administrator=True)
    async def thuebuild(self, ctx, price: int):
        random_id = ''.join(random.choices(string.digits, k=4))
        order_code = f"BUILD-{random_id}"
        
        target_user = next((m for m in ctx.channel.members if not m.bot and not m.guild_permissions.administrator), ctx.author)
        bank_waiting[order_code] = {"channel": ctx.channel.id, "price": price, "user": target_user.id}
        
        embed = discord.Embed(
            title="🏗️ XÁC NHẬN THUÊ BUILD",
            description=f"🆔 **Mã đơn:** `{order_code}`\n💰 **Giá:** `{price:,} VND`",
            color=0x3498DB
        )
        await ctx.send(content=target_user.mention, embed=embed, view=BuildPaymentView(price, order_code, self.bot))

    @commands.Cog.listener()
    async def on_message(self, message):
        # Kiểm tra ID kênh biến động số dư
        if message.author.bot or message.channel.id != BANK_CHANNEL_ID: return
        
        # CHÌA KHÓA: Tìm cụm BUILD + 4 chữ số trong tin nhắn ngân hàng
        match = re.search(r"BUILD(\d{4})", message.content.upper())
        if not match: return

        found_id = match.group(1) # Lấy 4 số, ví dụ: 2649
        full_code = f"BUILD-{found_id}"

        if full_code in bank_waiting:
            data = bank_waiting[full_code]
            channel = self.bot.get_channel(data["channel"])
            
            del bank_waiting[full_code] # Xóa khỏi RAM để dừng đếm ngược
            
            # Thông báo thành công cho khách
            embed_ok = discord.Embed(title="🎉 THANH TOÁN THÀNH CÔNG (TỰ ĐỘNG)", color=0x2ECC71)
            embed_ok.add_field(name="💰 Số tiền", value=f"{data['price']:,} VND")
            embed_ok.add_field(name="🆔 Mã đơn", value=full_code)
            embed_ok.set_footer(text="Hệ thống đã xác nhận giao dịch thành công!")
            
            if channel: await channel.send(content=f"<@{data['user']}>", embed=embed_ok)
            
            # Báo cho Admin
            admin_ch = self.bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
            if admin_ch:
                embed_ad = discord.Embed(title="👷 ĐƠN THUÊ BUILD MỚI", color=0xE67E22)
                embed_ad.add_field(name="Mã", value=full_code); embed_ad.add_field(name="Kênh", value=f"<#{data['channel']}>")
                await admin_ch.send(embed=embed_ad)

            await message.add_reaction("✅")

async def setup(bot):
    await bot.add_cog(BuildSystem(bot))
    
