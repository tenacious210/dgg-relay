from dggbot.message import Message
from dggbot import DGGBot
from os import getenv
from time import sleep
import discord

info = {}
discord_bot = discord.Client()

dgg_bot = DGGBot(getenv("DGG_AUTH"), username="TenaReturns", owner="Fritz")


async def fwd_to_disc(dgg_msg: Message):
    await info["relay_channel"].send(f"{dgg_msg.nick} said: {dgg_msg.data}")


@discord_bot.event
async def on_ready():
    info["relay_channel"] = discord_bot.get_channel(944252065515962468)
    print(f'Forwarding messages to {info["relay_channel"]}')


@discord_bot.event
async def on_message(disc_msg):
    if (disc_msg.author == discord_bot.user) or (
        disc_msg.channel != info["relay_channel"]
    ):
        return
    await info["relay_channel"].send("Message received")


@dgg_bot.event("on_mention")
def on_dgg_mention(dgg_msg):
    fwd_to_disc(dgg_msg)


@dgg_bot.event("on_message")
def on_dgg_message(dgg_msg):
    fwd_to_disc(dgg_msg)


discord_bot.run(getenv("DISC_AUTH"))
while True:
    dgg_bot.run()
    sleep(600)
