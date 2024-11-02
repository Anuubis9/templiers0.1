import discord
from discord.ext import commands
from discord import ui
import random
import asyncio
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from keep_alive import keep_alive

# Chargement des variables d'environnement
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Initialisation de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Liste des stations de radio disponibles
stations_radio = [87.8, 89.5, 91.3, 91.9, 94.6, 96.6, 99.7, 102.5]

# Liste des types de munitions et médicaments avec leurs emojis
munitions_list = {
    "5.56": "🟡",
    "5.45": "🟠",
    "7.62x39": "🔴",
    "308Win": "🟣",
    "Cal12C": "⚫",
    "Cal12R": "⚪",
    "9x39": "🟤",
    "7.62x54R": "🟢",
    "Bleu":"🟦",
    "Rouge": "🟥",
    "Verte": "🟩",
}

pharmacie_list = {
    "Morphine": "💉",
    "Tétracycline": "💊",
    "Charbon": "⚫",
    "Vitamine": "🟡",
    "Attelles": "🦿",
    "Kit Sanguin": "🩸",
    "O+": "🅾️",
    "O-": "🅾️",
    "serum phy": "💧",
    "kit intraveineuse": "💉",
    "kit de chirurgie": "🔧"
}

# Initialisation du bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Stockage des messages de stock
stock_message_munitions = None
stock_message_pharmacie = None

# Fonctions pour interagir avec Supabase
async def initialize_stocks():
    """Initialise les stocks dans Supabase si nécessaire"""
    # Initialisation des munitions
    for munition in munitions_list.keys():
        data = supabase.table('stock_munitions').select('*').eq('item', munition).execute()
        if not data.data:
            supabase.table('stock_munitions').insert({'item': munition, 'quantity': 0}).execute()
    
    # Initialisation des médicaments
    for medicament in pharmacie_list.keys():
        data = supabase.table('stock_pharmacie').select('*').eq('item', medicament).execute()
        if not data.data:
            supabase.table('stock_pharmacie').insert({'item': medicament, 'quantity': 0}).execute()

