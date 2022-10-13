from discord import Option, OptionChoice, Bot, Intents
from discord.ext.commands import Context, has_role
from time import sleep
from datetime import datetime
import tldextract
import requests
import re

from relay_logger import logger
from config import nicks, phrases, emotes, modes, save_config

intents = Intents.default()
intents.members = True
intents.messages = True

discord_bot = Bot(intents=intents)


def dgg_to_disc(dgg_nick: str, dgg_txt: str):
    """Converts DGG emotes/links to Discord ones"""
    for link in set(
        re.findall(r"(?:(?:https?|ftp):\/\/)?[\w/\-?=%.]+\.[\w/\-&?=%.]+", dgg_txt)
    ):
        url = tldextract.extract(link)
        if url.domain and url.suffix:
            if not re.search(r"\Ahttps?://", link):
                dgg_txt = dgg_txt.replace(link, f"https://{link}")
                link = f"https://{link}"
    disc_txt = []
    for part in dgg_txt.split():
        if not part.startswith("http"):
            for dgg_emote, disc_emote in emotes.items():
                part = re.sub(rf"\b{dgg_emote}\b", disc_emote, part)
            part = re.sub("[*_`|]", r"\\\g<0>", part)
        disc_txt.append(part)
    disc_txt = " ".join(disc_txt)
    dgg_nick = re.sub("[*_`|]", r"\\\g<0>", dgg_nick)
    if any([tag in disc_txt.lower() for tag in ("nsfw", "nsfl")]):
        disc_txt = f"||{disc_txt}||"
    return f"**{dgg_nick}:** {disc_txt}"


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
        logger.info(f"Emote {dgg_version} added as {discord_version}")
        await ctx.respond(f"Translating {dgg_version} to {discord_version}")
    else:
        await ctx.respond("Please contact tena#5751 to modify emotes", ephemeral=True)


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
                break
        if not relay_channel:
            await ctx.respond("Couldn't find this server's dgg-relay channel.")
            return
        if dgg_username not in nicks:
            nicks[dgg_username] = []
            logger.info(f'Added new relay list "{dgg_username}"')
        if mode == "add":
            if relay_channel not in nicks[dgg_username]:
                nicks[dgg_username].append(relay_channel)
                logger.info(
                    f'Added relay "{dgg_username}" for server "{ctx.guild.name}"'
                )
                response = (
                    f"Messages from '{dgg_username}' will be relayed to this server."
                )
            else:
                response = f"Messages from '{dgg_username}' are already being relayed to this server."
        elif mode == "remove" and relay_channel in nicks[dgg_username]:
            nicks[dgg_username].remove(relay_channel)
            logger.info(
                f'Removed relay "{dgg_username}" from server "{ctx.guild.name}"'
            )
            response = f"No longer relaying messages from '{dgg_username}'"
        elif mode == "remove" and relay_channel not in nicks[dgg_username]:
            await ctx.respond(
                f"Messages from {dgg_username} aren't being relayed to this server."
            )
            return
        if not nicks[dgg_username]:
            nicks.pop(dgg_username)
            logger.info(f'Removed empty relay list for "{dgg_username}"')
        save_config()
        await ctx.respond(response)
    else:
        await ctx.respond(f"Mode was invalid or user was not entered.")


