from src import image_gen, replay_reader, summoner_data
from discord import File
import os
import pandas as pd


def msg2sum(content, d_id):
    space_split = content.split(" ")
    if len(space_split) == 1:
        return None, d_id
    if space_split[1].startswith('<@') and space_split[1].endswith('>'):
        return " ".join(space_split[2:]), space_split[1][2:-1]  # given summonername, given discord id
    else:
        return " ".join(space_split[1:]), None  # given summoner name, no discord id


class BotFunctions:
    def __init__(self, prefix):
        self.summoner_data = summoner_data.SummonerData()
        self.image_gen = image_gen.ImageGen()
        self.prefix = prefix
        self.commands = {"id": {"func": self.id, "help": "rg:id {ID} - Gets info of match ID"},
                         "replay": {"func": self.replay,
                                    "help": "rg:replay - Attach a .ROFL or .json from a replay for the bot to display"},
                         "log": {"func": self.log, "help": "rg:log - Log a replay ID into the database"},
                         "link": {"func": self.link,
                                  "help": "rg:link {Summoner Name} - Links a summoner name to your Discord. Mention someone before the summoner name to link it to their Discord instead"},
                         "unlink": {"func": self.unlink, "help": "rg:unlink {Summoner Name} - Opposite of rg:link"},
                         "stats": {"func": self.stats,
                                    "help": "rg:stats {Summoner Name or @} {ha or sr, leave blank for all} - Get player's stats"},
                         "history": {"func": self.history,
                                     "help": "rg:history {Summoner Name or @} {ha or sr, leave blank for all} - Get recent matches"},
                         "help": {"func": self.help,
                                  "help": "rg:help {command} - Get syntax for given command, leave blank for list of commands"}}

    async def log(self, message=None, ids=None):
        if ids is None:
            ids = message.content[5:].split(",")
        for replay_id in ids:
            if os.path.exists("data/logged.txt"):
                with open("data/logged.txt", "r") as f:
                    logged_ids = f.readlines()
                    if replay_id + '\n' in logged_ids:
                        if message:
                            await message.channel.send(
                                content=f"Match {replay_id} was previously logged")  # The match has already been logged.
                        return
            elif not os.path.exists("data/logged.txt"):
                with open("data/logged.txt", "w") as f:
                    pass
            self.summoner_data.log(replay_id)
            with open("data/logged.txt", "a") as f:
                f.write(f"{replay_id}\n")
            if message:
                await message.channel.send(content=f"Match {replay_id} logged")

    async def id(self, message=None, ids=None):  # Get match from ID
        if ids is None:
            ids = message.content[6:].split(',')
        for replay_id in ids:
            try:
                replay = replay_reader.ReplayReader(replay_id)
            except FileNotFoundError:
                await message.channel.send(content="Replay file not found")
                return
            if not os.path.exists(f'data/match_imgs/{replay_id}.png'):
                replay.generate_game_img()
            await message.channel.send(file=File(f'data/match_imgs/{replay_id}.png'))

            alartlist, arrestlist = self.summoner_data.ward_alert(replay_id)
            if len(alartlist) > 0:
                await message.channel.send(content=f"Buy more control wards! (Bought control ward : 1)   {' '.join(alartlist)}")
            if len(arrestlist) > 0:
                await message.channel.send(content=f"**I'm arresting you! (Bought control ward : 0)   {' '.join(arrestlist)}**")

            if os.path.exists("data/logged.txt"):
                with open("data/logged.txt", "r") as f:
                    logged_ids = f.readlines()
                    if replay_id + '\n' in logged_ids:
                        if message:
                            await message.channel.send(
                                content=f"Match {replay_id} was previously logged")  # The match has already been logged.
                        return
            elif not os.path.exists("data/logged.txt"):
                with open("data/logged.txt", "w") as f:
                    pass
            self.summoner_data.log(replay_id)
            with open("data/logged.txt", "a") as f:
                f.write(f"{replay_id}\n")
            if message:
                await message.channel.send(content=f"Match {replay_id} logged")

    async def replay(self, message):  # Submit new replay
        attachments = message.attachments
        ids = []
        if len(attachments) > 0:
            for attachment in attachments:
                if attachment.filename.endswith('.rofl') or attachment.filename.endswith('.json'):
                    await attachment.save(f"data/replays/{attachment.filename}")
                    await message.channel.send(content=f"Replay {attachment.filename[:-5]} saved")
                    ids.append(attachment.filename[:-5])
                else:
                    await message.channel.send(content=f"File {attachment.filename} is not a supported file type")
        if len(ids) > 0:
            await self.id(message, ids)
        else:
            await message.channel.send(content="No replay file attached")

    async def link(self, message):
        summoner_name, discord_id = msg2sum(message.content, message.author.id)
        if discord_id is None:
            discord_id = message.author.id
        else:
            await message.channel.send(content=self.summoner_data.link_id2sum(summoner_name, str(discord_id)))

    async def unlink(self, message):
        summoner_name, discord_id = msg2sum(message.content, message.author.id)
        if discord_id is None:
            discord_id = message.author.id
        else:
            await message.channel.send(content=self.summoner_data.unlink(summoner_name, str(discord_id)))

    async def profile(self, message):
        matches = self.get_history(message)
        champ_data_list = self.summoner_data.profile(matches)
        self.image_gen.generate_player_profile(champ_data_list)
        await message.channel.send(file=File('temp.png'))

    async def history(self, message):
        matches = self.get_history(message)
        match_history = []
        if len(matches) == 1 and "|" not in matches[0]:
            await message.channel.send(content=matches[0])
            return
        for match in matches:
            champ, result, kda, game_id, csm = match.split("|")
            replay = replay_reader.ReplayReader(game_id)
            stats = replay.get_player_stats(champ=champ)
            match_history.append(
                [champ, result, stats['keystone'], stats['subperk'], kda, stats['cs'], stats['items'], stats['gold']])
        self.image_gen.generate_player_history(match_history)
        await message.channel.send(file=File('temp.png'))
        os.remove('temp.png')

    def get_history(self, message):
        game_map = "all"
        summoner_name, discord_id = msg2sum(message.content, message.author.id)
        return self.summoner_data.history(summoner_name=summoner_name, discord_id=discord_id, mode=game_map)

    async def help(self, message):
        space_split = message.content.split(" ")
        if len(space_split) == 1:
            cmd_list = ""
            for cmd in self.commands:
                cmd_list += cmd + ", "
            cmd_list = cmd_list[:-2] + "\n"
            cmd_list += f"Use {self.prefix}help {{command}} to get more help."
            await message.channel.send(content=cmd_list)
        elif len(space_split) == 2:
            for cmd in self.commands:
                if cmd.lower() == space_split[1].lower():
                    help_str = self.commands[cmd]["help"]
            await message.channel.send(content=help_str)
        else:
            await message.channel.send(content="Invalid syntax. Try rg:help {command}")

    async def handle_message(self, message):
        cmd_split = message.content.split(self.prefix)
        space_split = cmd_split[1].split(" ")
        if space_split[0] in self.commands:
            await self.commands[space_split[0]]["func"](message)
        else:
            await message.channel.send(content="Command not found")
    
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
                await message.channel.send(content="Summoner name is not linked")
                return

            name = f"<@{discord_id}>"
        else:
            name = summoner_name

        if os.path.exists('data/log/log.csv'):
            df = pd.read_csv('data/log/log.csv')
            summoner_df = df[df["name"] == summoner_name]

            if len(summoner_df) < 1:
                await message.channel.send(content="Log not found")
                return

            average_kill = str(sum(summoner_df["kill"].astype(int)) / len(summoner_df))
            average_death = str(sum(summoner_df["death"].astype(int)) / len(summoner_df))
            average_assist = str(sum(summoner_df["assist"].astype(int)) / len(summoner_df))
            average_kda = (float(average_kill) + float(average_assist)) / float(average_death)
            winrate = sum(summoner_df["result"] == 'Win') / len(summoner_df) * 100
            average_vision_ward = sum(summoner_df["vision_ward"].astype(int)) / len(summoner_df)

            if len(summoner_df) > 4:
                role = summoner_df['position'].value_counts()[:5]
                champ = summoner_df["champion"].value_counts()[:5]
            else:
                role = summoner_df['position'].value_counts()[:len(summoner_df)]
                champ = summoner_df["champion"].value_counts()[:len(summoner_df)]

            role_str = ''

            for index, v in role.items():
                role_str += f'{index} : {v}  '

            champ_str = ''
            for index, v in champ.items():
                champ_str += f'{index} : {v}  '

            await message.channel.send(
                content=f" {name} \n Winrate : {winrate:.3g}  KDA : {average_kda:.3g}  Wards : {average_vision_ward:.3g} \n Role :  {role_str} \n Champions :  {champ_str}")
        else:
            await message.channel.send(content="Log file not found")
            return
