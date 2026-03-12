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

bank_waiting = {}  # Đơn đang chờ thanh toán
active_orders = {} # Đơn đã thanh toán, đang build

class BuildPaymentView(discord.ui.View):
    def __init__(self, price, order_code, bot):
        super().__init__(timeout=None)
        self.price = price
        self.code = order_code 
        self.bot = bot
        self.info = order_code.replace("-", "").upper()

    @discord.ui.button(label="💳 HIỆN MÃ QR", style=discord.ButtonStyle.green)
    async def bank(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        button.label = "ĐÃ QUÉT MÃ"
        await interaction.message.edit(view=self)

        safe_info = urllib.parse.quote(self.info)
        qr_url = f"https://img.vietqr.io/image/MB-0764495919-compact2.png?amount={self.price}&addInfo={safe_info}"
        
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
        embed.set_footer(text="Hệ thống xác nhận tự động sau khi nhận biến động số dư.")
        
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        while seconds_left > 0:
            if self.code not in bank_waiting: return 
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
            await msg.edit(content="❌ Mã thanh toán đã hết hạn.", embed=None)

class BuildSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def confirm_order(self, order_id, is_manual=False):
        """Hàm xử lý chung khi đơn hàng được xác nhận (tự động hoặc thủ công)"""
        full_code = f"BUILD-{order_id}"
        if full_code in bank_waiting:
            data = bank_waiting[full_code]
            del bank_waiting[full_code]
            active_orders[data["channel"]] = {"code": order_id, "user": data["user"], "price": data["price"]}
            
            # Thông báo cho khách
            client_chan = self.bot.get_channel(data["channel"])
            if client_chan:
                title = "🎉 XÁC NHẬN THANH TOÁN" if is_manual else "🎉 THANH TOÁN THÀNH CÔNG (TỰ ĐỘNG)"
                embed_ok = discord.Embed(title=title, color=0x2ECC71)
                embed_ok.add_field(name="💰 Số tiền", value=f"{data['price']:,} VND", inline=True)
                embed_ok.add_field(name="🆔 Mã đơn", value=order_id, inline=True)
                embed_ok.add_field(name="📥 Ghi chú", value="Admin đã nhận được tiền và đang sắp xếp thời gian build cho bạn ngay khi có thông báo mới nhé!", inline=False)
                await client_chan.send(content=f"<@{data['user']}>", embed=embed_ok)

            # Gửi Webhook cho Admin
            admin_ch = self.bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
            if admin_ch:
                embed_ad = discord.Embed(title="👷 ĐƠN THUÊ BUILD MỚI", color=0xE67E22, timestamp=datetime.now())
                embed_ad.add_field(name="👤 Khách hàng", value=f"<@{data['user']}>", inline=True)
                embed_ad.add_field(name="🆔 Mã đơn", value=f"`{order_id}`", inline=True)
                embed_ad.add_field(name="💰 Doanh thu", value=f"**{data['price']:,} VND**", inline=True)
                embed_ad.add_field(name="📍 Kênh Ticket", value=f"<#{data['channel']}>", inline=True)
                embed_ad.set_footer(text="Dùng lệnh !xong tại ticket để bàn giao.")
                await admin_ch.send(embed=embed_ad)
            return True
        return False

    @commands.command(name="thuebuild")
    @commands.has_permissions(administrator=True)
    async def thuebuild(self, ctx, price: int):
        random_id = ''.join(random.choices(string.digits, k=5))
        order_code = f"BUILD-{random_id}"
        target_user = next((m for m in ctx.channel.members if not m.bot and not m.guild_permissions.administrator), ctx.author)
        bank_waiting[order_code] = {"channel": ctx.channel.id, "price": price, "user": target_user.id}
        
        embed = discord.Embed(title="🏗️ XÁC NHẬN THUÊ BUILD", color=0x3498DB)
        embed.add_field(name="🆔 Mã đơn", value=f"`{order_code}`", inline=True)
        embed.add_field(name="💰 Giá tiền", value=f"**{price:,} VND**", inline=True)
        await ctx.send(content=target_user.mention, embed=embed, view=BuildPaymentView(price, order_code, self.bot))

    # --- LỆNH DUYỆT THỦ CÔNG: !dathue <mã đơn> ---
    @commands.command(name="dathue")
    @commands.has_permissions(administrator=True)
    async def dathue(self, ctx, order_id: str):
        # Làm sạch mã đơn nếu LouIs gõ cả chữ "BUILD-"
        clean_id = order_id.upper().replace("BUILD-", "").replace("BUILD", "")
        success = await self.confirm_order(clean_id, is_manual=True)
        
        if success:
            await ctx.message.add_reaction("✅")
            await ctx.send(f"✅ Đã duyệt thủ công đơn hàng `BUILD-{clean_id}` thành công!")
        else:
            await ctx.send(f"❌ Không tìm thấy đơn hàng nào có mã `{order_id}` đang chờ thanh toán.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot and message.channel.id != BANK_CHANNEL_ID: return
        
        if message.channel.id == BANK_CHANNEL_ID:
            content = message.content.upper().replace(" ", "").replace("-", "").replace("#", "")
            matches = re.findall(r"BUILD(\d{5})", content)
            if matches:
                found_num = matches[-1]
                if await self.confirm_order(found_num):
                    await message.add_reaction("✅")

    @commands.command(name="xong")
    @commands.has_permissions(administrator=True)
    async def xong(self, ctx):
        if ctx.channel.id not in active_orders:
            return await ctx.send("❌ Kênh này không có đơn build nào cần xử lý.")
        
        order_data = active_orders[ctx.channel.id]
        embed_client = discord.Embed(title="✅ HOÀN TẤT CÔNG TRÌNH", color=0x00FFFF)
        embed_client.description = f"Chào <@{order_data['user']}>! Đơn hàng của bạn đã được hoàn thành."
        embed_client.add_field(name="🏗️ Trạng thái", value="`Đã bàn giao`", inline=True)
        embed_client.add_field(name="🆔 Mã đơn", value=f"`{order_data['code']}`", inline=True)
        await ctx.send(content=f"<@{order_data['user']}>", embed=embed_client)

        admin_ch = self.bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
        if admin_ch:
            embed_log = discord.Embed(title="📊 LOG: ĐƠN ĐÃ HOÀN TẤT", color=0x27AE60)
            embed_log.add_field(name="🆔 Mã đơn", value=f"`{order_data['code']}`", inline=True)
            embed_log.add_field(name="👷 Người thực hiện", value=ctx.author.mention, inline=True)
            embed_log.add_field(name="💵 Tiền nhận", value=f"{order_data['price']:,} VND", inline=False)
            await admin_ch.send(embed=embed_log)

        del active_orders[ctx.channel.id]
        await ctx.message.add_reaction("🎊")

async def setup(bot):
    await bot.add_cog(BuildSystem(bot))
