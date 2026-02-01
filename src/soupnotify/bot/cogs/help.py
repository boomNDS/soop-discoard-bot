import discord
from discord.ext import commands

from soupnotify.core.discord_utils import safe_respond
from soupnotify.core.command_log import log_command


class HelpCog(commands.Cog):
    def __init__(self) -> None:
        super().__init__()

    @commands.slash_command(name="help", description="Show bot commands")
    async def help_command(self, ctx: discord.ApplicationContext) -> None:
        log_command(ctx, "help")
        embed = discord.Embed(
            title="SoupNotify Commands",
            description="Use slash commands below. Admin-only commands are marked.",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Linking",
            value=(
                "/link soop_channel:<id> [notify_channel:<#channel|id>]\n"
                "/unlink soop_channel:<id> (admin)\n"
                "/unlink_all (admin)\n"
                "/link_list [page:<n>]\n"
                "/status"
            ),
            inline=False,
        )
        embed.add_field(
            name="Notifications",
            value=(
                "/test [soop_channel:<id>]\n"
                "/template action:<set|clear|list> ... (admin)\n"
                "/embed_template action:<set|clear|show> ... (admin)\n"
                "/default_channel action:<set|clear> channel:<#channel|id> (admin)\n"
                "/mention action:<set|clear|show> ... (admin)"
            ),
            inline=False,
        )
        embed.add_field(
            name="Admin / Debug",
            value="/config (admin)\n/metrics (admin)\n/debug_live_status (admin)\n/reset_live_status (admin)\n/sync (admin)",
            inline=False,
        )
        await safe_respond(ctx, embed=embed, ephemeral=True)
