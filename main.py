import os
import discord
from discord.ext import commands
from discord import ui
import random
import psycopg2
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')

# Configurations des listes
STATIONS_RADIO = [87.8, 89.5, 91.3, 91.9, 94.6, 96.6, 99.7, 102.5]
MUNITIONS_LIST = ["5.56", "5.45", "7.62x39", "308Win", "Cal12C", "Cal12R", "9x39", "7.62x54R"]
PHARMACIE_LIST = ["Morphine", "Tétracycline", "Charbon", "Vitamine", "Attelles", "Kit Sanguin", "O+", "O-", "serum phy", "kit intraveineuse", "kit de chirurgie"]

class InventoryBot:
    def __init__(self):
        # Configuration des intents
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix='!', intents=intents)

        # Connexion à la base de données
        self.conn = psycopg2.connect(DATABASE_URL)
        self.cur = self.conn.cursor()

        # Initialisation des tables
        self._create_tables()
        self._initialize_inventory()

        # Messages de stock globaux
        self.stock_message_munitions = None
        self.stock_message_pharmacie = None

        # Configuration des événements et commandes
        self._setup_events()
        self._setup_commands()

    def _create_tables(self):
        """Créer les tables nécessaires si elles n'existent pas"""
        tables = [
            '''CREATE TABLE IF NOT EXISTS stock_munitions (
                item TEXT PRIMARY KEY,
                quantity INTEGER
            )''',
            '''CREATE TABLE IF NOT EXISTS stock_pharmacie (
                item TEXT PRIMARY KEY,
                quantity INTEGER
            )'''
        ]
        
        for table in tables:
            self.cur.execute(table)
        self.conn.commit()

    def _initialize_inventory(self):
        """Initialiser l'inventaire avec des items si non existants"""
        def _add_items_to_table(table_name, item_list):
            for item in item_list:
                self.cur.execute(f'SELECT * FROM {table_name} WHERE item=%s', (item,))
                if not self.cur.fetchone():
                    self.cur.execute(f'INSERT INTO {table_name} (item, quantity) VALUES (%s, %s)', (item, 0))
            self.conn.commit()

        _add_items_to_table('stock_munitions', MUNITIONS_LIST)
        _add_items_to_table('stock_pharmacie', PHARMACIE_LIST)

    def _setup_events(self):
        @self.bot.event
        async def on_ready():
            print(f'{self.bot.user} est connecté à Discord!')

    def _setup_commands(self):
        @self.bot.command()
        async def radio(ctx):
            """Sélectionne une station de radio aléatoire"""
            station = random.choice(STATIONS_RADIO)
            await ctx.send(f"🎵 Station de radio sélectionnée : {station} MHz")

        @self.bot.command(name='init')
        @commands.has_permissions(administrator=True)
        async def init_inventory(ctx):
            """Initialise les canaux d'inventaire"""
            if not ctx.guild:
                await ctx.send("Cette commande doit être utilisée dans un serveur.")
                return

            # Canal des munitions
            munitions_channel = self.bot.get_channel(1290283964547989514)
            if munitions_channel:
                await munitions_channel.purge()
                self.stock_message_munitions = await munitions_channel.send("**Chargement du tableau des stocks de munitions...**")
                await self._update_stock_message(munitions_channel, 'munitions')

            # Canal de la pharmacie
            pharmacie_channel = self.bot.get_channel(1293868842115797013)
            if pharmacie_channel:
                await pharmacie_channel.purge()
                self.stock_message_pharmacie = await pharmacie_channel.send("**Chargement du tableau des stocks de pharmacie...**")
                await self._update_stock_message(pharmacie_channel, 'pharmacie')

        async def _update_stock_message(self, channel, stock_type):
            """Mettre à jour le message de stock"""
            if stock_type == 'munitions':
                self.cur.execute('SELECT item, quantity FROM stock_munitions')
                title = "**Stocks actuels des munitions :**"
                item_list = MUNITIONS_LIST
            else:
                self.cur.execute('SELECT item, quantity FROM stock_pharmacie')
                title = "**Stocks actuels de la pharmacie :**"
                item_list = PHARMACIE_LIST

            results = self.cur.fetchall()
            message = f"{title}\n\n"
            
            if results:
                message += "```\n"
                message += "{:<20} {:<10}\n".format("Items", "Quantité")
                message += "-" * 30 + "\n"
                for row in results:
                    message += "{:<20} {:<10}\n".format(row[0], row[1])
                message += "```\n"
            else:
                message += "*Aucun item en stock.*\n"

            view = InventoryView(stock_type)
            await channel.send(message, view=view)

        class InventoryView(discord.ui.View):
            def __init__(self, stock_type):
                super().__init__(timeout=None)
                items = MUNITIONS_LIST if stock_type == 'munitions' else PHARMACIE_LIST
                for item in items:
                    button = discord.ui.Button(
                        label=item, 
                        style=discord.ButtonStyle.blurple, 
                        custom_id=f"{stock_type}_{item}"
                    )
                    button.callback = self.on_button_click
                    self.add_item(button)

            async def on_button_click(self, interaction: discord.Interaction):
                await interaction.response.send_message(
                    f"Vous avez sélectionné : {interaction.custom_id}", 
                    ephemeral=True
                )

    def run(self):
        """Démarrer le bot"""
        self.bot.run(TOKEN)

def main():
    bot = InventoryBot()
    bot.run()

if __name__ == "__main__":
    main()
