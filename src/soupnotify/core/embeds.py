import discord


def build_live_embed(
    streamer_id: str,
    stream_url: str,
    info: dict | None = None,
    thumbnail_url: str | None = None,
) -> discord.Embed:
    title = f"{streamer_id} is now live on SOOP!"
    embed = discord.Embed(title=title, url=stream_url, color=discord.Color.red())

    if info:
        broad_title = info.get("broadTitle")
        if broad_title:
            embed.description = str(broad_title)

        category = info.get("categoryName")
        viewers = info.get("currentSumViewer")
        if category:
            embed.add_field(name="Category", value=str(category), inline=True)
        if viewers is not None:
            embed.add_field(name="Viewers", value=str(viewers), inline=True)

    embed.add_field(name="Watch", value=stream_url, inline=False)
    if thumbnail_url:
        embed.set_image(url=thumbnail_url)
    return embed
