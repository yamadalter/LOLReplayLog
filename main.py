from src import discord_bot
import configparser
import json

config = configparser.ConfigParser()
config.read('config.ini')
section = config['CONFIG']
token = section['token']
if token == "":
    print("Add your token to config.ini. You can find it at the Discord developer portal, under Bot.")
    exit()
prefix = section['prefix']
RGCustomsBot = discord_bot.RGCustoms(prefix, vc_list)
RGCustomsBot.run(token)
