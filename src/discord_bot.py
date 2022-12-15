from discord import Client, Game
from src import bot_functions
import os

TEAM_NUM = 5
EMOJI_CHECK = "✅"


class RGCustoms(Client):
    def __init__(self, prefix, vc_list, **options):
        super().__init__(**options)
        self.prefix = prefix
        self.vc_list = vc_list
        self.bot_funcs = bot_functions.BotFunctions(self.prefix, self.vc_list, self.fetch_user)

        req_directories = ['data', 'data/match_imgs', 'data/replays', 'data/players']
        for path in req_directories:
            if not os.path.exists(path):
                print(f"Required directory {path} not found, creating")
                os.mkdir(path)

    async def on_ready(self):
        print(f"Logged in as {self.user}, ID {self.user.id}")
        self.bot_funcs.vc_list = [self.get_channel(int(vch)) for vch in self.vc_list]
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
            and "カスタム参加する人は✅を押してください" in reaction.message.content
            and reaction.message.author == self.user):

            remove_str = f'<@!{str(author.id)}>'
            await reaction.message.edit(content=reaction.message.content.replace(remove_str, ''))

            if reaction.count == TEAM_NUM * 2 + 1:
                await self.bot_funcs.send_team(reaction)
                await reaction.message.delete()
