import os
import configparser
import discord
from common import TEAM_NUM, EMOJI_CHECK
from discord import Client, Game, Intents, Interaction, AllowedMentions, app_commands
from discord.app_commands import CommandTree
from discord.ext import tasks
from bot_functions import BotFunctions
from db import DB


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

db = DB()
id_list = []


@tasks.loop(seconds=20)
async def db_sync():
    global id_list
    # データベースから最新のデータを取得
    bot_funcs.df_game, bot_funcs.df_player, bot_funcs.df_team, bot_funcs.df_bans, bot_funcs.df_stats, bot_funcs.df_participants = db.get_tables()

    previous_ids = id_list
    id_list = bot_funcs.df_game['id'].tolist()
    new_ids = []
    # 新しいIDが追加された場合
    for i in id_list:
        # 新しく追加されたIDを取得
        if i not in previous_ids:
            new_ids.append(i)

    # 新しく追加されたIDごとに処理を行う
    for new_id in new_ids:
        print(f"New game ID: {new_id}")  # ここに新しいIDに対する処理を追加
        await bot_funcs.result(id=new_id)


@tasks.loop(hours=1)
async def update_version():
    bot_funcs.update(None)


@client.event
async def on_ready():
    global id_list
    print(f"Logged in as {client.user}, ID {client.user.id}")

    # アクティビティを設定
    await client.change_presence(activity=Game(name='produced by:yamadalter'))

    print("DB check start")

    bot_funcs.df_game, bot_funcs.df_player, bot_funcs.df_team, bot_funcs.df_bans, bot_funcs.df_stats, bot_funcs.df_participants = db.get_tables()
    id_list = bot_funcs.df_game['id'].tolist()

    # スラッシュコマンドを同期
    await tree.sync()

    await db_sync.start()


@tree.command(name='link', description='DiscordとRiot IDを紐づけます')
async def link(interaction: Interaction, riotid: str, tag: str, member: discord.Member = None):
    # await interaction.response.defer(thinking=True)
    await bot_funcs.link(interaction, riotid, tag, member)


@tree.command(name='unlink', description='DiscordとRiot IDの紐づけを解きます')
async def unlink(interaction: Interaction, member: discord.Member = None):
    await bot_funcs.unlink(interaction, member)


@tree.command(name='rename', description='紐づけしているRiot idを変更します')
async def rename(interaction: Interaction, riotid: str, tag: str, member: discord.Member = None):
    # await interaction.response.defer(thinking=True)
    await bot_funcs.rename(interaction, riotid, tag, member)


@tree.command(name='stats', description='戦績を確認します')
@app_commands.describe(
    member='戦績を確認するメンバーを選択します',
    season='統計を表示するシーズンを指定します（未指定で全期間）'
)
@app_commands.choices(season=[
    app_commands.Choice(name="Season 14", value="14"),
    app_commands.Choice(name="Season 15", value="15"),
    app_commands.Choice(name="Season 15-1", value="15-1"),
    app_commands.Choice(name="Season 15-2", value="15-2"),
    app_commands.Choice(name="Season 15-3", value="15-3"),
    app_commands.Choice(name="Season 16", value="16"),
    app_commands.Choice(name="Season 16-1", value="16-1"),
])
async def stats(interaction: Interaction, member: discord.Member = None, season: str = None):
    # 画像生成など重い処理を考慮し、応答を保留する
    await interaction.response.defer(thinking=True)
    await bot_funcs.stats(interaction, member, season)


@tree.command(name='detail', description='戦績の詳細を確認します')
async def detail(interaction: Interaction, member: discord.Member = None):
    # await interaction.response.defer(thinking=True)
    await bot_funcs.detail(interaction, member)


# @tree.command(name='bestgame', description='KDAの一番よかった試合を振り返ります')
# async def bestgame(interaction: Interaction, member: discord.Member = None):
#     await interaction.response.defer(thinking=True)
#     await bot_funcs.bestgame(interaction, member)

@tree.command(name='upload', description='DB情報をスプレッドシートに書き出す')
async def upload(interaction: Interaction):
    await interaction.response.defer(thinking=True)
    await bot_funcs.upload(interaction)


@tree.command(name='update', description='version upを行います')
async def update(interaction: Interaction):
    await interaction.response.defer(thinking=True)
    await bot_funcs.update(interaction)


client.run(DISCORD_BOT_TOKEN)
