import logging

from discord import Interaction, Guild

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_relay_channel(guild: Guild) -> int:
    relay_channel = None
    for channel in guild.channels:
        if channel.name == "dgg-relay":
            relay_channel = channel.id
            break
    return relay_channel


async def log_reply(ctx: Interaction, response: str, ephemeral=True):
    log = f"From {ctx.user}: {response}"
    if ctx.guild:
        log = f"From {ctx.user} in {ctx.guild.name}: {response}"
    logger.info(log)
    await ctx.response.send_message(response, ephemeral=ephemeral)
