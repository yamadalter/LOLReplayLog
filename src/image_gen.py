from PIL import Image, ImageDraw, ImageFont
import numpy as np
import matplotlib.pyplot as plt
import json
import pandas as pd
import scipy.stats
from pycirclize import Circos
import matplotlib as mpl
import io
mpl.rcParams['figure.facecolor'] = '#000000'
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
        self.large_font = ImageFont.truetype("data/NotoSansJP-Thin.otf", 24)
        self.normal_font = ImageFont.truetype("data/NotoSansJP-Thin.otf", 16)

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

    def resize_paste(self, img, size, center="", mvmt="right", space=10):
        if img is None:  # when does this happen ?
            pass
        else:
            x = self.current_pixel[0]
            y = self.current_pixel[1]
            if "x" in center:
                x += int(size[0]*.5)
            if "y" in center:
                y += int(size[1]*.5)
            self.current_image.paste(img.resize(size), (x, y))
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
        self.resize_paste(self.get_rune_img(player["perk0"], 0), (40, 40), space=2)
        self.resize_paste(self.get_style_img(player["perkSubStyle"]), (20, 20), center="y")
        self.resize_paste(self.get_champ_icon(player["SKIN"]), (40, 40))
        self.text(text=f'{player["gamename"]}', x=250)
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
        self.current_image = Image.new('RGBA', (775, 150 + additional_pixels), color='#000000')
        self.draw = ImageDraw.Draw(self.current_image)
        self.current_pixel = (0, 0)
        self.text(text=f"{player_list[3]} ({player_list[4]})")
        self.current_pixel = (0, self.current_pixel[1] + 20)
        self.text(text=f"Winners ({player_list[0][0]}) side:{player_list[5][0]}", font=self.large_font, y=40)
        self.current_pixel = (400, self.current_pixel[1])
        for ban in player_list[6][0]:
            self.resize_paste(self.get_champ_icon(ban), (25, 25), center="y")
        self.current_pixel = (0, self.current_pixel[1] + 50)
        for winner in player_list[1]:
            self.generate_player_imgs(winner)
        self.text(text=f"Losers ({player_list[0][1]}) side:{player_list[5][1]}", font=self.large_font, y=40)
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

    def generate_stats_img(self, dfs, puuid):
        df_game, df_player, df_stats, df_participants = dfs
        LANE = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']
        df = df_participants[df_participants['puuid'] == puuid]
        df = pd.merge(df_stats, df, on=['gameId', 'participantId', 'puuid'])
        n = len(df)
        gamename = df_player[df_player['puuid'] == puuid]['gameName'].iloc[0]
        tag = df_player[df_player['puuid'] == puuid]['tagLine'].iloc[0]

        self.current_image = Image.new('RGBA', (575, 500), color='#000000')
        self.draw = ImageDraw.Draw(self.current_image)
        self.current_pixel = (40, 0)

        # サモナーネームとタグの描画
        self.text(text=f"{gamename} #{tag}", font=self.large_font)

        # ゲーム情報、勝率、KDA の描画
        self.current_pixel = (20, self.current_pixel[1] + 50)
        self.text(text='All Game', font=self.large_font)
        kda = sum(df['kills'] + df['assists']) / np.clip(sum(df['deaths']), 1, None)
        win = sum(df['win']) / n
        y = self.current_pixel[1] + 35
        self.current_pixel = (40, y)
        self.text(text='Games', font=self.large_font)
        self.current_pixel = (150, y)
        self.text(text='Winrate', font=self.large_font)
        self.current_pixel = (65, y + 30)
        self.text(text=f'{n}', font=self.large_font)
        self.current_pixel = (160, y + 30)
        self.text(text=f'{win:.1%}', font=self.large_font)

        self.current_pixel = (70, y + 70)
        kills = np.mean(df['kills'])
        assists = np.mean(df['assists'])
        deaths = np.mean(df['deaths'])
        y = self.current_pixel[1]
        self.text(text=f'{kills:.1f}' , font=self.large_font, fill='green', x=35)
        self.current_pixel = (self.current_pixel[0], y)
        self.text(text='/' , font=self.large_font, x=15)
        self.current_pixel = (self.current_pixel[0], y)
        self.text(text=f'{deaths:.1f}' , font=self.large_font, fill='red', x=35)
        self.current_pixel = (self.current_pixel[0], y)
        self.text(text='/' , font=self.large_font, x=15)
        self.current_pixel = (self.current_pixel[0], y)
        self.text(text=f'{assists:.1f}' , font=self.large_font, fill='yellow', x=30)
        self.current_pixel = (70, self.current_pixel[1] + 30)
        self.text(text=f'Average KDA: {kda:.2f}')
        self.current_pixel = (0, self.current_pixel[1] + 30)

        # RaderChart
        dmg, cs, vision, kda, obj = 0, 0, 0, 0, 0
        for lane in LANE:
            lane_df = pd.merge(df_stats, df_participants.query('position==@lane'), on=['gameId', 'participantId'])
            lane_df = pd.merge(lane_df, df_game.rename(columns={'id': 'gameId'}), on=['gameId'])

            dmgs = lane_df['totalDamageDealtToChampions'] / (lane_df['gameDuration'] / 60)
            css = lane_df['totalMinionsKilled'] / (lane_df['gameDuration'] / 60)
            visions = lane_df['visionScore'] / (lane_df['gameDuration'] / 60)
            kdas = (lane_df['kills'] + lane_df['assists']) / np.clip(lane_df['deaths'], 1, None)
            objs = lane_df['damageDealtToObjectives'] / (lane_df['gameDuration'] / 60)
            flag = lane_df['puuid_x'] == puuid
            if sum(flag) > 0:
                dmg += np.mean(((scipy.stats.zscore(dmgs) + 1) / 2)[flag]) * sum(flag) / n
                cs += np.mean(((scipy.stats.zscore(css) + 1) / 2)[flag]) * sum(flag) / n
                vision += np.mean(((scipy.stats.zscore(visions) + 1) / 2)[flag]) * sum(flag) / n
                kda += np.mean(((scipy.stats.zscore(kdas) + 1) / 2)[flag]) * sum(flag) / n
                obj += np.mean(((scipy.stats.zscore(objs) + 1) / 2)[flag]) * sum(flag) / n
        label_list = ['KDA', 'CS', 'VISION', 'OBJECT', 'DMG']
        acc_list = [kda, cs, vision, obj, dmg]
        rader_df = pd.DataFrame([acc_list], index=['test'], columns=label_list)
        circos = Circos.radar_chart(
            rader_df,
            vmax=1,
            bg_color="#ffffff00",
            grid_interval_ratio=0.25
        )
        buf = io.BytesIO()
        circos.savefig(buf, figsize=(6, 6), dpi=250)
        buf.seek(0)
        img2 = Image.open(buf)
        self.current_pixel = (0, self.current_pixel[1])
        self.resize_paste(img2, (300, 300))

        # 各レーンの情報の描画
        x = 300
        self.current_pixel = (x, 50)
        self.text(text='Roles', font=self.large_font)
        self.current_pixel = (x, self.current_pixel[1] + 30)
        y = self.current_pixel[1]
        self.current_pixel = (x + 40, y)
        self.text("Role")
        self.current_pixel = (x + 80, y)
        self.text("Games")
        self.current_pixel = (x + 140, y)
        self.text("Winrate")
        self.current_pixel = (x + 200, y)
        self.text("KDA")
        y = y + 40
        for lane in LANE:
            self.current_pixel = (x + 45, y)
            self.resize_paste(Image.open(f"position_icon/icon-position-{lane.lower()}.png"), (20, 20), center="y")
            self.current_pixel = (x + 100, self.current_pixel[1] - 3)
            y = self.current_pixel[1]
            lane_df = df[df['position'] == lane]
            if len(lane_df) > 0:
                lane_df = df[df['position'] == lane]
                lane_kda = sum(lane_df['kills'] + lane_df['assists']) / np.clip(sum(lane_df['deaths']), 1, None)
                lane_win = sum(lane_df['win']) / len(lane_df)
                self.text(str(len(lane_df)))
                self.current_pixel = (x + 155, y)
                self.text(f"{lane_win:.1%}")
                self.current_pixel = (x + 210, y)
                self.text(f"{lane_kda:.2f}")
            else:
                self.text("-")
                self.current_pixel = (x + 155, y)
                self.text("-")
                self.current_pixel = (x + 210, y)
                self.text("-")
            y += 30

        # Favorite Champion
        self.current_pixel = (x, self.current_pixel[1] + 30)
        self.text(text='Favorite Champ', font=self.large_font)
        if len(df) > 4:
            champs = df["championName"].value_counts()[:5]
        else:
            champs = df["championName"].value_counts()[:len(df)]

        self.current_pixel = (x, self.current_pixel[1] + 30)
        y = self.current_pixel[1]
        self.current_pixel = (x + 40, y)
        self.text("Name")
        self.current_pixel = (x + 90, y)
        self.text("Games")
        self.current_pixel = (x + 150, y)
        self.text("Winrate")
        self.current_pixel = (x + 210, y)
        self.text("KDA")
        y += 40
        for champ, _ in champs.items():
            champ_df = df[df['championName'] == champ]
            self.current_pixel = (x + 47, y - 2)
            self.resize_paste(self.get_champ_icon(champ), (25, 25), center="y")
            self.current_pixel = (x + 100, self.current_pixel[1] + 2)
            y = self.current_pixel[1]
            champ_kda = sum(champ_df['kills'] + champ_df['assists']) / np.clip(sum(champ_df['deaths']), 1, None)
            champ_win = sum(champ_df['win']) / len(champ_df)
            self.text(str(len(champ_df)))
            self.current_pixel = (x + 155, y)
            self.text(f"{champ_win:.1%}")
            self.current_pixel = (x + 210, y)
            self.text(f"{champ_kda:.2f}")
            y += 30
        self.current_image.save(f"data/stats_imgs/{puuid}.png")