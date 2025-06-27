import discord
from discord.ext import commands
import json

CONFIG_PATH = 'databases/server_config.json'
EMBED_COLOR = 0x56DFCF

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

def is_supreme_leader(user_id):
    with open(CONFIG_PATH, 'r') as f:
        data = json.load(f)
    return user_id in data.get('supreme_leader_ids', [])

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel_id = get_welcome_channel_id()
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title="👋 Welcome to Gencorp Trading!",
                    description=(
                        f"Welcome to Gencorp Trading, {member.mention}!\n\n"
                        "You're now part of a premium community built for ambitious traders.\n\n"
                        "🔹 Start here: #start-here\n"
                        "🔹 Need help? Open a ticket: #open-a-ticket\n"
                        "🔹 Want to fast-track your progress? Check out #join-us\n\n"
                        "📲 You'll also get a DM with a personal welcome. Let's level up."
                    ),
                    color=EMBED_COLOR
                )
                await channel.send(content=f"{member.mention}", embed=embed)
        # Private DM funnel
        try:
            dm_embed = discord.Embed(
                title=f"👋 Hey {member.display_name}, welcome to Gencorp Trading!",
                description=(
                    "Glad you joined — this community is built to help traders grow with structure, tools, and proven systems.\n\n"
                    "Here's how to get started:\n\n"
                    "🔹 Watch this 2-min intro: https://youtu.be/_pkGpW7fdSk\n"
                    "🔹 Grab the free trading tools: https://taplink.cc/gencorptrading\n"
                    "🔹 Want real alerts, support & strategy? Check out the mentorship: https://gencorp-trading.webflow.io/\n\n"
                    "Need help or got a question? You can open a ticket anytime.\n\n"
                    "Let's build something real.\n— Dimitry"
                ),
                color=EMBED_COLOR
            )
            await member.send(embed=dm_embed)
        except Exception as e:
            print(f"Failed to send DM to {member}: {e}")

    @commands.hybrid_command(name='set-welcome-channel', description='Set the welcome channel (supreme only).')
    async def set_welcome_channel(self, ctx, channel: discord.TextChannel):
        if not is_supreme_leader(ctx.author.id):
            embed = discord.Embed(description="You do not have permission to use this command.", color=EMBED_COLOR)
            await ctx.send(embed=embed, ephemeral=True)
            return
        set_welcome_channel_id(channel.id)
        embed = discord.Embed(description=f"Welcome channel set to {channel.mention}", color=EMBED_COLOR)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Welcome(bot)) 