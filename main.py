from discord import Option, OptionChoice, Bot
from dggbot import DGGBot, Message
from discord.ext.commands import Context, has_permissions, has_role
from os import getenv
from threading import Thread
from asyncio import get_running_loop
from pathlib import Path
from queue import Queue
from time import sleep
import json
import re


discord_bot = Bot()
dgg_bot = DGGBot(None)
dgg_msg_queue = Queue()

config_path = Path(__file__).with_name("config.json")
with config_path.open("r") as config_file:
    config = json.loads(config_file.read())

nicks, phrases, emotes = config["nicks"], config["phrases"], config["emotes"]


def run_dgg_bot():
    while True:
        dgg_bot.run()
        sleep(5)


def parse_dgg_queue():
    while True:
        sleep(5)


dgg_thread = Thread(target=run_dgg_bot)
parse_dgg_queue_thread = Thread(target=parse_dgg_queue)


def save_config():
    to_json = {"nicks": nicks, "phrases": phrases, "emotes": emotes}
    with config_path.open("w") as config_file:
        json.dump(to_json, config_file, indent=2)


def dgg_to_disc(msg: Message):
    for dgg_emote, disc_emote in emotes.items():
        data = re.sub(rf"\b{dgg_emote}\b", disc_emote, msg.data)
    data = re.sub("[*_`]", r"\\\g<0>", data)
    if "nsfw" in data:
        data = f"NSFW ||{data}||"
    return f"{msg.nick}: {data}"


@discord_bot.slash_command(
    guild_ids=discord_bot.guilds,
    name="addemote",
    description="Add or modify emotes",
)
@has_role("dgg-relay-mod")
async def addemote(
    ctx: Context,
    dgg_version: Option(str, "The emote as used in DGG"),
    discord_version: Option(str, "The emote as used in Discord"),
):
    if (not dgg_version) or (not discord_version):
        ctx.respond("One of the parameters was invalid.")
        return
    emotes[dgg_version] = discord_version
    save_config()
    await ctx.respond(f"Translating {dgg_version} to {discord_version}", ephemeral=True)


@discord_bot.slash_command(
    guild_ids=discord_bot.guilds,
    name="relay",
    description="Add or remove a DGG user whose messages get forwarded to this server",
)
@has_role("dgg-relay-mod")
async def relay(
    ctx: Context,
    mode: Option(
        str,
        "Choose add or remove mode",
        required=True,
        choices=(
            OptionChoice(name="add", value="add"),
            OptionChoice(name="remove", value="remove"),
        ),
    ),
    dgg_username: Option(
        str,
        "The DGG username to add/remove",
        required=True,
    ),
):
    if mode in ("add", "remove") and dgg_username:
        guild = ctx.guild.id
        if mode == "add":
            if not nicks[dgg_username]:
                nicks[dgg_username] = []
            if guild not in nicks[dgg_username]:
                nicks[dgg_username].append(guild)
                response = (
                    f"Messages from '{dgg_username}' will be relayed to this server."
                )
            else:
                response = f"Messages from '{dgg_username}' are already being relayed to this server."
        elif mode == "remove" and guild in nicks[dgg_username]:
            nicks[dgg_username].remove(dgg_username)
            response = f"No longer relaying messages from '{dgg_username}'"
        elif mode == "remove" and guild not in nicks[dgg_username]:
            await ctx.respond(
                f"Messages from {dgg_username} aren't being relayed to this server."
            )
            return
        if not nicks[dgg_username]:
            nicks.pop(dgg_username)
        save_config()
        await ctx.respond(response)
    else:
        await ctx.respond(f"Mode was invalid or user was not entered.")


@discord_bot.event
async def on_ready():
    discord_bot.relay_channels = []
    for guild in discord_bot.guilds:
        for channel in guild.channels:
            print(channel.name)
            if channel.name == "dgg-relay" and channel.nsfw:
                discord_bot.relay_channels.append(channel)
    print(f"Forwarding messages to {discord_bot.relay_channels}")
    discord_bot.disc_loop = get_running_loop()
    for channel in discord_bot.relay_channels:
        await channel.send(f"Connecting to DGG")
    dgg_thread.start()
    parse_dgg_queue_thread.start()


@dgg_bot.event("on_msg")
def on_dgg_message(dgg_msg):
    dgg_msg_queue.put(dgg_msg)


if __name__ == "__main__":
    discord_bot.run(getenv("DISC_AUTH"))
