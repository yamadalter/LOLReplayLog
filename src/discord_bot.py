from discord import Client, Game, Intents
from src import bot_functions
import os

TEAM_NUM = 1
EMOJI_CHECK = "✅"


class RGCustoms(Client):
    def __init__(self, prefix, **options):
        super().__init__(intents=Intents.all(), **options)
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
            and "カスタム参加する人は✅を押してください" in reaction.message.content
            and reaction.message.author == self.user):

            remove_str = f'<@!{str(author.id)}>'
            await reaction.message.edit(content=reaction.message.content.replace(remove_str, ''))
            if reaction.count == TEAM_NUM * 2 + 1:
                await self.bot_funcs.send_team(reaction)
                await reaction.message.delete()

    # async def on_raw_reaction_remove(self, payload):
    #     author_id = payload.user_id
    #     msg = await self.get_channel(payload.channel_id).fetch_message(payload.message_id)
    #     if author_id == self.user.id:
    #         return
    #     if (payload.emoji.name == EMOJI_CHECK
    #         and "カスタム参加する人は✅を押してください" in msg.content
    #         and msg.author == self.user):
    #         message_str = f'{msg.content} <@!{str(author_id)}>'
    #         await msg.edit(content=message_str)