import discord
from discord.ext import commands
import asyncio
import random
import string
import urllib.parse
from datetime import datetime

# --- CẤU HÌNH ID ---
BANK_CHANNEL_ID = 1479440469120389221          
ADMIN_TRACKING_CHANNEL_ID = 1481705972325154939 
SHOP_NAME = "LoTuss's Schematic Shop"

bank_waiting = {}   
active_orders = {}  

class BuildPaymentView(discord.ui.View):
    def __init__(self, price, order_code, bot):
        super().__init__(timeout=None)
        self.price = price
        self.code = order_code 
        self.bot = bot
        self.info = order_code.replace("-", "").upper()

    @discord.ui.button(label="💳 THANH TOÁN BANK", style=discord.ButtonStyle.green, emoji="💰")
    async def bank(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        button.label = "ĐÃ HIỆN MÃ QR"
        await interaction.message.edit(view=self)

        qr_url = f"https://img.vietqr.io/image/MB-0764495999999-qr_only.png?amount={self.price}&addInfo={self.info}"
        
        embed = discord.Embed(title="🏦 CHUYỂN KHOẢN NGÂN HÀNG", color=0x00ff00)
        embed.description = f"Vui lòng chuyển đúng số tiền và nội dung bên dưới."
        embed.add_field(name="👤 Chủ TK", value="`NGUYEN VAN A`", inline=True)
        embed.add_field(name="🔢 STK", value="`0764495999999`", inline=True)
        embed.add_field(name="🏦 Ngân hàng", value="`MB Bank`", inline=True)
        embed.add_field(name="💰 Số tiền", value=f"**{self.price:,} VND**", inline=True)
        embed.add_field(name="📝 Nội dung", value=f"`{self.info}`", inline=True)
        embed.set_image(url=qr_url)
        embed.set_footer(text="Hệ thống sẽ tự động xác nhận sau khi nhận được tiền.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class BuildSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="buildthuebank") # Đã đổi tên lệnh theo yêu cầu
    @commands.has_permissions(administrator=True)
    async def buildthuebank(self, ctx, price: int):
        await ctx.message.delete()
        
        order_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        product_name = ctx.channel.name.replace("-", " ").upper()
        
        embed = discord.Embed(title=f"🏗️ {SHOP_NAME} - DỊCH VỤ BUILD", color=0x3498DB)
        embed.add_field(name="📦 Công trình", value=f"`{product_name}`", inline=False)
        embed.add_field(name="💵 Chi phí", value=f"**{price:,} VND**", inline=True)
        embed.add_field(name="🆔 Mã đơn", value=f"`BUILD-{order_code}`", inline=True)
        embed.set_footer(text="Nhấn nút bên dưới để lấy thông tin thanh toán.")

        view = BuildPaymentView(price, order_code, self.bot)
        msg = await ctx.send(embed=embed, view=view)
        
        bank_waiting[order_code] = {
            "user": ctx.author.id, # Trong thực tế nút bấm sẽ lấy user click, ở đây lưu mặc định
            "price": price,
            "channel": ctx.channel.id,
            "code": order_code,
            "product": product_name
        }

    @commands.command(name="dathuebank") # Đã đổi tên lệnh theo yêu cầu
    @commands.has_permissions(administrator=True)
    async def dathuebank(self, ctx, order_id: str):
        await ctx.message.delete()
        code = order_id.upper().replace("BUILD-", "").strip()
        
        if code in bank_waiting:
            order_data = bank_waiting.pop(code)
            active_orders[ctx.channel.id] = order_data
            
            embed = discord.Embed(title="✅ XÁC NHẬN THANH TOÁN", color=0x2ECC71)
            embed.description = f"Đã nhận thanh toán cho đơn `{order_id}`. Admin đang tiến hành build!"
            await ctx.send(content=f"<@{order_data['user']}>", embed=embed)
            
            # Gửi DM cho khách
            customer = self.bot.get_user(order_data['user'])
            if customer:
                try:
                    dm = discord.Embed(title="🧾 HÓA ĐƠN THANH TOÁN BANK", color=0x2ECC71)
                    dm.add_field(name="🆔 Mã đơn", value=f"`BUILD-{code}`", inline=True)
                    dm.add_field(name="💰 Số tiền", value=f"**{order_data['price']:,} VND**", inline=True)
                    dm.add_field(name="🚀 Trạng thái", value="`Đang xử lý` ✅", inline=False)
                    await customer.send(embed=dm)
                except: pass
        else:
            await ctx.send("❌ Không tìm thấy mã đơn này trong danh sách chờ.", delete_after=5)

    @commands.command(name="xongbank") # Đã đổi tên lệnh theo yêu cầu
    @commands.has_permissions(administrator=True)
    async def xongbank(self, ctx):
        await ctx.message.delete()
        if ctx.channel.id not in active_orders:
            return await ctx.send("❌ Kênh này không có đơn build nào đang xử lý.", delete_after=5)
            
        order_data = active_orders.pop(ctx.channel.id)
        
        # Thông báo tại kênh
        embed = discord.Embed(title="🎊 HOÀN TẤT CÔNG TRÌNH", color=0x00FFFF)
        embed.description = "Dịch vụ đã hoàn tất. Cảm ơn bạn đã ủng hộ shop!"
        await ctx.send(content=f"<@{order_data['user']}>", embed=embed)
        
        # Gửi biên lai DM
        customer = self.bot.get_user(order_data['user'])
        if customer:
            try:
                dm = discord.Embed(title="📦 BIÊN LAI BÀN GIAO", color=0x2ECC71)
                dm.add_field(name="🆔 Mã đơn", value=f"`BUILD-{order_data['code']}`", inline=True)
                dm.add_field(name="💰 Tổng tiền", value=f"**{order_data['price']:,} VND**", inline=True)
                await customer.send(embed=dm)
            except: pass

async def setup(bot):
    await bot.add_cog(BuildSystem(bot))
