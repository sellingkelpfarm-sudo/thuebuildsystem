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

bank_waiting = {}  
active_orders = {} 

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
        
        embed = discord.Embed(
            title="💳 HƯỚNG DẪN THANH TOÁN CHI TIẾT",
            description=(
                "Bạn vui lòng thực hiện chuyển khoản theo thông tin chính xác bên dưới.\n"
                "Hệ thống sẽ **tự động xác nhận** ngay khi nhận được tiền."
            ),
            color=0xF1C40F,
            timestamp=datetime.now()
        )
        embed.add_field(name="🏗️ Dịch vụ", value="`Thuê Build Công Trình`", inline=True)
        embed.add_field(name="💰 Tổng tiền", value=f"**{self.price:,} VND**", inline=True)
        embed.add_field(name="📝 Nội dung CK", value=f"`{self.info}`", inline=False)
        embed.add_field(name="🛡️ Lưu ý", value="1. Chuyển đúng nội dung và số tiền.\n2. Giữ lại ảnh giao dịch nếu có sự cố.\n3. Đơn sẽ hết hạn sau 5 phút.", inline=False)
        embed.set_image(url=qr_url)
        embed.set_footer(text="Schematics Shop - Uy Tín & Chất Lượng")
        
        await interaction.response.send_message(embed=embed)

class BuildSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def confirm_order(self, order_id):
        full_code = f"BUILD-{order_id}"
        if full_code in bank_waiting:
            data = bank_waiting[full_code]
            del bank_waiting[full_code]
            
            # --- 1. Gửi Embed Mới cho Admin (Rõ ràng hơn) ---
            admin_ch = self.bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
            admin_msg_id = None
            if admin_ch:
                embed_ad = discord.Embed(title="👷 THÔNG BÁO: CÓ ĐƠN BUILD CẦN LÀM", color=0xE67E22, timestamp=datetime.now())
                embed_ad.set_thumbnail(url="https://i.imgur.com/8N3fUfX.png")
                embed_ad.add_field(name="👤 Khách hàng", value=f"<@{data['user']}>", inline=True)
                embed_ad.add_field(name="🆔 Mã đơn hàng", value=f"`{order_id}`", inline=True)
                embed_ad.add_field(name="💰 Doanh thu", value=f"**{data['price']:,} VND**", inline=True)
                embed_ad.add_field(name="📍 Kênh Ticket", value=f"<#{data['channel']}>", inline=False)
                embed_ad.add_field(name="🛠️ Hướng dẫn", value="Hãy đến kênh ticket để thảo luận với khách. Gõ `!xong` sau khi bàn giao.", inline=False)
                embed_ad.set_footer(text="Vui lòng xử lý đơn sớm nhất có thể!")
                admin_msg = await admin_ch.send(embed=embed_ad)
                admin_msg_id = admin_msg.id

            active_orders[data["channel"]] = {
                "code": order_id, "user": data["user"], "price": data["price"], "admin_msg_id": admin_msg_id
            }
            
            # --- 2. Gửi Hóa Đơn DMs Chi Tiết ---
            customer = self.bot.get_user(data["user"])
            if customer:
                try:
                    inv = discord.Embed(title="🧾 HÓA ĐƠN XÁC NHẬN THANH TOÁN", color=0x2ECC71, timestamp=datetime.now())
                    inv.set_author(name="Schematics Shop Receipt", icon_url=customer.display_avatar.url)
                    inv.description = "Cảm ơn bạn đã thanh toán thành công đơn hàng thuê build!"
                    inv.add_field(name="📊 Trạng thái", value="`Đã thanh toán` ✅", inline=True)
                    inv.add_field(name="🆔 Mã đơn", value=f"`BUILD-{order_id}`", inline=True)
                    inv.add_field(name="💰 Số tiền nhận", value=f"**{data['price']:,} VND**", inline=True)
                    inv.add_field(name="⏳ Dự kiến", value="Admin đang duyệt và sẽ thông báo với bạn sau khi có thời gian nhé!", inline=False)
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
        
        embed = discord.Embed(title="🏗️ KHỞI TẠO ĐƠN THUÊ BUILD", color=0x3498DB, timestamp=datetime.now())
        embed.description = f"Chào {target_user.mention}! Admin đã thiết lập đơn hàng cho bạn."
        embed.add_field(name="👤 Chủ đơn", value=target_user.mention, inline=True)
        embed.add_field(name="🆔 Mã đơn", value=f"`{order_code}`", inline=True)
        embed.add_field(name="💰 Giá tiền", value=f"**{price:,} VND**", inline=True)
        embed.set_footer(text="Nhấn nút bên dưới để lấy thông tin chuyển khoản.")
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

        # --- 3. Gửi Log Hoàn Tất (Chi tiết doanh thu) ---
        if admin_ch:
            embed_log = discord.Embed(title="📊 BÁO CÁO: ĐƠN HÀNG HOÀN TẤT", color=0x27AE60, timestamp=datetime.now())
            embed_log.add_field(name="🆔 Mã đơn", value=f"`{order_data['code']}`", inline=True)
            embed_log.add_field(name="💵 Tiền nhận", value=f"**{order_data['price']:,} VND**", inline=True)
            embed_log.add_field(name="👷 Admin phụ trách", value=ctx.author.mention, inline=False)
            embed_log.set_footer(text="Dữ liệu đã được lưu vào hệ thống doanh thu.")
            await admin_ch.send(embed=embed_log)

        # --- 4. Gửi DMs Hoàn Tất Chi Tiết ---
        customer = self.bot.get_user(order_data["user"])
        if customer:
            try:
                done_dm = discord.Embed(title="📦 BIÊN LAI BÀN GIAO CÔNG TRÌNH", color=0x00FFFF, timestamp=datetime.now())
                done_dm.description = "Công trình của bạn đã được Admin bàn giao hoàn tất!"
                done_dm.add_field(name="🆔 Mã số đơn", value=f"`BUILD-{order_data['code']}`", inline=True)
                done_dm.add_field(name="🏗️ Trạng thái", value="`ĐÃ XONG (COMPLETED)` ✅", inline=True)
                done_dm.add_field(name="⭐ Feedback", value="Hãy để lại đánh giá của bạn để giúp Shop phát triển hơn nhé!", inline=False)
                done_dm.set_footer(text="Cảm ơn bạn đã đồng hành cùng Schematics Shop!")
                await customer.send(embed=done_dm)
            except: pass

        # Thông báo tại kênh Ticket
        embed_client = discord.Embed(title="🎊 CHÚC MỪNG: CÔNG TRÌNH ĐÃ XONG!", color=0x00FFFF)
        embed_client.add_field(name="👤 Người mua", value=f"<@{order_data['user']}>", inline=True)
        embed_client.add_field(name="🆔 Mã đơn", value=f"`{order_data['code']}`", inline=True)
        embed_client.add_field(name="👷 Admin", value=ctx.author.mention, inline=False)
        embed_client.set_image(url="https://i.imgur.com/E8jEOnU.gif") # Bạn có thể thay bằng gif thợ xây
        await ctx.send(content=f"<@{order_data['user']}>", embed=embed_client)

        del active_orders[ctx.channel.id]

