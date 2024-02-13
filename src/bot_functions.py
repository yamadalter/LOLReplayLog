from src import image_gen, replay_reader, summoner_data, skill_rating, riot_api
from discord import File, Embed, Colour, AllowedMentions, ui, ButtonStyle
import os
import shutil
import configparser
import json
import requests
import tarfile
import pandas as pd
import numpy as np


TEAM_NUM = 1
MU = 1500
SIGMA = MU / 3
INIT_SIGMA = 400
MIN_SIGMA = 250
LANE = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
LinkDataCSV = 'data/linkdata.csv'
# KEY = ['id', 'mu', 'sigma']


def msg2sum(content, d_id):
    space_split = content.split(" ")
    if len(space_split) == 1:
        return None, None, d_id
    if space_split[1].startswith('<@') and space_split[1].endswith('>'):
        if " ".join(space_split[2:]) == '':
            return None, None, space_split[1][2:-1]
        num_split = " ".join(space_split[2:]).split("#")
        if len(num_split) == 1:
            return None, None, space_split[1][2:-1]
        else:
            return num_split[0], num_split[1], space_split[1][2:-1]  # given game name, tag, given discord id
    else:
        num_split = " ".join(space_split[1:]).split("#")
        if len(num_split) == 1:
            return None, None, None
        else:
            return num_split[0], num_split[1], None  # given game name, tag


def _search_df_index(df, column, value):
    return df[df[column] == value].index[0]


def _df2list(df):
    mulist = []
    sigmalist = []
    gameidlist = []
    for _, row in df.iterrows():
        mulist.append(eval(row['mu']))
        sigmalist.append(eval(row['sigma']))
        gameidlist.append(eval(row['gameid']))
    df.loc[:, 'mu'] = mulist
    df.loc[:, 'sigma'] = sigmalist
    df.loc[:, 'gameid'] = gameidlist
    return df


