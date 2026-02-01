from __future__ import annotations

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
