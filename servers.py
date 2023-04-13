from helpers import logger, log_reply, get_relay_channel

from discord.ext.commands import GroupCog, Bot
from discord import Interaction, app_commands, Role


class ServerBaseCog(GroupCog):
    """Base GroupCog for server commands"""

    def __init__(self, bot: Bot):
        self.bot = bot

    async def interaction_check(self, ctx: Interaction) -> bool:
        err = None
        if not ctx.guild:
            err = "**Error:** This command is only usable in servers"
        elif not get_relay_channel(ctx.guild):
            err = f"**Error:** No '#dgg-relay' channel found in '{ctx.guild.name}'"
        elif "dgg-relay-mod" not in (role.name for role in ctx.user.roles):
            err = "**Error:** This command requires the 'dgg-relay-mod' role"
        if err:
            await log_reply(ctx, err)
            return False
        return True


class RelayCog(ServerBaseCog, group_name="relay"):
    """Cog for all of the /relay commands"""

    @app_commands.command(name="add")
    @app_commands.describe(dgg_username="The DGG user you want to relay messages from")
    async def relay_add(self, ctx: Interaction, dgg_username: str):
        """Add a DGG user whose messages get forwarded to this server (case sensitive!)"""
        relay_channel = get_relay_channel(ctx.guild)
        if dgg_username not in self.bot.relays:
            self.bot.relays[dgg_username] = []
            logger.info(f"Added new relay list '{dgg_username}'")
        if relay_channel not in self.bot.relays[dgg_username]:
            self.bot.relays[dgg_username].append(relay_channel)
            response = (
                f"Messages from '{dgg_username}' will be relayed to '{ctx.guild.name}'"
            )
        else:
            response = f"**Error:** '{dgg_username}' is already being relayed to '{ctx.guild.name}'"
        self.bot.save_cfg()
        await log_reply(ctx, response, ephemeral=False)

    @app_commands.command(name="remove")
    @app_commands.describe(dgg_username="The DGG user you want to stop relaying")
    async def relay_remove(self, ctx: Interaction, dgg_username: str):
        """Remove a DGG user's relay from this server"""
        relay_channel = get_relay_channel(ctx)
        response = None
        if dgg_username in self.bot.relays.keys():
            if relay_channel in self.bot.relays[dgg_username]:
                self.bot.relays[dgg_username].remove(relay_channel)
                response = f"Removed '{dgg_username}' relay from '{ctx.guild.name}'"
                if not self.bot.relays[dgg_username]:
                    self.bot.relays.pop(dgg_username)
                    logger.info(f"Removed empty relay list for '{dgg_username}'")
                self.bot.save_cfg()
        if not response:
            response = (
                f"**Error:** '{dgg_username}' isn't being relayed to '{ctx.guild.name}'"
                " (try the '/relay list' command)"
            )

        await log_reply(ctx, response, ephemeral=False)

    @app_commands.command(name="list")
    async def relay_list(self, ctx: Interaction):
        """Lists DGG users currently being relayed to this server."""
        relay_channel = get_relay_channel(ctx)
        relays = []
        for nickname in self.bot.relays:
            for channel in self.bot.relays[nickname]:
                if channel == relay_channel:
                    relays.append(nickname)
        relays = "', '".join(relays)
        response = f"This server gets messages from: '{relays}'"
        if not relays:
            response = "No relays are active for this server."
        await log_reply(ctx, response, ephemeral=False)


class LiveNotifCog(ServerBaseCog, group_name="live-notifications"):
    """Cog for all of the /live-notifications commands"""

    @app_commands.command(name="on")
    async def live_notifications_on(self, ctx: Interaction):
        """Enable live notifications for this server"""
        relay_channel = await get_relay_channel(ctx)
        if relay_channel not in self.bot.live["channels"].keys():
            self.bot.live["channels"][relay_channel] = {"role": None}
        self.bot.live["channels"][relay_channel]["enabled"] = True
        self.bot.save_cfg()
        response = f"Live notifications enabled for {ctx.guild.name}"
        await log_reply(ctx, response, ephemeral=False)

    @app_commands.command(name="off")
    async def live_notifications_off(self, ctx: Interaction):
        """Disable live notifications for this server"""
        relay_channel = await get_relay_channel(ctx)
        if relay_channel not in self.bot.live["channels"].keys():
            self.bot.live["channels"][relay_channel] = {"role": None}
        self.bot.live["channels"][relay_channel]["enabled"] = False
        self.bot.save_cfg()
        response = f"Live notifications disabled for {ctx.guild.name}"
        await log_reply(ctx, response, ephemeral=False)

    @app_commands.command(name="role")
    @app_commands.describe(role="The role that will be pinged")
    async def live_notifications_role(self, ctx: Interaction, role: Role):
        """Set a role that gets pinged for live notifications"""
        relay_channel = await get_relay_channel(ctx)
        if relay_channel not in self.bot.live["channels"].keys():
            self.bot.live["channels"][relay_channel] = {"enabled": True}
        self.bot.live["channels"][relay_channel]["role"] = role.id
        self.bot.save_cfg()
        response = (
            f'"<@&{role.id}>" will be pinged for live notifications in {ctx.guild.name}'
        )
        await log_reply(ctx, response, ephemeral=False)
