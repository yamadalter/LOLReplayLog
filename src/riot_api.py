from riotwatcher import LolWatcher, RiotWatcher, ApiError
import configparser

REGION = 'jp1'
ACCOUNTREGION = 'ASIA'


class Watcher:
    def __init__(self):
        super().__init__()
        config = configparser.ConfigParser()
        config.read('src/config.ini')
        apitoken = config['CONFIG']['riotapi']
        self.watcher = LolWatcher(apitoken)
        self.riotwatcher = RiotWatcher(apitoken)

    def search_name(self, name):
        try:
            res = self.watcher.summoner.by_name(REGION, name)
        except ApiError:
            res = None
        return res

    def search_puuid(self, puuid):
        try:
            res = self.watcher.summoner.by_puuid(REGION, puuid)
        except ApiError:
            res = None
        return res

    def search_by_riot_id(self, name, tag):
        try:
            res = self.riotwatcher.account.by_riot_id(ACCOUNTREGION, name, tag)
        except ApiError:
            res = None
        return res

    def search_rank(self, puuid):
        id = self.watcher.summoner.by_puuid(REGION, puuid)['id']
        rankdatas = self.watcher.league.by_summoner(REGION, id)
        if len(rankdatas) < 1:
            return None, None

        rank, tier = None, None
        for data in rankdatas:
            if data['queueType'] == 'RANKED_SOLO_5x5':
                rank = data['rank']
                tier = data['tier']

        return rank, tier
