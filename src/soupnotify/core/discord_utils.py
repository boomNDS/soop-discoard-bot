from __future__ import annotations

import re

import discord


async def safe_respond(
    ctx: discord.ApplicationContext,
    content: str | None = None,
    *,
    embed: discord.Embed | None = None,
    view: discord.ui.View | None = None,
    ephemeral: bool = False,
) -> None:
    kwargs = {"content": content, "embed": embed, "ephemeral": ephemeral}
    if view is not None:
        kwargs["view"] = view
    if ctx.response.is_done():
        await ctx.followup.send(**kwargs)
    else:
        await ctx.respond(**kwargs)


CHANNEL_MENTION_RE = re.compile(r"^<#(\d+)>$")


def parse_channel_id(value: str | None) -> str | None:
    if not value:
        return None
    match = CHANNEL_MENTION_RE.match(value.strip())
    if match:
        return match.group(1)
    if value.isdigit():
        return value
    return None
