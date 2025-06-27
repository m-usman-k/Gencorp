import discord
from discord.ext import commands
import sqlite3
import json
from datetime import timedelta, datetime

CONFIG_PATH = 'databases/server_config.json'
EMBED_COLOR = 0x56DFCF

def get_ticket_category_id():
    with open(CONFIG_PATH, 'r') as f:
        data = json.load(f)
    return data.get('ticket_category')

def set_ticket_category_id(category_id):
    with open(CONFIG_PATH, 'r+') as f:
        data = json.load(f)
        data['ticket_category'] = category_id
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()

def is_supreme_leader(user_id):
    with open(CONFIG_PATH, 'r') as f:
        data = json.load(f)
    return user_id in data.get('supreme_leader_ids', [])

def get_next_ticket_number(guild):
    conn = sqlite3.connect('databases/gencorp.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM tickets WHERE status=?', ('open',))
    count = cursor.fetchone()[0] + 1
    conn.close()
    return f"{count:02d}"

class TicketActionView(discord.ui.View):
    def __init__(self, bot, ticket_id, persistent=True):
        super().__init__(timeout=None)
        self.bot = bot
        self.ticket_id = ticket_id

    @discord.ui.button(label='Delete Ticket', style=discord.ButtonStyle.danger, custom_id='delete_ticket')
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_supreme_leader(interaction.user.id):
            await interaction.response.send_message(embed=discord.Embed(description="You do not have permission to delete tickets.", color=EMBED_COLOR), ephemeral=True)
            return
        channel_id = interaction.channel.id
        conn = sqlite3.connect('databases/gencorp.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM tickets WHERE channel_id=? AND status=?', (channel_id, 'open'))
        result = cursor.fetchone()
        if not result:
            await interaction.response.send_message(embed=discord.Embed(description='This is not an open ticket channel.', color=EMBED_COLOR), ephemeral=True)
            conn.close()
            return
        cursor.execute('UPDATE tickets SET status=? WHERE channel_id=?', ('closed', channel_id))
        conn.commit()
        conn.close()
        await interaction.response.send_message(embed=discord.Embed(description='Ticket deleted. This channel will be deleted in 10 seconds.', color=EMBED_COLOR), ephemeral=True)
        await discord.utils.sleep_until(datetime.utcnow() + timedelta(seconds=10))
        await interaction.channel.delete()

