import discord
from discord.ext import commands
import json
from config import SUPREME_USER_ID

CONFIG_PATH = 'databases/server_config.json'

def get_welcome_channel_id():
    with open(CONFIG_PATH, 'r') as f:
        data = json.load(f)
    return data.get('welcome_channel')

def set_welcome_channel_id(channel_id):
    with open(CONFIG_PATH, 'r+') as f:
        data = json.load(f)
        data['welcome_channel'] = channel_id
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel_id = get_welcome_channel_id()
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send(f"👋 Welcome to Gencorp Trading, {member.mention}!\n\nYou're now part of a premium community built for ambitious traders.\n\n🔹 Start here: #start-here\n🔹 Need help? Open a ticket: #open-a-ticket\n🔹 Want to fast-track your progress? Check out #join-us\n\n📲 You'll also get a DM with a personal welcome. Let's level up.")
        # Private DM funnel
        try:
            await member.send(f"👋 Hey {member.display_name}, welcome to Gencorp Trading!\n\nGlad you joined — this community is built to help traders grow with structure, tools, and proven systems.\n\nHere's how to get started:\n\n🔹 Watch this 2-min intro: [insert YouTube link]\n🔹 Grab the free trading tools: [Taplink]\n🔹 Want real alerts, support & strategy? Check out the mentorship: [insert mentorship link]\n\nNeed help or got a question? You can open a ticket anytime.\n\nLet's build something real.\n— Dimitry")
        except Exception as e:
            print(f"Failed to send DM to {member}: {e}")

    @commands.command()
    async def set_welcome_channel(self, ctx, channel: discord.TextChannel):
        if ctx.author.id != SUPREME_USER_ID:
            await ctx.send("You do not have permission to use this command.")
            return
        set_welcome_channel_id(channel.id)
        await ctx.send(f"Welcome channel set to {channel.mention}")

async def setup(bot):
    await bot.add_cog(Welcome(bot)) 