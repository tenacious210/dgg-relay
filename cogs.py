import logging
import json

from discord import Interaction, app_commands, Role
from discord.app_commands import Choice
from discord.ext.commands import Bot, Cog

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

with open("config.json") as cfg_json:
    cfg = json.loads(cfg_json.read())

owner_id = cfg["owner_id"]


async def log_reply(ctx: Interaction, response: str, ephemeral=True):
    log = f"From {ctx.user}: {response}"
    if ctx.guild:
        log = f"From {ctx.user} in {ctx.guild.name}: {response}"
    logger.info(log)
    await ctx.response.send_message(response, ephemeral=ephemeral)


async def is_owner(ctx: Interaction) -> bool:
    if ctx.user.id != owner_id:
        await log_reply(ctx, f"**Error:** Only my owner can use this command")
        return False
    return True


class CommandError(Exception):
    def __init__(self, msg: str):
        self.msg = msg
        super().__init__(msg)

    @classmethod
    async def send_err(cls, ctx: Interaction, msg: str):
        self = cls(msg)
        await log_reply(ctx, self.msg)
        return self


class OwnerCog(Cog):
    """Commands that can only be used by the bot's owner"""

    def __init__(self, bot: Bot):
        self.bot = bot

    @app_commands.command(name="sync")
    @app_commands.check(is_owner)
    async def sync_commands(self, ctx: Interaction):
        """(Owner only) Syncs app command info with Discord"""
        await self.bot.tree.sync()
        await log_reply(ctx, "Synced command tree with Discord")

    emote = app_commands.Group(
        name="emote",
        description=("(Owner only) Modify DGG emote translations"),
    )

    @emote.command(name="add")
    @app_commands.describe(
        dgg_version="The emote as it's used in DGG",
        disc_version="The emote as it's used in Discord",
    )
    @app_commands.check(is_owner)
    async def add_emote(self, ctx: Interaction, dgg_version: str, disc_version: str):
        """(Owner only) Add or modify a DGG emote translation"""
        self.bot.emotes[dgg_version] = disc_version
        self.bot.save_cfg()
        await log_reply(ctx, f"Translating {dgg_version} to {str(disc_version)}")

    @emote.command(name="remove")
    @app_commands.describe(dgg_version="The emote to remove (in DGG format)")
    @app_commands.check(is_owner)
    async def remove_emote(self, ctx: Interaction, dgg_version: str):
        """(Owner only) Remove a DGG emote translation"""
        if dgg_version in self.bot.emotes.keys():
            removed_emote = self.bot.emotes.pop(dgg_version)
            self.bot.save_cfg()
            await log_reply(ctx, f"Removed {removed_emote} from emotes")
        else:
            await log_reply(ctx, f"Couldn't find emote {dgg_version}")

    config = app_commands.Group(
        name="config",
        description=("(Owner only) Modify the bot's config file"),
    )

    @config.command(name="remove")
    @app_commands.choices(
        mode=[
            Choice(name="phrase", value="phrase"),
            Choice(name="relay", value="relay"),
        ]
    )
    @app_commands.check(is_owner)
    async def config_remove(self, ctx: Interaction, mode: str, value: str):
        """Remove a relay or phrase from the config file"""
        if mode == "phrase" and value in self.bot.phrases:
            del self.bot.phrases[value]
            self.bot.save_cfg()
            await log_reply(ctx, f"Removed '{value}' from phrases", ephemeral=False)
        elif mode == "relay" and value in self.bot.relays:
            del self.bot.relays[value]
            self.bot.save_cfg()
            await log_reply(ctx, f"Removed '{value}' from relays", ephemeral=False)
        else:
            await log_reply(ctx, f"Couldn't find '{value}' in {mode}s")


