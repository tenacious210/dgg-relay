from discord import Interaction, Message
from discord.ext.commands import Cog, Bot
from discord import app_commands
from discord.app_commands import Choice
import logging
import re

logger = logging.getLogger(__name__)


async def log_reply(ctx: Interaction, response: str, ephemeral=True):
    log = f"From {ctx.user}: {response}"
    if ctx.guild:
        log = f"From {ctx.user} in {ctx.guild.name}: {response}"
    logger.info(log)
    await ctx.response.send_message(response, ephemeral=ephemeral)


class OwnerCog(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def owner_error(self, ctx: Interaction, command: str):
        response = f"Error: Only {self.bot.owner} can use the {command} command"
        await log_reply(ctx, response)

    @Cog.listener()
    async def on_message(self, msg: Message):
        """
        Checks if the bot's owner has replied to one of its messages,
        and then sends the owner's message back to DGG
        """
        if (
            (ref := msg.reference)
            and not msg.is_system()
            and await self.bot.is_owner(msg.author)
        ):
            ref_msg: Message = await msg.channel.fetch_message(ref.message_id)
            if whisper_re := re.match(r"W \*\*(.+):\*\*.+", ref_msg.content):
                logger.info(f"Sending a whisper in reply to {ref_msg.id}")
                self.bot.dgg_bot.send_privmsg(whisper_re[1], msg.content)
            elif chat_re := re.match(r"\*\*(.+):\*\*.+", ref_msg.content):
                username = chat_re[1].replace("\\", "")
                logger.info(f"Sending a message in reply to {ref_msg.id}")
                self.bot.dgg_bot.send(f"{username} {msg.content}")
            if whisper_re or chat_re:
                await msg.add_reaction("☑️")
                for emote in self.bot.emotes.keys():
                    if re.search(rf"\b{emote}\b", msg.content):
                        er: str = self.bot.emotes[emote]
                        emote_id = int(er[er.find(":", 3) + 1 : er.find(">")])
                        reaction_emote = self.bot.get_emoji(emote_id)
                        await msg.add_reaction(reaction_emote)

    @app_commands.command(name="send")
    @app_commands.describe(message="The message to send to DGG chat")
    async def owner_send(self, ctx: Interaction, message: str):
        """(Owner only) Sends a message back to DGG"""
        if not await self.bot.is_owner(ctx.user):
            await self.owner_error(ctx, "/send")
            return
        self.bot.dgg_bot.send(message)
        response = f"Message sent {self.bot.dgg_to_disc(self.bot.owner.name, message)}"
        await log_reply(ctx, response, ephemeral=False)

    @app_commands.command(name="whisper")
    @app_commands.describe(
        user="The DGG user to whisper",
        message="The message to whisper the user",
    )
    async def owner_whisper(self, ctx: Interaction, user: str, message: str):
        """(Owner only) Sends a whisper to a DGG user"""
        if not await self.bot.is_owner(ctx.user):
            await self.owner_error(ctx, "/whisper")
            return
        self.bot.dgg_bot.send_privmsg(user, message)
        response = f"Whisper sent to {self.bot.dgg_to_disc(user, message)}"
        await log_reply(ctx, response, ephemeral=False)

    @app_commands.command(name="loglevel")
    @app_commands.choices(
        level=[
            Choice(name="warning", value=30),
            Choice(name="info", value=20),
            Choice(name="debug", value=10),
        ]
    )
    @app_commands.describe(level="The level to set the logger to")
    async def loglevel(self, ctx: Interaction, level: int):
        """(Owner only) Sets the level of the stdout logger"""
        if not await self.bot.is_owner(ctx.user):
            await self.owner_error(ctx, "/loglevel")
            return
        logger.setLevel(level)
        await log_reply(ctx, f"Set logging level to {logger.level}")

    @app_commands.command(name="sync")
    async def sync_commands(self, ctx: Interaction):
        """(Owner only) Syncs app command info with Discord"""
        if not await self.bot.is_owner(ctx.user):
            await self.owner_error(ctx, "/sync")
            return
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
    async def add_emote(self, ctx: Interaction, dgg_version: str, disc_version: str):
        """(Owner only) Add or modify a DGG emote translation"""
        if not await self.bot.is_owner(ctx.user):
            await self.owner_error(ctx, "/emote add")
            return
        self.bot.emotes[dgg_version] = disc_version
        self.bot.save_config()
        await log_reply(ctx, f"Translating {dgg_version} to {str(disc_version)}")

    @emote.command(name="remove")
    @app_commands.describe(dgg_version="The emote to remove (in DGG format)")
    async def remove_emote(self, ctx: Interaction, dgg_version: str):
        """(Owner only) Remove a DGG emote translation"""
        if not await self.bot.is_owner(ctx.user):
            await self.owner_error(ctx, "/emote remove")
            return
        if dgg_version in self.bot.emotes.keys():
            removed_emote = self.bot.emotes.pop(dgg_version)
            self.bot.save_config()
            await log_reply(ctx, f"Removed {removed_emote} from emotes")
        else:
            await log_reply(ctx, f"Couldn't find emote {dgg_version}")

    @emote.command(name="list")
    @app_commands.describe(version="The version of emotes to display")
    @app_commands.choices(
        version=[
            Choice(name="DGG", value="DGG"),
            Choice(name="Discord", value="Discord"),
        ]
    )
    async def list_emotes(self, ctx: Interaction, version: str):
        """(Owner only) List emotes currently being translated"""
        if not await self.bot.is_owner(ctx.user):
            await self.owner_error(ctx, "/emote list")
            return
        if version == "DGG":
            response = f"DGG versions: {', '.join(self.bot.emotes.keys())}"
        else:
            response = f"Discord versions: {', '.join(self.bot.emotes.values())}"
        await log_reply(ctx, response)


class PublicCog(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    relay = app_commands.Group(
        name="relay",
        description="Relays DGG messages to servers",
    )

    def get_relay_channel(self, ctx: Interaction) -> int:
        if not ctx.guild:
            return "Error: This command is only usable in servers"
        if "dgg-relay-mod" not in (role.name for role in ctx.user.roles):
            return "Error: This command requires the 'dgg-relay-mod' role"
        relay_channel = None
        for channel in ctx.guild.channels:
            if channel.name == "dgg-relay":
                relay_channel = channel.id
                break
        if not relay_channel:
            return f"Error: No #dgg-relay channel found in {ctx.guild.name}"
        return relay_channel

    @relay.command(name="add")
    @app_commands.describe(dgg_username="The DGG user you want to relay messages from")
    async def relay_add(self, ctx: Interaction, dgg_username: str):
        """Add a DGG user whose messages get forwarded to this server"""
        relay_channel = self.get_relay_channel(ctx)
        if type(relay_channel) is int:
            if dgg_username not in self.bot.nicks:
                self.bot.nicks[dgg_username] = []
                logger.info(f'Added new relay list "{dgg_username}"')
            if relay_channel not in self.bot.nicks[dgg_username]:
                self.bot.nicks[dgg_username].append(relay_channel)
                response = (
                    f"Messages from {dgg_username} will be relayed to {ctx.guild.name}"
                )
            else:
                response = f"Error: {dgg_username} is already being relayed to {ctx.guild.name}"
            self.bot.save_config()
        else:
            response = relay_channel
        await log_reply(ctx, response, ephemeral=False)

    @relay.command(name="remove")
    @app_commands.describe(dgg_username="The DGG user you want to stop relaying")
    async def relay_remove(self, ctx: Interaction, dgg_username: str):
        """Remove a DGG user's relay from this server"""
        relay_channel = self.get_relay_channel(ctx)
        if type(relay_channel) is int:
            if relay_channel in self.bot.nicks[dgg_username]:
                self.bot.nicks[dgg_username].remove(relay_channel)
                response = f"Removed {dgg_username} relay from {ctx.guild.name}"
                if not self.bot.nicks[dgg_username]:
                    self.bot.nicks.pop(dgg_username)
                    logger.info(f'Removed empty relay list for "{dgg_username}"')
            else:
                response = (
                    f"Error: {dgg_username} isn't being relayed to {ctx.guild.name}"
                )
            self.bot.save_config()
        else:
            response = relay_channel
        await log_reply(ctx, response, ephemeral=False)

    phrase = app_commands.Group(
        name="phrase",
        description="Relays DGG messages to users",
    )

    @phrase.command(name="add")
    @app_commands.describe(
        phrase="The phrase you want forwarded to you (most likely your DGG username)"
    )
    async def phrase_add(self, ctx: Interaction, phrase: str):
        """Add a phrase (usually a username) that will be forwarded to you when it's used in DGG"""
        disc_user = ctx.user.id
        if disc_user not in self.bot.presence.keys():
            self.bot.presence[disc_user] = "off"
            logger.info(f"Added new user {disc_user} to presence list")
        if phrase not in self.bot.phrases:
            self.bot.phrases[phrase] = []
            logger.info(f'Added new phrase list for "{phrase}"')
        if disc_user not in self.bot.phrases[phrase]:
            self.bot.phrases[phrase].append(disc_user)
            response = f"Forwarding '{phrase}' to {ctx.user}"
        else:
            response = f"Error: '{phrase}' is already being forwarded to {ctx.user}"
        self.bot.save_config()
        await log_reply(ctx, response)

    @phrase.command(name="remove")
    @app_commands.describe(phrase="The phrase you want to stop being forwarded")
    async def phrase_remove(self, ctx: Interaction, phrase: str):
        """Stop a phrase from being forwarded to you"""
        disc_user = ctx.user.id
        if disc_user in self.bot.phrases[phrase]:
            self.bot.phrases[phrase].remove(disc_user)
            response = f"No longer forwarding '{phrase}' to {ctx.user}"
        else:
            response = f"Error: '{phrase}' isn't being forwarded to {ctx.user}"
        if not self.bot.phrases[phrase]:
            self.bot.phrases.pop(phrase)
            logger.info(f'Removed empty phrase list "{phrase}"')
        self.bot.save_config()
        await log_reply(ctx, response)

    @phrase.command(name="detect-dgg-presence")
    @app_commands.describe(mode="Set to 'on' to detect DGG presence. Default is 'off'.")
    @app_commands.choices(
        mode=[
            Choice(name="on", value="on"),
            Choice(name="off", value="off"),
        ]
    )
    async def detect_dgg_presence(self, ctx: Interaction, mode: str):
        """Change behavior of the /phrase command by controlling when the bot messages you."""
        self.bot.presence[ctx.user.id] = mode
        self.bot.save_config()
        response = f"Presence detection for {ctx.user.name} set to {mode}"
        await log_reply(ctx, response)
