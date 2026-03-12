import discord
from discord.ext import commands
import asyncio
import random
import string
import urllib.parse
import re
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

    @discord.ui.button(label="💳THANH TOÁN THUÊ BUILD NGAY", style=discord.ButtonStyle.green, emoji="💰")
    async def bank(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        button.label = "ĐÃ HIỆN MÃ QR"
        await interaction.message.edit(view=self)

        safe_info = urllib.parse.quote(self.info)
        qr_url = f"https://img.vietqr.io/image/MB-0764495919-compact2.png?amount={self.price}&addInfo={safe_info}"
        
        embed = discord.Embed(
            title=f"💳 {SHOP_NAME} - THANH TOÁN",
            description="Vui lòng thực hiện chuyển khoản chính xác thông tin để được hệ thống tự động xác nhận.",
            color=0xF1C40F,
            timestamp=datetime.now()
        )
        embed.add_field(name="🏗️ Dịch vụ", value="`Thuê Build Công Trình`", inline=True)
        embed.add_field(name="💰 Tổng số tiền", value=f"**{self.price:,} VND**", inline=True)
        embed.add_field(name="📝 Nội dung bắt buộc", value=f"`{self.info}`", inline=False)
        embed.add_field(name="🛡️ Lưu ý", value="• Hệ thống duyệt tự động trong 30s - 2p.\n• Không đóng ticket khi chưa có xác nhận thành công.", inline=False)
        embed.set_image(url=qr_url)
        embed.set_footer(text=f"Cảm ơn bạn đã lựa chọn {SHOP_NAME}")
        
        await interaction.response.send_message(embed=embed)

class BuildSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def confirm_order(self, order_id):
        full_code = f"BUILD-{order_id}"
        if full_code in bank_waiting:
            data = bank_waiting[full_code]
            del bank_waiting[full_code]
            
            # 1. Thông báo cho Admin (Màu cam)
            admin_ch = self.bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
            admin_msg_id = None
            if admin_ch:
                embed_ad = discord.Embed(title="👷 ĐƠN THUÊ BUILD MỚI CẦN XỬ LÝ", color=0xE67E22, timestamp=datetime.now())
                embed_ad.set_author(name=SHOP_NAME)
                embed_ad.add_field(name="👤 Khách hàng", value=f"<@{data['user']}>", inline=True)
                embed_ad.add_field(name="🆔 Mã đơn", value=f"`{order_id}`", inline=True)
                embed_ad.add_field(name="💰 Doanh thu", value=f"**{data['price']:,} VND**", inline=True)
                embed_ad.add_field(name="📍 Kênh Ticket", value=f"<#{data['channel']}>", inline=False)
                embed_ad.set_footer(text="Dùng lệnh !xong tại ticket sau khi hoàn tất.")
                admin_msg = await admin_ch.send(embed=embed_ad)
                admin_msg_id = admin_msg.id

            active_orders[data["channel"]] = {
                "code": order_id, "user": data["user"], "price": data["price"], "admin_msg_id": admin_msg_id
            }
            
            # 2. Hóa đơn DMs gửi cho khách
            customer = self.bot.get_user(data["user"])
            if customer:
                try:
                    dm_inv = discord.Embed(title="🧾 HÓA ĐƠN XÁC NHẬN DỊCH VỤ", color=0x2ECC71, timestamp=datetime.now())
                    dm_inv.set_author(name=SHOP_NAME)
                    dm_inv.add_field(name="🆔 Mã hóa đơn", value=f"`BUILD-{order_id}`", inline=True)
                    dm_inv.add_field(name="💰 Tổng thanh toán", value=f"**{data['price']:,} VND**", inline=True)
                    dm_inv.add_field(name="🚀 Trạng thái", value="`Đang xử lý` ✅", inline=True)
                    dm_inv.set_footer(text="Hệ thống sẽ thông báo khi công trình hoàn tất.")
                    await customer.send(embed=dm_inv)
                except: pass

            # 3. Thông báo tại Ticket
            client_chan = self.bot.get_channel(data["channel"])
            if client_chan:
                embed_ok = discord.Embed(title="✅ THANH TOÁN THÀNH CÔNG", color=0x2ECC71)
                embed_ok.add_field(name="💰 Số tiền", value=f"`{data['price']:,} VND`", inline=True)
                embed_ok.add_field(name="🆔 Mã đơn", value=f"`{order_id}`", inline=True)
                embed_ok.description = "Admin đang duyệt và sẽ thông báo với bạn sau khi có thời gian nhé"
                await client_chan.send(content=f"<@{data['user']}>", embed=embed_ok)

            return True
        return False

    @commands.command(name="thuebuild")
    @commands.has_permissions(administrator=True)
    async def thuebuild(self, ctx, price: int):
        await ctx.message.delete()
        random_id = ''.join(random.choices(string.digits, k=5))
        order_code = f"BUILD-{random_id}"
        target_user = next((m for m in ctx.channel.members if not m.bot and not m.guild_permissions.administrator), ctx.author)
        bank_waiting[order_code] = {"channel": ctx.channel.id, "price": price, "user": target_user.id}
        
        embed = discord.Embed(title="🏗️ KHỞI TẠO ĐƠN THUÊ BUILD", color=0x3498DB, timestamp=datetime.now())
        embed.set_author(name=SHOP_NAME)
        embed.add_field(name="👤 Khách hàng", value=target_user.mention, inline=True)
        embed.add_field(name="🆔 Mã đơn", value=f"`{order_code}`", inline=True)
        embed.add_field(name="💰 Giá tiền", value=f"**{price:,} VND**", inline=True)
        await ctx.send(content=target_user.mention, embed=embed, view=BuildPaymentView(price, order_code, self.bot))

    @commands.command(name="xong")
    @commands.has_permissions(administrator=True)
    async def xong(self, ctx):
        await ctx.message.delete()
        if ctx.channel.id not in active_orders:
            return await ctx.send("❌ Kênh này không có đơn build nào.", delete_after=5)
        
        order_data = active_orders[ctx.channel.id]
        
        # Xóa dòng cam ở Admin
        admin_ch = self.bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
        if admin_ch and order_data["admin_msg_id"]:
            try:
                old_msg = await admin_ch.fetch_message(order_data["admin_msg_id"])
                await old_msg.delete()
            except: pass

        # Log hoàn tất cho Admin (Màu xanh lá)
        if admin_ch:
            embed_log = discord.Embed(title="📊 LOG: ĐƠN HÀNG ĐÃ HOÀN TẤT", color=0x27AE60, timestamp=datetime.now())
            embed_log.add_field(name="🆔 Mã đơn", value=f"`{order_data['code']}`", inline=True)
            embed_log.add_field(name="👷 Người thực hiện", value=ctx.author.mention, inline=True)
            embed_log.add_field(name="💵 Tiền nhận", value=f"**{order_data['price']:,} VND**", inline=False)
            await admin_ch.send(embed=embed_log)

        # Thông báo tại Ticket
        embed_client = discord.Embed(title="🎊 CÔNG TRÌNH ĐÃ HOÀN THÀNH!", color=0x00FFFF)
        embed_client.set_author(name=SHOP_NAME)
        embed_client.add_field(name="🆔 Mã đơn", value=f"`{order_data['code']}`", inline=True)
        embed_client.add_field(name="👷 Admin", value=ctx.author.name, inline=True)
        embed_client.description = "Admin đã bàn giao xong công trình. Hẹn gặp lại bạn lần sau!"
        await ctx.send(content=f"<@{order_data['user']}>", embed=embed_client)

        # Biên lai DMs cho khách
        customer = self.bot.get_user(order_data["user"])
        if customer:
            try:
                dm_done = discord.Embed(title="📦 BIÊN LAI BÀN GIAO", color=0x2ECC71, timestamp=datetime.now())
                dm_done.set_author(name=SHOP_NAME)
                dm_done.add_field(name="🆔 Mã đơn", value=f"`BUILD-{order_data['code']}`", inline=True)
                dm_done.add_field(name="💰 Tổng tiền", value=f"**{order_data['price']:,} VND**", inline=True)
                dm_done.set_footer(text="Cảm ơn bạn đã tin tưởng dịch vụ của chúng tôi!")
                await customer.send(embed=dm_done)
            except: pass

        del active_orders[ctx.channel.id]

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot and message.channel.id != BANK_CHANNEL_ID: return
        if message.channel.id == BANK_CHANNEL_ID:
            content = message.content.upper().replace(" ", "").replace("-", "")
            matches = re.findall(r"BUILD(\d{5})", content)
            if matches:
                if await self.confirm_order(matches[-1]):
                    await message.add_reaction("✅")

async def setup(bot):
    await bot.add_cog(BuildSystem(bot))