@discord_bot.slash_command(
    name="phrase",
    description="Add a phrase (usually a username) which will be searched for and messaged to you if it's used in DGG",
)
async def phrase(
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
        if disc_user not in modes.keys():
            modes[disc_user] = "on"
            logger.info(f"Added new user {disc_user} to modes list")
        if phrase not in phrases:
            phrases[phrase] = []
            logger.info(f'Added new phrase list for "{phrase}"')
        if mode == "add":
            if disc_user not in phrases[phrase]:
                phrases[phrase].append(disc_user)
                logger.info(f'Appended "{disc_user}" to phrase list "{phrase}"')
                response = f"Mentions of '{phrase}' will be messaged to you."
            else:
                response = f"Mentions of '{phrase}' are already being messaged to you."
        elif mode == "remove" and disc_user in phrases[phrase]:
            phrases[phrase].remove(disc_user)
            logger.info(f'Removed "{disc_user}" from phrase list "{phrase}"')
            response = f"No longer relaying mentions of '{phrase}'"
        elif mode == "remove" and disc_user not in phrases[phrase]:
            await ctx.respond(
                f"You can't remove a phrase that isn't being forwarded to you.",
                ephemeral=True,
            )
            return
        if not phrases[phrase]:
            phrases.pop(phrase)
            logger.info(f'Removed empty phrase list "{phrase}"')
        save_config()
        await ctx.respond(response, ephemeral=True)
    else:
        await ctx.respond(f"Mode or phrase was invalid.", ephemeral=True)


@discord_bot.slash_command(
    name="phrasemode",
    description="Enable or disable mentions forwarded through DMs. Default is 'on'",
)
async def phrasemode(
    ctx: Context,
    mode: Option(
        str,
        "Select a mode",
        choices=(
            OptionChoice(name="on", value="on"),
            OptionChoice(name="off", value="off"),
            OptionChoice(name="auto", value="auto"),
        ),
    ),
):
    if mode in ("on", "off", "auto"):
        modes[ctx.author.id] = mode
        save_config()
        logger.info(f'Phrase mode for "{ctx.author.id}" set to "{mode}"')
        await ctx.respond(f"Phrase mode set to {mode}", ephemeral=True)
    else:
        await ctx.respond("Invalid parameter", ephemeral=True)


@discord_bot.slash_command(
    name="stalk",
    description="Return the last couple DGG messages of a chatter. Max 100 messages (credit to Polecat)",
)
async def stalk(
    ctx: Context,
    user: Option(
        str,
        "The username to stalk",
        required=True,
    ),
    amount: Option(
        int, "The amount of messages to return", min_value=1, max_value=100, default=3
    ),
):
    if messages_json := requests.get(
        f"https://polecat.me/api/stalk/{user}?size={amount}"
    ).json():
        responses = []
        response = ""
        for message in messages_json:
            time = datetime.fromtimestamp(int(message["date"] / 1000) - 14400)
            timestamp = time.strftime("[%m-%d %H:%M EST]")
            line = f'{timestamp} {dgg_to_disc(message["nick"], message["text"])}\n'
            if len(response) + len(line) <= 2000:
                response += line
            else:
                responses.append(response)
                response = line
        responses.append(response)
        for response in responses:
            await ctx.respond(response, ephemeral=True)
            sleep(0.5)
    else:
        await ctx.respond(f"No recent messages by '{user}'", ephemeral=True)


@discord_bot.slash_command(
    name="mentions",
    description="Return the last couple mentions of a DGG chatter. Max 100 messages (credit to Polecat)",
)
async def mentions(
    ctx: Context,
    user: Option(
        str,
        "The username to stalk",
        required=True,
    ),
    amount: Option(
        int, "The amount of messages to return", min_value=1, max_value=100, default=3
    ),
):
    if messages_json := requests.get(
        f"https://polecat.me/api/mentions/{user}?size={amount}"
    ).json():
        responses = []
        response = ""
        for message in messages_json:
            time = datetime.fromtimestamp(int(message["date"] / 1000) - 14400)
            timestamp = time.strftime("[%m-%d %H:%M EST]")
            line = f'{timestamp} {dgg_to_disc(message["nick"], message["text"])}\n'
            if len(response) + len(line) <= 2000:
                response += line
            else:
                responses.append(response)
                response = line
        responses.append(response)
        for response in responses:
            await ctx.respond(response, ephemeral=True)
            sleep(0.5)
    else:
        await ctx.respond(f"No recent mentions of '{user}'", ephemeral=True)


@relay.error
async def relay_error(ctx, error):
    logger.error(f'Error: "{error}"')
    await ctx.send(f"Error: {error}")
