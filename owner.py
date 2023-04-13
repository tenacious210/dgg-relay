from helpers import log_reply

from discord.ext.commands import Cog, Bot
from discord import Interaction, app_commands
from discord.app_commands import Choice


class OwnerCog(Cog):
    """Commands that can only be used by the bot's owner"""

    def __init__(self, bot: Bot):
        self.bot = bot

    async def interaction_check(self, ctx: Interaction) -> bool:
        if not await self.bot.is_owner(ctx.user):
            await log_reply(ctx, f"**Error:** Only my owner can use this command")
            return False
        return True

    async def cog_after_invoke(self, ctx: Interaction) -> None:
        self.bot.save_cfg()

    @app_commands.command(name="sync")
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
    async def add_emote(self, ctx: Interaction, dgg_version: str, disc_version: str):
        """(Owner only) Add or modify a DGG emote translation"""
        self.bot.emotes[dgg_version] = disc_version
        await log_reply(ctx, f"Translating {dgg_version} to {str(disc_version)}")

    @emote.command(name="remove")
    @app_commands.describe(dgg_version="The emote to remove (in DGG format)")
    async def remove_emote(self, ctx: Interaction, dgg_version: str):
        """(Owner only) Remove a DGG emote translation"""
        if dgg_version in self.bot.emotes.keys():
            removed_emote = self.bot.emotes.pop(dgg_version)
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
    async def config_remove(self, ctx: Interaction, mode: str, value: str):
        """Remove a relay or phrase from the config file"""
        if mode == "phrase" and value in self.bot.phrases:
            del self.bot.phrases[value]
            await log_reply(ctx, f"Removed '{value}' from phrases", ephemeral=False)
        elif mode == "relay" and value in self.bot.relays:
            del self.bot.relays[value]
            await log_reply(ctx, f"Removed '{value}' from relays", ephemeral=False)
        else:
            await log_reply(ctx, f"Couldn't find '{value}' in {mode}s")
