import yaml
import os
import random
import itertools
import math
import numpy as np
from src import summoner_data
from openskill import Rating, rate, create_rating, team_rating
from typing import Union, List
from openskill.constants import beta
from openskill.statistics import phi_major

TEAM_NUM = 5
MU = 1500
SIGMA = MU / 3


class SkillRating:
    def __init__(self):
        self.summoner_data = summoner_data.SummonerData()
        if os.path.exists("data/ratings.yaml"):
            with open("data/ratings.yaml", "r", encoding="utf-8") as f:
                self.ratings = yaml.load(f, Loader=yaml.FullLoader)
        else:
            with open("data/ratings.yaml", "w", encoding="utf-8") as f:
                self.ratings = {'test': [MU, SIGMA]}

    async def make_team(self, reaction):
        players = []
        async for user in reaction.users():
            if not user == reaction.message.author:
                if str(user.id) not in self.ratings.keys():
                    self.ratings[str(user.id)] = [[MU], [SIGMA]]
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
                t1.append(create_rating(self.ratings[str(t1_name[j])]))
                t2.append(create_rating(self.ratings[str(t2_name[j])]))
            predictions = self.predict_win(teams=[t1, t2])

            if np.abs(predictions[0] - predictions[1]) < minp:
                team = [t1_name, t2_name]
                minp = np.abs(predictions[0] - predictions[1])
            if predictions[0] < 0.53 and predictions[0] >= 0.47:
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
                    (mu_a - mu_b)
                    / math.sqrt(n * beta(mu=1500) ** 2 + sigma_a + sigma_b)
                )
            )

        return [
            (sum(team_prob) / denom)
            for team_prob in itertools.zip_longest(
                *[iter(pairwise_probabilities)] * (n - 1)
            )
        ]

    def get_player(self, team):
        t = []
        t_name = []
        for p in team:
            id = self.summoner_data.id2sum.get(p, [])
            if len(id) > 0:
                name = id[0]
            else:
                name = p
                if name not in self.ratings.keys():
                    self.ratings[str(name)] = [[MU, SIGMA]]
                    self.save_ratings(self.ratings)
            t.append(create_rating(self.ratings[str(name)][-1]))
            t_name.append(name)
        return t, t_name

    def update_ratings(self, winners, losers):
        if len(winners) < TEAM_NUM or len(losers) < TEAM_NUM:
            return

        t1, t1_name = self.get_player(winners)
        t2, t2_name = self.get_player(losers)

        [t1, t2] = rate([t1, t2])
        for t, name in zip(t1, t1_name):
            self.ratings[str(name)].append([t.mu, t.sigma])
        for t, name in zip(t2, t2_name):
            self.ratings[str(name)].append([t.mu, t.sigma])

        self.save_ratings(self.ratings)
        return

    def init_ratings(self, id, sn, mu=1500, sigma=500):
        if id is not None:
            if (sn is not None) & (sn in self.ratings.keys()):
                del self.ratings[str(sn)]
            self.ratings[str(id)].append([mu, sigma])
        else:
            if sn is not None:
                self.ratings[str(sn)].append([mu, sigma])

        self.save_ratings(self.ratings)

    def save_ratings(self, ratings):
        self.ratings = ratings
        with open("data/ratings.yaml", "w", encoding="utf-8") as f:
            yaml.dump(self.ratings, f, allow_unicode=True, encoding='utf-8')
