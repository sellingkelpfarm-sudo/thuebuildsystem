import discord
from discord.ext import commands
import random
import string
import sqlite3
from datetime import datetime

SHOP_NAME = "LoTuss's Schematic Shop"
ADMIN_TRACKING_CHANNEL_ID = 1481705972325154939 
HISTORY_CHANNEL_ID = 1481239066115571885

class BuildCardSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def process_auto_success(self, order):
        admin_ch = self.bot.get_channel(ADMIN_TRACKING_CHANNEL_ID)
        if admin_ch:
            embed = discord.Embed(title="👷 ĐƠN THUÊ MỚI (TỰ ĐỘNG)", color=0xE67E22, timestamp=datetime.now())
            embed.add_field(name="👤 Khách", value=f"<@{order['user_id']}>", inline=True)
            embed.add_field(name="💰 Giá", value=f"{order['amount']:,} VND", inline=True)
            embed.set_footer(text=f"Mã: {order['request_id']}")
            await admin_ch.send(embed=embed)

    @commands.command(name="thuebuildcard")
    @commands.has_permissions(administrator=True)
    async def thuebuildcard(self, ctx, price: int):
        await ctx.message.delete()
        rid = ''.join(random.choices(string.digits, k=5))
        user = next((m for m in ctx.channel.members if not m.bot and not m.guild_permissions.administrator), ctx.author)
        
        conn = sqlite3.connect('orders.db')
        conn.execute("INSERT INTO orders VALUES (?,?,?,?,?,?)", (rid, ctx.channel.id, ctx.channel.name, user.id, price, "PENDING"))
        conn.commit()
        conn.close()

        embed = discord.Embed(title="🏗️ KHỞI TẠO ĐƠN THUÊ BUILD (CARD)", color=0x3498DB, timestamp=datetime.now())
        embed.set_author(name=SHOP_NAME)
        embed.add_field(name="👤 Khách hàng", value=user.mention, inline=True)
        embed.add_field(name="🆔 Mã đơn", value=f"`BUILD-{rid}`", inline=True)
        embed.add_field(name="💰 Giá tiền", value=f"**{price:,} VND**", inline=True)
        
        from main import BuyView
        await ctx.send(content=user.mention, embed=embed, view=BuyView(price, rid))

    @commands.command(name="dathuecard")
    @commands.has_permissions(administrator=True)
    async def dathuecard(self, ctx, request_id: str):
        await ctx.message.delete()
        rid = request_id.replace("BUILD-", "")
        conn = sqlite3.connect('orders.db')
        row = conn.execute("SELECT user_id, amount FROM orders WHERE request_id = ?", (rid,)).fetchone()
        if row:
            embed = discord.Embed(title="✅ XÁC NHẬN ĐÃ THANH TOÁN", color=0x2ECC71, timestamp=datetime.now())
            embed.description = f"Đơn hàng `{request_id}` đã được xác nhận. Admin đang build!"
            await ctx.send(content=f"<@{row[0]}>", embed=embed)
            
            h_ch = self.bot.get_channel(HISTORY_CHANNEL_ID)
            if h_ch:
                await h_ch.send(embed=discord.Embed(description=f"💳 **Giao dịch mới**: <@{row[0]}> - {row[1]:,} VND", color=0x2ECC71))
        conn.close()

    @commands.command(name="xongcard")
    @commands.has_permissions(administrator=True)
    async def xongcard(self, ctx, request_id: str):
        await ctx.message.delete()
        rid = request_id.replace("BUILD-", "")
        conn = sqlite3.connect('orders.db')
        row = conn.execute("SELECT user_id FROM orders WHERE request_id = ?", (rid,)).fetchone()
        if row:
            embed = discord.Embed(title="🎊 HOÀN THÀNH ĐƠN BUILD", color=0xF1C40F, timestamp=datetime.now())
            embed.set_author(name=SHOP_NAME)
            embed.description = f"Đơn hàng `{request_id}` đã xong! Cảm ơn bạn."
            await ctx.send(content=f"<@{row[0]}>", embed=embed)
            conn.execute("DELETE FROM orders WHERE request_id = ?", (rid,))
            conn.commit()
        conn.close()

async def setup(bot):
    await bot.add_cog(BuildCardSystem(bot))
