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
        if os.path.exists("data/rating.yaml"):
            with open("data/rating.yaml", "r", encoding="utf-8") as f:
                self.ratings = yaml.load(f, Loader=yaml.FullLoader)
        else:
            with open("data/rating.yaml", "w", encoding="utf-8") as f:
                self.ratings = {}

    async def make_team(self, reaction):
        players = []
        async for user in reaction.users():
            if not user == reaction.message.author:
                if user.id not in self.ratings.keys():
                    self.ratings[user.id] = [MU, SIGMA]
                players.append(user.id)
        self.save_ratings()
        minp = 1
        team = []
        for _ in range(252):
            t1 = []
            t2 = []
            random.shuffle(players)
            t1_name = players[:5]
            t2_name = players[5:]
            for j in range(5):
                t1.append(create_rating(self.ratings[t1_name[j]]))
                t2.append(create_rating(self.ratings[t2_name[j]]))
            predictions = self.predict_win(teams=[t1, t2])

            if np.abs(predictions[0] - predictions[1]) < minp:
                team = [t1_name, t2_name]
                minp = np.abs(predictions[0] - predictions[1])
            if predictions[0] < 0.52 and predictions[0] >= 0.48:
                team = [t1_name, t2_name]
                break

        self.save_ratings()
        return team

    def predict_win(teams: List[List[Rating]], **options) -> List[Union[int, float]]:
        if len(teams) < 2:
            raise ValueError(f"Expected at least two teams.")

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

    def update_ratings(self, winners, losers):
        if len(winners) < TEAM_NUM or len(losers) < TEAM_NUM:
            return
        t1, t2 = [], []
        t1_name, t2_name = [], []
        players = []
        for p in winners:
            id = summoner_data.id2sum.get(p, [])
            if len(id) > 0:
                name = id[0]
            else:
                name = p
            players.append(name)
            if name not in self.ratings.keys():
                self.ratings[name] = [MU, SIGMA]
            t1.append(create_rating(self.ratings[name]))
            t1_name.append(name)
        for p in losers:
            id = summoner_data.id2sum.get(p, [])
            if len(id) > 0:
                name = id[0]
            else:
                name = p
            players.append(name)
            if name not in self.ratings.keys():
                self.ratings[name] = [MU, SIGMA]
            t2.append(create_rating(self.ratings[name]))
            t2_name.append(name)

        [t1,t2] = rate([t1,t2])
        for t, name in zip(t1, t1_name):
            self.ratings[name] = [t.mu, t.sigma]
        for t, name in zip(t2, t2_name):
            self.ratings[name] = [t.mu, t.sigma]


    def save_ratings(self):
        with open("data/ratings.yaml", "w", encoding="utf-8") as f:
            yaml.dump(self.ratings, f, allow_unicode=True, encoding='utf-8')
