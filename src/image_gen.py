from PIL import Image, ImageDraw, ImageFont
import matplotlib as mpl
import matplotlib.pyplot as plt
import json


class ImageGen:
    def __init__(self):
        try:
            with open("data/runesReforged.json", "r") as f:
                self.rune_data = json.load(f)
        except FileNotFoundError:
            print("data/runesReforged.json not found. Download it from Riot's datadragon and restart.")
            exit()
        self.current_image = None
        self.draw = None
        self.current_pixel = (0, 0)
        self.large_font = ImageFont.truetype("/usr/share/fonts/google-noto/NotoSansJP-Thin.otf", 24)
        self.normal_font = ImageFont.truetype("/usr/share/fonts/google-noto/NotoSansJP-Thin.otf", 16)

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
        self.resize_paste(self.get_rune_img(player["keystone"], 0), (40, 40), space=2)
        self.resize_paste(self.get_style_img(player["subperk"]), (20, 20), center="y")
        self.resize_paste(self.get_champ_icon(player["champion"]), (40, 40))
        self.text(text=player["name"], x=150)
        self.text(text=player["kda"], x=75)
        self.current_pixel = (self.current_pixel[0], self.current_pixel[1] + 5)
        for item in player["items"]:
            self.resize_paste(self.get_item_icon(item), (30, 30), space=1)
        self.current_pixel = (self.current_pixel[0] + 10, self.current_pixel[1])
        self.text(text=player["cs"], x=40, fill=(135, 157, 237, 255))
        gold_with_comma = str(player["gold"][0:-3]) + "," + str(player["gold"][-3:])
        self.text(text=gold_with_comma, x=75, fill="Yellow")
        visions = f'{str(player["vision_score"])}/{str(player["ward_placed"])}/{str(player["ward_kill"])}/{str(player["vision_ward"])}'
        self.text(text=visions, x=75, fill="Red")
        self.current_pixel = (0, self.current_pixel[1] + 40)

    def generate_game_img(self, player_list, replay_id=None):
        # [[winner kda, loser kda], Winners, Losers, map, timestamp]
        # in each team will be a list of players, containing [KEYSTONE_ID, PERK_SUB_STYLE, champ, name, KDA, minions_killed, [items], gold_earned]
        additional_pixels = (len(player_list[1]) + len(player_list[2])) * 43  # add another 45 pts for each player
        self.current_image = Image.new('RGBA', (800, 150 + additional_pixels))
        self.draw = ImageDraw.Draw(self.current_image)
        self.current_pixel = (0, 0)
        self.text(text=f"{player_list[3]} ({player_list[4]})")
        self.current_pixel = (0, self.current_pixel[1] + 20)
        self.text(text=f"Winners ({player_list[0][0]})", font=self.large_font, y=40)
        self.current_pixel = (0, self.current_pixel[1] + 50)
        for winner in player_list[1]:
            self.generate_player_imgs(winner)
        self.text(text=f"Losers ({player_list[0][1]})", font=self.large_font, y=40)
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

    def generate_profile_stats(self, champ_data):
        """
        Draws champion data on the current image (self.current_image) with given data
        :param dict champ_data: Champion data, should contain keys "champion", "wins", "games", "kda", "csm", "wr"
        :return:
        """
        self.resize_paste(self.get_champ_icon(champ_data["champion"]), (50, 50))
        self.current_pixel = (self.current_pixel[0], self.current_pixel[1] - 12)
        self.text(champ_data["champion"], font=self.large_font, direction="down")
        self.text(f"{champ_data['csm']} CS/min", font=self.normal_font)
        self.current_pixel = (self.current_pixel[0] + 40, self.current_pixel[1] - 43)
        self.text(f"{champ_data['kdr']} KDA Ratio", font=self.large_font, direction="down")
        self.text(champ_data["kda"])
        self.current_pixel = (self.current_pixel[0] + 120, self.current_pixel[1] - 35)
        self.text(f"{champ_data['wr']} %", font=self.large_font, direction="down")
        self.text(f"{champ_data['games']} played")
        self.current_pixel = (0, self.current_pixel[1] + 30)

    def generate_player_profile(self, champ_data):
        """
        Draws a player profile akin to OP.GG's seasonal data on a new image.
        :param list champ_data: A list of champion data to be passed to generate_profile_stats
        :return:
        """
        self.current_image = Image.new('RGBA', (430, 50+(len(champ_data)*53)))
        self.draw = ImageDraw.Draw(self.current_image)
        self.current_pixel = (0, 50)
        overall_games = 0
        overall_wins = 0
        for champ in champ_data:
            self.generate_profile_stats(champ)
            overall_games += champ["games"]
            overall_wins += champ["wins"]
        overall_losses = overall_games - overall_wins
        overall_wr = int(round((overall_wins / overall_games) * 100, 0))
        self.current_pixel = (0, 0)
        self.text(text=f"{overall_wins}W {overall_losses}L ({overall_wr}% Winrate)", font=self.large_font)
        self.current_image.save("temp.png")

    def generate_rating_img(self, ratings, sigmas, name):

        x = range(len(ratings))
        l = len(ratings) - 1
        plt.style.use('dark_background')
        fig = plt.figure(figsize=(12, 4))
        plt.rcParams["font.size"] = 12
        plt.plot([0, l], [1500, 1500], '--b')
        plt.xticks([])
        ax = plt.subplot(111)
        ax.plot(x, ratings, marker="o", color="lime")
        ax.fill_between(x, ratings + sigmas, ratings - sigmas, alpha=0.15, color="aquamarine")
        ax.set_xlim(0, l)
        ax.set_title("Your Rating Transition")
        ax.grid()
        fig.savefig(f"data/ratings_imgs/{name}.png", transparent=True, bbox_inches='tight', pad_inches=0)
