from dggbot import DGGBot
from dggbot import Message as DGGMessage
from discord.ext.commands import Context
from discord.commands.context import ApplicationContext
from discord import Option, OptionChoice
from discord import Message as DiscMessage
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


@discord_bot.event
async def on_message(msg: DiscMessage):
    if (ref := msg.reference) and (msg.author.id == discord_bot.tena.id):
        ref_msg: DiscMessage = await msg.channel.fetch_message(ref.message_id)
        if ref_msg.author.id == discord_bot.user.id:
            if whisper_re := re.match(r"W \*\*(\w+):\*\*.+", ref_msg.content):
                logger.debug(f"Sending a whisper in reply to {ref_msg.content}")
                await tena_whisper(ctx=msg, user=whisper_re[1], message=msg.content)
                await msg.add_reaction(emoji="✅")
            elif chat_re := re.match(r"\*\*(\w+):\*\*.+", ref_msg.content):
                logger.debug(f"Sending a chat message in reply to {ref_msg.content}")
                await tena_send(ctx=msg, message=f"{chat_re[1]} {msg.content}")
                await msg.add_reaction(emoji="☑")


@discord_bot.slash_command(name="send")
async def tena_send(
    ctx: ApplicationContext,
    message: Option(
        str,
        "The message to send",
        required=True,
    ),
):
    print(type(ctx))
    if ctx.author.id == discord_bot.tena.id:
        logger.debug(f"Sending message from tena: {message}")
        dgg_bot.send(message)
        response = f"Message sent {dgg_to_disc('tena', message)}"
        if isinstance(ctx, ApplicationContext):
            await ctx.respond(response, ephemeral=True)
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
        logger.debug(f"Sending whisper from tena to {user}: {message}")
        dgg_bot.send_privmsg(user, message)
        response = f"Message sent to {dgg_to_disc(user, message)}"
        if isinstance(ctx, Context):
            await ctx.respond(response, ephemeral=True)
    else:
        logger.info(f"{ctx.author.id} tried to use whisper command")
        await ctx.respond(
            "Only my creator tena can use this command :)", ephemeral=True
        )


@discord_bot.slash_command(name="loglevel")
async def loglevel(
    ctx: Context,
    level: Option(
        str,
        "Choose logger level",
        required=True,
        choices=(
            OptionChoice(name="warning", value="30"),
            OptionChoice(name="info", value="20"),
            OptionChoice(name="debug", value="10"),
        ),
    ),
):
    if ctx.author.id == discord_bot.tena.id:
        logger.setLevel(int(level))
        response = f"Set logging level to {logger.level}"
        logger.info(response)
        await ctx.respond(response, ephemeral=True)
    else:
        logger.info(f"{ctx.author.id} tried to use loglevel command")
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
        msg: DGGMessage = dgg_msg_queue.get()
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
                    logger.debug(
                        f"Relayed '{msg.nick}: {msg.data}' to channel {channel.id}"
                    )
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
                            logger.debug(f"Relayed '{msg.nick}: {msg.data}' to {user}")
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
