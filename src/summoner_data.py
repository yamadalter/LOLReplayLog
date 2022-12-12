import yaml
import os
from src import replay_reader
import pandas as pd


def simplify(num):
    if num % 1 == 0:
        return int(num)
    else:
        return num


class SummonerData:
    def __init__(self):
        self.winners = []
        self.losers = []
        if os.path.exists("data/id_to_summoner.yaml"):
            with open("data/id_to_summoner.yaml", "r", encoding="utf-8") as f:
                self.id2sum = yaml.load(f, Loader=yaml.FullLoader)
        else:
            with open("data/id_to_summoner.yaml", "w", encoding="utf-8") as f:
                self.id2sum = {'test': '0'}

    def link_id2sum(self, summoner_name, discord_id):
        ids = self.id2sum.get(summoner_name, [])
        taken_ids = []
        for summoner_names in self.id2sum:
            for taken_id in self.id2sum[summoner_names]:
                taken_ids.append(taken_id)
        if discord_id in ids:
            return "Summoner already linked"
        elif discord_id in taken_ids:
            return "Someone else already has this summoner name"
        else:
            ids.append(discord_id)
            self.id2sum[summoner_name] = ids
            self.save_id2sum()
            return "Summoner successfully linked"

    def unlink(self, summoner_name, discord_id):
        if summoner_name is None:
            summoner_name = self.sum2id(discord_id)
        if summoner_name not in self.id2sum.keys():
            return "Summoner was not linked"
        del self.id2sum[summoner_name]
        self.save_id2sum()
        return "Summoner unlinked"

    def log(self, replay_id, old_df):  # Summoner name (file) -> map (1 of 2 lists) -> [Champion, game result, KDA]
        replay = replay_reader.ReplayReader(replay_id)
        self.winners, self.losers = replay.results()
        pstats = replay.get_player_stats()
        df = pd.DataFrame()
        for player in pstats:
            df = pd.concat([df, pd.DataFrame(player.values(), index=player.keys()).T])
        df = pd.concat([df, old_df])
        return df

    def history(self, discord_id=None, summoner_name=None, mode="all"):
        names = []
        if discord_id:
            if str(discord_id) in self.sum2id:
                for summoner_names in self.sum2id[str(discord_id)]:
                    names.append(summoner_names)
            else:
                return ["Discord ID not linked."]
        elif summoner_name:
            names.append(summoner_name)
        matches = []
        for name in names:
            try:
                with open(f"data/players/{name}.yaml", "r") as f:
                    match_history = yaml.load(f, Loader=yaml.FullLoader)
            except FileNotFoundError:
                return [f"Summoner name {name} not found"]
            sr_matches = match_history.get("Summoner's Rift", [])
            ha_matches = match_history.get("Howling Abyss", [])
            if mode.lower() == "all":
                matches += sr_matches
                matches += ha_matches
            elif mode.lower() == "ha" or mode.lower().replace(" ", "") == "howlingabyss":
                matches += ha_matches
            elif mode.lower() == "sr" or mode.lower().replace(" ", "").replace("'", "") == "summonersrift":
                matches += sr_matches
        return matches

    def profile(self, matches):
        games = 0
        wins = 0
        champ_data = {}
        if len(matches) == 0:
            return "No matches found on that map"
        if len(matches) == 1 and not ("|" in matches[0]):
            return matches[0]
        for match in matches:
            champ, result, kda, game_id, csm = match.split("|")
            current_champ_data = champ_data.get(champ, [0, 0, 0, 0, 0, 0])  # {Champ: [W, L, K, D, A, CS/M]}
            if result == "Win":
                current_champ_data[0] += 1
                wins += 1
            elif result == "Loss":
                current_champ_data[1] += 1
            games += 1
            kills, deaths, assists = kda.split("/")
            current_champ_data[2] += int(kills)
            current_champ_data[3] += int(deaths)
            current_champ_data[4] += int(assists)
            current_champ_data[5] += float(csm)
            champ_data[champ] = current_champ_data
        champ_data_list = []
        for champ in champ_data:
            avg_champ_data = {"champion": champ, "games": champ_data[champ][0] + champ_data[champ][1], "wins": champ_data[champ][0]}
            avg_champ_data["wr"] = int((champ_data[champ][0] / avg_champ_data["games"]) * 100)  # Winrate
            average_k = simplify((champ_data[champ][2] / avg_champ_data["games"]))  # Average kills
            average_d = simplify((champ_data[champ][3] / avg_champ_data["games"]))  # Average deaths
            average_a = simplify((champ_data[champ][4] / avg_champ_data["games"]))  # Average assists
            avg_champ_data["kda"] = f"{average_k}/{average_d}/{average_a}"
            avg_champ_data["kdr"] = round((average_a + average_k) / average_d, 2)
            avg_champ_data["csm"] = simplify(round(champ_data[champ][5] / avg_champ_data["games"], 1))  # Average CS per minute
            champ_data_list.append(avg_champ_data)
        return champ_data_list

    def save_id2sum(self): 
        with open("data/id_to_summoner.yaml", "w", encoding="utf-8") as f:
            yaml.dump(self.id2sum, f, allow_unicode=True, encoding='utf-8')

    def ward_alert(self, replay_id): 
        replay = replay_reader.ReplayReader(replay_id)
        pstats = replay.get_player_stats()
        alert_list = []
        arrest_list = []
        for player in pstats:
            id = self.id2sum.get(player['name'], [])
            if len(id) > 0:
                name = f'<@{id[0]}>'
            else:
                name = player['name']

            if int(player['vision_ward']) == 1:
                alert_list.append(name)
            elif int(player['vision_ward']) < 1:
                arrest_list.append(name)

        return alert_list, arrest_list

    def sum2id(self, discord_id):
        list_of_key = list(self.id2sum.keys())
        multi_list = list(self.id2sum.values())
        list_of_value = [x[0] for x in multi_list]
        if str(discord_id) in list_of_value:
            position = list_of_value.index(discord_id)
            return list_of_key[position]
        else:
            return None
