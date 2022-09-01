from discord import Client, Game
from src import bot_functions
import os

EMOJI_CHECK = "✅"

class RGCustoms(Client):
    def __init__(self, prefix, **options):
        super().__init__(**options)
        self.prefix = prefix
        self.bot_funcs = bot_functions.BotFunctions(self.prefix, self.fetch_user)

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

    async def on_reaction_add(self, reaction, author):
        if author == self.user:
            return

        if (reaction.emoji == EMOJI_CHECK
            and reaction.message.content == "参加する人は✅を押してください"
            and reaction.message.author == self.user):

            if reaction.count == 11:
                await self.bot_funcs.make_team(reaction)
                await reaction.message.delete()
