import discord


def _parse_color(color_hex: str | None) -> discord.Color:
    if not color_hex:
        return discord.Color.red()
    value = color_hex.strip().lstrip("#")
    if len(value) != 6:
        return discord.Color.red()
    try:
        return discord.Color(int(value, 16))
    except ValueError:
        return discord.Color.red()


def build_live_embed(
    streamer_id: str,
    stream_url: str,
    info: dict | None = None,
    thumbnail_url: str | None = None,
    title_override: str | None = None,
    description_override: str | None = None,
    color_hex: str | None = None,
) -> discord.Embed:
    title = title_override or f"{streamer_id} is now live on SOOP!"
    embed = discord.Embed(title=title, url=stream_url, color=_parse_color(color_hex))

    if info:
        broad_title = info.get("broadTitle")
        if broad_title:
            embed.description = str(broad_title)

    if description_override:
        embed.description = description_override

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
