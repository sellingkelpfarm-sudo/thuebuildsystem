import discord
from discord.ext import commands
import sqlite3
import os
from datetime import datetime

class TopSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="settopbuild")
    async def settopbuild(self, ctx):
        """Hiển thị bảng xếp hạng đại gia thuê build theo phong cách sang trọng"""
        
        # Kết nối lấy dữ liệu từ database thực tế
        conn = sqlite3.connect('bank_orders.db')
        c = conn.cursor()
        try:
            # Lấy top 10 người chi tiêu nhiều nhất từ bảng leaderboard
            c.execute("SELECT user_id, total_spent FROM leaderboard ORDER BY total_spent DESC LIMIT 10")
            data = c.fetchall()
        except sqlite3.OperationalError:
            data = []
        conn.close()

        if not data:
            return await ctx.send("🚀 *Hiện chưa có dữ liệu vinh danh, hãy trở thành người đầu tiên!*")

        # GIỮ NGUYÊN EMBED GỐC CỦA BẠN
        embed = discord.Embed(
            title="✨ 🏆 BẢNG VÀNG ĐẠI GIA ĐÃ THUÊ BUILD - LOTUSS'S SHOP 🏆 ✨", 
            description=(
                "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
                "💎 *Nơi vinh danh những vị khách hàng thân thiết,\n"
                "đã luôn đồng hành và ủng hộ Shop hết mình.*\n"
                "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
            ), 
            color=0xf1c40f, 
            timestamp=datetime.now()
        )

        medals = ["🥇", "🥈", "🥉", "👤", "👤", "👤", "👤", "👤", "👤", "👤"]
        top_list = ""

        for i, (u_id, total) in enumerate(data):
            user_mention = f"<@{u_id}>"
            money = f"{int(total):,}" 
            
            if i == 0: # QUÁN QUÂN
                top_list += f"⭐ {medals[i]} **QUÁN QUÂN: {user_mention}**\n┗ 💰 Tổng chi: `{money} VND`\n\n"
            elif i < 3: # TOP 2, 3
                top_list += f"{medals[i]} **Top {i+1}: {user_mention}**\n┗ 💸 Tổng chi: `{money} VND`\n\n"
            else: # TOP 4-10
                top_list += f"🔹 `Top {i+1:02d}` | {user_mention} | `{money} VND`\n"

        embed.add_field(name="✨ DANH SÁCH VINH DANH ✨", value=top_list, inline=False)
        
        # Footer kèm ảnh avatar bot
        avatar_url = self.bot.user.display_avatar.url if self.bot.user else None
        embed.set_footer(
            text=f"🕒 Cập nhật lúc: {datetime.now().strftime('%H:%M - %d/%m/%Y')}",
            icon_url=avatar_url
        )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(TopSystem(bot))
