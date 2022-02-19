from dggbot.message import Message
from dggbot import DGGBot
from os import getenv
from time import sleep
from threading import Thread
from asyncio import get_running_loop, create_task
from pathlib import Path
import json
import discord

discord_bot = discord.Client()

with Path(__file__).with_name("config.json").open("r") as config_file:
    config = json.loads(config_file.read())


dgg_bot = DGGBot(auth_token=getenv("DGG_AUTH"), username="TenaReturns", owner="Fritz")
dgg_thread = Thread(target=dgg_bot.run)


@discord_bot.event
async def on_ready():
    discord_bot.relay_channel = discord_bot.get_channel(944252065515962468)
    print(f"Forwarding messages to {discord_bot.relay_channel}")
    discord_bot.disc_loop = get_running_loop()
    await discord_bot.relay_channel.send("Connecting to DGG")
    dgg_thread.start()


@discord_bot.event
async def on_message(disc_msg):
    if (disc_msg.author == discord_bot.user) or (
        disc_msg.channel != discord_bot.relay_channel
    ):
        return
    dgg_bot.send(disc_msg.content)


@dgg_bot.event("on_mention")
def on_dgg_mention(dgg_msg):
    discord_bot.disc_loop.create_task(
        discord_bot.relay_channel.send(f"{dgg_msg.nick} said: {dgg_msg.data}")
    )


@dgg_bot.event("on_msg")
def on_dgg_message(dgg_msg):
    if dgg_msg.nick in config["whitelist"]:
        discord_bot.disc_loop.create_task(
            discord_bot.relay_channel.send(f"{dgg_msg.nick} said: {dgg_msg.data}")
        )


discord_bot.run(getenv("DISC_AUTH"))
