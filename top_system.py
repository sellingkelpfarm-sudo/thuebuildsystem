import discord
from discord.ext import commands, tasks
import sqlite3
import os
from datetime import datetime

class TopSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_top_task.start() # Bắt đầu vòng lặp tự động cập nhật

    def cog_unload(self):
        self.update_top_task.cancel() # Dừng vòng lặp khi tắt hệ thống

    @tasks.loop(minutes=30)
    async def update_top_task(self):
        await self.bot.wait_until_ready()
        
        # Kết nối database chung bank_orders.db
        conn = sqlite3.connect('bank_orders.db')
        c = conn.cursor()
        
        # Lấy ID kênh và ID tin nhắn đã lưu
        c.execute("SELECT value FROM config WHERE key = 'top_channel'")
        ch_res = c.fetchone()
        c.execute("SELECT value FROM config WHERE key = 'top_message'")
        msg_res = c.fetchone()
        
        if not ch_res:
            conn.close()
            return
            
        channel = self.bot.get_channel(int(ch_res[0]))
        if not channel:
            conn.close()
            return
            
        # Lấy dữ liệu Top 10 đại gia
        try:
            c.execute("SELECT user_id, total_spent FROM leaderboard ORDER BY total_spent DESC LIMIT 10")
            rows = c.fetchall()
        except sqlite3.OperationalError:
            rows = []
        
        # GIỮ NGUYÊN EMBED GỐC SANG TRỌNG CỦA BẠN
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
        
        if not rows:
            top_list = "🚀 *Hiện chưa có dữ liệu vinh danh, hãy trở thành người đầu tiên!*"
        else:
            for i, (u_id, total) in enumerate(rows):
                user_mention = f"<@{u_id}>"
                money = f"{int(total):,}"
                
                if i == 0: # QUÁN QUÂN
                    top_list += f"⭐ {medals[i]} **QUÁN QUÂN: {user_mention}**\n┗ 💰 Tổng chi: `{money} VND`\n\n"
                elif i < 3: # TOP 2, 3
                    top_list += f"{medals[i]} **Top {i+1}: {user_mention}**\n┗ 💸 Tổng chi: `{money} VND`\n\n"
                else: # TOP 4-10
                    top_list += f"🔹 `Top {i+1:02d}` | {user_mention} | `{money} VND`\n"

        embed.add_field(name="✨ DANH SÁCH VINH DANH ✨", value=top_list, inline=False)
        
        avatar_url = self.bot.user.display_avatar.url if self.bot.user else None
        embed.set_footer(
            text=f"🕒 Cập nhật tự động lúc: {datetime.now().strftime('%H:%M - %d/%m/%Y')}",
            icon_url=avatar_url
        )
        
        # Logic gửi mới hoặc sửa tin nhắn cũ (giống mẫu code bạn gửi)
        message = None
        if msg_res:
            try: message = await channel.fetch_message(int(msg_res[0]))
            except: message = None
            
        if message: 
            await message.edit(embed=embed)
        else:
            new_msg = await channel.send(embed=embed)
            c.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('top_message', ?)", (str(new_msg.id),))
            conn.commit()
            
        conn.close()

    @commands.command(name="settopbuild")
    @commands.has_permissions(administrator=True)
    async def settopbuild(self, ctx):
        """Thiết lập kênh này làm nơi hiển thị Bảng Xếp Hạng Top Build"""
        conn = sqlite3.connect('bank_orders.db')
        # Lưu ID kênh hiện tại vào database
        conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('top_channel', ?)", (str(ctx.channel.id),))
        # Xóa ID tin nhắn cũ để bot tạo tin nhắn mới ở kênh này
        conn.execute("DELETE FROM config WHERE key = 'top_message'")
        conn.commit()
        conn.close()
        
        await ctx.send(f"✅ Đã thiết lập kênh {ctx.channel.mention} làm nơi hiện BXH Top Build. Bot sẽ khởi tạo bảng ngay...", delete_after=5)
        # Chạy cập nhật ngay lập tức
        await self.update_top_task.__wrapped__(self)

async def setup(bot):
    await bot.add_cog(TopSystem(bot))
