import discord
from discord.ext import commands
from discord import ui
import random
import asyncio
import os
from dotenv import load_dotenv
from keep_alive import keep_alive
import psycopg2
from psycopg2 import sql

load_dotenv()
token = os.getenv('DISCORD_TOKEN')
database_url = os.getenv('DATABASE_URL')

# Variables globales pour stocker les messages de stock
stock_message_munitions = None
stock_message_pharmacie = None

# Liste des stations de radio disponibles
stations_radio = [87.8, 89.5, 91.3, 91.9, 94.6, 96.6, 99.7, 102.5]

# Connexion à la base de données PostgreSQL
conn = psycopg2.connect(database_url)
cur = conn.cursor()

# Création des tables si elles n'existent pas encore
cur.execute('''
CREATE TABLE IF NOT EXISTS stock_munitions (
    item TEXT PRIMARY KEY,
    quantity INTEGER
)
''')
conn.commit()

cur.execute('''
CREATE TABLE IF NOT EXISTS stock_pharmacie (
    item TEXT PRIMARY KEY,
    quantity INTEGER
)
''')
conn.commit()

cur.execute('''
CREATE TABLE IF NOT EXISTS bot_state (
    key TEXT PRIMARY KEY,
    value TEXT
)
''')
conn.commit()

cur.execute('''
CREATE TABLE IF NOT EXISTS bot_state_pharmacie (
    key TEXT PRIMARY KEY,
    value TEXT
)
''')
conn.commit()

# Liste des types de munitions
munitions_list = ["5.56", "5.45", "7.62x39", "308Win", "Cal12C", "Cal12R", "9x39", "7.62x54R"]

# Liste des médicaments
pharmacie_list = ["Morphine", "Tétracycline", "Charbon", "Vitamine", "Attelles", "Kit Sanguin", "O+", "O-", "serum phy", "kit intraveineuse", "kit de chirurgie"]

# Ajout des types de munitions dans la base de données s'ils n'existent pas encore
for munition in munitions_list:
    cur.execute('SELECT * FROM stock_munitions WHERE item=%s', (munition,))
    if not cur.fetchone():
        cur.execute('INSERT INTO stock_munitions (item, quantity) VALUES (%s, %s)', (munition, 0))
conn.commit()

# Ajout des médicaments dans la base de données s'ils n'existent pas encore
for medicament in pharmacie_list:
    cur.execute('SELECT * FROM stock_pharmacie WHERE item=%s', (medicament,))
    if not cur.fetchone():
        cur.execute('INSERT INTO stock_pharmacie (item, quantity) VALUES (%s, %s)', (medicament, 0))
conn.commit()

# Initialisation du bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Event when bot is ready
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    # Récupération des messages de stock sauvegardés
    global stock_message_munitions, stock_message_pharmacie
    
    try:
        # Récupération du message des munitions
        cur.execute('SELECT value FROM bot_state WHERE key = %s', ('stock_message_id_munitions',))
        result = cur.fetchone()
        if result:
            message_id = int(result[0])
            channel = bot.get_channel(1290283964547989514)
            try:
                stock_message_munitions = await channel.fetch_message(message_id)
            except:
                stock_message_munitions = None

        # Récupération du message de la pharmacie
        cur.execute('SELECT value FROM bot_state_pharmacie WHERE key = %s', ('stock_message_id_pharmacie',))
        result = cur.fetchone()
        if result:
            message_id = int(result[0])
            channel = bot.get_channel(1293868842115797013)
            try:
                stock_message_pharmacie = await channel.fetch_message(message_id)
            except:
                stock_message_pharmacie = None
    except Exception as e:
        print(f"Erreur lors de la récupération des messages : {e}")

# Fonction pour mettre à jour les tableaux de stock
async def update_stock_message_munitions():
    global stock_message_munitions
    if stock_message_munitions is not None:
        cur.execute('SELECT item, quantity FROM stock_munitions')
        munitions_results = cur.fetchall()
        message = "**Stocks actuels des munitions :**\n\n"
        if munitions_results:
            message += "```\n"
            message += "{:<20} {:<10}\n".format("Munitions", "Quantité")
            message += "-" * 30 + "\n"
            for row in munitions_results:
                message += "{:<20} {:<10}\n".format(row[0], row[1])
            message += "```\n"
        else:
            message += "*Aucune munition en stock.*\n"
        await stock_message_munitions.edit(content=message)

async def update_stock_message_pharmacie():
    global stock_message_pharmacie
    if stock_message_pharmacie is not None:
        cur.execute('SELECT item, quantity FROM stock_pharmacie')
        pharmacie_results = cur.fetchall()
        message = "**Stocks actuels de la pharmacie :**\n\n"
        if pharmacie_results:
            message += "```\n"
            message += "{:<20} {:<10}\n".format("Médicaments", "Quantité")
            message += "-" * 30 + "\n"
            for row in pharmacie_results:
                message += "{:<20} {:<10}\n".format(row[0], row[1])
            message += "```\n"
        else:
            message += "*Aucun médicament en stock.*\n"
        await stock_message_pharmacie.edit(content=message)

