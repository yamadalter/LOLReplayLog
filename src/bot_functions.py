import image_gen
import replay_reader
import summoner_data
import skill_rating
import riot_api
import asyncio
import logging
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
from db import DB
from PIL import Image, ImageDraw


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
        self.df_rating = None

    async def result(self, interaction=None, id=None):  # Get match from ID
        if id is None:
            logging.error("result function called with id=None")
            return

        try:
            image_path = f'data/match_imgs/{id}.png'

            # 画像がなければ生成する
            if not os.path.exists(image_path):
                replay = replay_reader.ReplayReader(self, id)
                
                # 画像生成を別スレッドで実行してブロッキングを回避
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None,  # デフォルトのThreadPoolExecutorを使用
                    replay.generate_game_img,
                    self.dic
                )

            # 画像生成が成功したか再チェック
            if not os.path.exists(image_path):
                logging.error(f"Image generation failed for match ID: {id}")
                return

            # EmbedとFileを作成して送信
            embed = Embed(title="Result", description=f"{id}", color=Colour.blurple())
            file = File(image_path, filename="image.png")
            embed.set_image(url="attachment://image.png")

            if interaction is not None:
                await interaction.followup.send(file=file, embed=embed)
            else:
                async with aiohttp.ClientSession() as session:
                    webhook = Webhook.from_url(result_webhook, session=session)
                    await webhook.send(file=file, embed=embed)

        except FileNotFoundError:
            logging.error(f"Image file not found for match ID: {id} after generation attempt.")
        except Exception as e:
            logging.error(f"An error occurred in result function for match ID {id}: {e}", exc_info=True)

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

    async def stats(self, interaction, member, season=None):
        discord_id = str(interaction.user.id) if member is None else str(member.id)
        if discord_id in self.dic:
            gamename = self.dic[discord_id]['gamename']
            tag = self.dic[discord_id]['tag']
        else:
            await interaction.followup.send(content="Summoner is not linked", ephemeral=True)
            return

        puuid_series = self.df_player.query('gameName == @gamename and tagLine == @tag')['puuid']
        if len(puuid_series) > 0:
            puuid = puuid_series.values[0]
        else:
            await interaction.followup.send(content="Log not found", ephemeral=True)
            return

        name = f"<@{discord_id}>"
        avator = await self.user(discord_id)

        if self.df_player is not None:
            # データのコピー（フィルタリング用）
            game_df = self.df_game.copy()
            stats_df = self.df_stats.copy()
            p_df = self.df_participants.copy()

            # --- シーズンフィルタリング ---
            if season is not None:
                # バージョン列名を自動判別
                version_col = next((c for c in ['gameVersion', 'version', 'game_version'] if c in game_df.columns), None)
                
                if version_col:
                    v_split = game_df[version_col].str.split('.', expand=True)
                    game_df['major'] = pd.to_numeric(v_split[0], errors='coerce').fillna(0).astype(int)
                    game_df['minor'] = pd.to_numeric(v_split[1], errors='coerce').fillna(0).astype(int)

                    if season == "14":
                        game_df = game_df[game_df['major'] < 15]
                    elif season == "15":
                        game_df = game_df[(game_df['major'] == 15) | ((game_df['major'] == 15) & (game_df['minor'] >= 1))]
                    elif season == "15-1":
                        game_df = game_df[(game_df['major'] == 15) & (game_df['minor'] >= 1) & (game_df['minor'] <= 8)]
                    elif season == "15-2":
                        game_df = game_df[(game_df['major'] == 15) & (game_df['minor'] >= 9) & (game_df['minor'] <= 16)]
                    elif season == "15-3":
                        game_df = game_df[(game_df['major'] == 15) & ((game_df['major'] == 15) & (game_df['minor'] >= 17))]
                    elif season == "16":
                        game_df = game_df[(game_df['major'] == 16)]
                    elif season == "16-1":
                        game_df = game_df[(game_df['major'] == 16) & (game_df['minor'] >= 1) & (game_df['minor'] <= 8)]
                    elif season == "16-2":
                        game_df = game_df[(game_df['major'] == 16) & (game_df['minor'] >= 9) & (game_df['minor'] <= 15)]
                    elif season == "16-3":
                        game_df = game_df[(game_df['major'] == 16) & (game_df['minor'] >= 16) & (game_df['minor'] <= 24)]
                    # 絞り込まれたゲームIDに一致する全プレイヤーのデータを抽出
                    valid_ids = game_df['id'].tolist()
                    stats_df = stats_df[stats_df['gameId'].isin(valid_ids)]
                    p_df = p_df[p_df['gameId'].isin(valid_ids)]

            # 本人のデータがあるかチェック
            user_stats = stats_df[stats_df["puuid"] == puuid]
            if len(user_stats) < 1:
                period_name = f"Season {season}" if season else "全期間"
                await interaction.followup.send(content=f"{period_name}の戦績が見つかりませんでした。", ephemeral=True)
                return

            # 勝率に応じたカラー設定
            winrate = sum(user_stats["win"]) / len(user_stats) * 100
            stats_color = 0xFFFFFF 
            if winrate > 60: stats_color = 0x0099E1
            elif winrate > 50: stats_color = 0x00D166
            elif winrate > 40: stats_color = 0xF8C300
            else: stats_color = 0xFD0061

            # 画像左上に表示するテキスト
            display_period = f"Season {season}" if season else "All Time"
            
            # 画像生成の実行 (stats_df, p_df は絞り込まれた全プレイヤー分を渡す)
            self.image_gen.generate_stats_img([game_df, self.df_player, stats_df, p_df], puuid, period_text=display_period)
            
            # チャンピオンアイコン取得用
            user_p = p_df[p_df["puuid"] == puuid]
            famouschamp = user_p["championName"].value_counts().keys()[0] if not user_p.empty else "Aatrox"

            # Embedの作成
            embed = Embed(title=f"Stats ({display_period})", description=f"**{name}**\n", color=stats_color)
            user_icon = avator.avatar.url if (avator and avator.avatar) else ""
            embed.set_author(name=f'{gamename} #{tag}', icon_url=user_icon)
            
            file1 = File(f'img/champion/{famouschamp}.png', filename='champ.png')
            file2 = File(f'data/stats_imgs/{puuid}.png', filename="image.png")
            embed.set_thumbnail(url="attachment://champ.png")
            embed.set_image(url="attachment://image.png")
            
            await interaction.followup.send(files=[file1, file2], embed=embed)
        else:
            await interaction.followup.send(content="Log file not found", ephemeral=True)
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

    async def rating_graph(self, interaction, member=None):
        """Display skill rating progression for a linked summoner, combined lane graphs."""
        discord_id = str(interaction.user.id) if member is None else str(member.id)
        if discord_id not in self.dic:
            await interaction.followup.send(content="Summoner is not linked", ephemeral=True)
            return
        gamename = self.dic[discord_id]['gamename']
        tag = self.dic[discord_id]['tag']
        puuid_series = self.df_player.query('gameName == @gamename and tagLine == @tag')['puuid']
        if len(puuid_series) == 0:
            await interaction.followup.send(content="Log not found", ephemeral=True)
            return
        puuid = puuid_series.values[0]

        if self.df_player is None:
            await interaction.followup.send(content="Player data not loaded yet", ephemeral=True)
            return
        if self.df_rating is None or self.df_rating.empty:
            await interaction.followup.send(content="Rating history not loaded yet", ephemeral=True)
            return

        # Filter for this puuid
        df_user = self.df_rating[self.df_rating['puuid'] == puuid].copy()
        if df_user.empty:
            await interaction.followup.send(content="No rating history found for this summoner", ephemeral=True)
            return

        # Ensure required columns exist
        required = {'mu_after', 'sigma_after', 'updated_at', 'gameId', 'lane'}
        missing = [c for c in required if c not in df_user.columns]
        if missing:
            await interaction.followup.send(content=f"Rating history missing columns: {missing}. Available: {list(df_user.columns)}", ephemeral=True)
            return

        # Normalize lane strings (lowercase)
        df_user['lane'] = df_user['lane'].astype(str).str.lower()

        # Define lanes we want to display
        lanes = ['top', 'jg', 'mid', 'bot', 'sup']
        lane_images = []  # list of (lane, PIL.Image)
        lane_counts = {}  # lane -> number of games

        for lane in lanes:
            df_lane = df_user[df_user['lane'] == lane].copy()
            if df_lane.empty:
                continue
            # Keep one row per gameId (if multiple entries per game, take first)
            df_lane = df_lane.drop_duplicates(subset=['gameId'], keep='first')
            # Sort by updated_at ascending (oldest first)
            df_lane = df_lane.sort_values(by='updated_at')
            mu_list = df_lane['mu_after'].tolist()
            sigma_list = df_lane['sigma_after'].tolist()
            if len(mu_list) == 0:
                continue
            # Generate image for this lane
            os.makedirs('data/ratings_imgs', exist_ok=True)
            img_path = f'data/ratings_imgs/{puuid}_{lane}.png'
            self.image_gen.generate_rating_img(mu_list, sigma_list, f"{puuid}_{lane}")
            # Open the generated image
            img = Image.open(img_path)
            # Draw lane label on the image
            draw = ImageDraw.Draw(img)
            # Use a small font; fallback to default
            label = lane.upper()
            # Position at top-left with some padding
            draw.text((10, 10), label, fill=(255, 255, 255))
            lane_images.append((lane, img))
            lane_counts[lane] = len(mu_list)

        if not lane_images:
            await interaction.followup.send(content="Not enough data to generate rating graphs for any lane.", ephemeral=True)
            return

        # Combine images horizontally
        # Ensure all images have same height (resize keeping aspect ratio)
        target_height = max(img.height for _, img in lane_images)
        resized_images = []
        for lane, img in lane_images:
            if img.height != target_height:
                # Compute new width to preserve aspect ratio
                w = int(img.width * target_height / img.height)
                img = img.resize((w, target_height), Image.LANCZOS)
            resized_images.append(img)

        total_width = sum(img.width for img in resized_images)
        combined = Image.new('RGBA', (total_width, target_height), (0, 0, 0, 0))
        x_offset = 0
        for img in resized_images:
            combined.paste(img, (x_offset, 0))
            x_offset += img.width

        combined_path = f'data/ratings_imgs/{puuid}_combined.png'
        combined.save(combined_path)

        # Prepare file to send
        file = File(combined_path, filename="rating_combined.png")
        # Create embed with description of lanes
        embed = Embed(title=f"Rating Progression for {gamename}#{tag}", color=Colour.blurple())
        # Add fields for each lane with game counts
        for lane in lanes:
            if lane in lane_counts:
                embed.add_field(name=lane.upper(), value=f"{lane_counts[lane]} games", inline=True)
        embed.set_image(url="attachment://rating_combined.png")

        await interaction.followup.send(embed=embed, file=file)

        # Optional: delete temporary lane images to save space
        for lane in lanes:
            try:
                os.remove(f'data/ratings_imgs/{puuid}_{lane}.png')
            except FileNotFoundError:
                pass