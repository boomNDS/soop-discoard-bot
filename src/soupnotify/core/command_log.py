from __future__ import annotations

import logging

import discord

logger = logging.getLogger("soupnotify.commands")


def log_command(ctx: discord.ApplicationContext, name: str) -> None:
    guild_id = getattr(ctx.guild, "id", None)
    guild_name = getattr(ctx.guild, "name", None)
    user = getattr(ctx.user, "name", None)
    user_id = getattr(ctx.user, "id", None)
    logger.info(
        "Command /%s by %s (%s) in %s (%s)",
        name,
        user,
        user_id,
        guild_name,
        guild_id,
    )
