import discord
from discord.ext import commands
import logging
import os
import sqlite3
import json
from config import BOT_TOKEN
from extensions.ticket import OpenTicketButton, TicketActionView

EMBED_COLOR = 0x56DFCF

# Logging setup
if not os.path.exists('logs'):
    os.makedirs('logs')
logging.basicConfig(
    filename='logs/bot.log',
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s'
)

# Database setup
if not os.path.exists('databases'):
    os.makedirs('databases')
conn = sqlite3.connect('databases/gencorp.db')
cursor = conn.cursor()
# Example: create a table for tickets if not exists
cursor.execute('''CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')
conn.commit()
conn.close()

# Bot setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

views_registered = False  # Flag to ensure views are only registered once

CONFIG_PATH = 'databases/server_config.json'

def is_supreme_leader(user_id):
    with open(CONFIG_PATH, 'r') as f:
        data = json.load(f)
    return user_id in data.get('supreme_leader_ids', [])

# New help command as a slash command, grouped by category
@bot.hybrid_command(name="help", description="Show this help message.")
async def help_command(ctx):
    if not is_supreme_leader(ctx.author.id):
        embed = discord.Embed(description="You do not have permission to use this command.", color=EMBED_COLOR)
        await ctx.send(embed=embed, ephemeral=True)
        return
    # Group commands by category, only names, sorted by length
    categories = {
        "General": [
            "help",
        ],
        "Tickets": [
            "tickets",
            "add-to-ticket",
            "remove-from-ticket",
            "summon-ticket-panel",
            "set-ticket-category",
        ],
        "Welcome": [
            "set-welcome-channel",
        ],
        "News": [
            "set-news-category",
        ],
        "Admin": [
            "add-supreme-leader",
        ],
    }
    embed = discord.Embed(title="Gencorp Assistant Help", color=EMBED_COLOR)
    for cat, cmds in categories.items():
        sorted_cmds = sorted(cmds, key=len)
        desc = '\n'.join([f"/{name}" for name in sorted_cmds])
        embed.add_field(name=cat, value=f"```\n{desc}\n```", inline=False)
    # Always send as embed, whether in DM or channel
    await ctx.send(embed=embed)

# Command for server owner to add a supreme leader
@bot.hybrid_command(name="add-supreme-leader", description="Add a new supreme leader (server owner only).")
async def add_supreme_leader(ctx, user: discord.User):
    if ctx.author.id != ctx.guild.owner_id:
        embed = discord.Embed(description="Only the server owner can add supreme leaders.", color=EMBED_COLOR)
        await ctx.send(embed=embed, ephemeral=True)
        return
    # Update config file
    with open(CONFIG_PATH, 'r+') as f:
        data = json.load(f)
        supreme_ids = set(data.get('supreme_leader_ids', []))
        supreme_ids.add(user.id)
        data['supreme_leader_ids'] = list(supreme_ids)
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()
    embed = discord.Embed(description=f"{user.mention} has been added as a supreme leader.", color=EMBED_COLOR)
    await ctx.send(embed=embed)

# Load cogs/extensions
async def load_extensions():
    for filename in os.listdir('./extensions'):
        if filename.endswith('.py') and filename != '__init__.py':
            await bot.load_extension(f'extensions.{filename[:-3]}')

@bot.event
async def on_ready():
    global views_registered
    if not views_registered:
        bot.add_view(OpenTicketButton(bot))
        # Register persistent ticket action views for all open tickets
        conn = sqlite3.connect('databases/gencorp.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM tickets WHERE status=?', ('open',))
        for (ticket_id,) in cursor.fetchall():
            bot.add_view(TicketActionView(bot, ticket_id))
        conn.close()
        views_registered = True
    await load_extensions()
    await bot.tree.sync()
    logging.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')

if __name__ == '__main__':
    bot.run(BOT_TOKEN) 