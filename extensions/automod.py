import discord
from discord.ext import commands
import re
import logging

BLACKLIST = [
    'badword1', 'badword2', 'scamword'  # Add more as needed
]
INVITE_REGEX = r'(?:https?://)?discord(?:\.gg|app\.com/invite)/[\w-]+'
SCAM_LINKS = ['scam.com', 'phish.com']  # Add more as needed

class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        # Profanity/blacklist
        for word in BLACKLIST:
            if word in message.content.lower():
                await message.delete()
                await message.channel.send(f'{message.author.mention}, that word is not allowed here.', delete_after=5)
                logging.info(f'Blacklisted word deleted from {message.author} in {message.channel}')
                return
        # Discord invite links
        if re.search(INVITE_REGEX, message.content):
            await message.delete()
            await message.channel.send(f'{message.author.mention}, invite links are not allowed.', delete_after=5)
            logging.info(f'Invite link deleted from {message.author} in {message.channel}')
            return
        # Scam link protection
        for scam in SCAM_LINKS:
            if scam in message.content.lower():
                await message.delete()
                await message.channel.send(f'{message.author.mention}, scam links are not allowed.', delete_after=5)
                logging.info(f'Scam link deleted from {message.author} in {message.channel}')
                return
        # Do NOT call process_commands here to avoid double command invocation

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        await self.on_message(after)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        # Set slowmode for public chats (example: 5s)
        if isinstance(channel, discord.TextChannel) and channel.category and 'public' in channel.category.name.lower():
            await channel.edit(slowmode_delay=5)
            logging.info(f'Slowmode set for {channel.name}')

async def setup(bot):
    await bot.add_cog(AutoMod(bot)) 