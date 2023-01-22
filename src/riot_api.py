from riotwatcher import LolWatcher
import configparser

REGION = 'jp1'


class RiotWatcher:
    def __init__(self):
        super().__init__()
        config = configparser.ConfigParser()
        config.read('config.ini')
        apitoken = config['CONFIG']['riotapi']
        self.watcher = LolWatcher(apitoken)

    def search_rank(self, name):
        id = self.watcher.summoner.by_name(REGION, name)['id']
        rankdatas = self.watcher.league.by_summoner(REGION, id)
        if len(rankdatas) < 1:
            return None, None

        rank, tier = None, None
        for data in rankdatas:
            if data['queueType'] == 'RANKED_SOLO_5x5':
                rank = data['rank']
                tier = data['tier']

        return rank, tier
