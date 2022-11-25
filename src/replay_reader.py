import json
import os
import time
from src import image_gen


class ReplayReader:
    def __init__(self, replay_id):
        if os.path.exists(f'data/replays/{replay_id}.json'):
            filename = f"data/replays/{replay_id}.json"
        else:
            filename = f"data/replays/{replay_id}.rofl"
        if filename.endswith('.rofl'):
            with open(filename, 'r', encoding="utf8", errors="ignore") as f:
                read_data = f.read()
                start_json = read_data.find(r'{"gameLength"')
                read_data = read_data[start_json:]
                end_json = read_data.find(r'\"}]"}')
                read_data = read_data[:(end_json + 6)]
            with open(f"{filename[0:-5]}.json", "w") as f:
                json_from_rofl = json.loads(read_data)
                new_json_str = json.dumps(json_from_rofl, indent=2)
                f.write(new_json_str)
            os.remove(filename)  # Rofl files take up a lot of space. Convert them to their JSON and delete them
            filename = filename[0:-5] + ".json"
        with open(filename) as json_file:
            self.json = json.load(json_file)
        self.stats = json.loads(self.json['statsJson'])
        self.map = self.infer_map()
        self.game_time = (self.json['gameLength'] / 1000)  # (Milliseconds -> Seconds)
        self.game_time_str = time.strftime("%M:%S", time.gmtime(self.game_time))
        self.match_id = replay_id
        self.image_gen = image_gen.ImageGen()

    def infer_map(self):  # The map is not given to us, so we must infer.
        sr_trinkets = [3340, 3364, 3363, 3513]
        sr_stats = ["BARON_KILLS", "DRAGON_KILLS", "WARD_PLACED",
                    "NEUTRAL_MINIONS_KILLED"]  # If any of these stats are above 0, it is guaranteed to be Summoner's Rift.
        poro_snax = 2052
        is_aram = True
        for player_stats in self.stats:
            for sr_stat in sr_stats:
                if int(player_stats[sr_stat]) > 0:
                    is_aram = False
            for trinket in sr_trinkets:  # Check trinket to find wards (SR) or Poro-Snax (HA)
                if int(player_stats["ITEM6"]) == trinket:
                    is_aram = False
                elif int(player_stats["ITEM6"]) == poro_snax:
                    is_aram = True
        if is_aram:
            return "Howling Abyss"
        elif not is_aram:  # Sadly Twisted Treeline no longer exists
            return "Summoner's Rift"

    def results(self):  # Returns a list of winners & losers
        winners = []
        losers = []
        for player_stats in self.stats:
            if player_stats["WIN"] == "Win":
                winners.append(player_stats["NAME"])
            elif player_stats["WIN"] == "Fail":
                losers.append(player_stats["NAME"])
        return winners, losers

    def get_player_stats(self, summoner_name=None, champ=None):
        """
        Can take a summoner name or champion as arguments. Returns player stats as a dict for that player/champ.
        If neither are given, returns a list of all players and their stats.
        :param summoner_name:
        :param champ:
        :return:
        """
        player_list = []
        for players in self.stats:
            player_dict = {}
            items = []
            for i in range(7):
                items.append(players[f"ITEM{i}"])
            if players["NAME"] == summoner_name or players["SKIN"] == champ or (summoner_name is None and champ is None):
                player_dict["game_id"] = self.match_id
                player_dict["name"] = players["NAME"]
                player_dict["champion"] = players["SKIN"]
                player_dict["position"] = players["TEAM_POSITION"]
                player_dict["result"] = 'Win' if players["WIN"] == "Win" else 'Lose'
                player_dict["kda"] = f"{players['CHAMPIONS_KILLED']}/{players['NUM_DEATHS']}/{players['ASSISTS']}"
                player_dict["kill"] = players["CHAMPIONS_KILLED"]
                player_dict["death"] = players['NUM_DEATHS']
                player_dict["assist"] = players['ASSISTS']
                player_dict["cs"] = str(int(players["MINIONS_KILLED"]) + int(players["NEUTRAL_MINIONS_KILLED"]))
                player_dict["csm"] = int(player_dict["cs"]) / (self.game_time / 60)
                player_dict["vision_score"] = players["VISION_SCORE"]
                player_dict["ward_placed"] = players["WARD_PLACED"]
                player_dict["ward_kill"] = players["WARD_KILLED"]
                player_dict["vision_ward"] = players["VISION_WARDS_BOUGHT_IN_GAME"]
                player_dict["damage_to_champ"] = players['TOTAL_DAMAGE_DEALT_TO_CHAMPIONS']
                player_dict["damage_taken"] = players['TOTAL_DAMAGE_TAKEN']
                player_dict["double_kill"] = players["DOUBLE_KILLS"]
                player_dict["triple_kill"] = players["TRIPLE_KILLS"]
                player_dict["quadra_kill"] = players["QUADRA_KILLS"]
                player_dict["penta_kill"] = players["PENTA_KILLS"]
                player_dict["game_time"] = self.game_time
                player_dict["keystone"] = players["KEYSTONE_ID"]
                player_dict["subperk"] = players["PERK_SUB_STYLE"]
                player_dict["runes"] = [[players["PERK1"], players["PERK2"], players["PERK3"]], [players["PERK4"], players["PERK5"]]]  # smaller runes
                player_dict["gold"] = players["GOLD_EARNED"]
                player_dict["items"] = items
                player_dict["map"] = self.map
                # player_dict["rate"] = rate[players["NAME"]]
                player_list.append(player_dict)
        if len(player_list) == 1:
            return player_list[0]
        return player_list

    def get_team_kdas(self):
        winner_kda = [0, 0, 0]
        loser_kda = [0, 0, 0]
        for player_stats in self.stats:
            if player_stats["WIN"] == "Win":
                kda = winner_kda
            elif player_stats["WIN"] == "Fail":
                kda = loser_kda
            kda[0] += int(player_stats["CHAMPIONS_KILLED"])
            kda[1] += int(player_stats["NUM_DEATHS"])
            kda[2] += int(player_stats["ASSISTS"])
        return f"{winner_kda[0]}/{winner_kda[1]}/{winner_kda[2]}", f"{loser_kda[0]}/{loser_kda[1]}/{loser_kda[2]}"

    def generate_game_img(self):
        winners = []  # [KEYSTONE_ID, PERK_SUB_STYLE, champ, name, KDA, [items]]
        losers = []
        for player in self.get_player_stats():
            if player["result"] == "Lose":
                list_to_mod = losers
            elif player["result"] == "Win":
                list_to_mod = winners
            list_to_mod.append(player)
        win_kda, lose_kda = self.get_team_kdas()
        self.image_gen.generate_game_img([[win_kda, lose_kda], winners, losers, self.map, self.game_time_str], self.match_id)