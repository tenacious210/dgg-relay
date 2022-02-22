from dggbot import DGGBot, Message
from os import getenv
from threading import Thread
from asyncio import get_running_loop, create_task
from pathlib import Path
from queue import Queue
from discord import Option, OptionChoice, Emoji
from time import sleep
import logging
import json
import discord
import re


class CustomBot(DGGBot):
    def __init__(
        self,
        auth_token,
        emotes,
        whitelist,
        filter_level="whitelist",
        username="TenaReturns",
        owner="tena",
        prefix="!",
    ):
        super().__init__(
            auth_token=auth_token, username=username, prefix=prefix, owner=owner
        )
        self.username = username
        self.msg_queue = Queue()
        self.emotes = emotes
        self.whitelist = whitelist
        self.filter_level = filter_level

    def _on_error(self, ws, error):
        logging.error(error)
        dgg_bot.msg_queue.put(f'DGG bot raised an error: "{error}"')

    def run_forever(self):
        while True:
            self.run()
            sleep(5)


discord_bot = discord.Bot()

config_path = Path(__file__).with_name("config.json")
with config_path.open("r") as config_file:
    config = json.loads(config_file.read())


dgg_bot = CustomBot(
    getenv("DGG_AUTH"), emotes=config["emotes"], whitelist=config["whitelist"]
)


def parse_dgg_queue():
    while True:
        discord_bot.disc_loop.create_task(
            discord_bot.relay_channel.send(dgg_bot.msg_queue.get())
        )


dgg_thread = Thread(target=dgg_bot.run_forever)
parse_dgg_thread = Thread(target=parse_dgg_queue)


def save_config():
    to_json = {"whitelist": dgg_bot.whitelist, "emotes": dgg_bot.emotes}
    with config_path.open("w") as config_file:
        json.dump(to_json, config_file)


def dgg_to_disc(msg: str):
    for dgg_emote, disc_emote in dgg_bot.emotes.items():
        msg = re.sub(rf"\b{dgg_emote}\b", disc_emote, msg)
    if "nsfw" in msg:
        msg = f"||{msg}||"
    return msg


@discord_bot.slash_command(
    guild_ids=[889845466915819551],
    name="addemote",
    description="Adds a phrase which gets translated from DGG emote to Discord emote",
)
async def addemote(
    ctx,
    dgg_version: Option(str, "The emote as used in DGG"),
    discord_version: Option(str, "The emote as used in Discord"),
):
    if (not dgg_version) or (not discord_version):
        ctx.respond("One of the parameters was invalid.")
        return
    dgg_bot.emotes[dgg_version] = discord_version
    save_config()
    await ctx.respond(f"{dgg_version} : {discord_version}", ephemeral=True)


@discord_bot.slash_command(
    guild_ids=[889845466915819551],
    name="filter",
    description="Change the level of the DGG bot's filter.",
)
async def filter(
    ctx,
    level: Option(
        str,
        "The level to change the DGG bot filter to",
        required=True,
        default=None,
        choices=(
            OptionChoice(name="Mentions only", value="mention"),
            OptionChoice(name="Whitelist only", value="whitelist"),
            OptionChoice(name="No filter", value="off"),
        ),
    ),
):
    if level in ("mention", "whitelist", "off"):
        dgg_bot.filter_level = level
        response = f'Changed the filter level to "{level}"'
    elif level == None:
        response = f'The filter level is "{dgg_bot.filter_level}"'
    else:
        response = f'Invalid filter level: "{level}"'
    await ctx.respond(response)


@discord_bot.slash_command(
    guild_ids=[889845466915819551],
    name="whitelist",
    description="Modify the whitelist",
)
async def whitelist(
    ctx,
    mode: Option(
        str,
        "Choose add or remove mode",
        required=True,
        choices=(
            OptionChoice(name="add", value="add"),
            OptionChoice(name="remove", value="remove"),
        ),
    ),
    user: Option(
        str,
        "The user to add/remove from the whitelist",
        required=True,
    ),
):
    if mode in ("add", "remove") and user:
        if mode == "add":
            dgg_bot.whitelist.append(user)
            response = f'"{user}" was added to the whitelist.'
        elif mode == "remove" and user in dgg_bot.whitelist:
            dgg_bot.whitelist.remove(user)
            response = f'"{user}" was removed from the whitelist.'
        elif mode == "remove" and user not in dgg_bot.whitelist:
            await ctx.respond(f'"{user}" was not found in the whitelist.')
            return
        save_config()
        await ctx.respond(response)
    else:
        await ctx.respond(f"Mode was invalid or user was not entered.")


@discord_bot.event
async def on_ready():
    discord_bot.relay_channel = discord_bot.get_channel(944252065515962468)
    print(f"Forwarding messages to {discord_bot.relay_channel}")
    discord_bot.disc_loop = get_running_loop()
    await discord_bot.relay_channel.send(f"Connecting to DGG as {dgg_bot.username}")
    dgg_thread.start()
    parse_dgg_thread.start()


@discord_bot.event
async def on_message(disc_msg):
    if (disc_msg.author == discord_bot.user) or (
        disc_msg.channel != discord_bot.relay_channel
    ):
        return
    dgg_bot.send(disc_msg.content)


@dgg_bot.event("on_msg")
def on_dgg_message(dgg_msg):
    if dgg_msg.nick == dgg_bot.username:
        prefix = "S"
    elif dgg_bot.username.lower() in dgg_msg.data.lower():
        prefix = "M"
    elif dgg_bot.filter_level == "whitelist" and dgg_msg.nick in dgg_bot.whitelist:
        prefix = "WL"
    elif dgg_bot.filter_level == "off":
        prefix = "NF"
    else:
        prefix = None

    if prefix:
        dgg_bot.msg_queue.put(
            f"**({prefix}) {dgg_msg.nick}:** {dgg_to_disc(dgg_msg.data)}"
        )


discord_bot.run(getenv("DISC_AUTH"))