class BotFunctions():
    def __init__(self, prefix, user):
        super().__init__()
        config = configparser.ConfigParser()
        config.read('config.ini')
        self.tierdf = pd.read_csv('data/tier.csv', index_col='Rank')
        if os.path.exists(LinkDataCSV):
            self.df = pd.read_csv(LinkDataCSV, index_col='DiscordID')
            self.df = _df2list(self.df)
        self.summoner_data = summoner_data.SummonerData()
        self.image_gen = image_gen.ImageGen()
        self.skill_rating = skill_rating.SkillRating()
        self.watcher = riot_api.Watcher()
        self.prefix = prefix
        self.user = user
        if os.path.exists('data/log/log.csv'):
            self.logdf = pd.read_csv('data/log/log.csv')
        else:
            self.logdf = None
        self.commands = {"id": {"func": self.id, "help": "/id {ID} - Gets info of match ID"},
                         "replay": {"func": self.replay,
                                    "help": "/replay - Attach a .ROFL or .json from a replay for the bot to display"},
                         "log": {"func": self.log, "help": "/log - Log a replay ID into the database"},
                         "link": {"func": self.link,
                                  "help": "/link {name} {#tag}- Links a summoner name to your Discord. Mention someone before the summoner name to link it to their Discord instead"},
                         "unlink": {"func": self.unlink, "help": "/unlink {Summoner Name} - Opposite of rg:link"},
                         "stats": {"func": self.stats,
                                    "help": "/stats {@mention} {ha or sr, leave blank for all} - Get player's stats"},
                         "detail": {"func": self.detail,
                                    "help": "/detail {@mention} {ha or sr, leave blank for all} - Get player's detail stats"},
                         "bestgame": {"func": self.bestgame,
                                    "help": "/bestgame {@mention}  - Get player's bestgame"},
                         "team": {"func": self.team,
                                    "help": "/team  - Get teams"},
                         "revert": {"func": self.revert,
                                    "help": "/revert {ID} - Revert game of match ID"},
                         "rename": {"func": self.rename,
                                    "help": "/rename {before sn},{after sn} - Rename summoner name"},
                         "reset_rate": {"func": self.reset_rate,
                                    "help": "/reset_rate {Summoner Name}, - Reset Rate"},
                         "update": {"func": self.update,
                                  "help": "/update - Get new version data files"},
                         "help": {"func": self.help,
                                  "help": "/help {command} - Get syntax for given command, leave blank for list of commands"}}

    async def log(self, message=None, ids=None):
        if ids is None:
            ids = message.content[5:].split(",")
        for replay_id in ids:
            if os.path.exists("data/logged.txt"):
                with open("data/logged.txt", "r") as f:
                    logged_ids = f.readlines()
                    if replay_id + '\n' in logged_ids:
                        if message:
                            await message.reply(
                                content=f"Match {replay_id} was previously logged")  # The match has already been logged.
                        return
            elif not os.path.exists("data/logged.txt"):
                with open("data/logged.txt", "w") as f:
                    pass
            self.logdf = self.summoner_data.log(replay_id, self.logdf)
            self.logdf.to_csv('data/log/log.csv', index=False)
            with open("data/logged.txt", "a") as f:
                f.write(f"{replay_id}\n")
            if message:
                await message.reply(content=f"Match {replay_id} logged")

    async def id(self, message=None, ids=None):  # Get match from ID
        if ids is None:
            ids = message.content[4:].split(',')
        for replay_id in ids:
            try:
                replay = replay_reader.ReplayReader(replay_id)
            except FileNotFoundError:
                await message.reply(content="Replay file not found")
                return
            if not os.path.exists("data/logged.txt"):
                with open("data/logged.txt", "w") as f:
                    pass
            with open("data/logged.txt", "r") as f:
                logged_ids = f.readlines()
            if not replay_id + '\n' in logged_ids:
                old_log = self.logdf
                self.logdf = self.summoner_data.log(replay_id, self.logdf)
                self.df, names = self.skill_rating.update_ratings(self.df, replay_id, self.summoner_data.winners, self.summoner_data.losers)
                if names is not None:
                    await self.team_result(message, self.summoner_data.winners, self.summoner_data.losers)
                else:
                    await message.reply(content="not linked summoner found")
                    self.logdf = old_log
                    return
                with open("data/logged.txt", "a") as f:
                    f.write(f"{replay_id}\n")
                self.logdf.to_csv('data/log/log.csv', index=False)
            if not os.path.exists(f'data/match_imgs/{replay_id}.png'):
                replay.generate_game_img()
            embed = Embed(title="Replay", description=f"{replay_id}", color=Colour.blurple())
            file = File(f'data/match_imgs/{replay_id}.png', filename="image.png")
            embed.set_image(url="attachment://image.png")
            if message:
                await message.reply(file=file, embed=embed)

    async def replay(self, message):  # Submit new replay
        attachments = message.attachments
        ids = []
        if len(attachments) > 0:
            for attachment in attachments:
                if attachment.filename.endswith('.rofl') or attachment.filename.endswith('.json'):
                    await attachment.save(f"data/replays/{attachment.filename}")
                    ids.append(attachment.filename[:-5])
                else:
                    await message.reply(content=f"File {attachment.filename} is not a supported file type")
        if len(ids) > 0:
            await self.id(message, ids)
        else:
            await message.reply(content="No replay file attached")

    async def link(self, message):
        # link id
        gamename, tag, discord_id = msg2sum(message.content, message.author.id)
        if discord_id is None:
            discord_id = message.author.id
        if discord_id not in self.df.index:
            await message.reply(content='<@{discord_id}> is already linked')
            return
        if (gamename is None) or (tag is None):
            await message.reply(content='/link gamename #tag')
            return
        res = self.watcher.search_by_riot_id(gamename, tag)
        if res is None:
            await message.reply(content=f'{gamename} #{tag} has not found')
            return
        else:
            puuid = res['puuid']
            gamename = res['gameName']
            tag = res['tagLine']
            sn = self.watcher.search_puuid(puuid)['name']
            rank, tier = self.watcher.search_rank(puuid)
            if rank is not None and tier is not None:
                mu = self.tierdf.loc[f'{tier} {rank}', 'Point']
                sigma = INIT_SIGMA
                await message.reply(content=f'{gamename} Rate:{mu}')
            else:
                mu, sigma = MU, SIGMA
                await message.reply(content=f'unranked summmoner. Rate:1500')
            # set rating
            self.df.loc[discord_id] = [puuid, gamename, tag, sn, [mu], [sigma], ['init']]
            self.save_df2csv()

    async def unlink(self, message):
        gamename, tag, discord_id = msg2sum(message.content, message.author.id)
        self.df = self.df.drop(discord_id)
        await message.reply(content=f'{gamename} has been unlinked')

    async def help(self, message):
        space_split = message.content.split(" ")
        if len(space_split) == 1:
            cmd_list = ""
            for cmd in self.commands:
                cmd_list += cmd + ", "
            cmd_list = cmd_list[:-2] + "\n"
            cmd_list += f"Use {self.prefix}help {{command}} to get more help."
            await message.reply(content=cmd_list)
        elif len(space_split) == 2:
            for cmd in self.commands:
                if cmd.lower() == space_split[1].lower():
                    help_str = self.commands[cmd]["help"]
            await message.reply(content=help_str)
        else:
            await message.reply(content="Invalid syntax. Try /help {command}")

    async def handle_message(self, message):
        cmd_split = message.content.split(self.prefix)
        space_split = cmd_split[1].split(" ")
        if space_split[0] in self.commands:
            await self.commands[space_split[0]]["func"](message)
        else:
            await message.reply(content="Command not found")

    async def stats(self, message):
        gamename, tag, discord_id = msg2sum(message.content, message.author.id)
        if discord_id is not None:
            summoner_name = self.df.loc[discord_id, 'sn']
            if summoner_name is None:
                await message.reply(content="Summoner name is not linked")
                return
            name = f"<@{discord_id}>"
            avator = await self.user(discord_id)
        else:
            await message.reply(content="Commnad:/stats @username")
            return
        if self.logdf is not None:
            summoner_df = self.logdf[self.logdf["NAME"] == summoner_name]
            if len(summoner_df) < 1:
                await message.reply(content="Log not found")
                return
            average_kill = str(sum(summoner_df["CHAMPIONS_KILLED"].astype(int)) / len(summoner_df))
            average_death = str(sum(summoner_df["NUM_DEATHS"].astype(int)) / len(summoner_df))
            if average_death == '0.0':
                average_death = '1.0'
            average_assist = str(sum(summoner_df["ASSISTS"].astype(int)) / len(summoner_df))
            average_kda = (float(average_kill) + float(average_assist)) / float(average_death)
            winrate = sum(summoner_df["result"] == 'Win') / len(summoner_df) * 100
            average_vision_ward = sum(summoner_df["VISION_WARDS_BOUGHT_IN_GAME"].astype(int)) / len(summoner_df)
            if len(summoner_df) > 4:
                role = summoner_df['TEAM_POSITION'].value_counts()
                champ = summoner_df["SKIN"].value_counts()[:5]
            else:
                role = summoner_df['TEAM_POSITION'].value_counts()[:len(summoner_df)]
                champ = summoner_df["SKIN"].value_counts()[:len(summoner_df)]
            famouschamp = champ.keys()[0]
            role_str = ''
            for index, v in role.items():
                role_str += f'**{index}** : {v}   '
            champ_str = ''
            for index, v in champ.items():
                champ_str += f'**{index}** : {v}  '
            if len(summoner_df) > 10:
                games = 10
            else:
                games = len(summoner_df)
            recent = '** '
            for _, row in summoner_df[:games][::-1].iterrows():
                if row["result"] == 'Win':
                    recent += ":blue_square: "
                else:
                    recent += ":red_square: "
            recent += '** '
            if winrate > 60:
                stats_color = 0x0099E1
            elif winrate > 50:
                stats_color = 0x00D166
            elif winrate > 40:
                stats_color = 0xF8C300
            else:
                stats_color = 0xFD0061
            file = File(f'img/champion/{famouschamp}.png', filename='champ.png')
            embed = Embed(title="Stats", description=f"**{name}**\nTotal Games {len(summoner_df)}\n", color=stats_color)
            if (avator is not None) and (avator.avatar is not None):
                user_icon = avator.avatar.url
            else:
                user_icon = ""
            embed.set_author(name=f'{gamename} #{tag}', icon_url=user_icon)
            embed.set_thumbnail(url="attachment://champ.png")
            rate = self.df.loc[discord_id, 'mu'][-1]
            embed.add_field(name="Rating", value=f"{int(rate)}", inline=False)
            embed.add_field(name="Winrate", value=f"{winrate:.3g}")
            embed.add_field(name="KDA", value=f"{average_kda:.3g}")
            embed.add_field(name="Wards", value=f"{average_vision_ward:.3g}")
            embed.add_field(name="\nRole", value=f"{role_str}", inline=False)
            embed.add_field(name="\nFavorite Champions", value=f"{champ_str}", inline=False)
            # embed.add_field(name="\nRecent Games", value=f"{recent}", inline=False)
            mus = self.df.loc[discord_id, 'mu']
            sigmas = self.df.loc[discord_id, 'mu']
            self.image_gen.generate_rating_img(mus, sigmas, summoner_name)
            file = File(f'data/ratings_imgs/{summoner_name}.png', filename="image.png")
            embed.set_image(url="attachment://image.png")
            await message.reply(file=file, embed=embed)
        else:
            await message.reply(content="Log file not found")
            return

    async def bestgame(self, message):
        gamename, tag, discord_id = msg2sum(message.content, message.author.id)
        if discord_id is not None:
            summoner_name = self.df.loc[discord_id, 'sn']
            if summoner_name is None:
                await message.reply(content="Summoner name is not linked")
                return
            name = f"<@{discord_id}>"
        else:
            await message.reply(content="Commnad:/bestgame @username")
            return
        if self.logdf is not None:
            summoner_df = self.logdf[self.logdf["NAME"] == summoner_name]
            if len(summoner_df) < 1:
                await message.reply(content="Log not found")
                return
            kill = summoner_df["CHAMPIONS_KILLED"].astype(int) / len(summoner_df)
            death = summoner_df["NUM_DEATHS"].astype(int) / len(summoner_df)
            assist = summoner_df["ASSISTS"].astype(int) / len(summoner_df)
            kda = ((kill) + (assist)) / (death)
            max_index = np.argmax(kda)
            replay_id = list(summoner_df["game_id"])[max_index]
            if not os.path.exists(f'data/match_imgs/{replay_id}.png'):
                return
            embed = Embed(title="Best Game", description=f"{name}", color=Colour.blurple())
            file = File(f'data/match_imgs/{replay_id}.png', filename="image.png")
            embed.set_image(url="attachment://image.png")
            if message:
                await message.reply(file=file, embed=embed)

    async def detail(self, message):
        gamename, tag, discord_id = msg2sum(message.content, message.author.id)
        if discord_id is not None:
            summoner_name = self.df.loc[discord_id, 'sn']
            if summoner_name is None:
                await message.reply(content="Summoner name is not linked")
                return
            name = f"<@{discord_id}>"
            avator = await self.user(discord_id)
        else:
            await message.reply(content="Commnad:/detail @username")
            return
        if self.logdf is not None:
            summoner_df = self.logdf[self.logdf["NAME"] == summoner_name]
            if len(summoner_df) < 1:
                await message.reply(content="Log not found")
                return
            if avator is not None and avator.avatar is not None:
                user_icon = avator.avatar.url
            else:
                user_icon = ""
            embed = Embed(title="Detail stats", description=f"**{name}**\nTotal Games {len(summoner_df)}\n", color=0xFFFFFF)
            embed.set_author(name=f'{gamename} #{tag}', icon_url=user_icon)
            for lane in LANE:
                lane_df = summoner_df[summoner_df["TEAM_POSITION"] == lane]
                if len(lane_df) > 0:
                    average_kill = str(sum(lane_df["CHAMPIONS_KILLED"].astype(int)) / len(lane_df))
                    average_death = str(sum(lane_df["NUM_DEATHS"].astype(int)) / len(lane_df))
                    average_assist = str(sum(lane_df["ASSISTS"].astype(int)) / len(lane_df))
                    if average_death == '0.0':
                        average_death = '1.0'
                    average_kda = (float(average_kill) + float(average_assist)) / float(average_death)
                    winrate = sum(lane_df["result"] == 'Win') / len(lane_df) * 100
                    average_vision_ward = sum(lane_df["VISION_WARDS_BOUGHT_IN_GAME"].astype(int)) / len(lane_df)
                    if len(lane_df) > 4:
                        champ = lane_df["SKIN"].value_counts()[:5]
                    else:
                        champ = lane_df["SKIN"].value_counts()[:len(lane_df)]
                    champ_str = ''
                    for index, v in champ.items():
                        champ_str += f'**{index}** : {v}  '
                    embed.add_field(name=f"{lane}", value=f"**Games** : **{len(lane_df)}**", inline=False)
                    embed.add_field(name="Winrate", value=f"{winrate:.3g}")
                    embed.add_field(name="KDA", value=f"{average_kda:.3g}")
                    embed.add_field(name="Wards", value=f"{average_vision_ward:.3g}")
                    embed.add_field(name="\nFavorite Champions", value=f"{champ_str}\n\u200b", inline=False)
            average_kill = str(sum(summoner_df["CHAMPIONS_KILLED"].astype(int)) / len(summoner_df))
            average_death = str(sum(summoner_df["NUM_DEATHS"].astype(int)) / len(summoner_df))
            average_assist = str(sum(summoner_df["ASSISTS"].astype(int)) / len(summoner_df))
            if average_death == '0.0':
                average_death = '1.0'
            average_kda = (float(average_kill) + float(average_assist)) / float(average_death)
            winrate = sum(summoner_df["result"] == 'Win') / len(summoner_df) * 100
            average_vision_ward = sum(summoner_df["VISION_WARDS_BOUGHT_IN_GAME"].astype(int)) / len(summoner_df)
            embed.add_field(name="Total Winrate", value=f"{winrate:.3g}")
            embed.add_field(name="KDA", value=f"{average_kda:.3g}")
            embed.add_field(name="Wards", value=f"{average_vision_ward:.3g}")
            await message.reply(embed=embed)
        else:
            await message.reply(content="Log file not found")
            return

    async def team(self, message):
        allowed_mentions = AllowedMentions(everyone=True)
        new_message = await message.channel.send(f"@here カスタム参加する人は✅を押してください \n\u200b", allowed_mentions=allowed_mentions)
        await new_message.add_reaction("✅")

    async def send_team(self, reaction):
        res, team = await self.skill_rating.make_team(self.df, reaction)
        if not res:
            await reaction.message.reply(content=f"<@{team}> is not linked")
            return
        team1 = ''
        team2 = ''
        for i in range(TEAM_NUM):
            team1 += self.team_str(team[0][i])
            team2 += self.team_str(team[1][i])
        name_list = []
        for id in team[0]:
            gamename = self.df.loc[id, 'gamename'].replace(' ', '+')
            tag = self.df.loc[id, 'tag']
            name_list.append(f'{gamename}%23{tag}')
        name1 = '%2C'.join(name_list)
        button = ui.Button(label="OPGG", style=ButtonStyle.primary, url=f'https://www.op.gg/multisearch/jp?summoners={name1}')
        view = ui.View()
        view.add_item(button)
        embed = Embed(title="Team 1", color=0x0000ff)
        embed.add_field(name="Blue", value=team1, inline=False)
        await reaction.message.channel.send(embed=embed, view=view)
        name_list = []
        for id in team[1]:
            gamename = self.df.loc[id, 'gamename'].replace(' ', '+')
            tag = self.df.loc[id, 'tag']
            name_list.append(f'{gamename}%23{tag}')
        name2 = '%2C'.join(name_list)
        button = ui.Button(label="OPGG", style=ButtonStyle.primary, url=f'https://www.op.gg/multisearch/jp?summoners={name2}')
        view = ui.View()
        view.add_item(button)
        embed = Embed(title="Team 2", color=0xff0000)
        embed.add_field(name="Red", value=team2, inline=False)
        await reaction.message.channel.send(embed=embed, view=view)

    def team_str(self, id):
        name = self.df.loc[id, 'sn']
        rate = self.df.loc[id, 'mu'][-1]
        gamename = self.df.loc[id, 'gamename']
        tag = self.df.loc[id, 'tag']
        if name is None:
            name = 'not linked summoner'
        summoner_df = self.logdf[self.logdf["NAME"] == name]
        if len(summoner_df) < 1:
            stats = f'Log not found: Rate:{rate}'
        else:
            winrate = sum(summoner_df["result"] == 'Win') / len(summoner_df) * 100
            win = int(sum(summoner_df["result"] == 'Win'))
            lose = int(sum(summoner_df["result"] == 'Lose'))
            stats = f'Win:{win} Lose:{lose} {winrate:.3g}% Rate:{rate}'
        return f'<@{id}> ({gamename}#{tag}) \n\u200b {stats} \n\u200b'

    def result_str(self, team):
        team_str = ''
        for sn in team:
            if sn in self.df['sn'].values:
                id = _search_df_index(self.df, 'sn', sn)
                team_str += f'<@{id}> ({sn}) \n\u200b'
            else:
                id = sn
                team_str += f'not linked summoner ({sn}) \n\u200b'
            if len(self.df.loc[id, 'mu']) > 1:
                diff = int(self.df.loc[id, 'mu'][-1] - self.df.loc[id, 'mu'][-2])
            else:
                diff = 0
            summoner_df = self.logdf[self.logdf["NAME"] == sn]
            winrate = sum(summoner_df["result"] == 'Win') / len(summoner_df) * 100
            win = int(sum(summoner_df["result"] == 'Win'))
            lose = int(sum(summoner_df["result"] == 'Lose'))
            rate = int(self.df.loc[id, 'mu'][-1])
            if diff > 0:
                diff = '+' + str(diff)
            stats = f'Win:{win} Lose:{lose} {winrate:.3g}% Rate:{rate} ({diff})'
            team_str += f'{stats} \n\u200b'
        return team_str

    async def team_result(self, message, winners, losers):
        embed = Embed(title="Team result", color=0xE0FFFF)
        team1 = self.result_str(winners)
        team2 = self.result_str(losers)
        embed.add_field(name="Winners", value=team1, inline=False)
        embed.add_field(name="Losers", value=team2, inline=False)
        self.logdf.to_csv('data/log/log.csv', index=False)
        await message.reply(embed=embed)

    async def revert(self, message):
        ids = message.content[8:].split(",")
        for replay_id in ids:
            if os.path.exists("data/logged.txt"):
                with open("data/logged.txt", "r") as f:
                    logged_ids = f.readlines()
                    if replay_id + '\n' not in logged_ids:
                        if message:
                            await message.reply(
                                content=f"Match {replay_id} was not found")
                        return
                    else:
                        game_df = self.logdf[self.logdf["game_id"] == replay_id]
                        for _, row in game_df.iterrows():
                            name = row["NAME"]
                            if name in self.df['sn'].values:
                                discord_id = _search_df_index(self.df, 'sn', name)
                                idx = self.df.loc[discord_id, 'gameid'].index(replay_id)
                                self.df.loc[discord_id, 'mu'].pop(idx)
                                self.df.loc[discord_id, 'sigma'].pop(idx)
                                self.df.loc[discord_id, 'gameid'].pop(idx)
                        self.save_df2csv()
                        target = self.logdf.index[self.logdf["game_id"] == replay_id]
                        self.logdf = self.logdf.drop(target)
                        self.logdf.to_csv('data/log/log.csv', index=False)
                        with open("data/logged.txt", "r") as f:
                            data_lines = f.read()
                        data_lines = data_lines.replace(replay_id + '\n', "")
                        with open("data/logged.txt", "w") as f:
                            f.write(data_lines)
                        if(os.path.isfile(f'data/match_imgs/{replay_id}.png') is True):
                            os.remove(f'data/match_imgs/{replay_id}.png')
                        if(os.path.isfile(f'data/replays/{replay_id}.json') is True):
                            os.remove(f'data/replays/{replay_id}.json')
                        if(os.path.isfile(f'data/replays/{replay_id}.rofl') is True):
                            os.remove(f'data/replays/{replay_id}.rofl')
        await message.reply(content="Reverted")

    async def reset_rate(self, message):
        gamename, tag, discord_id = msg2sum(message.content, message.author.id)
        if discord_id is None:
            discord_id = message.author.id
        puuid = self.df.loc[discord_id, 'puuid']
        if puuid is None:
            await message.reply(content="Summoner name is not linked")
        else:
            # set rating
            rank, tier = self.watcher.search_rank(puuid)
            if rank is not None and tier is not None:
                mu = self.tierdf.loc[f'{tier} {rank}', 'Point']
                sigma = INIT_SIGMA
                await message.reply(content=f'{gamename} Rate:{mu}')
            else:
                mu, sigma = MU, SIGMA
                await message.reply(content=f'unranked summmoner. Rate:1500')
            self.df.loc[discord_id]['mu'].append(mu)
            self.df.loc[discord_id]['sigma'].append(sigma)
            self.df.loc[discord_id]['gameid'].append('reset')
            self.save_df2csv()

    async def rename(self, message):
        #  /rename Feder Kissen,Sakura Laurel
        gamename, tag, discord_id = msg2sum(message.content, message.author.id)
        if discord_id is None:
            discord_id = message.author.id
        if (gamename is None) or (tag is None):
            await message.reply(content='/link gamename #tag')
        res = self.watcher.search_by_riot_id(gamename, tag)
        if res is None:
            await message.reply(content=f'{gamename} #{tag} has not found')
        else:
            gamename = res['gameName']
            tag = res['tagLine']
            self.df.loc[discord_id]['gamename'].append(gamename)
            self.df.loc[discord_id]['tag'].append(tag)
            self.save_df2csv()

    async def update(self, message):
        #  download versions.json
        url = 'https://ddragon.leagueoflegends.com/api/versions.json'
        filename = 'data/versions.json'
        urlData = requests.get(url).content
        with open(filename, mode='wb') as f:
            f.write(urlData)
        f = open(filename, 'r')
        json_dict = json.load(f)
        version = json_dict[0]
        #  download Data Dragon
        url = f'https://ddragon.leagueoflegends.com/cdn/dragontail-{version}.tgz'
        filename = 'dragontail.tgz'
        with requests.get(url, stream=True) as r:
            with open(filename, mode='wb') as f:
                for chunk in r.iter_content(chunk_size=8096 * 1024):
                    f.write(chunk)
        with tarfile.open(filename, 'r:gz') as tar:
            tar.extractall(path='dragontail')
        if os.path.isdir('img'):
            shutil.rmtree('img')
        shutil.move(f'dragontail/{version}/img', './')
        shutil.move('dragontail/img/perk-images', 'img/perk-images')
        shutil.move(f'dragontail/{version}/data/en_US/runesReforged.json', 'data/runesReforged.json')
        await message.reply(content=f"updated version {version}")

    def save_df2csv(self):
        self.df.to_csv(LinkDataCSV)
