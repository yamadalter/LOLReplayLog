import pymysql
import pandas as pd
from common import RDS_HOST, RDS_USER, RDS_PASSWORD, RDS_DB


class DB:
    def __init__(self):
        self.db_name = RDS_DB
        self.user_password = RDS_PASSWORD
        self.user_name = RDS_USER
        self.host_name = RDS_HOST

    def get_tables(self):
        # MySQLデータベースに接続
        connection = pymysql.connect(host=RDS_HOST, user=RDS_USER, password=RDS_PASSWORD, database=RDS_DB)

        datalist = []
        for table in ['game', 'player', 'team', 'bans', 'stats', 'participants']:
            query = f"SELECT * FROM {table}"
            cursor = connection.cursor()
            cursor.execute(query)
            # データを取得し、pandasデータフレームに変換
            datalist.append(cursor.fetchall())

        df_game = pd.DataFrame(datalist[0]).set_index('id')
        df_player = pd.DataFrame(datalist[1]).set_index('puuid')
        df_team = pd.DataFrame(datalist[2]).set_index(['gameId', 'teamId'])
        df_bans = pd.DataFrame(datalist[3]).set_index(['gameId', 'teamId', 'pickTurn'])
        df_stats = pd.DataFrame(datalist[4]).set_index(['participantId', 'gameId'])
        df_participants = pd.DataFrame(datalist[5]).set_index(['participantId', 'gameId'])

        return df_game, df_player, df_team, df_bans, df_stats, df_participants

