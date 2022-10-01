from dggbot import DGGBot, Message
from discord.ext.commands import Context
from discord import Option
from threading import Thread
from queue import Queue
from os import getenv
from asyncio import get_running_loop
import sys
import re

from config import nicks, phrases, modes
from relay_logger import logger
from discord_bot import discord_bot, dgg_to_disc

sys.tracebacklimit = 3


dgg_bot = DGGBot(getenv("DGG_AUTH"))
dgg_msg_queue = Queue()


@discord_bot.event
async def on_ready():
    discord_bot.disc_loop = get_running_loop()
    discord_bot.tena = discord_bot.get_user(504613278769479681)
    dgg_thread.start()
    parse_dgg_queue_thread.start()


@discord_bot.slash_command(name="send")
async def tena_send(
    ctx: Context,
    message: Option(
        str,
        "The message to send",
        required=True,
    ),
):
    if ctx.author.id == discord_bot.tena.id:
        logger.debug(f"Sending message from tena: {message}")
        dgg_bot.send(message)
        await ctx.respond(f"Message sent: {message}", ephemeral=True)
    else:
        logger.info(f"{ctx.author.id} tried to use send command")
        await ctx.respond(
            "Only my creator tena can use this command :)", ephemeral=True
        )


@discord_bot.slash_command(name="whisper")
async def tena_whisper(
    ctx: Context,
    user: Option(
        str,
        "The user to whisper",
        required=True,
    ),
    message: Option(
        str,
        "The message to whisper",
        required=True,
    ),
):
    if ctx.author.id == discord_bot.tena.id:
        logger.debug(f"Sending whisper from tena: {message}")
        dgg_bot.send_privmsg(user, message)
        await ctx.respond(f"Message sent to {user}: {message}", ephemeral=True)
    else:
        logger.info(f"{ctx.author.id} tried to use whisper command")
        await ctx.respond(
            "Only my creator tena can use this command :)", ephemeral=True
        )


def run_dgg_bot():
    """Thread that runs the DGG bot"""
    while True:
        logger.debug("Starting DGG bot")
        dgg_bot.run()


def parse_dgg_queue():
    """Thread that distributes DGG messages to Discord"""
    while True:
        msg: Message = dgg_msg_queue.get()
        if msg.nick.lower() in [nick.lower() for nick in nicks.keys()]:
            for channel_id in nicks[msg.nick]:
                if channel := discord_bot.get_channel(channel_id):
                    if (
                        "nsfw" in msg.data.lower() or "nsfl" in msg.data.lower()
                    ) and not channel.is_nsfw():
                        discord_bot.disc_loop.create_task(
                            channel.send(f"**{msg.nick}:** _Censored for nsfw tag_")
                        )
                    else:
                        discord_bot.disc_loop.create_task(
                            channel.send(dgg_to_disc(msg.nick, msg.data))
                        )
                    logger.debug(f"Relayed to channel {channel.id}")
                else:
                    logger.warning(f"Channel {channel_id} wasn't found")
        for phrase in phrases.keys():
            lower_phrase = phrase.lower()
            if re.search(rf"\b{lower_phrase}\b", msg.data.lower()):
                for user_id in phrases[phrase]:
                    if user := discord_bot.get_user(user_id):
                        if (
                            modes[user_id] == "auto"
                            and lower_phrase not in dgg_bot.users.keys()
                            or modes[user_id] == "on"
                        ):
                            discord_bot.disc_loop.create_task(
                                user.send(dgg_to_disc(msg.nick, msg.data))
                            )
                        logger.debug(f"Relayed to user {user}")
                    else:
                        logger.warning(f"User {user_id} wasn't found")


dgg_thread = Thread(target=run_dgg_bot)
parse_dgg_queue_thread = Thread(target=parse_dgg_queue)


@dgg_bot.event("on_msg")
def on_dgg_message(dgg_msg):
    dgg_msg_queue.put(dgg_msg)


@dgg_bot.event("on_privmsg")
def on_dgg_whisper(dgg_whisper):
    logger.debug(f"Forwarding whisper to tena: {dgg_whisper.nick}: {dgg_whisper.data}")
    discord_bot.disc_loop.create_task(
        discord_bot.tena.send(f"W {dgg_to_disc(dgg_whisper.nick, dgg_whisper.data)}")
    )


if __name__ == "__main__":
    logger.info("Starting Discord bot")
    discord_bot.run(getenv("DISC_AUTH"))