class OpenTicketButton(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Open Ticket', style=discord.ButtonStyle.green, custom_id='open_ticket_button')
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        conn = sqlite3.connect('databases/gencorp.db')
        cursor = conn.cursor()
        cursor.execute('SELECT channel_id FROM tickets WHERE user_id=? AND status=?', (user_id, 'open'))
        result = cursor.fetchone()
        if result:
            await interaction.response.send_message(embed=discord.Embed(description=f'You already have an open ticket: <#{result[0]}>', color=EMBED_COLOR), ephemeral=True)
            conn.close()
            return
        guild = interaction.guild
        category_id = get_ticket_category_id()
        if not category_id:
            await interaction.response.send_message(embed=discord.Embed(description='No category for tickets is set. Please ask an admin to set it.', color=EMBED_COLOR), ephemeral=True)
            return
        category = guild.get_channel(category_id)
        ticket_number = get_next_ticket_number(guild)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(f'ticket-{ticket_number}', category=category, overwrites=overwrites)
        cursor.execute('INSERT INTO tickets (user_id, channel_id, status) VALUES (?, ?, ?)', (user_id, channel.id, 'open'))
        conn.commit()
        ticket_id = cursor.lastrowid
        conn.close()
        embed = Ticket.ticket_embed(interaction.user)
        await channel.send(embed=embed, view=TicketActionView(self.bot, ticket_id))
        await interaction.response.send_message(embed=discord.Embed(description=f'Ticket created: {channel.mention}', color=EMBED_COLOR), ephemeral=True)

class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(OpenTicketButton(bot))
        # No need to add TicketActionView globally, will be added per ticket

    @staticmethod
    def ticket_embed(user):
        embed = discord.Embed(title="🎫 Support Ticket", color=EMBED_COLOR)
        embed.description = (
            f"Welcome {user.mention}!\n\n"
            "A team member will assist you soon.\n\n"
            "**Actions:**\n"
            "- `/add-to-ticket @user` to add a user to this ticket\n"
            "- `/remove-from-ticket @user` to remove a user from this ticket\n"
            "- `/summon-ticket-panel` to resummon this panel (admins only)\n"
            "- Delete Ticket (admins only)"
        )
        return embed

    @commands.hybrid_command(name='tickets', description='Show the ticket panel with a button to open a ticket.')
    async def tickets(self, ctx):
        if not is_supreme_leader(ctx.author.id):
            embed = discord.Embed(description="You do not have permission to use this command.", color=EMBED_COLOR)
            await ctx.send(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(title="Support Tickets", description="Click the button below to open a support ticket.", color=EMBED_COLOR)
        await ctx.send(embed=embed, view=OpenTicketButton(self.bot))

    @commands.hybrid_command(name='summon-ticket-panel', description='Resummon the ticket panel in a ticket channel (admin only).')
    async def summon_ticket_panel(self, ctx):
        if not is_supreme_leader(ctx.author.id):
            embed = discord.Embed(description="You do not have permission to use this command.", color=EMBED_COLOR)
            await ctx.send(embed=embed, ephemeral=True)
            return
        # Only allow in ticket channels
        conn = sqlite3.connect('databases/gencorp.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM tickets WHERE channel_id=? AND status=?', (ctx.channel.id, 'open'))
        result = cursor.fetchone()
        conn.close()
        if not result:
            embed = discord.Embed(description='This is not an open ticket channel.', color=EMBED_COLOR)
            await ctx.send(embed=embed, ephemeral=True)
            return
        embed = self.ticket_embed(ctx.author)
        await ctx.send(embed=embed, view=TicketActionView(self.bot, result[0]))

    @commands.hybrid_command(name='add-to-ticket', description='Add a user to this ticket (admins only, ticket channels only).')
    async def add_to_ticket(self, ctx, member: discord.Member):
        if not is_supreme_leader(ctx.author.id):
            embed = discord.Embed(description="You do not have permission to use this command.", color=EMBED_COLOR)
            await ctx.send(embed=embed, ephemeral=True)
            return
        # Only allow in ticket channels
        conn = sqlite3.connect('databases/gencorp.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM tickets WHERE channel_id=? AND status=?', (ctx.channel.id, 'open'))
        result = cursor.fetchone()
        conn.close()
        if not result:
            embed = discord.Embed(description='This is not an open ticket channel.', color=EMBED_COLOR)
            await ctx.send(embed=embed, ephemeral=True)
            return
        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        embed = discord.Embed(description=f'{member.mention} has been added to this ticket.', color=EMBED_COLOR)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='remove-from-ticket', description='Remove a user from this ticket (admins only, ticket channels only).')
    async def remove_from_ticket(self, ctx, member: discord.Member):
        if not is_supreme_leader(ctx.author.id):
            embed = discord.Embed(description="You do not have permission to use this command.", color=EMBED_COLOR)
            await ctx.send(embed=embed, ephemeral=True)
            return
        # Only allow in ticket channels
        conn = sqlite3.connect('databases/gencorp.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM tickets WHERE channel_id=? AND status=?', (ctx.channel.id, 'open'))
        result = cursor.fetchone()
        conn.close()
        if not result:
            embed = discord.Embed(description='This is not an open ticket channel.', color=EMBED_COLOR)
            await ctx.send(embed=embed, ephemeral=True)
            return
        await ctx.channel.set_permissions(member, overwrite=None)
        embed = discord.Embed(description=f'{member.mention} has been removed from this ticket.', color=EMBED_COLOR)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='set-ticket-category', description='Set the ticket category (supreme only).')
    async def set_ticket_category(self, ctx, category: discord.CategoryChannel):
        if not is_supreme_leader(ctx.author.id):
            embed = discord.Embed(description="You do not have permission to use this command.", color=EMBED_COLOR)
            await ctx.send(embed=embed, ephemeral=True)
            return
        set_ticket_category_id(category.id)
        embed = discord.Embed(description=f"Ticket category set to {category.name}", color=EMBED_COLOR)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Ticket(bot)) 