from helpers import logger, log_reply

import discord
from discord import Interaction, app_commands
from discord.ext.commands import Bot, GroupCog


class UserBaseCog(GroupCog):
    """Base GroupCog for user commands"""

    def __init__(self, bot: Bot):
        self.bot = bot

    async def interaction_check(self, ctx: Interaction) -> bool:
        """Checks if the user accepts DMs before letting them use a command"""
        ch = ctx.user.dm_channel
        if ch is None:
            ch = await ctx.user.create_dm()

        try:
            await ch.send()
        except discord.Forbidden:
            err = "**Error**: You can't use this command because your DMs are closed."
            await log_reply(ctx, err)
            return False
        except discord.HTTPException:
            return True

    async def cog_before_invoke(self, ctx: Interaction) -> None:
        """Adds new users to the preferences dict"""
        if ctx.user.id not in self.bot.user_prefs.keys():
            self.bot.user_prefs[ctx.user.id] = {"detect_presence": False, "ignores": []}
            logger.info(f"Added new user '{ctx.user.id}' to preferences list")

    async def cog_after_invoke(self, ctx: Interaction) -> None:
        self.bot.save_cfg()


class PhraseCog(UserBaseCog, group_name="phrase"):
    """Cog for all of the /phrase commands"""

    @app_commands.command(name="add")
    @app_commands.describe(
        phrase="The phrase you want forwarded to you (most likely your DGG username)"
    )
    async def phrase_add(self, ctx: Interaction, phrase: str):
        """Add a phrase (usually a username) that will be forwarded
        to you when it's used in DGG"""
        if phrase not in self.bot.phrases:
            self.bot.phrases[phrase] = []
            logger.info(f"Added new phrase list for '{phrase}'")
        if ctx.user.id not in self.bot.phrases[phrase]:
            self.bot.phrases[phrase].append(ctx.user.id)
            response = f"Forwarding '{phrase}' to {ctx.user}"
        else:
            response = f"**Error:** '{phrase}' is already being forwarded to {ctx.user}"
        await log_reply(ctx, response)

    @app_commands.command(name="remove")
    @app_commands.describe(phrase="The phrase you want to stop being forwarded")
    async def phrase_remove(self, ctx: Interaction, phrase: str):
        """Stop a phrase from being forwarded to you"""
        response = None
        if phrase in self.bot.phrases:
            if ctx.user.id in self.bot.phrases[phrase]:
                self.bot.phrases[phrase].remove(ctx.user.id)
                response = f"No longer forwarding '{phrase}' to {ctx.user}"
                if not self.bot.phrases[phrase]:
                    self.bot.phrases.pop(phrase)
                    logger.info(f"Removed empty phrase list '{phrase}'")
        if not response:
            response = (
                f"**Error:** '{phrase}' isn't being forwarded to {ctx.user}"
                " (try the '/phrase list' command)"
            )
        await log_reply(ctx, response)

    @app_commands.command(name="list")
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

    @app_commands.command(name="detect-dgg-presence")
    @app_commands.describe(mode="Set to True to detect DGG presence. Default is False.")
    async def detect_dgg_presence(self, ctx: Interaction, mode: bool):
        """Change behavior of the /phrase command by controlling when the bot messages you."""
        self.bot.user_prefs[ctx.user.id]["detect_presence"] = mode
        word = "enabled" if mode else "disabled"
        response = f"Presence detection {word} for {ctx.user.name}"
        await log_reply(ctx, response)


class IgnoreCog(UserBaseCog):
    """Cog for all of the /ignore commands"""

    @app_commands.command(name="add")
    @app_commands.describe(dgg_username="The user in DGG you want to ignore")
    async def add_ignore(self, ctx: Interaction, dgg_username: str):
        """Ignore messages from a DGG user"""
        ignores = self.bot.user_prefs[ctx.user.id]["ignores"]
        ignores.append(dgg_username)
        self.bot.user_prefs[ctx.user.id]["ignores"] = list(set(ignores))
        response = f"'{dgg_username}' added to your ignore list"
        await log_reply(ctx, response)

    @app_commands.command(name="remove")
    @app_commands.describe(dgg_username="The user in DGG you want to unignore")
    async def add_ignore(self, ctx: Interaction, dgg_username: str):
        """Remove someone from your ignore list"""
        ignores = self.bot.user_prefs[ctx.user.id]["ignores"]
        if dgg_username not in ignores:
            await log_reply(ctx, f"'{dgg_username}' is not in your ignore list")
            return
        self.bot.user_prefs[ctx.user.id]["ignores"].remove(dgg_username)
        response = f"'{dgg_username}' removed from your ignore list"
        await log_reply(ctx, response)