async def update_stock_message_munitions():
    """Met à jour le message de stock des munitions"""
    global stock_message_munitions
    if stock_message_munitions is not None:
        data = supabase.table('stock_munitions').select('*').execute()
        munitions_results = data.data
        
        message = "🎯 **Inventaire des Munitions** 🎯\n\n"
        if munitions_results:
            for row in munitions_results:
                emoji = munitions_list[row['item']]
                quantity = row['quantity']
                # Barre de progression
                progress = min(quantity // 10, 10)  # Max 10 barres
                bars = "█" * progress + "▒" * (10 - progress)
                
                message += f"{emoji} **{row['item']}**\n"
                message += f"└─ Quantité: `{quantity:>4}` |{bars}|\n\n"
        else:
            message += "*🚫 Aucune munition en stock actuellement.*\n"
        
        message += "\n💡 *Utilisez les boutons ci-dessous pour modifier les stocks*"
        await stock_message_munitions.edit(content=message)

async def update_stock_message_pharmacie():
    """Met à jour le message de stock de la pharmacie"""
    global stock_message_pharmacie
    if stock_message_pharmacie is not None:
        data = supabase.table('stock_pharmacie').select('*').execute()
        pharmacie_results = data.data
        
        message = "⚕️ **Inventaire de la Pharmacie** ⚕️\n\n"
        if pharmacie_results:
            for row in pharmacie_results:
                emoji = pharmacie_list[row['item']]
                quantity = row['quantity']
                # Barre de progression
                progress = min(quantity // 5, 10)  # Max 10 barres
                bars = "█" * progress + "▒" * (10 - progress)
                
                message += f"{emoji} **{row['item']}**\n"
                message += f"└─ Quantité: `{quantity:>4}` |{bars}|\n\n"
        else:
            message += "*🚫 Aucun médicament en stock actuellement.*\n"
        
        message += "\n💡 *Utilisez les boutons ci-dessous pour modifier les stocks*"
        await stock_message_pharmacie.edit(content=message)

class MunitionsView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.create_buttons()

    def create_buttons(self):
        for munition, emoji in munitions_list.items():
            button = ui.Button(
                label=f"{emoji} {munition}", 
                style=discord.ButtonStyle.secondary, 
                custom_id=f"mod_munitions_{munition}"
            )
            self.add_item(button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        custom_id = interaction.data["custom_id"]
        if custom_id.startswith("mod_munitions_"):
            munition = custom_id[len("mod_munitions_"):]
            emoji = munitions_list[munition]
            await interaction.response.send_message(
                f"{emoji} Combien de **{munition}** voulez-vous ajouter ou retirer ?\n"
                f"*(Nombre positif pour ajouter, négatif pour retirer)*", 
                ephemeral=True
            )
            
            def check(message):
                return message.author == interaction.user and message.channel == interaction.channel
                
            try:
                response = await bot.wait_for('message', check=check, timeout=30)
                try:
                    quantity_change = int(response.content)
                except ValueError:
                    await interaction.followup.send("❌ Veuillez entrer un nombre valide.", ephemeral=True)
                    return False

                await response.delete(delay=10)
                
                data = supabase.table('stock_munitions').select('quantity').eq('item', munition).execute()
                if data.data:
                    current_quantity = data.data[0]['quantity']
                    new_quantity = max(0, current_quantity + quantity_change)
                    
                    supabase.table('stock_munitions').update(
                        {'quantity': new_quantity}
                    ).eq('item', munition).execute()
                    
                    operation = "ajoutées" if quantity_change > 0 else "retirées"
                    confirmation_message = await interaction.followup.send(
                        f"{emoji} **{abs(quantity_change)}** {munition} {operation}\n"
                        f"📊 Nouveau stock : **{new_quantity}**", 
                        ephemeral=True
                    )
                    
                    await asyncio.sleep(10)
                    await confirmation_message.delete()
                    await update_stock_message_munitions()
                    
            except asyncio.TimeoutError:
                await interaction.followup.send("⏰ Temps écoulé, veuillez réessayer.", ephemeral=True)
        return True

class PharmacieView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.create_buttons()

    def create_buttons(self):
        for medicament, emoji in pharmacie_list.items():
            button = ui.Button(
                label=f"{emoji} {medicament}", 
                style=discord.ButtonStyle.secondary, 
                custom_id=f"mod_pharmacie_{medicament}"
            )
            self.add_item(button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        custom_id = interaction.data["custom_id"]
        if custom_id.startswith("mod_pharmacie_"):
            medicament = custom_id[len("mod_pharmacie_"):]
            emoji = pharmacie_list[medicament]
            await interaction.response.send_message(
                f"{emoji} Combien de **{medicament}** voulez-vous ajouter ou retirer ?\n"
                f"*(Nombre positif pour ajouter, négatif pour retirer)*", 
                ephemeral=True
            )
            
            def check(message):
                return message.author == interaction.user and message.channel == interaction.channel
                
            try:
                response = await bot.wait_for('message', check=check, timeout=30)
                try:
                    quantity_change = int(response.content)
                except ValueError:
                    await interaction.followup.send("❌ Veuillez entrer un nombre valide.", ephemeral=True)
                    return False

                await response.delete(delay=10)
                
                data = supabase.table('stock_pharmacie').select('quantity').eq('item', medicament).execute()
                if data.data:
                    current_quantity = data.data[0]['quantity']
                    new_quantity = max(0, current_quantity + quantity_change)
                    
                    supabase.table('stock_pharmacie').update(
                        {'quantity': new_quantity}
                    ).eq('item', medicament).execute()
                    
                    operation = "ajoutés" if quantity_change > 0 else "retirés"
                    confirmation_message = await interaction.followup.send(
                        f"{emoji} **{abs(quantity_change)}** {medicament} {operation}\n"
                        f"📊 Nouveau stock : **{new_quantity}**", 
                        ephemeral=True
                    )
                    
                    await asyncio.sleep(10)
                    await confirmation_message.delete()
                    await update_stock_message_pharmacie()
                    
            except asyncio.TimeoutError:
                await interaction.followup.send("⏰ Temps écoulé, veuillez réessayer.", ephemeral=True)
        return True

@bot.command()
async def init_munitions(ctx):
    global stock_message_munitions
    if ctx.channel.id == 1290283964547989514:  # ID du canal de munitions
        view = MunitionsView()

        if stock_message_munitions is None:
            stock_message_munitions = await ctx.send("🔄 **Chargement de l'inventaire...**")
            await update_stock_message_munitions()
            await ctx.send("🎯 **Gestion des Munitions**", view=view)

            supabase.table('bot_state').upsert({
                'key': 'stock_message_id_munitions',
                'value': str(stock_message_munitions.id)
            }).execute()

        await ctx.message.delete(delay=10)

@bot.command()
async def init_pharmacie(ctx):
    global stock_message_pharmacie
    if ctx.channel.id == 1293868842115797013:  # ID du canal de pharmacie
        view = PharmacieView()

        if stock_message_pharmacie is None:
            stock_message_pharmacie = await ctx.send("🔄 **Chargement de l'inventaire...**")
            await update_stock_message_pharmacie()
            await ctx.send("⚕️ **Gestion de la Pharmacie**", view=view)

            supabase.table('bot_state').upsert({
                'key': 'stock_message_id_pharmacie',
                'value': str(stock_message_pharmacie.id)
            }).execute()

        await ctx.message.delete(delay=10)

class RadioButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="📻 Choisir une station", style=discord.ButtonStyle.success)
    async def select_radio(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.channel.name == "radio":
            selected_station = random.choice(stations_radio)
            await interaction.response.send_message(
                f"📻 Station sélectionnée : **{selected_station} FM** 📡"
            )
        else:
            await interaction.response.send_message(
                "⚠️ Cette commande ne peut être utilisée que dans le canal **radio**."
            )

@bot.command()
async def init_radio(ctx):
    if ctx.channel.id == 1291085634538176572:  # ID du canal de Radio
        view = RadioButton()
        embed = discord.Embed(
            title="📻 Radio DayZ",
            description="Appuyez sur le bouton pour sélectionner une fréquence radio aléatoire",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=view)
    else:
        await ctx.send("⚠️ Cette commande ne peut être utilisée que dans le canal **radio**.")

@bot.event
async def on_ready():
    print(f'🤖 {bot.user} est maintenant connecté au serveur!')
    await initialize_stocks()

keep_alive()
bot.run(DISCORD_TOKEN)
