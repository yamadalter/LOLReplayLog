import json
import os
import time
import image_gen
from utils import get_keys


class ReplayReader():
    def __init__(self, bot_functions, replay_id):
        self.match_id = replay_id
        self.image_gen = image_gen.ImageGen()
        f = open('data/versions.json', 'r')
        json_dict = json.load(f)
        self.version = json_dict[0]
        self.game_df = bot_functions.game.query(f'id == {replay_id}')
        self.player_df = bot_functions.df_player
        self.team_df = bot_functions.df_team.query(f'gameId == {replay_id}')
        self.bans_df = bot_functions.df_bans.query(f'gameId == {replay_id}')
        self.stats_df = bot_functions.df_stats.query(f'gameId == {replay_id}')
        self.participants_df = bot_functions.df_participants.query(f'gameId == {replay_id}')
        self.game_time = self.game_df['gameDuration']
        self.game_time_str = str(self.game_df['duration'])

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
        for p in self.participants_df:
            puuid = p['puuid']
            pid = p['participantId']
            player_dict = self.stats_df.query(f'participantId == {pid}')
            items = []
            for i in range(7):
                items.append(self.stats_df[f"item{i}"])
            player_dict['puuid'] = puuid
            player_dict["game_id"] = self.match_id
            player_dict["result"] = 'Win' if player_dict["win"] else 'Lose'
            player_dict["kda"] = f"{player_dict['kills']}/{player_dict['deaths']}/{player_dict['assists']}"
            player_dict["cs"] = str(int(player_dict["totalMinionsKilled"]) + int(player_dict["neutralMinionsKilled"]))
            player_dict["csm"] = int(player_dict["cs"]) / (self.game_time / 60)
            player_dict["game_time"] = self.game_time
            player_dict["runes"] = [[player_dict["perk0"], player_dict["perk1"], player_dict["perk2"]], [player_dict["perk3"], player_dict["perk4"]]]  # smaller runes
            player_dict["items"] = items
            player_dict['version'] = self.version
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

    def generate_game_img(self, d):
        winners = []  # [KEYSTONE_ID, PERK_SUB_STYLE, champ, name, KDA, [items]]
        losers = []
        for player in self.get_player_stats():
            if player["result"] == "Lose":
                list_to_mod = losers
            elif player["result"] == "Win":
                list_to_mod = winners
            player['gamename'] = self.player_df.loc[player['puuid']]['gameName']
            player['tag'] = self.player_df.loc[player['puuid']]['tagLine']
            list_to_mod.append(player)
        win_kda, lose_kda = self.get_team_kdas()
        self.image_gen.generate_game_img([[win_kda, lose_kda], winners, losers, "Summoner's Rift", self.game_time_str], self.match_id)