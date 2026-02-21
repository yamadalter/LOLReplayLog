from PIL import Image, ImageDraw, ImageFont
import numpy as np
import matplotlib.pyplot as plt
import json
import pandas as pd
import scipy.stats
from pycirclize import Circos
import matplotlib as mpl
import io
mpl.rcParams['figure.facecolor'] = '#010a13'
mpl.rcParams['axes.labelcolor'] = 'white'
mpl.rcParams['axes.titlecolor'] = 'white'
mpl.rcParams['xtick.color'] = 'white'
mpl.rcParams['ytick.color'] = 'white'
mpl.rcParams['text.color'] = 'white'


class ImageGen:
    def __init__(self):
        try:
            with open("data/runesReforged.json", "r", encoding="utf-8") as f:
                self.rune_data = json.load(f)
        except FileNotFoundError:
            print("data/runesReforged.json not found. Download it from Riot's datadragon and restart.")
            exit()
        self.current_image = None
        self.draw = None
        self.current_pixel = (0, 0)
        self.large_font = ImageFont.truetype("font/BeaufortforLOL-Bold.ttf", 24)
        self.normal_font = ImageFont.truetype("font/BeaufortforLOL-Regular.ttf", 16)
        self.large_jp_font = ImageFont.truetype("font/RocknRollOne-Regular.ttf", 24)
        self.normal_jp_font = ImageFont.truetype("font/RocknRollOne-Regular.ttf", 16)
    
    def text(self, text, font=None, fill="white", x=60, y=30, direction="right"):
        if font is None:
            font = self.normal_font
            y_mod = 0
        else:
            y_mod = 6
        self.draw.text((self.current_pixel[0], self.current_pixel[1] + (y/3)), text, fill=fill, font=font)
        if direction == "right":
            self.current_pixel = (self.current_pixel[0] + x, self.current_pixel[1] + y_mod)
        elif direction == "down":
            self.current_pixel = (self.current_pixel[0], self.current_pixel[1] + y + y_mod)

    def resize_paste(self, img, size, center="", mvmt="right", space=10, mask=None):
        if img is None:  # when does this happen ?
            pass
        else:
            x = self.current_pixel[0]
            y = self.current_pixel[1]
            if "x" in center:
                x += int(size[0]*.5)
            if "y" in center:
                y += int(size[1]*.5)
            if mask is not None:
                mask = mask.resize(size)
            self.current_image.paste(img.resize(size), (x, y), mask=mask)
            if mvmt == "right":
                self.current_pixel = (self.current_pixel[0] + size[0] + space, self.current_pixel[1])
            elif mvmt == "down":
                self.current_pixel = (self.current_pixel[0], self.current_pixel[1] + space + size[1])

    def get_rune_img(self, rune_id, slot):
        for style in self.rune_data:
            for runes in style["slots"][slot]["runes"]:
                if str(runes["id"]) == str(rune_id):
                    return Image.open("img/" + runes["icon"])

    def get_style_img(self, style_id):
        for style in self.rune_data:
            if str(style["id"]) == str(style_id):
                return Image.open("img/" + style["icon"])

    def get_champ_icon(self, champ):
        return Image.open(f"img/champion/{champ}.png")

    def get_item_icon(self, item):
        if str(item) == "0":  # empty item slot, make empty item slot img to take up space
            return Image.new('RGBA', (30, 30))
        else:
            return Image.open(f"img/item/{item}.png")

    def generate_player_imgs(self, player):
        rune = self.get_rune_img(player["perk0"], 0)
        self.resize_paste(rune, (40, 40), space=2, mask=rune)
        style = self.get_style_img(player["perkSubStyle"])
        self.resize_paste(style, (20, 20), center="y", mask=style)
        self.resize_paste(self.get_champ_icon(player["SKIN"]), (40, 40))
        self.text(text=f'{player["gamename"]}', x=250, font=self.normal_jp_font)
        self.text(text=player["kda"], x=75)
        self.current_pixel = (self.current_pixel[0], self.current_pixel[1] + 5)
        for item in player["items"]:
            self.resize_paste(self.get_item_icon(item), (30, 30), space=1)
        self.current_pixel = (self.current_pixel[0] + 10, self.current_pixel[1])
        self.text(text=player["cs"], x=40, fill=(135, 157, 237, 255))
        gold_with_comma = str(player["goldEarned"])[0:-3] + "," + str(player["goldEarned"])[-3:]
        self.text(text=gold_with_comma, x=75, fill="Yellow")
        # visions = f'{str(player["VISION_SCORE"])}/{str(player["WARD_PLACED"])}/{str(player["WARD_KILLED"])}/{str(player["VISION_WARDS_BOUGHT_IN_GAME"])}'
        # self.text(text=visions, x=75, fill="Red")
        self.current_pixel = (0, self.current_pixel[1] + 40)

    def generate_game_img(self, player_list, replay_id=None):
        # [[winner kda, loser kda], Winners, Losers, map, timestamp]
        # in each team will be a list of players, containing [KEYSTONE_ID, PERK_SUB_STYLE, champ, name, KDA, minions_killed, [items], gold_earned]
        additional_pixels = (len(player_list[1]) + len(player_list[2])) * 43  # add another 45 pts for each player
        self.current_image = Image.new('RGBA', (775, 220 + additional_pixels), color='#010a13')
        self.draw = ImageDraw.Draw(self.current_image)
        self.current_pixel = (0, 0)
        self.text(text=f"{player_list[3]} ({player_list[4]})")
        self.current_pixel = (0, self.current_pixel[1] + 20)
        self.text(text=f"Winners ({player_list[0][0]}) side: {player_list[5][0]}", font=self.large_font, y=40)
        self.current_pixel = (400, self.current_pixel[1])
        for ban in player_list[6][0]:
            self.resize_paste(self.get_champ_icon(ban), (25, 25), center="y")
        self.current_pixel = (0, self.current_pixel[1] + 50)
        for winner in player_list[1]:
            self.generate_player_imgs(winner)
        self.text(text=f"Losers ({player_list[0][1]}) side: {player_list[5][1]}", font=self.large_font, y=40)
        self.current_pixel = (400, self.current_pixel[1])
        for ban in player_list[6][1]:
            self.resize_paste(self.get_champ_icon(ban), (25, 25), center="y")
        self.current_pixel = (0, self.current_pixel[1] + 50)
        for loser in player_list[2]:
            self.generate_player_imgs(loser)
        if replay_id is None:
            self.current_image.save("temp.png")
        else:
            self.current_image.save(f"data/match_imgs/{replay_id}.png")

    def generate_history_game(self, match):  # match = [champ, win/loss, keystone_id, perk_sub_style, kda, cs, [items], gold]
        self.resize_paste(self.get_champ_icon(match[0]), (50, 50), space=3)
        self.resize_paste(self.get_rune_img(match[2], 0), (30, 30), mvmt="down")
        self.current_pixel = (self.current_pixel[0], self.current_pixel[1] - 10)
        self.resize_paste(self.get_style_img(match[3]), (15, 15), center="x")
        self.current_pixel = (self.current_pixel[0] + 3, self.current_pixel[1] - 30)
        if match[1] == "Win":
            result_color = "Green"
        elif match[1] == "Loss":
            result_color = "Red"
        else:
            result_color = "White"
        self.text(match[1], font=self.large_font, fill=result_color, x=50)
        self.text(match[4], x=75)
        self.current_pixel = (self.current_pixel[0], self.current_pixel[1] + 5)
        for item in match[6]:
            self.resize_paste(self.get_item_icon(item), (30, 30), space=1)
        self.current_pixel = (self.current_pixel[0] + 10, self.current_pixel[1])
        self.text(match[5], x=40, fill=(135, 157, 237, 255))
        gold_with_comma = str(match[7][0:-3]) + "," + str(match[7][-3:])
        self.text(text=gold_with_comma, x=75, fill="Yellow")

    def generate_player_history(self, match_history):  # match history = [[match], [match]]
        self.current_image = Image.new('RGBA', (530, 50*len(match_history)))
        self.draw = ImageDraw.Draw(self.current_image)
        self.current_pixel = (0, 0)
        for match in match_history:
            self.generate_history_game(match)
            self.current_pixel = (0, self.current_pixel[1] + 40)
        self.current_image.save("temp.png")

    def generate_rating_img(self, ratings, sigmas, name):
        x = range(len(ratings))
        n = len(ratings) - 1
        plt.style.use('dark_background')
        fig = plt.figure(figsize=(12, 4))
        plt.rcParams["font.size"] = 12
        # plt.plot([0, n], [1500, 1500], '--b')
        plt.xticks([])
        ax = plt.subplot(111)
        upper = np.asarray(ratings, dtype='float') + np.asarray(sigmas, dtype='float')
        lower = np.asarray(ratings, dtype='float') - np.asarray(sigmas, dtype='float')
        ax.plot(x, ratings, marker="o", color="lime")
        ax.fill_between(x, upper, lower, alpha=0.15, color="aquamarine")
        ax.set_xlim(0, n)
        ax.set_title("Your Rating Transition")
        ax.grid()
        fig.savefig(f"data/ratings_imgs/{name}.png", transparent=True, bbox_inches='tight', pad_inches=0)

    def generate_stats_img(self, dfs, puuid, period_text='All Time'):
        df_game, df_player, df_stats, df_participants = dfs
        LANE = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']
        
        # 本人のデータのみを抽出した概要用データフレーム
        df_user_p = df_participants[df_participants['puuid'] == puuid]
        df = pd.merge(df_stats, df_user_p, on=['gameId', 'participantId', 'puuid'])
        n = len(df)

        self.current_image = Image.new('RGBA', (575, 485), color='#010a13')
        self.draw = ImageDraw.Draw(self.current_image)

        # タイトルの描画 (All Time or Season X)
        self.current_pixel = (20, 0)
        self.text(text=period_text, font=self.large_font, fill='#e79500')
        
        # 全体スタッツの描画
        kda_val = sum(df['kills'] + df['assists']) / np.clip(sum(df['deaths']), 1, None)
        win = sum(df['win']) / n
        y = self.current_pixel[1] + 35
        self.current_pixel = (40, y)
        self.text(text='Games', font=self.large_font, fill='#e79500')
        self.current_pixel = (150, y)
        self.text(text='Winrate', font=self.large_font, fill='#e79500')
        self.current_pixel = (65, y + 30)
        self.text(text=f'{n}', font=self.large_font)
        self.current_pixel = (160, y + 30)
        self.text(text=f'{win:.1%}', font=self.large_font)

        self.current_pixel = (70, y + 70)
        avg_kills = np.mean(df['kills'])
        avg_assists = np.mean(df['assists'])
        avg_deaths = np.mean(df['deaths'])
        y_pos = self.current_pixel[1]
        self.text(text=f'{avg_kills:.1f}' , font=self.large_font, fill='green', x=35)
        self.current_pixel = (self.current_pixel[0], y_pos)
        self.text(text='/' , font=self.large_font, x=15)
        self.current_pixel = (self.current_pixel[0], y_pos)
        self.text(text=f'{avg_deaths:.1f}' , font=self.large_font, fill='red', x=35)
        self.current_pixel = (self.current_pixel[0], y_pos)
        self.text(text='/' , font=self.large_font, x=15)
        self.current_pixel = (self.current_pixel[0], y_pos)
        self.text(text=f'{avg_assists:.1f}' , font=self.large_font, fill='yellow', x=30)
        self.current_pixel = (70, self.current_pixel[1] + 30)
        self.text(text=f'Average KDA: {kda_val:.2f}')
        
        # Radar Chart の計算 (母集団は全プレイヤー)
        dmg, cs, vision, kda_radar, obj = 0, 0, 0, 0, 0
        for lane in LANE:
            # そのレーンの全プレイヤーを抽出
            lane_all = pd.merge(df_stats, df_participants.query('position==@lane'), on=['gameId', 'participantId'])
            lane_all = pd.merge(lane_all, df_game.rename(columns={'id': 'gameId'}), on=['gameId'])

            if len(lane_all) < 2: continue # 比較対象がいない場合はスキップ

            # 各指標の算出
            dmgs = lane_all['totalDamageDealtToChampions'] / (lane_all['gameDuration'] / 60)
            css = lane_all['totalMinionsKilled'] / (lane_all['gameDuration'] / 60)
            visions = lane_all['visionScore'] / (lane_all['gameDuration'] / 60)
            kdas = (lane_all['kills'] + lane_all['assists']) / np.clip(lane_all['deaths'], 1, None)
            objs = lane_all['damageDealtToObjectives'] / (lane_all['gameDuration'] / 60)
            
            # 全プレイヤーの分布における本人のZスコア
            flag = lane_all['puuid_x'] == puuid
            if sum(flag) > 0:
                dmg += np.mean(((scipy.stats.zscore(dmgs) + 1) / 2)[flag]) * sum(flag) / n
                cs += np.mean(((scipy.stats.zscore(css) + 1) / 2)[flag]) * sum(flag) / n
                vision += np.mean(((scipy.stats.zscore(visions) + 1) / 2)[flag]) * sum(flag) / n
                kda_radar += np.mean(((scipy.stats.zscore(kdas) + 1) / 2)[flag]) * sum(flag) / n
                obj += np.mean(((scipy.stats.zscore(objs) + 1) / 2)[flag]) * sum(flag) / n

        label_list = ['KDA', 'CS', 'VISION', 'OBJECT', 'DMG']
        acc_list = np.clip([kda_radar, cs, vision, obj, dmg], 0, 1)
        rader_df = pd.DataFrame([acc_list], index=['stats'], columns=label_list)
        circos = Circos.radar_chart(rader_df, vmax=1, bg_color="#010a1300", grid_interval_ratio=0.25)
        
        buf = io.BytesIO()
        circos.savefig(buf, figsize=(6, 6), dpi=250)
        buf.seek(0)
        radar_img = Image.open(buf)
        self.current_pixel = (0, self.current_pixel[1] + 30)
        self.resize_paste(radar_img, (300, 300))

        # Roles の描画
        x_start = 300
        self.current_pixel = (x_start, 40)
        self.text(text='Roles', font=self.large_font, fill='#e79500')
        self.current_pixel = (x_start, self.current_pixel[1] + 30)
        y_role = self.current_pixel[1]
        self.current_pixel = (x_start + 40, y_role)
        self.text("Role")
        self.current_pixel = (x_start + 80, y_role)
        self.text("Games")
        self.current_pixel = (x_start + 140, y_role)
        self.text("Winrate")
        self.current_pixel = (x_start + 200, y_role)
        self.text("KDA")
        y_role += 30
        for lane in LANE:
            self.current_pixel = (x_start + 45, y_role)
            try:
                lane_icon = Image.open(f"position_icon/icon-position-{lane.lower()}.png")
                self.resize_paste(lane_icon, (20, 20), center="y", mask=lane_icon)
            except: pass
            self.current_pixel = (x_start + 100, self.current_pixel[1] - 3)
            y_curr = self.current_pixel[1]
            lane_df = df[df['position'] == lane]
            if len(lane_df) > 0:
                l_kda = sum(lane_df['kills'] + lane_df['assists']) / np.clip(sum(lane_df['deaths']), 1, None)
                l_win = sum(lane_df['win']) / len(lane_df)
                self.text(str(len(lane_df)))
                self.current_pixel = (x_start + 155, y_curr)
                self.text(f"{l_win:.1%}")
                self.current_pixel = (x_start + 210, y_curr)
                self.text(f"{l_kda:.2f}")
            else:
                self.text("-")
                self.current_pixel = (x_start + 155, y_curr)
                self.text("-")
                self.current_pixel = (x_start + 210, y_curr)
                self.text("-")
            y_role += 30

        # Champs の描画
        self.current_pixel = (x_start, y_role)
        self.text(text='Champs', font=self.large_font, fill='#e79500')
        champs = df["championName"].value_counts()[:5]

        self.current_pixel = (x_start, self.current_pixel[1] + 30)
        y_champ = self.current_pixel[1]
        self.current_pixel = (x_start + 40, y_champ)
        self.text("Name")
        self.current_pixel = (x_start + 90, y_champ)
        self.text("Games")
        self.current_pixel = (x_start + 150, y_champ)
        self.text("Winrate")
        self.current_pixel = (x_start + 210, y_champ)
        self.text("KDA")
        y_champ += 30
        for champ, _ in champs.items():
            champ_df = df[df['championName'] == champ]
            self.current_pixel = (x_start + 47, y_champ - 2)
            self.resize_paste(self.get_champ_icon(champ), (25, 25), center="y")
            self.current_pixel = (x_start + 100, self.current_pixel[1] + 2)
            y_curr = self.current_pixel[1]
            c_kda = sum(champ_df['kills'] + champ_df['assists']) / np.clip(sum(champ_df['deaths']), 1, None)
            c_win = sum(champ_df['win']) / len(champ_df)
            self.text(str(len(champ_df)))
            self.current_pixel = (x_start + 155, y_curr)
            self.text(f"{c_win:.1%}")
            self.current_pixel = (x_start + 210, y_curr)
            self.text(f"{c_kda:.2f}")
            y_champ += 30
            
        self.current_image.save(f"data/stats_imgs/{puuid}.png")