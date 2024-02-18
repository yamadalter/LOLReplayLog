import os
import configparser
import discord
from common import TEAM_NUM, EMOJI_CHECK
from discord import Client, Game, Intents, Interaction, AllowedMentions
from discord.app_commands import CommandTree
from bot_functions import BotFunctions


config = configparser.ConfigParser()
config.read('src/config.ini')
section = config['CONFIG']
DISCORD_BOT_TOKEN = section['token']
if DISCORD_BOT_TOKEN == "":
    print("Add your token to config.ini. You can find it at the Discord developer portal, under Bot.")
    exit()

intents = Intents.default()
intents.message_content = True
client = Client(intents=intents)
tree = CommandTree(client)

bot_funcs = BotFunctions(client)
req_directories = ['data', 'data/match_imgs', 'data/replays', 'data/players']
for path in req_directories:
    if not os.path.exists(path):
        print(f"Required directory {path} not found, creating")
        os.mkdir(path)


@client.event
async def on_ready():

    print(f"Logged in as {client.user}, ID {client.user.id}")

    # アクティビティを設定
    await client.change_presence(activity=Game(name='produced by:yamadalter'))

    # スラッシュコマンドを同期
    await tree.sync()


@tree.command(name='link', description='DiscordとRiot IDを紐づけます')
async def link(interaction: Interaction, riotid: str, tag: str, member: discord.Member = None):
    await interaction.response.defer(thinking=True)
    await bot_funcs.link(interaction, riotid, tag, member)


@tree.command(name='unlink', description='DiscordとRiot IDの紐づけを解きます')
async def unlink(interaction: Interaction, member: discord.Member = None):
    await bot_funcs.link(interaction, member)


@tree.command(name='rename', description='紐づけしているRiot idを変更します')
async def rename(interaction: Interaction, riotid: str, tag: str, member: discord.Member = None):
    await interaction.response.defer(thinking=True)
    await bot_funcs.rename(interaction, riotid, tag, member)


@tree.command(name='set_rate', description='レートを任意の値に変更します')
async def set_rate(interaction: Interaction, rate: int, sigma: int = 400, member: discord.Member = None):
    await bot_funcs.set_rate(interaction, rate, sigma, member)


@tree.command(name='reset_rate', description='SoloQレートを基にレートをリセットします')
async def reset_rate(interaction: Interaction, member: discord.Member = None):
    await interaction.response.defer(thinking=True)
    await bot_funcs.reset_rate(interaction, member)


@tree.command(name='team', description='チーム分けを行います')
async def team(interaction: Interaction):
    allowed_mentions = AllowedMentions(everyone=True)
    await interaction.response.send_message('@here カスタム参加する人は✅を押してください', allowed_mentions=allowed_mentions)
    msg = await interaction.original_response()
    await msg.add_reaction('✅')


@tree.command(name='replay', description='リプレイファイルをアップロードし、戦績を保管します')
async def replay(interaction: Interaction, attachment: discord.Attachment):
    await interaction.response.defer(thinking=True)
    await bot_funcs.replay(interaction, attachment)


@tree.command(name='revert', description='戦績を戻します')
async def revert(interaction: Interaction, gameid: str):
    await interaction.response.defer(thinking=True)
    await bot_funcs.revert(interaction, gameid)


@tree.command(name='stats', description='戦績を確認します')
async def stats(interaction: Interaction, member: discord.Member = None):
    await interaction.response.defer(thinking=True)
    await bot_funcs.stats(interaction, member)


@tree.command(name='detail', description='戦績の詳細を確認します')
async def detail(interaction: Interaction, member: discord.Member = None):
    await interaction.response.defer(thinking=True)
    await bot_funcs.detail(interaction, member)


@tree.command(name='bestgame', description='KDAの一番よかった試合を振り返ります')
async def bestgame(interaction: Interaction, member: discord.Member = None):
    await interaction.response.defer(thinking=True)
    await bot_funcs.bestgame(interaction, member)


@tree.command(name='update', description='version upを行います')
async def update(interaction: Interaction):
    await interaction.response.defer(thinking=True)
    await bot_funcs.update(interaction)


@client.event
async def on_reaction_add(reaction, author):
    if author == client.user:
        return

    if (reaction.emoji == EMOJI_CHECK
        and "カスタム参加する人は✅を押してください" in reaction.message.content
        and reaction.message.author == client.user):

        remove_str = f'<@!{str(author.id)}>'
        await reaction.message.edit(content=reaction.message.content.replace(remove_str, ''))
        if reaction.count == TEAM_NUM * 2 + 1:
            await bot_funcs.send_team(reaction)
            await reaction.message.delete()


client.run(DISCORD_BOT_TOKEN)
