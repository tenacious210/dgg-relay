from dggbot.message import Message
from dggbot import DGGBot
from os import getenv
from time import sleep
from threading import Thread
from asyncio import run, get_running_loop, create_task
import discord


info = {}
discord_bot = discord.Client()

dgg_bot = DGGBot(auth_token=getenv("DGG_AUTH"), username="TenaReturns", owner="Fritz")
dgg_thread = Thread(target=dgg_bot.run)


@discord_bot.event
async def on_ready():
    info["relay_channel"] = discord_bot.get_channel(944252065515962468)
    print(f'Forwarding messages to {info["relay_channel"]}')
    info["disc_loop"] = get_running_loop()
    dgg_thread.start()


@discord_bot.event
async def on_message(disc_msg):
    if (disc_msg.author == discord_bot.user) or (
        disc_msg.channel != info["relay_channel"]
    ):
        return
    await info["relay_channel"].send("Message received")


@dgg_bot.event("on_msg")
def on_dgg_message(dgg_msg):
    info["disc_loop"].create_task(
        info["relay_channel"].send(f"{dgg_msg.nick} said: {dgg_msg.data}")
    )


discord_bot.run(getenv("DISC_AUTH"))
