from src import image_gen, replay_reader, summoner_data, skill_rating
from discord import File, Embed, Colour, AllowedMentions
import os
import pandas as pd
import numpy as np

TEAM_NUM = 5
LANE = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]


def msg2sum(content, d_id):
    space_split = content.split(" ")
    if len(space_split) == 1:
        return None, str(d_id)
    if space_split[1].startswith('<@') and space_split[1].endswith('>'):
        if " ".join(space_split[2:]) == '':
            return None, space_split[1][2:-1]
        return " ".join(space_split[2:]), space_split[1][2:-1]  # given summonername, given discord id
    else:
        return " ".join(space_split[1:]), None  # given summoner name, no discord id


class BotFunctions():
    def __init__(self, prefix, user):
        super().__init__()
        self.summoner_data = summoner_data.SummonerData()
        self.image_gen = image_gen.ImageGen()
        self.skill_rating = skill_rating.SkillRating()
        self.prefix = prefix
        self.user = user
        if os.path.exists('data/log/log.csv'):
            self.df = pd.read_csv('data/log/log.csv')
        else:
            self.df = None
        self.commands = {"id": {"func": self.id, "help": "/id {ID} - Gets info of match ID"},
                         "replay": {"func": self.replay,
                                    "help": "/replay - Attach a .ROFL or .json from a replay for the bot to display"},
                         "log": {"func": self.log, "help": "/log - Log a replay ID into the database"},
                         "link": {"func": self.link,
                                  "help": "/link {Summoner Name} - Links a summoner name to your Discord. Mention someone before the summoner name to link it to their Discord instead"},
                         "unlink": {"func": self.unlink, "help": "/unlink {Summoner Name} - Opposite of rg:link"},
                         "stats": {"func": self.stats,
                                    "help": "/stats {Summoner Name or @} {ha or sr, leave blank for all} - Get player's stats"},
                         "detail": {"func": self.detail,
                                    "help": "/detail {Summoner Name or @} {ha or sr, leave blank for all} - Get player's detail stats"},
                         "bestgame": {"func": self.bestgame,
                                    "help": "/bestgame {Summoner Name or @}  - Get player's bestgame"},
                         "team": {"func": self.team,
                                    "help": "/team  - Get teams"},
                         "revert": {"func": self.revert,
                                    "help": "/revert {ID} - Revert game of match ID"},
                         "rename": {"func": self.rename,
                                    "help": "/rename {before sn},{after sn} - Rename summoner name"},
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
            self.df = self.summoner_data.log(replay_id, self.df)
            self.df.to_csv('data/log/log.csv', index=False)
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
                with open("data/logged.txt", "a") as f:
                    f.write(f"{replay_id}\n")
                    self.df = self.summoner_data.log(replay_id, self.df)
                    self.df.to_csv('data/log/log.csv', index=False)
                    self.skill_rating.update_ratings(self.summoner_data.winners, self.summoner_data.losers)
                    await self.team_result(message, self.summoner_data.winners, self.summoner_data.losers)

            if not os.path.exists(f'data/match_imgs/{replay_id}.png'):
                replay.generate_game_img()
            embed = Embed(title="Replay", description=f"{replay_id}", color=Colour.blurple())
            file = File(f'data/match_imgs/{replay_id}.png', filename="image.png")
            embed.set_image(url="attachment://image.png")

            alartlist, arrestlist = self.summoner_data.ward_alert(replay_id)
            if len(alartlist) > 0:
                embed.add_field(name="\nBuy more control wards! (Bought control ward : 1)", value=f"{' '.join(alartlist)}", inline=False)
            if len(arrestlist) > 0:
                embed.add_field(name="\n**I'm arresting you! (Bought control ward : 0)**", value=f"{' '.join(arrestlist)}", inline=False)

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
        summoner_name, discord_id = msg2sum(message.content, message.author.id)
        if discord_id is None:
            discord_id = message.author.id
        await message.reply(content=self.summoner_data.link_id2sum(summoner_name, str(discord_id)))

        if summoner_name in self.skill_rating.ratings.keys():
            self.skill_rating.ratings[discord_id] = self.skill_rating.ratings[summoner_name]
            del self.skill_rating.ratings[summoner_name]
        else:
            self.skill_rating.init_ratings(discord_id, summoner_name)
        self.skill_rating.save_ratings(self.skill_rating.ratings)

    async def unlink(self, message):
        summoner_name, discord_id = msg2sum(message.content, message.author.id)
        await message.reply(content=self.summoner_data.unlink(summoner_name, str(discord_id)))

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
        summoner_name, discord_id = msg2sum(message.content, message.author.id)
        if discord_id is not None:
            summoner_name = self.summoner_data.sum2id(str(discord_id))
            if summoner_name is None:
                await message.reply(content="Summoner name is not linked")
                return

            name = f"<@{discord_id}>"
            avator = await self.user(discord_id)
        else:
            name = summoner_name
            avator = None

        if self.df is not None:
            summoner_df = self.df[self.df["NAME"] == summoner_name]

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

            if avator is not None:
                user_icon = avator.avatar_url
            else:
                user_icon = ""

            embed.set_author(name=summoner_name, icon_url=user_icon)
            embed.set_thumbnail(url="attachment://champ.png")
            if discord_id is not None:
                name_key = str(discord_id)
            else:
                if summoner_name in self.skill_rating.ratings.keys():
                    name_key = str(summoner_name)
                else:
                    name_key = str(id)
            rate = self.skill_rating.ratings[str(name_key)][-1][0]
            sigma = self.skill_rating.ratings[str(name_key)][-1][1]
            embed.add_field(name="Rating", value=f"{int(rate)}", inline=False)
            embed.add_field(name="Winrate", value=f"{winrate:.3g}")
            embed.add_field(name="KDA", value=f"{average_kda:.3g}")
            embed.add_field(name="Wards", value=f"{average_vision_ward:.3g}")

            embed.add_field(name="\nRole", value=f"{role_str}", inline=False)
            embed.add_field(name="\nFavorite Champions", value=f"{champ_str}", inline=False)
            embed.add_field(name="\nRecent Games", value=f"{recent}", inline=False)

            mus = summoner_df['mu'].values
            sigmas = summoner_df['sigma'].values
            mus = np.append(mus[::-1], rate)
            sigmas = np.append(sigmas[::-1], sigma)
            self.image_gen.generate_rating_img(mus, sigmas, summoner_name)
            file = File(f'data/ratings_imgs/{summoner_name}.png', filename="image.png")
            embed.set_image(url="attachment://image.png")

            await message.reply(file=file, embed=embed)
        else:
            await message.reply(content="Log file not found")
            return

    async def bestgame(self, message):
        summoner_name, discord_id = msg2sum(message.content, message.author.id)
        if discord_id is not None:
            summoner_name = self.summoner_data.sum2id(str(discord_id))
            if summoner_name is None:
                await message.reply(content="Summoner name is not linked")
                return

            name = f"<@{discord_id}>"
        else:
            name = summoner_name

        if self.df is not None:
            summoner_df = self.df[self.df["NAME"] == summoner_name]

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

        summoner_name, discord_id = msg2sum(message.content, message.author.id)
        if discord_id is not None:
            summoner_name = self.summoner_data.sum2id(str(discord_id))
            if summoner_name is None:
                await message.reply(content="Summoner name is not linked")
                return

            name = f"<@{discord_id}>"
            avator = await self.user(discord_id)
        else:
            name = summoner_name
            avator = None

        if self.df is not None:
            summoner_df = self.df[self.df["name"] == summoner_name]

            if len(summoner_df) < 1:
                await message.reply(content="Log not found")
                return

            if avator is not None:
                user_icon = avator.avatar_url
            else:
                user_icon = ""

            embed = Embed(title="Detail stats", description=f"**{name}**\nTotal Games {len(summoner_df)}\n", color=0xFFFFFF)
            embed.set_author(name=summoner_name, icon_url=user_icon)
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
        new_message = await message.channel.send("@here カスタム参加する人は✅を押してください", allowed_mentions=allowed_mentions)
        await new_message.add_reaction("✅")

    async def send_team(self, reaction):

        team = await self.skill_rating.make_team(reaction)
        embed = Embed(title="Team", color=0xF945C0)
        team1 = ''
        team2 = ''
        for i in range(TEAM_NUM):
            team1 += self.team_str(str(team[0][i]))
            team2 += self.team_str(str(team[1][i]))

        embed.add_field(name="Team 1", value=team1, inline=False)
        embed.add_field(name="Team 2", value=team2, inline=False)

        await reaction.message.channel.send(embed=embed)

    def team_str(self, id):
        name = self.summoner_data.sum2id(str(id))
        rate = int(self.skill_rating.ratings[str(id)][-1][0])
        if name is None:
            name = 'not linked summoner'
        summoner_df = self.df[self.df["NAME"] == name]
        if len(summoner_df) < 1:
            stats = f'Log not found: Rate:{rate}'
        else:
            winrate = sum(summoner_df["result"] == 'Win') / len(summoner_df) * 100
            win = int(sum(summoner_df["result"] == 'Win'))
            lose = int(sum(summoner_df["result"] == 'Lose'))
            stats = f'Win:{win} Lose:{lose} {winrate:.3g}% Rate:{rate}'
        return f'<@{id}> ({name}) \n\u200b {stats} \n\u200b'

    def result_str(self, team):
        team_str = ''
        for sn in team:
            if sn in self.summoner_data.id2sum.keys():
                id = self.summoner_data.id2sum[sn][0]
                team_str += f'<@{id}> ({sn}) \n\u200b'
            else:
                id = sn
                team_str += f'not linked summoner ({sn}) \n\u200b'
            if len(self.skill_rating.ratings[str(id)]) > 1:
                diff = int(self.skill_rating.ratings[str(id)][-1][0] - self.skill_rating.ratings[str(id)][-2][0])
            else:
                diff = int(self.skill_rating.ratings[str(id)][-1][0] - 1500)
            summoner_df = self.df[self.df["NAME"] == sn]
            winrate = sum(summoner_df["result"] == 'Win') / len(summoner_df) * 100
            win = int(sum(summoner_df["result"] == 'Win'))
            lose = int(sum(summoner_df["result"] == 'Lose'))
            rate = int(self.skill_rating.ratings[str(id)][-1][0])
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
        self.df.to_csv('data/log/log.csv', index=False)
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
                        game_df = self.df[self.df["game_id"] == replay_id]
                        for _, row in game_df.iterrows():
                            name = row["NAME"]
                            mu = row["mu"]
                            sigma = row["sigma"]
                            if name in self.summoner_data.id2sum.keys():
                                name = self.summoner_data.id2sum[name][0]
                            del self.skill_rating.ratings[str(name)][-1][0]
                            del self.skill_rating.ratings[str(name)][-1][1]
                        self.skill_rating.save_ratings(self.skill_rating.ratings)
                        target = self.df.index[self.df["game_id"] == replay_id]
                        self.df = self.df.drop(target)
                        self.df.to_csv('data/log/log.csv', index=False)

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

    async def init_rate(self, message):

        space_split = message.split(" ")
        if len(space_split) == 1:
            name_space = space_split[1]
            mu = 1500
            sigma = 500
        elif len(space_split) == 2:
            name_space = space_split[1]
            mu = space_split[2]
            sigma = 500
        elif len(space_split) == 3:
            name_space = space_split[1]
            mu = space_split[2]
            sigma = space_split[3]

        if name_space.startswith('<@') and name_space.endswith('>'):
            id = name_space
            sn = self.summoner_data.sum2id(id)
        else:
            sn = space_split[1]
            if id in self.summoner_data.id2sum.keys():
                id = self.summoner_data.id2sum[sn][0]
            else:
                id = None

        self.skill_rating.init_rate(id, sn, mu, sigma)
        await message.reply(content="Done")

    async def rename(self, message):
        #  /rename Feder Kissen,Sakura Laurel
        space_split = message.content.split(' ')
        tmp_names = " ".join(space_split[1:])
        old_sn = tmp_names.split(',')[0]
        sn = tmp_names.split(',')[1]
        # rename logdata
        if self.df is not None:
            summoner_df = self.df[self.df["NAME"] == old_sn]
            if len(summoner_df) < 1:
                await message.reply(content=f"summoner name {old_sn} Log not found")
                return
        else:
            await message.reply(content="Log not found")
            return
        self.df[self.df["NAME"] == old_sn]['NAME'] = sn
        self.df.to_csv('data/log/log.csv', index=False)
        await message.reply(content="Rename Successfully Log data")
        # rename discord id
        if old_sn in self.summoner_data.id2sum.keys():
            self.summoner_data.id2sum[sn] = self.summoner_data.id2sum.pop(old_sn)
            self.summoner_data.save_id2sum()
        else:
            await message.reply(content=f"{old_sn} not linked")
            return
        await message.reply(content="Rename Successfully discord id")
        return
