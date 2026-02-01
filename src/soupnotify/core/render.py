from __future__ import annotations

from typing import Any


def render_template_value(
    template: str | None,
    soop_channel_id: str,
    notify_channel_id: int,
    guild_name: str,
    stream_url_base: str,
) -> str | None:
    if not template:
        return None
    soop_url = f"{stream_url_base.rstrip('/')}/{soop_channel_id}"
    return (
        template.replace("{soop_channel_id}", soop_channel_id)
        .replace("{notify_channel}", f"<#{notify_channel_id}>")
        .replace("{guild}", guild_name)
        .replace("{soop_url}", soop_url)
    )


def render_message(
    template: str | None,
    soop_channel_id: str,
    notify_channel_id: int,
    guild_name: str,
    stream_url_base: str,
    mention: str | None = None,
) -> str:
    rendered = render_template_value(
        template, soop_channel_id, notify_channel_id, guild_name, stream_url_base
    )
    if rendered:
        return f"{mention} {rendered}".strip() if mention else rendered
    soop_url = f"{stream_url_base.rstrip('/')}/{soop_channel_id}"
    base = f"\N{LARGE RED CIRCLE} **Live Now** on SOOP: `{soop_channel_id}` {soop_url}"
    return f"{mention} {base}".strip() if mention else base


def render_embed_overrides(
    embed_settings: dict[str, Any],
    soop_channel_id: str,
    notify_channel_id: int,
    guild_name: str,
    stream_url_base: str,
) -> tuple[str | None, str | None, str | None]:
    title = render_template_value(
        embed_settings.get("title"),
        soop_channel_id,
        notify_channel_id,
        guild_name,
        stream_url_base,
    )
    description = render_template_value(
        embed_settings.get("description"),
        soop_channel_id,
        notify_channel_id,
        guild_name,
        stream_url_base,
    )
    color = embed_settings.get("color")
    return title, description, color
