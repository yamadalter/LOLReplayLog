from discord import Client, Game
from src import bot_functions
import os


class RGCustoms(Client):
    def __init__(self, prefix, **options):
        super().__init__(**options)
        self.prefix = prefix
        self.bot_funcs = bot_functions.BotFunctions(self.prefix)

        req_directories = ['data', 'data/match_imgs', 'data/replays', 'data/players']
        for path in req_directories:
            if not os.path.exists(path):
                print(f"Required directory {path} not found, creating")
                os.mkdir(path)

    async def on_ready(self):
        print(f"Logged in as {self.user}, ID {self.user.id}")
        await self.change_presence(activity=Game(name=f'{self.prefix}help'))

    async def on_message(self, message):
        if message.author == self.user:
            return
        if not message.content.startswith(self.prefix):
            return
        await self.bot_funcs.handle_message(message)