class PublicCog(Cog):
    """Commands that can be used by anybody"""

    def __init__(self, bot: Bot):
        self.bot = bot

    async def get_relay_channel(self, ctx: Interaction) -> int:
        if not ctx.guild:
            err = "**Error:** This command is only usable in servers"
            raise await CommandError(err).send_err(ctx, err)
        if "dgg-relay-mod" not in (role.name for role in ctx.user.roles):
            err = "**Error:** This command requires the 'dgg-relay-mod' role"
            raise await CommandError(err).send_err(ctx, err)
        relay_channel = None
        for channel in ctx.guild.channels:
            if channel.name == "dgg-relay":
                relay_channel = channel.id
                break
        if not relay_channel:
            err = f"**Error:** No '#dgg-relay' channel found in '{ctx.guild.name}'"
            raise await CommandError(err).send_err(ctx, err)
        return relay_channel

    relay = app_commands.Group(
        name="relay",
        description="Relays DGG messages to servers",
    )

    @relay.command(name="add")
    @app_commands.describe(dgg_username="The DGG user you want to relay messages from")
    async def relay_add(self, ctx: Interaction, dgg_username: str):
        """Add a DGG user whose messages get forwarded to this server (case sensitive!)"""
        relay_channel = await self.get_relay_channel(ctx)
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

    @relay.command(name="remove")
    @app_commands.describe(dgg_username="The DGG user you want to stop relaying")
    async def relay_remove(self, ctx: Interaction, dgg_username: str):
        """Remove a DGG user's relay from this server"""
        relay_channel = await self.get_relay_channel(ctx)
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

    @relay.command(name="list")
    async def relay_list(self, ctx: Interaction):
        """Lists DGG users currently being relayed to this server."""
        relay_channel = await self.get_relay_channel(ctx)
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

    live_notifications = app_commands.Group(
        name="live-notifications",
        description="Configure live notifications for Destiny",
    )

    @live_notifications.command(name="on")
    async def live_notifications_on(self, ctx: Interaction):
        """Enable live notifications for this server"""
        relay_channel = await self.get_relay_channel(ctx)
        if relay_channel not in self.bot.live["channels"].keys():
            self.bot.live["channels"][relay_channel] = {"role": None}
        self.bot.live["channels"][relay_channel]["enabled"] = True
        self.bot.save_cfg()
        response = f"Live notifications enabled for {ctx.guild.name}"
        await log_reply(ctx, response, ephemeral=False)

    @live_notifications.command(name="off")
    async def live_notifications_off(self, ctx: Interaction):
        """Disable live notifications for this server"""
        relay_channel = await self.get_relay_channel(ctx)
        if relay_channel not in self.bot.live["channels"].keys():
            self.bot.live["channels"][relay_channel] = {"role": None}
        self.bot.live["channels"][relay_channel]["enabled"] = False
        self.bot.save_cfg()
        response = f"Live notifications disabled for {ctx.guild.name}"
        await log_reply(ctx, response, ephemeral=False)

    @live_notifications.command(name="role")
    @app_commands.describe(role="The role that will be pinged")
    async def live_notifications_role(self, ctx: Interaction, role: Role):
        """Set a role that gets pinged for live notifications"""
        relay_channel = await self.get_relay_channel(ctx)
        if relay_channel not in self.bot.live["channels"].keys():
            self.bot.live["channels"][relay_channel] = {"enabled": True}
        self.bot.live["channels"][relay_channel]["role"] = role.id
        self.bot.save_cfg()
        response = (
            f'"<@&{role.id}>" will be pinged for live notifications in {ctx.guild.name}'
        )
        await log_reply(ctx, response, ephemeral=False)

    def check_prefs(self, disc_user):
        if disc_user not in self.bot.user_prefs.keys():
            self.bot.user_prefs[disc_user] = {"detect_presence": False, "ignores": []}
            logger.info(f"Added new user '{disc_user}' to preferences list")

    phrase = app_commands.Group(
        name="phrase",
        description="Relays DGG messages to users",
    )

    @phrase.command(name="add")
    @app_commands.describe(
        phrase="The phrase you want forwarded to you (most likely your DGG username)"
    )
    async def phrase_add(self, ctx: Interaction, phrase: str):
        """Add a phrase (usually a username) that will be forwarded
        to you when it's used in DGG (case insensitive)"""
        self.check_prefs(ctx.user.id)
        if phrase not in self.bot.phrases:
            self.bot.phrases[phrase] = []
            logger.info(f"Added new phrase list for '{phrase}'")
        if ctx.user.id not in self.bot.phrases[phrase]:
            self.bot.phrases[phrase].append(ctx.user.id)
            response = f"Forwarding '{phrase}' to {ctx.user}"
        else:
            response = f"**Error:** '{phrase}' is already being forwarded to {ctx.user}"
        self.bot.save_cfg()
        await log_reply(ctx, response)

    @phrase.command(name="remove")
    @app_commands.describe(phrase="The phrase you want to stop being forwarded")
    async def phrase_remove(self, ctx: Interaction, phrase: str):
        """Stop a phrase from being forwarded to you"""
        self.check_prefs(ctx.user.id)
        response = None
        if phrase in self.bot.phrases:
            if ctx.user.id in self.bot.phrases[phrase]:
                self.bot.phrases[phrase].remove(ctx.user.id)
                response = f"No longer forwarding '{phrase}' to {ctx.user}"
                if not self.bot.phrases[phrase]:
                    self.bot.phrases.pop(phrase)
                    logger.info(f"Removed empty phrase list '{phrase}'")
                self.bot.save_cfg()
        if not response:
            response = (
                f"**Error:** '{phrase}' isn't being forwarded to {ctx.user}"
                " (try the '/phrase list' command)"
            )
        await log_reply(ctx, response)

    @phrase.command(name="list")
    async def phrase_list(self, ctx: Interaction):
        """List the phrases currently being forwarded to you"""
        disc_user = ctx.user.id
        user_phrases = []
        for phrase in self.bot.phrases:
            for user_id in self.bot.phrases[phrase]:
                if user_id == disc_user:
                    user_phrases.append(phrase)
        user_phrases = "', '".join(user_phrases)
        response = f"Your phrases: '{user_phrases}'"
        if not user_phrases:
            response = "No phrases are being forwarded to you."
        await log_reply(ctx, response)

    @phrase.command(name="detect-dgg-presence")
    @app_commands.describe(mode="Set to True to detect DGG presence. Default is False.")
    async def detect_dgg_presence(self, ctx: Interaction, mode: bool):
        """Change behavior of the /phrase command by controlling when the bot messages you."""
        self.check_prefs(ctx.user.id)
        self.bot.user_prefs[ctx.user.id]["detect_presence"] = mode
        self.bot.save_cfg()
        word = "enabled" if mode else "disabled"
        response = f"Presence detection {word} for {ctx.user.name}"
        await log_reply(ctx, response)

    ignore = app_commands.Group(
        name="ignore",
        description="Configure your DGG Relay ignore list",
    )

    @ignore.command(name="add")
    @app_commands.describe(dgg_username="The user in DGG you want to ignore")
    async def add_ignore(self, ctx: Interaction, dgg_username: str):
        """Ignore messages from a DGG user"""
        self.check_prefs(ctx.user.id)
        ignores = self.bot.user_prefs[ctx.user.id]["ignores"]
        ignores.append(dgg_username)
        self.bot.user_prefs[ctx.user.id]["ignores"] = list(set(ignores))
        self.bot.save_cfg()
        response = f"'{dgg_username}' added to your ignore list"
        await log_reply(ctx, response)

    @ignore.command(name="remove")
    @app_commands.describe(dgg_username="The user in DGG you want to unignore")
    async def add_ignore(self, ctx: Interaction, dgg_username: str):
        """Remove someone from your ignore list"""
        self.check_prefs(ctx.user.id)
        ignores = self.bot.user_prefs[ctx.user.id]["ignores"]
        if dgg_username not in ignores:
            await log_reply(ctx, f"'{dgg_username}' is not in your ignore list")
            return
        self.bot.user_prefs[ctx.user.id]["ignores"].remove(dgg_username)
        self.bot.save_cfg()
        response = f"'{dgg_username}' removed from your ignore list"
        await log_reply(ctx, response)
