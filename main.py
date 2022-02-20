from dggbot import DGGBot, Message
from os import getenv
from time import sleep
from threading import Thread
from asyncio import get_running_loop, create_task
from pathlib import Path
import json
import discord
from discord import Option, OptionChoice

discord_bot = discord.Bot()

config_path = Path(__file__).with_name("config.json")
with config_path.open("r") as config_file:
    config = json.loads(config_file.read())


dgg_bot = DGGBot(auth_token=getenv("DGG_AUTH"),
                 username="TenaReturns", owner="Fritz")
dgg_bot.filter_level = "whitelist"
dgg_thread = Thread(target=dgg_bot.run)


def relay_send(payload: str):
    discord_bot.disc_loop.create_task(discord_bot.relay_channel.send(payload))


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
        await ctx.respond(f"Changed the filter level to '{level}'")
    else:
        await ctx.respond(f"'{level}' isn't a valid filter level")


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
            config["whitelist"].append(user)
        elif mode == "remove" and user in config["whitelist"]:
            config["whitelist"].remove(user)
        elif mode == "remove" and user not in config["whitelist"]:
            await ctx.respond(f"'{user}' was not found in the whitelist.")
            return
        to_json = {"whitelist": config["whitelist"]}
        with config_path.open("w") as config_file:
            json.dump(to_json, config_file)
        await ctx.respond(
            f"'{user}' was {'added' if mode == 'add' else 'removed'} {'to' if mode == 'add' else 'from'} the whitelist."
        )
    else:
        await ctx.respond(f"Mode was invalid or user was not entered.")


@discord_bot.event
async def on_ready():
    discord_bot.relay_channel = discord_bot.get_channel(944252065515962468)
    print(f"Forwarding messages to {discord_bot.relay_channel}")
    discord_bot.disc_loop = get_running_loop()
    await discord_bot.relay_channel.send(f"Connecting to DGG as {dgg_bot.username}")
    dgg_thread.start()


@discord_bot.event
async def on_message(disc_msg):
    if (disc_msg.author == discord_bot.user) or (
        disc_msg.channel != discord_bot.relay_channel
    ):
        return
    dgg_bot.send(disc_msg.content)


# Always forward messages if they mention the bot
@dgg_bot.event("on_mention")
def on_dgg_mention(dgg_msg):
    relay_send(f"**(M) {dgg_msg.nick}:**: {dgg_msg.data}")


@dgg_bot.event("on_msg")
def on_dgg_message(dgg_msg):
    if dgg_bot.filter_level == "mention" or "tenareturns" in dgg_msg.data.lower():
        return
    elif dgg_bot.filter_level == "whitelist" and dgg_msg.nick in config["whitelist"]:
        relay_send(f"**(WL) {dgg_msg.nick}:**: {dgg_msg.data}")
    elif dgg_bot.filter_level == "off":
        relay_send(f"**(NF) {dgg_msg.nick}:**: {dgg_msg.data}")


discord_bot.run(getenv("DISC_AUTH"))