# Classes pour les vues (MunitionsView, PharmacieView, RadioButton restent identiques)
# Classe pour gérer les munitions
class MunitionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ajouter des munitions", style=discord.ButtonStyle.green, custom_id="add_munitions")
    async def add_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddMunitionsModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Retirer des munitions", style=discord.ButtonStyle.red, custom_id="remove_munitions")
    async def remove_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RemoveMunitionsModal()
        await interaction.response.send_modal(modal)

class AddMunitionsModal(discord.ui.Modal, title="Ajouter des munitions"):
    def __init__(self):
        super().__init__()
        self.type = discord.ui.Select(
            placeholder="Choisir le type de munitions",
            options=[discord.SelectOption(label=munition) for munition in munitions_list]
        )
        self.quantity = discord.ui.TextInput(
            label="Quantité à ajouter",
            placeholder="Entrez un nombre",
            required=True
        )
        self.add_item(self.type)
        self.add_item(self.quantity)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            quantity = int(self.quantity.value)
            if quantity <= 0:
                raise ValueError("La quantité doit être positive")
            
            cur.execute(
                'UPDATE stock_munitions SET quantity = quantity + %s WHERE item = %s',
                (quantity, self.type.values[0])
            )
            conn.commit()
            
            await update_stock_message_munitions()
            await interaction.response.send_message(f"✅ {quantity} {self.type.values[0]} ont été ajoutées au stock.", ephemeral=True)
            
        except ValueError as e:
            await interaction.response.send_message("❌ Erreur : " + str(e), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("❌ Une erreur est survenue lors de l'ajout des munitions.", ephemeral=True)

class RemoveMunitionsModal(discord.ui.Modal, title="Retirer des munitions"):
    def __init__(self):
        super().__init__()
        self.type = discord.ui.Select(
            placeholder="Choisir le type de munitions",
            options=[discord.SelectOption(label=munition) for munition in munitions_list]
        )
        self.quantity = discord.ui.TextInput(
            label="Quantité à retirer",
            placeholder="Entrez un nombre",
            required=True
        )
        self.add_item(self.type)
        self.add_item(self.quantity)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            quantity = int(self.quantity.value)
            if quantity <= 0:
                raise ValueError("La quantité doit être positive")
            
            cur.execute('SELECT quantity FROM stock_munitions WHERE item = %s', (self.type.values[0],))
            current_stock = cur.fetchone()[0]
            
            if quantity > current_stock:
                raise ValueError("Stock insuffisant")
            
            cur.execute(
                'UPDATE stock_munitions SET quantity = quantity - %s WHERE item = %s',
                (quantity, self.type.values[0])
            )
            conn.commit()
            
            await update_stock_message_munitions()
            await interaction.response.send_message(f"✅ {quantity} {self.type.values[0]} ont été retirées du stock.", ephemeral=True)
            
        except ValueError as e:
            await interaction.response.send_message("❌ Erreur : " + str(e), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("❌ Une erreur est survenue lors du retrait des munitions.", ephemeral=True)

# Classe pour gérer la pharmacie
class PharmacieView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ajouter des médicaments", style=discord.ButtonStyle.green, custom_id="add_pharmacie")
    async def add_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddPharmacieModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Retirer des médicaments", style=discord.ButtonStyle.red, custom_id="remove_pharmacie")
    async def remove_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RemovePharmacieModal()
        await interaction.response.send_modal(modal)

class AddPharmacieModal(discord.ui.Modal, title="Ajouter des médicaments"):
    def __init__(self):
        super().__init__()
        self.type = discord.ui.Select(
            placeholder="Choisir le type de médicament",
            options=[discord.SelectOption(label=med) for med in pharmacie_list]
        )
        self.quantity = discord.ui.TextInput(
            label="Quantité à ajouter",
            placeholder="Entrez un nombre",
            required=True
        )
        self.add_item(self.type)
        self.add_item(self.quantity)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            quantity = int(self.quantity.value)
            if quantity <= 0:
                raise ValueError("La quantité doit être positive")
            
            cur.execute(
                'UPDATE stock_pharmacie SET quantity = quantity + %s WHERE item = %s',
                (quantity, self.type.values[0])
            )
            conn.commit()
            
            await update_stock_message_pharmacie()
            await interaction.response.send_message(f"✅ {quantity} {self.type.values[0]} ont été ajoutés au stock.", ephemeral=True)
            
        except ValueError as e:
            await interaction.response.send_message("❌ Erreur : " + str(e), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("❌ Une erreur est survenue lors de l'ajout des médicaments.", ephemeral=True)

class RemovePharmacieModal(discord.ui.Modal, title="Retirer des médicaments"):
    def __init__(self):
        super().__init__()
        self.type = discord.ui.Select(
            placeholder="Choisir le type de médicament",
            options=[discord.SelectOption(label=med) for med in pharmacie_list]
        )
        self.quantity = discord.ui.TextInput(
            label="Quantité à retirer",
            placeholder="Entrez un nombre",
            required=True
        )
        self.add_item(self.type)
        self.add_item(self.quantity)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            quantity = int(self.quantity.value)
            if quantity <= 0:
                raise ValueError("La quantité doit être positive")
            
            cur.execute('SELECT quantity FROM stock_pharmacie WHERE item = %s', (self.type.values[0],))
            current_stock = cur.fetchone()[0]
            
            if quantity > current_stock:
                raise ValueError("Stock insuffisant")
            
            cur.execute(
                'UPDATE stock_pharmacie SET quantity = quantity - %s WHERE item = %s',
                (quantity, self.type.values[0])
            )
            conn.commit()
            
            await update_stock_message_pharmacie()
            await interaction.response.send_message(f"✅ {quantity} {self.type.values[0]} ont été retirés du stock.", ephemeral=True)
            
        except ValueError as e:
            await interaction.response.send_message("❌ Erreur : " + str(e), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("❌ Une erreur est survenue lors du retrait des médicaments.", ephemeral=True)

# Classe pour le bouton radio
class RadioButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Changer de station", style=discord.ButtonStyle.primary, custom_id="radio_button")
    async def radio_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        station = random.choice(stations_radio)
        await interaction.response.send_message(f"📻 Fréquence radio : {station} MHz", ephemeral=True)

# Nouvelle commande !init globale
@bot.command()
@commands.has_permissions(administrator=True)  # Seuls les administrateurs peuvent utiliser cette commande
async def init(ctx):
    global stock_message_munitions, stock_message_pharmacie
    
    # Vérification que la commande est exécutée dans un serveur
    if not ctx.guild:
        await ctx.send("Cette commande doit être utilisée dans un serveur.")
        return

    try:
        # Initialisation du tableau des munitions
        munitions_channel = bot.get_channel(1290283964547989514)
        if munitions_channel:
            # Supprime les anciens messages dans le canal
            await munitions_channel.purge()
            
            stock_message_munitions = await munitions_channel.send("**Chargement du tableau des stocks...**")
            await update_stock_message_munitions()
            view_munitions = MunitionsView()
            await munitions_channel.send("Gestion des munitions :", view=view_munitions)
            
            # Sauvegarde l'ID du message dans la base de données
            cur.execute('INSERT INTO bot_state (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = %s',
                        ("stock_message_id_munitions", str(stock_message_munitions.id), str(stock_message_munitions.id)))
            conn.commit()

        # Initialisation du tableau de la pharmacie
        pharmacie_channel = bot.get_channel(1293868842115797013)
        if pharmacie_channel:
            # Supprime les anciens messages dans le canal
            await pharmacie_channel.purge()
            
            stock_message_pharmacie = await pharmacie_channel.send("**Chargement du tableau des stocks...**")
            await update_stock_message_pharmacie()
            view_pharmacie = PharmacieView()
            await pharmacie_channel.send("Gestion de la pharmacie :", view=view_pharmacie)
            
            # Sauvegarde l'ID du message dans la base de données
            cur.execute('INSERT INTO bot_state_pharmacie (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = %s',
                        ("stock_message_id_pharmacie", str(stock_message_pharmacie.id), str(stock_message_pharmacie.id)))
            conn.commit()

        # Initialisation du bouton radio
        radio_channel = bot.get_channel(1291085634538176572)
        if radio_channel:
            # Supprime les anciens messages dans le canal
            await radio_channel.purge()
            
            view_radio = RadioButton()
            await radio_channel.send("Appuyez sur le bouton pour sélectionner une station de radio aléatoire :", view=view_radio)

        # Message de confirmation
        success_message = await ctx.send("✅ Initialisation terminée avec succès!")
        await asyncio.sleep(5)
        await success_message.delete()
        if ctx.message:
            await ctx.message.delete()

    except Exception as e:
        error_message = await ctx.send(f"❌ Une erreur est survenue lors de l'initialisation : {str(e)}")
        await asyncio.sleep(10)
        await error_message.delete()
        if ctx.message:
            await ctx.message.delete()

# Gestion des erreurs pour la commande init
@init.error
async def init_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        message = await ctx.send("❌ Vous devez être administrateur pour utiliser cette commande.")
        await asyncio.sleep(5)
        await message.delete()
        if ctx.message:
            await ctx.message.delete()

keep_alive()

# Lancement du bot
bot.run(token)
