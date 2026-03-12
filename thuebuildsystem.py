import discord
from discord.ext import commands
import asyncio
import sqlite3
import random
import string
import urllib.parse
from datetime import datetime, timedelta

# --- CẤU HÌNH ID ---
BANK_CHANNEL_ID = 1479440469120389221         
ADMIN_TRACKING_CHANNEL_ID = 1481705972325154939 

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
    def __init__(self, price, order_code, customer_name, bot):
        super().__init__(timeout=None)
        self.price = price
        self.code = order_code
        self.bot = bot
        self.info = f"BUILD{order_code.split('-')[1]}" 

    @discord.ui.button(label="💳 CHUYỂN KHOẢN", style=discord.ButtonStyle.green)
    async def bank(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        button.label = "ĐÃ HIỆN MÃ QR"
        await interaction.message.edit(view=self)

        safe_info = urllib.parse.quote(self.info)
        qr_url = f"https://img.vietqr.io/image/MB-0764495919-compact2.png?amount={self.price}&addInfo={safe_info}"
        
        # --- LOGIC ĐẾM NGƯỢC TỪNG GIÂY (GIỐNG SELL_SYSTEM) ---
        seconds_left = 300 # 5 phút
        
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
        
        # Gửi tin nhắn ban đầu
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        # Vòng lặp cập nhật thời gian mỗi giây
        while seconds_left > 0:
            # Nếu mã đơn không còn trong danh sách chờ (nghĩa là đã thanh toán xong) thì dừng đếm
            if self.code not in bank_waiting:
                return

            await asyncio.sleep(1)
            seconds_left -= 1
            
            # Định dạng phút:giây
            mins, secs = divmod(seconds_left, 60)
            time_str = f"{mins:02d}:{secs:02d}"
            
            # Cập nhật description của embed
            new_embed = embed.copy()
            new_embed.description = (
                f"🏗️ **Sản phẩm:** `Thuê Build`\n"
                f"💰 **Số tiền:** **{self.price:,} VND**\n"
                f"📝 **Nội dung:** `{self.info}`\n\n"
                f"⏳ **Thời gian còn lại:** `{time_str}`"
            )
            
            try:
                await msg.edit(embed=new_embed)
            except:
                break # Phòng trường hợp tin nhắn bị xóa thủ công

        # Khi hết thời gian mà vẫn chưa thanh toán
        if self.code in bank_waiting:
            del bank_waiting[self.code]
            timeout_embed = discord.Embed(
                title="❌ MÃ THANH TOÁN HẾT HẠN", 
                description="Đơn hàng đã bị hủy tự động. Vui lòng tạo đơn mới.", 
                color=discord.Color.red()
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
        customer_name = ctx.channel.name.split('-')[1] if '-' in ctx.channel.name else ctx.channel.name
        
        target_user = None
        for m in ctx.channel.members:
            if not m.bot and not m.guild_permissions.administrator:
                target_user = m; break
        if not target_user: target_user = ctx.author

        bank_waiting[order_code] = {"channel": ctx.channel.id, "price": price, "user": target_user.id}
        
        conn = sqlite3.connect('build_orders.db')
        conn.execute("INSERT OR REPLACE INTO waiting_builds VALUES (?, ?, ?, ?, ?, ?)", 
                     (order_code, ctx.channel.id, f"Thuê Build", price, target_user.id, 0))
        conn.commit()
        conn.close()

        embed = discord.Embed(
            title="🏗️ XÁC NHẬN THUÊ BUILD",
            description=f"Chào {target_user.mention}! Admin đã tạo đơn thuê build cho bạn.\n\n"
                        f"🆔 **Mã đơn:** `{order_code}`\n"
                        f"💰 **Giá tiền:** `{price:,} VND`",
            color=0x3498DB
        )
        await ctx.send(content=target_user.mention, embed=embed, view=BuildPaymentView(price, order_code, customer_name, self.bot))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.channel.id != BANK_CHANNEL_ID: return
        
        content = message.content.upper().replace(" ", "").replace("-", "").replace("#", "")
        
        matched_code = None
        for code in list(bank_waiting.keys()):
            if code.replace("-", "").upper() in content:
                matched_code = code
                break
        
        if matched_code:
            data = bank_waiting[matched_code]
            channel = self.bot.get_channel(data["channel"])
            
            # Xóa khỏi danh sách chờ ngay lập tức để vòng lặp đếm ngược dừng lại
            del bank_waiting[matched_code]
            
            embed_success = discord.Embed(title="🎉 THANH TOÁN THÀNH CÔNG", color=0x2ECC71)
            embed_success.add_field(name="💰 Số tiền", value=f"{data['price']:,} VND")
            embed_success.add_field(name="🆔 Mã đơn", value=matched_code)
            embed_success.add_field(name="📥 Ghi chú", value="Admin đã nhận tiền và đang sắp xếp thời gian xây. Đợi nhé!", inline=False)
            
            if channel: await channel.send(content=f"<@{data['user']}>", embed=embed_success)
            
            admin_ch = self.bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
            if admin_ch:
                embed_admin = discord.Embed(title="👷 ĐƠN THUÊ BUILD MỚI", color=0xE67E22)
                embed_admin.add_field(name="🆔 Mã đơn", value=f"`{matched_code}`")
                embed_admin.add_field(name="📍 Kênh", value=f"<#{data['channel']}>")
                await admin_ch.send(embed=embed_admin)

            db_update_status(matched_code, 1)
            await message.add_reaction("✅")

async def setup(bot):
    await bot.add_cog(BuildSystem(bot))
