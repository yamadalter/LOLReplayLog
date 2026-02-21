from sqlalchemy import create_engine
import pandas as pd
from common import RDS_HOST, RDS_USER, RDS_PASSWORD, RDS_DB
from sqlalchemy.orm import sessionmaker


class DB:
    def __init__(self):
        self.engine = create_engine(f'mysql+pymysql://{RDS_USER}:{RDS_PASSWORD}@{RDS_HOST}:16816/{RDS_DB}')
        self.Session = sessionmaker(bind=self.engine)

    def get_tables(self):
        # MySQLデータベースに接続
        with self.engine.connect() as conn:  # Obtain a connection from the engine
            with self.Session(bind=conn) as session:  # Create a session bound to the connection
                df_game = pd.read_sql_table('game', conn)  # Use conn for read_sql_table
                df_player = pd.read_sql_table('player', conn)
                df_team = pd.read_sql_table('team', conn)
                df_bans = pd.read_sql_table('bans', conn)
                df_stats = pd.read_sql_table('stats', conn)
                df_participants = pd.read_sql_table('participants', conn)

        return df_game, df_player, df_team, df_bans, df_stats, df_participants

