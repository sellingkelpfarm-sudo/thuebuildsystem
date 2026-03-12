import discord
from discord.ext import commands
import asyncio
import random
import string
import urllib.parse
import re
from datetime import datetime

# --- CẤU HÌNH ID (LouIs hãy kiểm tra kỹ các ID này) ---
BANK_CHANNEL_ID = 1479440469120389221         
ADMIN_TRACKING_CHANNEL_ID = 1481705972325154939 

bank_waiting = {}  # Đơn chờ thanh toán
active_orders = {} # Đơn đang xử lý

class BuildPaymentView(discord.ui.View):
    def __init__(self, price, order_code, bot):
        super().__init__(timeout=None)
        self.price = price
        self.code = order_code 
        self.bot = bot
        self.info = order_code.replace("-", "").upper()

    @discord.ui.button(label="💳 NHẬN THÔNG TIN THANH TOÁN", style=discord.ButtonStyle.green, emoji="💰")
    async def bank(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        button.label = "ĐÃ HIỆN MÃ QR"
        await interaction.message.edit(view=self)

        safe_info = urllib.parse.quote(self.info)
        qr_url = f"https://img.vietqr.io/image/MB-0764495919-compact2.png?amount={self.price}&addInfo={safe_info}"
        
        seconds_left = 300 
        embed = discord.Embed(
            title="💳 HƯỚNG DẪN THANH TOÁN",
            description=(
                f"🏗️ **Sản phẩm:** `Thuê Build`\n"
                f"💰 **Số tiền:** **{self.price:,} VND**\n"
                f"📝 **Nội dung:** `{self.info}`\n\n"
                f"⚠️ *Vui lòng chuyển đúng số tiền và nội dung để hệ thống duyệt tự động.*"
            ),
            color=0xF1C40F
        )
        embed.set_image(url=qr_url)
        embed.set_footer(text=f"Mã sẽ hết hạn sau 5 phút.")
        
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        while seconds_left > 0:
            if self.code not in bank_waiting: return 
            await asyncio.sleep(1)
            seconds_left -= 1
            mins, secs = divmod(seconds_left, 60)
            embed.set_footer(text=f"⏳ Thời gian còn lại: {mins:02d}:{secs:02d}")
            try: await msg.edit(embed=embed)
            except: break

        if self.code in bank_waiting:
            del bank_waiting[self.code]
            await msg.edit(content="❌ Mã thanh toán đã hết hạn.", embed=None)

class BuildSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def confirm_order(self, order_id):
        full_code = f"BUILD-{order_id}"
        if full_code in bank_waiting:
            data = bank_waiting[full_code]
            del bank_waiting[full_code]
            
            # Gửi Webhook cho Admin và lưu ID tin nhắn để xóa sau này [MỚI]
            admin_ch = self.bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
            admin_msg_id = None
            if admin_ch:
                embed_ad = discord.Embed(title="👷 ĐƠN THUÊ BUILD MỚI CẦN XỬ LÝ", color=0xE67E22, timestamp=datetime.now())
                embed_ad.add_field(name="👤 Khách hàng", value=f"<@{data['user']}>", inline=True)
                embed_ad.add_field(name="🆔 Mã đơn", value=f"`{order_id}`", inline=True)
                embed_ad.add_field(name="💰 Doanh thu", value=f"**{data['price']:,} VND**", inline=True)
                embed_ad.add_field(name="📍 Kênh Ticket", value=f"<#{data['channel']}>", inline=False)
                embed_ad.set_footer(text="Dùng lệnh !xong tại ticket để hoàn tất.")
                admin_msg = await admin_ch.send(embed=embed_ad)
                admin_msg_id = admin_msg.id

            # Lưu vào danh sách đơn đang chạy
            active_orders[data["channel"]] = {
                "code": order_id, 
                "user": data["user"], 
                "price": data["price"],
                "admin_msg_id": admin_msg_id # Lưu lại để xóa khi gõ !xong
            }
            
            # Thông báo khách & DMs hóa đơn
            client_chan = self.bot.get_channel(data["channel"])
            if client_chan:
                embed_ok = discord.Embed(title="✅ THANH TOÁN THÀNH CÔNG", color=0x2ECC71)
                embed_ok.description = "Hệ thống đã nhận được tiền. Admin đang chuẩn bị thực hiện build."
                await client_chan.send(content=f"<@{data['user']}>", embed=embed_ok)

            customer = self.bot.get_user(data["user"])
            if customer:
                try:
                    inv = discord.Embed(title="🧾 HÓA ĐƠN DỊCH VỤ", color=0x2ECC71, timestamp=datetime.now())
                    inv.description = f"Bạn đã thanh toán thành công đơn hàng `BUILD-{order_id}`."
                    inv.add_field(name="💰 Số tiền", value=f"{data['price']:,} VND", inline=True)
                    inv.set_footer(text="Cảm ơn bạn đã tin tưởng Schematics Shop!")
                    await customer.send(embed=inv)
                except: pass
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
        
        embed = discord.Embed(title="🏗️ THIẾT LẬP ĐƠN BUILD", color=0x3498DB)
        embed.add_field(name="🆔 Mã đơn", value=f"`{order_code}`", inline=True)
        embed.add_field(name="💰 Giá tiền", value=f"**{price:,} VND**", inline=True)
        await ctx.send(content=target_user.mention, embed=embed, view=BuildPaymentView(price, order_code, self.bot))

    @commands.command(name="dathue")
    @commands.has_permissions(administrator=True)
    async def dathue(self, ctx, order_id: str):
        await ctx.message.delete()
        clean_id = order_id.upper().replace("BUILD-", "").replace("BUILD", "")
        await self.confirm_order(clean_id)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot and message.channel.id != BANK_CHANNEL_ID: return
        if message.channel.id == BANK_CHANNEL_ID:
            content = message.content.upper().replace(" ", "").replace("-", "")
            matches = re.findall(r"BUILD(\d{5})", content)
            if matches:
                if await self.confirm_order(matches[-1]):
                    await message.add_reaction("✅")

    # --- LỆNH HOÀN TẤT (XÓA DÒNG CAM Ở ADMIN) ---
    @commands.command(name="xong")
    @commands.has_permissions(administrator=True)
    async def xong(self, ctx):
        await ctx.message.delete()
        if ctx.channel.id not in active_orders:
            return await ctx.send("❌ Kênh này không có đơn build nào.", delete_after=5)
        
        order_data = active_orders[ctx.channel.id]
        admin_ch = self.bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)

        # 1. XÓA DÒNG THÔNG BÁO CAM TẠI KÊNH ADMIN [CẬP NHẬT]
        if admin_ch and order_data["admin_msg_id"]:
            try:
                old_msg = await admin_ch.fetch_message(order_data["admin_msg_id"])
                await old_msg.delete()
            except: pass

        # 2. Gửi Log đơn đã hoàn tất (Màu xanh lá)
        if admin_ch:
            embed_log = discord.Embed(title="📊 LOG: ĐƠN ĐÃ HOÀN TẤT", color=0x27AE60, timestamp=datetime.now())
            embed_log.add_field(name="🆔 Mã đơn", value=f"`{order_data['code']}`", inline=True)
            embed_log.add_field(name="👷 Người thực hiện", value=ctx.author.mention, inline=True)
            embed_log.add_field(name="💵 Tiền nhận", value=f"**{order_data['price']:,} VND**", inline=False)
            await admin_ch.send(embed=embed_log)

        # 3. Thông báo cho khách và gửi DMs biên lai
        embed_client = discord.Embed(title="🎊 CÔNG TRÌNH HOÀN THÀNH", color=0x00FFFF)
        embed_client.description = "Admin đã bàn giao xong công trình. Hẹn gặp lại bạn lần sau!"
        await ctx.send(content=f"<@{order_data['user']}>", embed=embed_client)

        customer = self.bot.get_user(order_data["user"])
        if customer:
            try:
                done_dm = discord.Embed(title="📦 BIÊN LAI HOÀN TẤT", color=0x2ECC71, timestamp=datetime.now())
                done_dm.description = "Công trình của bạn đã hoàn thành. Cảm ơn bạn đã sử dụng dịch vụ!"
                done_dm.add_field(name="🆔 Mã đơn", value=f"`BUILD-{order_data['code']}`", inline=True)
                await customer.send(embed=done_dm)
            except: pass

        del active_orders[ctx.channel.id]

async def setup(bot):
    await bot.add_cog(BuildSystem(bot))
