from discord import Option, OptionChoice, Bot, Intents
from discord.ext.commands import Context, has_role
from dggbot import DGGChat, Message
from os import getenv
from threading import Thread
from asyncio import get_running_loop
from pathlib import Path
from queue import Queue
from time import sleep
import json
import re

intents = Intents.default()
intents.members = True

discord_bot = Bot(intents=intents)
dgg_bot = DGGChat()
dgg_msg_queue = Queue()

config_path = Path(__file__).with_name("config.json")
with config_path.open("r") as config_file:
    config = json.loads(config_file.read())

nicks, phrases, emotes = config["nicks"], config["phrases"], config["emotes"]


def dgg_to_disc(msg: Message):
    data = msg.data
    for dgg_emote, disc_emote in emotes.items():
        data = re.sub(rf"\b{dgg_emote}\b", disc_emote, data)
    data = re.sub("[*_`|]", r"\\\g<0>", data)
    if "nsfw" in data.lower():
        data = f"||{data}||"
    return f"**{msg.nick}:** {data}"


def save_config():
    to_json = {"nicks": nicks, "phrases": phrases, "emotes": emotes}
    with config_path.open("w") as config_file:
        json.dump(to_json, config_file, indent=2)


def run_dgg_bot():
    while True:
        dgg_bot.run()
        sleep(5)


def parse_dgg_queue():
    while True:
        msg: Message = dgg_msg_queue.get()
        if msg.nick.lower() in [nick.lower() for nick in nicks.keys()]:
            for channel_id in nicks[msg.nick]:
                if channel := discord_bot.get_channel(channel_id):
                    if "nsfw" not in msg.data.lower():
                        discord_bot.disc_loop.create_task(
                            channel.send(dgg_to_disc(msg))
                        )
                    else:
                        discord_bot.disc_loop.create_task(
                            channel.send(
                                dgg_to_disc(f"**{msg.nick}:** _Censored for nsfw tag_")
                            )
                        )
                else:
                    print(f"Channel {channel_id} wasn't found")
        for phrase in phrases.keys():
            lower_phrase = phrase.lower()
            if re.search(rf"\b{lower_phrase}\b", msg.data.lower()):
                for user_id in phrases[phrase]:
                    if user := discord_bot.get_user(user_id):
                        discord_bot.disc_loop.create_task(user.send(dgg_to_disc(msg)))
                    else:
                        print(f"User {user_id} wasn't found")


dgg_thread = Thread(target=run_dgg_bot)
parse_dgg_queue_thread = Thread(target=parse_dgg_queue)


@has_role("dgg-relay-mod")
@discord_bot.slash_command(name="addemote", description="Add or modify emotes")
async def addemote(
    ctx: Context,
    dgg_version: Option(str, "The emote as used in DGG"),
    discord_version: Option(str, "The emote as used in Discord"),
):
    if ctx.guild.id == 889845466915819551:
        if (not dgg_version) or (not discord_version):
            ctx.respond("One of the parameters was invalid.")
            return
        emotes[dgg_version] = discord_version
        save_config()
        await ctx.respond(f"Translating {dgg_version} to {discord_version}")
    else:
        ctx.respond(
            "Please contact tena#5751 to modify emote translations", ephemeral=True
        )


@has_role("dgg-relay-mod")
@discord_bot.slash_command(
    name="relay",
    description="Add or remove a DGG user whose messages get forwarded to this server",
)
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
        relay_channel = None
        for channel in ctx.guild.channels:
            if channel.name == "dgg-relay":
                relay_channel = channel.id
        if not relay_channel:
            await ctx.respond("Couldn't find this server's dgg-relay channel.")
            return
        if mode == "add":
            if dgg_username not in nicks:
                nicks[dgg_username] = []
            if relay_channel not in nicks[dgg_username]:
                nicks[dgg_username].append(relay_channel)
                response = (
                    f"Messages from '{dgg_username}' will be relayed to this server."
                )
            else:
                response = f"Messages from '{dgg_username}' are already being relayed to this server."
        elif mode == "remove" and relay_channel in nicks[dgg_username]:
            nicks[dgg_username].remove(relay_channel)
            response = f"No longer relaying messages from '{dgg_username}'"
        elif mode == "remove" and relay_channel not in nicks[dgg_username]:
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


@discord_bot.slash_command(
    name="mention",
    description="Add a phrase (usually a username) which will be searched for and messaged to you if it's used in DGG",
)
async def mention(
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
    phrase: Option(
        str,
        "The phrase to search for",
        required=True,
    ),
):
    if mode in ("add", "remove") and phrase:
        disc_user = ctx.author.id
        if mode == "add":
            if phrase not in phrases:
                phrases[phrase] = []
            if disc_user not in phrases[phrase]:
                phrases[phrase].append(disc_user)
                response = f"Mentions of '{phrase}' will be messaged to you."
            else:
                response = f"Mentions of '{phrase}' are already being messaged to you."
        elif mode == "remove" and disc_user in phrases[phrase]:
            phrases[phrase].remove(disc_user)
            response = f"No longer relaying mentions of '{phrase}'"
        elif mode == "remove" and disc_user not in phrases[phrase]:
            await ctx.respond(
                f"You can't remove a phrase that isn't being forwarded to you.",
                ephemeral=True,
            )
            return
        if not phrases[phrase]:
            phrases.pop(phrase)
        save_config()
        await ctx.respond(response, ephemeral=True)
    else:
        await ctx.respond(f"Mode or phrase was invalid.", ephemeral=True)


@relay.error
async def relay_error(ctx, error):
    await ctx.send(f"Error: {error}")


@discord_bot.event
async def on_ready():
    discord_bot.disc_loop = get_running_loop()
    dgg_thread.start()
    parse_dgg_queue_thread.start()
    print("Starting")


@dgg_bot.event("on_msg")
def on_dgg_message(dgg_msg):
    dgg_msg_queue.put(dgg_msg)


if __name__ == "__main__":
    discord_bot.run(getenv("DISC_AUTH"))
