from src import image_gen, replay_reader, summoner_data
from discord import File, Embed, Colour
import os
import pandas as pd
import numpy as np
import yaml
import trueskill
import random
mu = 1500.
sigma = mu / 3.
beta = sigma / 2.
tau = sigma / 100.
draw_probability = 0.1
backend = None

LANE = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]


def msg2sum(content, d_id):
    space_split = content.split(" ")
    if len(space_split) == 1:
        return None, str(d_id)
    if space_split[1].startswith('<@') and space_split[1].endswith('>'):
        return " ".join(space_split[2:]), space_split[1][2:-1]  # given summonername, given discord id
    else:
        return " ".join(space_split[1:]), None  # given summoner name, no discord id


class BotFunctions():
    def __init__(self, prefix, user):
        super().__init__()
        if os.path.exists("data/rating.yaml"):
            with open("data/rating.yaml", "r", encoding="utf-8") as f:
                self.ratings = yaml.load(f, Loader=yaml.FullLoader)
        else:
            with open("data/rating.yaml", "w", encoding="utf-8") as f:
                self.ratings = {}
        self.env = trueskill.TrueSkill(
            mu=mu, sigma=sigma, beta=beta, tau=tau,
            draw_probability=draw_probability, backend=backend)
        self.summoner_data = summoner_data.SummonerData()
        self.image_gen = image_gen.ImageGen()
        self.prefix = prefix
        self.user = user
        self.commands = {"id": {"func": self.id, "help": "rg:id {ID} - Gets info of match ID"},
                         "replay": {"func": self.replay,
                                    "help": "/replay - Attach a .ROFL or .json from a replay for the bot to display"},
                         "log": {"func": self.log, "help": "rg:log - Log a replay ID into the database"},
                         "link": {"func": self.link,
                                  "help": "/link {Summoner Name} - Links a summoner name to your Discord. Mention someone before the summoner name to link it to their Discord instead"},
                         "unlink": {"func": self.unlink, "help": "rg:unlink {Summoner Name} - Opposite of rg:link"},
                         "stats": {"func": self.stats,
                                    "help": "/stats {Summoner Name or @} {ha or sr, leave blank for all} - Get player's stats"},
                         "detail": {"func": self.detail,
                                    "help": "/detail {Summoner Name or @} {ha or sr, leave blank for all} - Get player's detail stats"},
                         "bestgame": {"func": self.bestgame,
                                    "help": "/bestgame {Summoner Name or @}  - Get player's bestgame"},
                         "team": {"func": self.team,
                                    "help": "/team  - Get teams"},
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
            self.summoner_data.log(replay_id)
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

            if not os.path.exists("data/logged.txt"):
                with open("data/logged.txt", "w") as f:
                    pass

            with open("data/logged.txt", "r") as f:
                logged_ids = f.readlines()

            if not replay_id + '\n' in logged_ids: 
                with open("data/logged.txt", "a") as f:
                    f.write(f"{replay_id}\n")
                    self.summoner_data.log(replay_id)
                    self.update_ratings(self.summoner_data.winners, self.summoner_data.losers)
                    self.save_ratings()

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
        else:
            await message.reply(content=self.summoner_data.link_id2sum(summoner_name, str(discord_id)))

        if summoner_name in self.ratings.keys():
            self.ratings[discord_id] = self.ratings[summoner_name]
            del self.ratings[summoner_name]
            self.save_ratings()

    async def unlink(self, message):
        summoner_name, discord_id = msg2sum(message.content, message.author.id)
        if discord_id is None:
            discord_id = message.author.id
        else:
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
            await message.reply(content="Invalid syntax. Try rg:help {command}")

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
            list_of_key = list(self.summoner_data.id2sum.keys())
            multi_list = list(self.summoner_data.id2sum.values())
            list_of_value = [x[0] for x in multi_list]

            if discord_id in list_of_value:
                position = list_of_value.index(discord_id)
                summoner_name = list_of_key[position]

            if summoner_name is None:
                await message.reply(content="Summoner name is not linked")
                return

            name = f"<@{discord_id}>"
            avator = await self.user(discord_id)
        else:
            name = summoner_name
            avator = None

        if os.path.exists('data/log/log.csv'):
            df = pd.read_csv('data/log/log.csv')
            summoner_df = df[df["name"] == summoner_name]

            if len(summoner_df) < 1:
                await message.reply(content="Log not found")
                return

            average_kill = str(sum(summoner_df["kill"].astype(int)) / len(summoner_df))
            average_death = str(sum(summoner_df["death"].astype(int)) / len(summoner_df))
            if average_death == '0.0':
                average_death = '1.0'
            average_assist = str(sum(summoner_df["assist"].astype(int)) / len(summoner_df))
            average_kda = (float(average_kill) + float(average_assist)) / float(average_death)
            winrate = sum(summoner_df["result"] == 'Win') / len(summoner_df) * 100
            average_vision_ward = sum(summoner_df["vision_ward"].astype(int)) / len(summoner_df)

            if len(summoner_df) > 4:
                role = summoner_df['position'].value_counts()
                champ = summoner_df["champion"].value_counts()[:5]
            else:
                role = summoner_df['position'].value_counts()[:len(summoner_df)]
                champ = summoner_df["champion"].value_counts()[:len(summoner_df)]

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
            for _, row in summoner_df[:games].iterrows():
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
            embed.add_field(name="Winrate", value=f"{winrate:.3g}")
            embed.add_field(name="KDA", value=f"{average_kda:.3g}")
            embed.add_field(name="Wards", value=f"{average_vision_ward:.3g}")

            embed.add_field(name="\nRole", value=f"{role_str}", inline=False)
            embed.add_field(name="\nFavorite Champions", value=f"{champ_str}", inline=False)
            embed.add_field(name="\nRecent Games", value=f"{recent}", inline=False)

            await message.reply(file=file, embed=embed)
        else:
            await message.reply(content="Log file not found")
            return

    async def bestgame(self, message):
        summoner_name, discord_id = msg2sum(message.content, message.author.id)
        if discord_id is not None:
            list_of_key = list(self.summoner_data.id2sum.keys())
            multi_list = list(self.summoner_data.id2sum.values())
            list_of_value = [x[0] for x in multi_list]

            if discord_id in list_of_value:
                position = list_of_value.index(discord_id)
                summoner_name = list_of_key[position]

            if summoner_name is None:
                await message.reply(content="Summoner name is not linked")
                return

            name = f"<@{discord_id}>"
        else:
            name = summoner_name

        if os.path.exists('data/log/log.csv'):
            df = pd.read_csv('data/log/log.csv')
            summoner_df = df[df["name"] == summoner_name]

            if len(summoner_df) < 1:
                await message.reply(content="Log not found")
                return

            kill = summoner_df["kill"].astype(int) / len(summoner_df)
            death = summoner_df["death"].astype(int) / len(summoner_df)
            assist = summoner_df["assist"].astype(int) / len(summoner_df)
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
            list_of_key = list(self.summoner_data.id2sum.keys())
            multi_list = list(self.summoner_data.id2sum.values())
            list_of_value = [x[0] for x in multi_list]

            if discord_id in list_of_value:
                position = list_of_value.index(discord_id)
                summoner_name = list_of_key[position]

            if summoner_name is None:
                await message.reply(content="Summoner name is not linked")
                return

            name = f"<@{discord_id}>"
            avator = await self.user(discord_id)
        else:
            name = summoner_name
            avator = None

        if os.path.exists('data/log/log.csv'):
            df = pd.read_csv('data/log/log.csv')
            summoner_df = df[df["name"] == summoner_name]

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
                lane_df = summoner_df[summoner_df["position"] == lane]
                if len(lane_df) > 0:
                    average_kill = str(sum(lane_df["kill"].astype(int)) / len(lane_df))
                    average_death = str(sum(lane_df["death"].astype(int)) / len(lane_df))
                    average_assist = str(sum(lane_df["assist"].astype(int)) / len(lane_df))
                    if average_death == '0.0':
                        average_death = '1.0'
                    average_kda = (float(average_kill) + float(average_assist)) / float(average_death)
                    winrate = sum(lane_df["result"] == 'Win') / len(lane_df) * 100
                    average_vision_ward = sum(lane_df["vision_ward"].astype(int)) / len(lane_df)

                    if len(lane_df) > 4:
                        champ = lane_df["champion"].value_counts()[:5]
                    else:
                        champ = lane_df["champion"].value_counts()[:len(lane_df)]

                    champ_str = ''
                    for index, v in champ.items():
                        champ_str += f'**{index}** : {v}  '

                    embed.add_field(name=f"{lane}", value=f"**Games** : **{len(lane_df)}**", inline=False)
                    embed.add_field(name="Winrate", value=f"{winrate:.3g}")
                    embed.add_field(name="KDA", value=f"{average_kda:.3g}")
                    embed.add_field(name="Wards", value=f"{average_vision_ward:.3g}")
                    embed.add_field(name="\nFavorite Champions", value=f"{champ_str}\n\u200b", inline=False)

            average_kill = str(sum(summoner_df["kill"].astype(int)) / len(summoner_df))
            average_death = str(sum(summoner_df["death"].astype(int)) / len(summoner_df))
            average_assist = str(sum(summoner_df["assist"].astype(int)) / len(summoner_df))
            if average_death == '0.0':
                average_death = '1.0'
            average_kda = (float(average_kill) + float(average_assist)) / float(average_death)
            winrate = sum(summoner_df["result"] == 'Win') / len(summoner_df) * 100
            average_vision_ward = sum(summoner_df["vision_ward"].astype(int)) / len(summoner_df)

            embed.add_field(name="Total Winrate", value=f"{winrate:.3g}")
            embed.add_field(name="KDA", value=f"{average_kda:.3g}")
            embed.add_field(name="Wards", value=f"{average_vision_ward:.3g}")

            await message.reply(embed=embed)
        else:
            await message.reply(content="Log file not found")
            return

    async def team(self, message):

        new_message = await message.channel.send("参加する人は✅を押してください")
        await new_message.add_reaction("✅")

    async def make_team(self, reaction):

        players = []
        maxq = 0
        team = []
        t_num = 5
        async for user in reaction.users():
            if not user == reaction.message.author:
                if user.id not in self.ratings.keys():
                    init = self.env.create_rating()
                    self.ratings[user.id] = [init.mu, init.sigma]
                players.append(user.id)

        self.save_ratings()

        for _ in range(252):
            t1 = {}
            t2 = {}
            random.shuffle(players)
            t1_id = players[:t_num]
            t2_id = players[t_num:]
            for j in range(t_num):
                t1[t1_id[j]] = self.env.create_rating(self.ratings[t1_id[j]][0], self.ratings[t1_id[j]][1])
                t2[t2_id[j]] = self.env.create_rating(self.ratings[t2_id[j]][0], self.ratings[t2_id[j]][1])
            q = self.env.quality((t1, t2,))
            if q > maxq:
                team = [t1_id, t2_id]
            if q > 0.85:
                team = [t1_id, t2_id]
                break

        self.save_ratings()
        embed = Embed(title="Team", color=0xF945C0)

        team1 = ''
        team2 = ''
        for i in range(t_num):
            team1 += f'<@{team[0][i]}>\n\u200b'
            team2 += f'<@{team[1][i]}>\n\u200b'

        embed.add_field(name="Team 1", value=team1)
        embed.add_field(name="Team 2", value=team2)

        await reaction.message.channel.send(embed=embed)

    async def update_ratings(self, winners, losers):
        if len(winners) < 5 or len(losers) < 5:
            return
        t1, t2 = {}, {}
        players = []
        for p in winners:
            id = self.summoner_data.id2sum.get(p, [])
            if len(id) > 0:
                name = id[0]
            else:
                name = p
            players.append(name)
            if name not in self.ratings.keys():
                init = self.env.create_rating()
                self.ratings[name] = [init.mu, init.sigma]
            t1[name] = self.env.create_rating(self.ratings[name][0], self.ratings[name][1])

        for p in losers:
            id = self.summoner_data.id2sum.get(p, [])
            if len(id) > 0:
                name = id[0]
            else:
                name = p
            players.append(name)
            if name not in self.ratings.keys():
                init = self.env.create_rating()
                self.ratings[name] = [init.mu, init.sigma]
            t2[name] = self.env.create_rating(self.ratings[name][0], self.ratings[name][1])

        t1, t2, = self.env.rate((t1, t2,))
        for name in players:
            if name in t1.keys():
                self.ratings[name] = [t1[name].mu, t1[name].sigma]
            else:
                self.ratings[name] = [t2[name].mu, t2[name].sigma]

    def save_ratings(self):  # Saves sum2id yaml file
        with open("data/ratings.yaml", "w", encoding="utf-8") as f:
            yaml.dump(self.ratings, f, allow_unicode=True, encoding='utf-8')