async def setup(bot):
    await bot.add_cog(BuildSystem(bot))import discord
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

bank_waiting = {}  
active_orders = {} 

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
        
        embed = discord.Embed(
            title="💳 HƯỚNG DẪN THANH TOÁN CHI TIẾT",
            description=(
                "Bạn vui lòng thực hiện chuyển khoản theo thông tin chính xác bên dưới.\n"
                "Hệ thống sẽ **tự động xác nhận** ngay khi nhận được tiền."
            ),
            color=0xF1C40F,
            timestamp=datetime.now()
        )
        embed.add_field(name="🏗️ Dịch vụ", value="`Thuê Build Công Trình`", inline=True)
        embed.add_field(name="💰 Tổng tiền", value=f"**{self.price:,} VND**", inline=True)
        embed.add_field(name="📝 Nội dung CK", value=f"`{self.info}`", inline=False)
        embed.add_field(name="🛡️ Lưu ý", value="1. Chuyển đúng nội dung và số tiền.\n2. Giữ lại ảnh giao dịch nếu có sự cố.\n3. Đơn sẽ hết hạn sau 5 phút.", inline=False)
        embed.set_image(url=qr_url)
        embed.set_footer(text="Schematics Shop - Uy Tín & Chất Lượng")
        
        await interaction.response.send_message(embed=embed)

class BuildSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def confirm_order(self, order_id):
        full_code = f"BUILD-{order_id}"
        if full_code in bank_waiting:
            data = bank_waiting[full_code]
            del bank_waiting[full_code]
            
            # --- 1. Gửi Embed Mới cho Admin (Rõ ràng hơn) ---
            admin_ch = self.bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
            admin_msg_id = None
            if admin_ch:
                embed_ad = discord.Embed(title="👷 THÔNG BÁO: CÓ ĐƠN BUILD CẦN LÀM", color=0xE67E22, timestamp=datetime.now())
                embed_ad.set_thumbnail(url="https://i.imgur.com/8N3fUfX.png")
                embed_ad.add_field(name="👤 Khách hàng", value=f"<@{data['user']}>", inline=True)
                embed_ad.add_field(name="🆔 Mã đơn hàng", value=f"`{order_id}`", inline=True)
                embed_ad.add_field(name="💰 Doanh thu", value=f"**{data['price']:,} VND**", inline=True)
                embed_ad.add_field(name="📍 Kênh Ticket", value=f"<#{data['channel']}>", inline=False)
                embed_ad.add_field(name="🛠️ Hướng dẫn", value="Hãy đến kênh ticket để thảo luận giá cả với khách. Gõ `!xong` sau khi bàn giao.", inline=False)
                embed_ad.set_footer(text="Vui lòng xử lý đơn sớm nhất có thể!")
                admin_msg = await admin_ch.send(embed=embed_ad)
                admin_msg_id = admin_msg.id

            active_orders[data["channel"]] = {
                "code": order_id, "user": data["user"], "price": data["price"], "admin_msg_id": admin_msg_id
            }
            
            # --- 2. Gửi Hóa Đơn DMs Chi Tiết ---
            customer = self.bot.get_user(data["user"])
            if customer:
                try:
                    inv = discord.Embed(title="🧾 HÓA ĐƠN XÁC NHẬN THANH TOÁN", color=0x2ECC71, timestamp=datetime.now())
                    inv.set_author(name="Schematics Shop Receipt", icon_url=customer.display_avatar.url)
                    inv.description = "Cảm ơn bạn đã thanh toán thành công đơn hàng thuê build!"
                    inv.add_field(name="📊 Trạng thái", value="`Đã thanh toán` ✅", inline=True)
                    inv.add_field(name="🆔 Mã đơn", value=f"`BUILD-{order_id}`", inline=True)
                    inv.add_field(name="💰 Số tiền nhận", value=f"**{data['price']:,} VND**", inline=True)
                    inv.add_field(name="⏳ Dự kiến", value="Admin đang duyệt và sẽ thông báo với bạn sau khi có thời gian nhé", inline=False)
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
        
        embed = discord.Embed(title="🏗️ KHỞI TẠO ĐƠN THUÊ BUILD", color=0x3498DB, timestamp=datetime.now())
        embed.description = f"Chào {target_user.mention}! Admin đã thiết lập đơn hàng cho bạn."
        embed.add_field(name="👤 Chủ đơn", value=target_user.mention, inline=True)
        embed.add_field(name="🆔 Mã đơn", value=f"`{order_code}`", inline=True)
        embed.add_field(name="💰 Giá tiền", value=f"**{price:,} VND**", inline=True)
        embed.set_footer(text="Nhấn nút bên dưới để lấy thông tin chuyển khoản.")
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

        # --- 3. Gửi Log Hoàn Tất (Chi tiết doanh thu) ---
        if admin_ch:
            embed_log = discord.Embed(title="📊 BÁO CÁO: ĐƠN HÀNG HOÀN TẤT", color=0x27AE60, timestamp=datetime.now())
            embed_log.add_field(name="🆔 Mã đơn", value=f"`{order_data['code']}`", inline=True)
            embed_log.add_field(name="💵 Tiền nhận", value=f"**{order_data['price']:,} VND**", inline=True)
            embed_log.add_field(name="👷 Admin phụ trách", value=ctx.author.mention, inline=False)
            embed_log.set_footer(text="Dữ liệu đã được lưu vào hệ thống doanh thu.")
            await admin_ch.send(embed=embed_log)

        # --- 4. Gửi DMs Hoàn Tất Chi Tiết ---
        customer = self.bot.get_user(order_data["user"])
        if customer:
            try:
                done_dm = discord.Embed(title="📦 BIÊN LAI BÀN GIAO CÔNG TRÌNH", color=0x00FFFF, timestamp=datetime.now())
                done_dm.description = "Công trình của bạn đã được Admin bàn giao hoàn tất!"
                done_dm.add_field(name="🆔 Mã số đơn", value=f"`BUILD-{order_data['code']}`", inline=True)
                done_dm.add_field(name="🏗️ Trạng thái", value="`ĐÃ XONG (COMPLETED)` ✅", inline=True)
                done_dm.add_field(name="⭐ Feedback", value="Hãy để lại đánh giá của bạn để giúp Shop phát triển hơn nhé!", inline=False)
                done_dm.set_footer(text="Cảm ơn bạn đã đồng hành cùng Schematics Shop!")
                await customer.send(embed=done_dm)
            except: pass

        # Thông báo tại kênh Ticket
        embed_client = discord.Embed(title="🎊 CHÚC MỪNG: CÔNG TRÌNH ĐÃ XONG!", color=0x00FFFF)
        embed_client.add_field(name="👤 Người mua", value=f"<@{order_data['user']}>", inline=True)
        embed_client.add_field(name="🆔 Mã đơn", value=f"`{order_data['code']}`", inline=True)
        embed_client.add_field(name="👷 Admin", value=ctx.author.mention, inline=False)
        embed_client.set_image(url="https://i.imgur.com/E8jEOnU.gif") # Bạn có thể thay bằng gif thợ xây
        await ctx.send(content=f"<@{order_data['user']}>", embed=embed_client)

        del active_orders[ctx.channel.id]

async def setup(bot):
    await bot.add_cog(BuildSystem(bot))
