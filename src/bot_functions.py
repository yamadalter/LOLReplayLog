import image_gen
import replay_reader
import summoner_data
import skill_rating
import riot_api
from discord import File, Embed, Colour, ui, ButtonStyle, Webhook
from utils import get_keys
from common import TEAM_NUM, MU, SIGMA, INIT_SIGMA, MIN_SIGMA, LANE, LinkDataJSON, TierData, result_webhook, CREDENTIALS_JSON, SHEET_ID
import aiohttp
import os
import shutil
import configparser
import json
import requests
import tarfile
import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials


class BotFunctions():
    def __init__(self, client):
        super().__init__()
        config = configparser.ConfigParser()
        config.read('config.ini')
        if os.path.exists(LinkDataJSON):
            json_open = open(LinkDataJSON, 'r', encoding='utf-8')
            self.dic = json.load(json_open)
        else:
            self.dic = {}
        self.summoner_data = summoner_data.SummonerData()
        self.image_gen = image_gen.ImageGen()
        self.skill_rating = skill_rating.SkillRating()
        self.watcher = riot_api.Watcher()
        self.user = client.fetch_user
        if os.path.exists('data/log/log.csv'):
            self.logdf = pd.read_csv('data/log/log.csv')
        else:
            self.logdf = None
        f = open('data/versions.json', 'r')
        json_dict = json.load(f)
        self.version = json_dict[0]
        self.df_game = None
        self.df_player = None
        self.df_team = None
        self.df_bans = None
        self.df_stats = None
        self.df_participants = None

    async def result(self, interaction=None, id=None):  # Get match from ID
        replay = replay_reader.ReplayReader(self, id)
        if not os.path.exists(f'data/match_imgs/{id}.png'):
            replay.generate_game_img(self.dic)
        embed = Embed(title="Result", description=f"{id}", color=Colour.blurple())
        file = File(f'data/match_imgs/{id}.png', filename="image.png")
        embed.set_image(url="attachment://image.png")
        if interaction is not None:
            await interaction.followup.send(file=file, embed=embed)
        else:
            async with aiohttp.ClientSession() as session:
                webhook = Webhook.from_url(result_webhook, session=session)
                await webhook.send(file=file, embed=embed)

    async def link(self, interaction, riotid, tag, member=None):
        # link id
        discord_id = str(interaction.user.id) if member is None else str(member.id)
        if discord_id in self.dic:
            await interaction.response.send_message(content=f'<@{discord_id}> is already linked', ephemeral=True)
            return
        if (riotid is None) or (tag is None):
            await interaction.response.send_message(content='/link gamename #tag')
            return
        res = self.watcher.search_by_riot_id(riotid, tag)
        if res is None:
            await interaction.response.send_message(content=f'{riotid} #{tag} has not found', ephemeral=True)
            return
        else:
            puuid = res['puuid']
            gamename = res['gameName']
            tag = res['tagLine']
            # sn = self.watcher.search_puuid(puuid)['name']
            await interaction.response.send_message(content='Successfully linked!', ephemeral=True)
            # set rating
            self.dic[discord_id] = {
                'puuid': puuid,
                'gamename': gamename,
                'tag': tag,
            }
            self.save_dic2json()

    async def unlink(self, interaction, member=None):
        discord_id = str(interaction.user.id) if member is None else str(member.id)
        self.dic.pop(discord_id)
        await interaction.response.send_message(content=f'<@{discord_id}> has been unlinked', ephemeral=True)

    async def stats(self, interaction, member):
        discord_id = str(interaction.user.id) if member is None else str(member.id)
        if discord_id in self.dic:
            gamename = self.dic[discord_id]['gamename']
            tag = self.dic[discord_id]['tag']
        else:
            await interaction.response.send_message(content="Summoner is not linked", ephemeral=True)
            return
        puuid = self.df_player.query('gameName == @gamename and tagLine == @tag')['puuid']
        if len(puuid) > 0:
            puuid = puuid.values[0]
        else:
            await interaction.response.send_message(content="Log not found", ephemeral=True)
            return
        name = f"<@{discord_id}>"
        avator = await self.user(discord_id)

        if self.df_player is not None:
            stats_df = self.df_stats[self.df_stats["puuid"] == puuid]
            p_df = self.df_participants[self.df_participants["puuid"] == puuid]
            if len(stats_df) < 1:
                await interaction.response.send_message(content="Log not found", ephemeral=True)
                return
            winrate = sum(stats_df["win"]) / len(stats_df) * 100
            if len(p_df) > 4:
                champ = p_df["championName"].value_counts()[:5]
            else:
                champ = p_df["championName"].value_counts()[:len(p_df)]
            famouschamp = champ.keys()[0]
            if winrate > 60:
                stats_color = 0x0099E1
            elif winrate > 50:
                stats_color = 0x00D166
            elif winrate > 40:
                stats_color = 0xF8C300
            else:
                stats_color = 0xFD0061
            file1 = File(f'img/champion/{famouschamp}.png', filename='champ.png')
            embed = Embed(title="Stats", description=f"**{name}**\n", color=stats_color)
            if (avator is not None) and (avator.avatar is not None):
                user_icon = avator.avatar.url
            else:
                user_icon = ""
            embed.set_author(name=f'{gamename} #{tag}', icon_url=user_icon)
            embed.set_thumbnail(url="attachment://champ.png")
            self.image_gen.generate_stats_img([self.df_game, self.df_player, self.df_stats, self.df_participants], puuid)
            file2 = File(f'data/stats_imgs/{puuid}.png', filename="image.png")
            embed.set_image(url="attachment://image.png")
            await interaction.response.send_message(files=[file1, file2], embed=embed)
        else:
            await interaction.response.send_message(content="Log file not found", ephemeral=True)
            return

    async def bestgame(self, interaction, member):
        discord_id = str(interaction.user.id) if member is None else str(member.id)
        summoner_name = self.dic[discord_id]['sn']
        if summoner_name is None:
            await interaction.response.send_message(content="Summoner name is not linked")
            return
        name = f"<@{discord_id}>"
        if self.logdf is not None:
            summoner_df = self.logdf[self.logdf["NAME"] == summoner_name]
            if len(summoner_df) < 1:
                await interaction.response.send_message(content="Log not found")
                return
            kill = summoner_df["CHAMPIONS_KILLED"].astype(int) / len(summoner_df)
            death = summoner_df["NUM_DEATHS"].astype(int) / len(summoner_df)
            assist = summoner_df["ASSISTS"].astype(int) / len(summoner_df)
            kda = ((kill) + (assist)) / (death)
            max_index = np.argmax(kda)
            replay_id = list(summoner_df["game_id"])[max_index]
            if not os.path.exists(f'data/match_imgs/{replay_id}.png'):
                await interaction.response.send_message(content="Log not found")
                return
            embed = Embed(title="Best Game", description=f"{name}", color=Colour.blurple())
            file = File(f'data/match_imgs/{replay_id}.png', filename="image.png")
            embed.set_image(url="attachment://image.png")
            await interaction.response.send_message(file=file, embed=embed)

    async def detail(self, interaction, member):
        discord_id = str(interaction.user.id) if member is None else str(member.id)
        if discord_id in self.dic:
            gamename = self.dic[discord_id]['gamename']
            tag = self.dic[discord_id]['tag']
        else:
            await interaction.response.send_message(content="Summoner is not linked", ephemeral=True)
            return
        puuid = self.df_player.query('gameName == @gamename and tagLine == @tag')['puuid']
        if len(puuid) > 0:
            puuid = puuid.values[0]
        else:
            await interaction.response.send_message(content="Log not found", ephemeral=True)
            return
        name = f"<@{discord_id}>"
        avator = await self.user(discord_id)

        if self.df_player is not None:
            stats_df = self.df_stats[self.df_stats["puuid"] == puuid]
            p_df = self.df_participants[self.df_participants["puuid"] == puuid]
            if len(stats_df) < 1:
                await interaction.response.send_message(content="Log not found", ephemeral=True)
                return
            if avator is not None and avator.avatar is not None:
                user_icon = avator.avatar.url
            else:
                user_icon = ""
            embed = Embed(title="Detail stats", description=f"**{name}**\nTotal Games {len(stats_df)}\n", color=0xFFFFFF)
            embed.set_author(name=f'{gamename} #{tag}', icon_url=user_icon)
            for lane in LANE:
                lane_df = p_df[p_df["position"] == lane]
                merged_df = pd.merge(lane_df, stats_df, on=["gameId", "participantId"])
                if len(lane_df) > 0:
                    average_kill = str(sum(merged_df["kills"].astype(int)) / len(merged_df))
                    average_death = str(sum(merged_df["deaths"].astype(int)) / len(merged_df))
                    average_assist = str(sum(merged_df["assists"].astype(int)) / len(merged_df))
                    if average_death == '0.0':
                        average_death = '1.0'
                    average_kda = (float(average_kill) + float(average_assist)) / float(average_death)
                    winrate = sum(merged_df["win"]) / len(lane_df) * 100
                    # average_vision_ward = sum(lane_df["VISION_WARDS_BOUGHT_IN_GAME"].astype(int)) / len(lane_df)
                    if len(lane_df) > 4:
                        champ = merged_df["championName"].value_counts()[:5]
                    else:
                        champ = merged_df["championName"].value_counts()[:len(lane_df)]
                    champ_str = ''
                    for index, v in champ.items():
                        champ_str += f'**{index}** : {v}  '
                    embed.add_field(name=f"**{lane}**", value=f"**Games** : {len(merged_df)}")
                    embed.add_field(name="Winrate", value=f"{winrate:.3g}")
                    embed.add_field(name="KDA", value=f"{average_kda:.3g}")
                    # embed.add_field(name="Wards", value=f"{average_vision_ward:.3g}")
                    embed.add_field(name="\nFavorite Champions", value=f"{champ_str}\n\u200b", inline=False)
            average_kill = str(sum(stats_df["kills"].astype(int)) / len(stats_df))
            average_death = str(sum(stats_df["deaths"].astype(int)) / len(stats_df))
            average_assist = str(sum(stats_df["assists"].astype(int)) / len(stats_df))
            if average_death == '0.0':
                average_death = '1.0'
            average_kda = (float(average_kill) + float(average_assist)) / float(average_death)
            winrate = sum(stats_df["win"]) / len(stats_df) * 100
            # average_vision_ward = sum(summoner_df["VISION_WARDS_BOUGHT_IN_GAME"].astype(int)) / len(summoner_df)
            embed.add_field(name="Total Winrate", value=f"{winrate:.3g}")
            embed.add_field(name="KDA", value=f"{average_kda:.3g}")
            # embed.add_field(name="Wards", value=f"{average_vision_ward:.3g}")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(content="Log file not found", ephemeral=True)
            return

    async def rename(self, interaction, gamename, tag, member=None):
        discord_id = str(interaction.user.id) if member is None else str(member.id)
        if (gamename is None) or (tag is None):
            await interaction.response.send_message(content='/link gamename #tag', ephemeral=True)
            return
        res = self.watcher.search_by_riot_id(gamename, tag)
        if res is None:
            await interaction.response.send_message(content=f'{gamename} #{tag} has not found', ephemeral=True)
            return
        else:
            gamename = res['gameName']
            tag = res['tagLine']
            self.dic[discord_id]['gamename'] = gamename
            self.dic[discord_id]['tag'] = tag
            self.save_dic2json()
            await interaction.response.send_message(content=f'Success rename {gamename} #{tag}', ephemeral=True)
            return

    async def upload(self, interaction):
        # Dataframeをスプレッドシートに書き出す
        dataframes = [self.df_game, self.df_player, self.df_team, self.df_bans, self.df_stats, self.df_participants]
        sheetnames = ['game', 'player', 'team', 'bans', 'stats', 'participants']

        # スプレッドシートへのアクセス認証情報を設定します。
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_JSON, scope)  # 認証情報ファイルへのパスを指定
        client = gspread.authorize(creds)

        # スプレッドシートを開きます。存在しない場合は新規作成します。
        try:
            spreadsheet = client.open_by_key(SHEET_ID)
        except gspread.SpreadsheetNotFound:
            spreadsheet = client.create('NSFP')

        for sheet_name, dataframe in zip(sheetnames, dataframes):

            rows = len(dataframe)
            cols = len(dataframe.columns)

            dataframe = dataframe.astype(str)

            # シートを開きます。存在しない場合は新規作成します。
            try:
                worksheet = spreadsheet.worksheet(sheet_name)
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=rows, cols=cols)  # 必要に応じて行数と列数を調整

            # DataFrameの値をスプレッドシートに書き込みます。
            # DataFrameの値をリストに変換
            data = dataframe.values.tolist()

            # ヘッダー行を追加
            data.insert(0, dataframe.columns.tolist())

            # スプレッドシートに書き込む
            worksheet.update('A1', data)

        if interaction is not None:
            await interaction.followup.send(content=f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}/edit?gid=0#gid=0")

    async def update(self, interaction):
        #  download versions.json
        url = 'https://ddragon.leagueoflegends.com/api/versions.json'
        filename = 'data/versions.json'
        urlData = requests.get(url).content
        with open(filename, mode='wb') as f:
            f.write(urlData)
        f = open(filename, 'r')
        json_dict = json.load(f)
        if self.version != json_dict[0]:
            self.version = json_dict[0]
            #  download Data Dragon
            url = f'https://ddragon.leagueoflegends.com/cdn/dragontail-{self.version}.tgz'
            filename = 'dragontail.tgz'
            with requests.get(url, stream=True) as r:
                with open(filename, mode='wb') as f:
                    for chunk in r.iter_content(chunk_size=8096 * 1024):
                        f.write(chunk)
            with tarfile.open(filename, 'r:gz') as tar:
                tar.extractall(path='dragontail')
            if os.path.isdir('img'):
                shutil.rmtree('img')
            shutil.move(f'dragontail/{self.version}/img', './')
            shutil.move('dragontail/img/perk-images', 'img/perk-images')
            shutil.move(f'dragontail/{self.version}/data/en_US/runesReforged.json', 'data/runesReforged.json')
            if interaction is not None:
                await interaction.followup.send(content=f"updated version {self.version}")

    def save_dic2json(self):
        json_file = open(LinkDataJSON, mode="w", encoding='utf-8')
        json.dump(self.dic, json_file, indent=2, ensure_ascii=False)