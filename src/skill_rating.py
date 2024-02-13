import random
import itertools
import math
import numpy as np
import pandas as pd
from openskill import Rating, rate, create_rating, team_rating
from typing import Union, List
from openskill.constants import beta
from openskill.statistics import phi_major

TEAM_NUM = 1
MU = 1500
SIGMA = MU / 3
INIT_SIGMA = 400
MIN_SIGMA = 250
SHUFFLE_NUM = 1000


class SkillRating:
    def __init__(self):
        self.ratings = {}
        self.tierdf = pd.read_csv('data/tier.csv', index_col='Rank')

    async def make_team(self, df, reaction):
        players = []
        async for user in reaction.users():
            if not user == reaction.message.author:
                if user.id not in df.index:
                    return False, str(user.id)
                players.append(user.id)
        minp = 1
        team = []
        for _ in range(SHUFFLE_NUM):
            t1 = []
            t2 = []
            random.shuffle(players)
            t1_name = players[:TEAM_NUM]
            t2_name = players[TEAM_NUM:]
            for j in range(TEAM_NUM):
                mu = df.loc[t1_name[j], 'mu'][-1]
                sigma = df.loc[t1_name[j], 'sigma'][-1]
                t1.append(create_rating([mu, sigma]))
                mu = df.loc[t2_name[j], 'mu'][-1]
                sigma = df.loc[t2_name[j], 'sigma'][-1]
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

    def get_player(self, df, team):
        t = []
        t_name = []
        for p in team:
            id = df[df['sn'] == p].index
            if len(id) > 0:
                name = id[0]
            else:
                return None, p
            mu = df.loc[name, 'mu'][-1]
            sigma = df.loc[name, 'sigma'][-1]
            t.append(create_rating([mu, sigma]))
            t_name.append(name)
        return t, t_name

    def update_ratings(self, df, id, winners, losers):
        if len(winners) < TEAM_NUM or len(losers) < TEAM_NUM:
            return None
        t1, t1_name = self.get_player(df, winners)
        t2, t2_name = self.get_player(df, losers)
        if t1 is None or t2 is None:
            return df, None
        [t1, t2] = rate([t1, t2])
        for t, name in zip(t1, t1_name):
            if t.sigma < MIN_SIGMA:
                t.sigma = MIN_SIGMA
                df.loc[name]['mu'].append(t.mu)
                df.loc[name]['sigma'].append(t.sigma)
                df.loc[name]['gameid'].append(id)
        for t, name in zip(t2, t2_name):
            if t.sigma < MIN_SIGMA:
                t.sigma = MIN_SIGMA
                df.loc[name]['mu'].append(t.mu)
                df.loc[name]['sigma'].append(t.sigma)
                df.loc[name]['gameid'].append(id)
        return df, t1_name + t2_name
