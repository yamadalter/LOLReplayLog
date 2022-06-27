from src import image_gen, replay_reader, summoner_data
from discord import File, Embed, Colour
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
                embed.add_field(name="\n Buy more control wards! (Bought control ward : 1)", value=f"{' '.join(alartlist)}", inline=False)
            if len(arrestlist) > 0:
                embed.add_field(name="\n **I'm arresting you! (Bought control ward : 0)**", value=f"{' '.join(arrestlist)}", inline=False)

            if not os.path.exists("data/logged.txt"):
                with open("data/logged.txt", "w") as f:
                    pass

            

            with open("data/logged.txt", "r") as f:
                logged_ids = f.readlines()

            if not replay_id + '\n' in logged_ids:
                with open("data/logged.txt", "a") as f:
                    f.write(f"{replay_id}\n")
                    self.summoner_data.log(replay_id)

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
        else:
            await message.reply(content=self.summoner_data.link_id2sum(summoner_name, str(discord_id)))

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
        else:
            name = summoner_name

        if os.path.exists('data/log/log.csv'):
            df = pd.read_csv('data/log/log.csv')
            summoner_df = df[df["name"] == summoner_name]

            if len(summoner_df) < 1:
                await message.reply(content="Log not found")
                return

            average_kill = str(sum(summoner_df["kill"].astype(int)) / len(summoner_df))
            average_death = str(sum(summoner_df["death"].astype(int)) / len(summoner_df))
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

            role_str = ''

            for index, v in role.items():
                role_str += f'**{index}** : {v}   '

            champ_str = ''
            for index, v in champ.items():
                champ_str += f'**{index}** : {v}  '

            if winrate > 60:
                stats_color = 0x0099E1
            elif winrate > 50:
                stats_color = 0x00D166
            elif winrate > 40:
                stats_color = 0xF8C300
            else:
                stats_color = 0xFD0061
            
            embed = Embed(title=f"Stats", description=f"{name} Total Games {len(summoner_df)} \n", color=stats_color)
            embed.add_field(name="Winrate", value=f"{winrate:.3g}")
            embed.add_field(name="KDA", value=f"{average_kda:.3g}")
            embed.add_field(name="Wards", value=f"{average_vision_ward:.3g}")

            embed.add_field(name="\n Role", value=f"{role_str}", inline=False)
            embed.add_field(name="\n Favorite Champions", value=f"{champ_str}", inline=False)
            
            await message.reply(embed=embed)
        else:
            await message.reply(content="Log file not found")
            return
