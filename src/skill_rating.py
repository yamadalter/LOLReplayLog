import yaml
import os
import glob
import random
import itertools
import math
import numpy as np
from src import summoner_data
from openskill import Rating, rate, create_rating, team_rating
from typing import Union, List
from openskill.constants import beta
from openskill.statistics import phi_major
from src import riot_api

TEAM_NUM = 5
MU = 1500
SIGMA = MU / 3
KEY = ['id', 'mu', 'sigma']
TIER = ['IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']
RANK = ['IV', 'III', 'II', 'I']


class SkillRating:
    def __init__(self):
        self.ratings = {}
        for path in glob.glob('data/ratings/*.yaml'):
            name = os.path.splitext(os.path.basename(path))[0]
            with open(path, "r", encoding="utf-8") as f:
                self.ratings[name] = yaml.load(f, Loader=yaml.FullLoader)

    async def make_team(self, reaction):
        players = []
        async for user in reaction.users():
            if not user == reaction.message.author:
                if str(user.id) not in self.ratings.keys():
                    self.ratings[str(user.id)] = {'id': ['init'], 'mu': [MU], 'sigma': [SIGMA]}
                    self.save_ratings(self.ratings)
                players.append(user.id)
        minp = 1
        team = []
        for _ in range(252):
            t1 = []
            t2 = []
            random.shuffle(players)
            t1_name = players[:TEAM_NUM]
            t2_name = players[TEAM_NUM:]
            for j in range(TEAM_NUM):
                t1.append(create_rating([self.ratings[str(t1_name[j])][k][-1] for k in KEY[1:]]))
                t2.append(create_rating([self.ratings[str(t2_name[j])][k][-1] for k in KEY[1:]]))
            predictions = self.predict_win(teams=[t1, t2])

            if np.abs(predictions[0] - predictions[1]) < minp:
                team = [t1_name, t2_name]
                minp = np.abs(predictions[0] - predictions[1])
            if predictions[0] < 0.52 and predictions[0] >= 0.48:
                team = [t1_name, t2_name]
                break

        self.save_ratings(self.ratings)
        return team

    def predict_win(self, teams: List[List[Rating]], **options) -> List[Union[int, float]]:
        if len(teams) < 2:
            raise ValueError("Expected at least two teams.")

        n = len(teams)
        denom = (n * (n - 1)) / 2

        pairwise_probabilities = []
        for pairwise_subset in itertools.permutations(teams, 2):
            current_team_a_rating = team_rating([pairwise_subset[0]])
            current_team_b_rating = team_rating([pairwise_subset[1]])
            mu_a = current_team_a_rating[0][0]
            sigma_a = current_team_a_rating[0][1]
            mu_b = current_team_b_rating[0][0]
            sigma_b = current_team_b_rating[0][1]
            pairwise_probabilities.append(
                phi_major(
                    (mu_a - mu_b) / math.sqrt(n * beta(mu=1500) ** 2 + sigma_a + sigma_b)
                )
            )

        return [
            (sum(team_prob) / denom)
            for team_prob in itertools.zip_longest(
                *[iter(pairwise_probabilities)] * (n - 1)
            )
        ]

    def get_player(self, team):
        Summoner_data = summoner_data.SummonerData()
        t = []
        t_name = []
        for p in team:
            id = Summoner_data.id2sum.get(p, None)
            if id is not None:
                name = id[0]
            else:
                return None, p
            t.append(create_rating([self.ratings[str(name)][k][-1] for k in KEY[1:]]))
            t_name.append(name)
        return t, t_name

    def update_ratings(self, id, winners, losers):
        if len(winners) < TEAM_NUM or len(losers) < TEAM_NUM:
            return None

        t1, t1_name = self.get_player(winners)
        t2, t2_name = self.get_player(losers)
        if t1 is None or t2 is None:
            return None
        [t1, t2] = rate([t1, t2])
        for t, name in zip(t1, t1_name):
            if t.sigma < 300:
                t.sigma = 300
            for k, item in zip(KEY, [id, t.mu, t.sigma]):
                self.ratings[str(name)][k].append(item)
        for t, name in zip(t2, t2_name):
            if t.sigma < 300:
                t.sigma = 300
            for k, item in zip(KEY, [id, t.mu, t.sigma]):
                self.ratings[str(name)][k].append(item)

        self.save_ratings(self.ratings)
        return t1_name + t2_name

    def init_ratings(self, id, sn):
        if id and sn is not None:
            watcher = riot_api.RiotWatcher()
            rank, tier = watcher.search_rank(sn)
            if rank is not None and tier is not None:
                if tier == 'MASTER':
                    mu = 2900
                elif tier == 'GRANDMASTER':
                    mu = 3200
                elif tier == 'CHALLENGER':
                    mu = 3500
                else:
                    mu = TIER.index(tier) * 400 + RANK.index(rank) * 100 + 500
                sigma = 400
            else:
                if str(id) in self.ratings.keys():
                    for k, item in zip(KEY, ['reset', 1500, 500]):
                        self.ratings[str(id)][k].append(item)
                else:
                    self.ratings[str(id)] = {'id': ['init'], 'mu': [1500], 'sigma': [500]}
                return None, 1500
            if str(id) in self.ratings.keys():
                for k, item in zip(KEY, ['reset', mu, sigma]):
                    self.ratings[str(id)][k].append(item)
            else:
                self.ratings[str(id)] = {'id': ['init'], 'mu': [mu], 'sigma': [sigma]}

            self.save_ratings(self.ratings)
            return f'your rank is {tier} {rank}  \n\u200b your rate is {mu}', mu
        else:
            return None, None

    def save_ratings(self, ratings):
        self.ratings = ratings
        for k in self.ratings.keys():
            with open(f"data/ratings/{k}.yaml", "w", encoding="utf-8") as f:
                yaml.dump(self.ratings[k], f, allow_unicode=True, encoding='utf-8')
