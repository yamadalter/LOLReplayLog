import image_gen
import replay_reader
import summoner_data
import skill_rating
import riot_api
from discord import File, Embed, Colour, ui, ButtonStyle
from utils import get_keys
from common import TEAM_NUM, MU, SIGMA, INIT_SIGMA, MIN_SIGMA, LANE, LinkDataJSON, TierData
import os
import shutil
import configparser
import json
import requests
import tarfile
import pandas as pd
import numpy as np



class BotFunctions():
    def __init__(self, client):
        super().__init__()
        config = configparser.ConfigParser()
        config.read('config.ini')
        json_open = open(TierData, 'r', encoding='utf-8')
        self.tierdic = json.load(json_open)
        if os.path.exists(LinkDataJSON):
            json_open = open(LinkDataJSON, 'r', encoding='utf-8')
            self.dic = json.load(json_open)
        else:
            self.dic = {}
        self.summoner_data = summoner_data.SummonerData()
        self.image_gen = image_gen.ImageGen()
        self.skill_rating = skill_rating.SkillRating()
        self.watcher = riot_api.Watcher()
        self.user = client.fetch_user
        if os.path.exists('data/log/log.csv'):
            self.logdf = pd.read_csv('data/log/log.csv')
        else:
            self.logdf = None

    async def id(self, interaction=None, ids=None):  # Get match from ID
        if ids is None:
            await interaction.followup.send(content="Replay file not found")
            return
        for replay_id in ids:
            try:
                replay = replay_reader.ReplayReader(replay_id)
            except FileNotFoundError:
                await interaction.followup.send(content="Replay file not found")
                return
            if not os.path.exists("data/logged.txt"):
                with open("data/logged.txt", "w") as f:
                    pass
            with open("data/logged.txt", "r") as f:
                logged_ids = f.readlines()
            if not replay_id + '\n' in logged_ids:
                old_log = self.logdf
                self.logdf = self.summoner_data.log(replay_id, self.logdf)
                self.dic, names = self.skill_rating.update_ratings(self.dic, replay_id, self.summoner_data.winners, self.summoner_data.losers)
                if names is not None:
                    self.save_dic2json()
                    await self.team_result(interaction, self.summoner_data.winners, self.summoner_data.losers)
                else:
                    await interaction.followup.send(content="not linked summoner found")
                    self.logdf = old_log
                    return
                with open("data/logged.txt", "a") as f:
                    f.write(f"{replay_id}\n")
                self.logdf.to_csv('data/log/log.csv', index=False)
            if not os.path.exists(f'data/match_imgs/{replay_id}.png'):
                replay.generate_game_img(self.dic)
            embed = Embed(title="Replay", description=f"{replay_id}", color=Colour.blurple())
            file = File(f'data/match_imgs/{replay_id}.png', filename="image.png")
            embed.set_image(url="attachment://image.png")
            await interaction.followup.send(file=file, embed=embed)

    async def replay(self, interaction, attachment):  # Submit new replay
        ids = []
        if attachment.filename.endswith('.rofl') or attachment.filename.endswith('.json'):
            await attachment.save(f"data/replays/{attachment.filename}")
            ids.append(attachment.filename[:-5])

        if len(ids) > 0:
            await self.id(interaction, ids)
        else:
            await interaction.followup.send(content="No replay file attached")
            return

    async def link(self, interaction, riotid, tag, member=None):
        # link id
        discord_id = str(interaction.user.id) if member is None else str(member.id)
        if discord_id in self.dic:
            await interaction.followup.send(content=f'<@{discord_id}> is already linked')
            return
        if (riotid is None) or (tag is None):
            await interaction.followup.send(content='/link gamename #tag')
            return
        res = self.watcher.search_by_riot_id(riotid, tag)
        if res is None:
            await interaction.followup.send(content=f'{riotid} #{tag} has not found')
            return
        else:
            puuid = res['puuid']
            gamename = res['gameName']
            tag = res['tagLine']
            sn = self.watcher.search_puuid(puuid)['name']
            rank, tier = self.watcher.search_rank(puuid)
            if rank is not None and tier is not None:
                mu = self.tierdic[tier][rank]
                sigma = INIT_SIGMA
                await interaction.followup.send(content=f'Successfully linked! {gamename} Rate:{mu}')
            else:
                mu, sigma = MU, SIGMA
                await interaction.followup.send(content='Successfully linked! unranked summmoner. Rate:1500')
            # set rating
            self.dic[discord_id] = {
                'puuid': puuid,
                'gamename': gamename,
                'tag': tag,
                'sn': sn,
                'mu': [float(mu)],
                'sigma': [float(sigma)],
                'gameid': ['init']
            }
            self.save_dic2json()

    async def unlink(self, interaction, member=None):
        discord_id = str(interaction.user.id) if member is None else str(member.id)
        self.dic.pop(discord_id)
        await interaction.response.send_message(content=f'<@{discord_id}> has been unlinked')

    async def stats(self, interaction, member):
        discord_id = str(interaction.user.id) if member is None else str(member.id)
        summoner_name = self.dic[discord_id]['sn']
        gamename = self.dic[discord_id]['gamename']
        tag = self.dic[discord_id]['tag']
        if summoner_name is None:
            await interaction.followup.send(content="Summoner name is not linked")
            return
        name = f"<@{discord_id}>"
        avator = await self.user(discord_id)

        if self.logdf is not None:
            summoner_df = self.logdf[self.logdf["NAME"] == summoner_name]
            if len(summoner_df) < 1:
                await interaction.followup.send(content="Log not found")
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
            rate = self.dic[discord_id]['mu'][-1]
            embed.add_field(name="Rating", value=f"{int(rate)}", inline=False)
            embed.add_field(name="Winrate", value=f"{winrate:.3g}")
            embed.add_field(name="KDA", value=f"{average_kda:.3g}")
            embed.add_field(name="Wards", value=f"{average_vision_ward:.3g}")
            embed.add_field(name="\nRole", value=f"{role_str}", inline=False)
            embed.add_field(name="\nFavorite Champions", value=f"{champ_str}", inline=False)
            # embed.add_field(name="\nRecent Games", value=f"{recent}", inline=False)
            mus = self.dic[discord_id]['mu']
            sigmas = self.dic[discord_id]['sigma']
            self.image_gen.generate_rating_img(mus, sigmas, summoner_name)
            file = File(f'data/ratings_imgs/{summoner_name}.png', filename="image.png")
            embed.set_image(url="attachment://image.png")
            await interaction.followup.send(file=file, embed=embed)
        else:
            await interaction.followup.send(content="Log file not found")
            return

    async def bestgame(self, interaction, member):
        discord_id = str(interaction.user.id) if member is None else str(member.id)
        summoner_name = self.dic[discord_id]['sn']
        if summoner_name is None:
            await interaction.followup.send(content="Summoner name is not linked")
            return
        name = f"<@{discord_id}>"
        if self.logdf is not None:
            summoner_df = self.logdf[self.logdf["NAME"] == summoner_name]
            if len(summoner_df) < 1:
                await interaction.followup.send(content="Log not found")
                return
            kill = summoner_df["CHAMPIONS_KILLED"].astype(int) / len(summoner_df)
            death = summoner_df["NUM_DEATHS"].astype(int) / len(summoner_df)
            assist = summoner_df["ASSISTS"].astype(int) / len(summoner_df)
            kda = ((kill) + (assist)) / (death)
            max_index = np.argmax(kda)
            replay_id = list(summoner_df["game_id"])[max_index]
            if not os.path.exists(f'data/match_imgs/{replay_id}.png'):
                await interaction.followup.send(content="Log not found")
                return
            embed = Embed(title="Best Game", description=f"{name}", color=Colour.blurple())
            file = File(f'data/match_imgs/{replay_id}.png', filename="image.png")
            embed.set_image(url="attachment://image.png")
            await interaction.followup.send.reply(file=file, embed=embed)

    async def detail(self, interaction, member):
        discord_id = str(interaction.user.id) if member is None else str(member.id)
        summoner_name = self.dic[discord_id]['sn']
        gamename = self.dic[discord_id]['gamename']
        tag = self.dic[discord_id]['tag']
        if summoner_name is None:
            await interaction.followup.send(content="Summoner name is not linked")
            return
        name = f"<@{discord_id}>"
        avator = await self.user(discord_id)

        if self.logdf is not None:
            summoner_df = self.logdf[self.logdf["NAME"] == summoner_name]
            if len(summoner_df) < 1:
                await interaction.followup.send(content="Log not found")
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
                    embed.add_field(name=f"**{lane}**", value=f"**Games** : {len(lane_df)}")
                    embed.add_field(name="Winrate", value=f"{winrate:.3g}")
                    embed.add_field(name="KDA", value=f"{average_kda:.3g}")
                    # embed.add_field(name="Wards", value=f"{average_vision_ward:.3g}")
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
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(content="Log file not found")
            return

    async def send_team(self, reaction):
        res, team = await self.skill_rating.make_team(self.dic, reaction)
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
            gamename = self.dic[id]['gamename'].replace(' ', '+')
            tag = self.dic[id]['tag']
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
            gamename = self.dic[id]['gamename'].replace(' ', '+')
            tag = self.dic[id]['tag']
            name_list.append(f'{gamename}%23{tag}')
        name2 = '%2C'.join(name_list)
        button = ui.Button(label="OPGG", style=ButtonStyle.primary, url=f'https://www.op.gg/multisearch/jp?summoners={name2}')
        view = ui.View()
        view.add_item(button)
        embed = Embed(title="Team 2", color=0xff0000)
        embed.add_field(name="Red", value=team2, inline=False)
        await reaction.message.channel.send(embed=embed, view=view)

    def team_str(self, id):
        name = self.dic[id]['sn']
        rate = self.dic[id]['mu'][-1]
        gamename = self.dic[id]['gamename']
        tag = self.dic[id]['tag']
        if name is None:
            name = 'not linked summoner'
        summoner_df = self.logdf[self.logdf["NAME"] == name]
        if len(summoner_df) < 1:
            stats = f'Log not found: Rate:{rate}'
        else:
            winrate = sum(summoner_df["result"] == 'Win') / len(summoner_df) * 100
            win = int(sum(summoner_df["result"] == 'Win'))
            lose = int(sum(summoner_df["result"] == 'Lose'))
            stats = f'Win:{win} Lose:{lose} {winrate:.3g}% Rate:{int(rate)}'
        return f'<@{id}> ({gamename}#{tag}) \n\u200b {stats} \n\u200b'

    def result_str(self, team):
        team_str = ''
        for sn in team:
            id = get_keys(self.dic, 'sn', sn)
            if id is None:
                id = sn
                team_str += f'not linked summoner ({sn}) \n\u200b'
            else:
                gamename = self.dic[id]['gamename']
                tag = self.dic[id]['tag']
                team_str += f'<@{id}> ({gamename} #{tag}) \n\u200b'
            if len(self.dic[id]['mu']) > 1:
                diff = int(self.dic[id]['mu'][-1] - self.dic[id]['mu'][-2])
            else:
                diff = 0
            summoner_df = self.logdf[self.logdf["NAME"] == sn]
            winrate = sum(summoner_df["result"] == 'Win') / len(summoner_df) * 100
            win = int(sum(summoner_df["result"] == 'Win'))
            lose = int(sum(summoner_df["result"] == 'Lose'))
            rate = int(self.dic[id]['mu'][-1])
            if diff > 0:
                diff = '+' + str(diff)
            stats = f'Win:{win} Lose:{lose} {winrate:.3g}% Rate:{int(rate)} ({diff})'
            team_str += f'{stats} \n\u200b'
        return team_str

    async def team_result(self, interaction, winners, losers):
        embed = Embed(title="Team result", color=0xE0FFFF)
        team1 = self.result_str(winners)
        team2 = self.result_str(losers)
        embed.add_field(name="Winners", value=team1, inline=False)
        embed.add_field(name="Losers", value=team2, inline=False)
        self.logdf.to_csv('data/log/log.csv', index=False)
        await interaction.followup.send(embed=embed)

    async def revert(self, interaction, gameid):
        replay_id = gameid
        if os.path.exists("data/logged.txt"):
            with open("data/logged.txt", "r") as f:
                logged_ids = f.readlines()
                if replay_id + '\n' not in logged_ids:
                    await interaction.followup.send(
                        content=f"Match {replay_id} was not found")
                    return
                else:
                    game_df = self.logdf[self.logdf["game_id"] == replay_id]
                    for _, row in game_df.iterrows():
                        name = row["NAME"]
                        discord_id = get_keys(self.dict, 'sn', name)
                        if discord_id is not None:
                            idx = self.dic[discord_id]['gameid'].index(replay_id)
                            self.dic[discord_id]['mu'].pop(idx)
                            self.dic[discord_id]['sigma'].pop(idx)
                            self.dic[discord_id]['gameid'].pop(idx)
                    self.save_dic2json()
                    target = self.logdf.index[self.logdf["game_id"] == replay_id]
                    self.logdf = self.logdf.drop(target)
                    self.logdf.to_csv('data/log/log.csv', index=False)
                    with open("data/logged.txt", "r") as f:
                        data_lines = f.read()
                    data_lines = data_lines.replace(replay_id + '\n', "")
                    with open("data/logged.txt", "w") as f:
                        f.write(data_lines)
                    if (os.path.isfile(f'data/match_imgs/{replay_id}.png') is True):
                        os.remove(f'data/match_imgs/{replay_id}.png')
                    if (os.path.isfile(f'data/replays/{replay_id}.json') is True):
                        os.remove(f'data/replays/{replay_id}.json')
                    if (os.path.isfile(f'data/replays/{replay_id}.rofl') is True):
                        os.remove(f'data/replays/{replay_id}.rofl')
        await interaction.followup.send(content="Reverted")

    async def reset_rate(self, interaction, member):
        discord_id = str(interaction.user.id) if member is None else str(member.id)
        puuid = self.dic[discord_id]['puuid']
        gamename = self.dic[discord_id]['gamename']
        if puuid is None:
            await interaction.followup.send(content="Summoner name is not linked")
        else:
            # set rating
            rank, tier = self.watcher.search_rank(puuid)
            if rank is not None and tier is not None:
                mu = int(self.tierdf.loc[f'{tier} {rank}', 'Point'])
                sigma = INIT_SIGMA
                await interaction.followup.send(content=f'{gamename} Rate:{mu}')
            else:
                mu, sigma = MU, SIGMA
                await interaction.followup.send(content=f'unranked summmoner. Rate:{MU}')
            self.dic[discord_id]['mu'].append(mu)
            self.dic[discord_id]['sigma'].append(sigma)
            self.dic[discord_id]['gameid'].append('reset')
            self.save_dic2json()

    async def set_rate(self, interaction, mu, sigma=400, member=None):
        discord_id = str(interaction.user.id) if member is None else str(member.id)
        puuid = self.dic[discord_id]['puuid']
        gamename = self.dic[discord_id]['gamename']
        if puuid is None:
            await interaction.response.send_message(content="Summoner name is not linked")
        else:
            await interaction.response.send_message(content=f'{gamename} Rate:{mu}')
            self.dic[discord_id]['mu'].append(mu)
            self.dic[discord_id]['sigma'].append(sigma)
            self.dic[discord_id]['gameid'].append('set')
            self.save_dic2json()

    async def rename(self, interaction, gamename, tag, member=None):
        discord_id = str(interaction.user.id) if member is None else str(member.id)
        if (gamename is None) or (tag is None):
            await interaction.followup.send(content='/link gamename #tag')
            return
        res = self.watcher.search_by_riot_id(gamename, tag)
        if res is None:
            await interaction.followup.send(content=f'{gamename} #{tag} has not found')
            return
        else:
            gamename = res['gameName']
            tag = res['tagLine']
            self.dic[discord_id]['gamename'] = gamename
            self.dic[discord_id]['tag'] = tag
            self.save_dic2json()
            await interaction.followup.send(content=f'Success rename {gamename} #{tag}')
            return

    async def update(self, interaction):
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
        await interaction.followup.send(content=f"updated version {version}")

    def save_dic2json(self):
        json_file = open(LinkDataJSON, mode="w", encoding='utf-8')
        json.dump(self.dic, json_file, indent=2, ensure_ascii=False)