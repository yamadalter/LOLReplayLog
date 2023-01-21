from riotwatcher import LolWatcher
import configparser

REGION = 'jp1'
RANK = ['IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']
TIER = ['IV', 'III', 'II', 'I']

config = configparser.ConfigParser()
config.read('config.ini')
apitoken = config['CONFIG']['riotapi']


class ReplayReader:
    def __init__(self, apitoken):
        super().__init__()
        self.watcher = LolWatcher(apitoken)

    def search_rank(self, name):
        id = self.watcher.by_name(REGION, name)['id']
        rankdatas = self.watcher.league.by_summoner(REGION, id)
        if len(rankdatas) < 1:
            return

        for data in rankdatas:
            if data['queueType'] == 'RANKED_SOLO_5x5':
                rank = data['rank']
                tier = data['tier']
                if rank == 'MASTER':
                    rank_point = 2900
                elif rank == 'GRANDMASTER':
                    rank_point = 3200
                elif rank == 'CHALLENGER':
                    rank_point = 3500
                else:
                    rank_point = RANK.index(rank) * 400 + TIER.index(tier) * 100 + 500

        return rank_point 
