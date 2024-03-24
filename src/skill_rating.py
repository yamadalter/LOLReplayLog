import random
import itertools
import math
import numpy as np
import pandas as pd
from utils import get_keys
from common import TEAM_NUM, MU, SIGMA, INIT_SIGMA, MIN_SIGMA, SHUFFLE_NUM
from openskill import Rating, rate, create_rating, team_rating
from typing import Union, List
from openskill.constants import beta
from openskill.statistics import phi_major


class SkillRating:
    def __init__(self):
        self.ratings = {}

    async def make_team(self, d, reaction):
        players = []
        async for user in reaction.users():
            if not user == reaction.message.author:
                if str(user.id) not in d:
                    return False, str(user.id)
                players.append(str(user.id))
        minp = 1
        team = []
        for _ in range(SHUFFLE_NUM):
            t1 = []
            t2 = []
            random.shuffle(players)
            t1_name = players[:TEAM_NUM]
            t2_name = players[TEAM_NUM:]
            for j in range(TEAM_NUM):
                mu = d[t1_name[j]]['mu'][-1]
                sigma = d[t1_name[j]]['sigma'][-1]
                t1.append(create_rating([mu, sigma]))
                mu = d[t2_name[j]]['mu'][-1]
                sigma = d[t2_name[j]]['sigma'][-1]
                t2.append(create_rating([mu, sigma]))
            predictions = self.predict_win(teams=[t1, t2])

            if np.abs(predictions[0] - predictions[1]) < minp:
                team = [t1_name, t2_name]
                minp = np.abs(predictions[0] - predictions[1])
            if predictions[0] < 0.52 and predictions[0] >= 0.48:
                team = [t1_name, t2_name]
                break

        return True, team

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

    def get_player(self, d, team):
        t = []
        t_name = []
        for p in team:
            id = get_keys(d, 'sn', p)
            if id is not None:
                name = id
            else:
                return None, p
            mu = d[name]['mu'][-1]
            sigma = d[name]['sigma'][-1]
            t.append(create_rating([mu, sigma]))
            t_name.append(name)
        return t, t_name

    def update_ratings(self, d, id, winners, losers):
        if len(winners) < TEAM_NUM or len(losers) < TEAM_NUM:
            return None, None
        t1, t1_name = self.get_player(d, winners)
        t2, t2_name = self.get_player(d, losers)
        if t1 is None or t2 is None:
            return d, None
        [t1, t2] = rate([t1, t2])
        for t, name in zip(t1, t1_name):
            if t.sigma < MIN_SIGMA:
                t.sigma = MIN_SIGMA
            d[name]['mu'].append(t.mu)
            d[name]['sigma'].append(t.sigma)
            d[name]['gameid'].append(id)
        for t, name in zip(t2, t2_name):
            if t.sigma < MIN_SIGMA:
                t.sigma = MIN_SIGMA
            d[name]['mu'].append(t.mu)
            d[name]['sigma'].append(t.sigma)
            d[name]['gameid'].append(id)
        return d, t1_name + t2_name
