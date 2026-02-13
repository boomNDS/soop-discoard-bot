import discord

from soupnotify.core.discord_utils import safe_respond
from soupnotify.core.storage import Storage


def is_admin(ctx: discord.ApplicationContext, storage: Storage) -> bool:
    member = ctx.user if isinstance(ctx.user, discord.Member) else None
    if not member and ctx.guild:
        member = ctx.guild.get_member(ctx.user.id)
    if not member:
        return False
    admin_role_id = storage.get_admin_role(str(ctx.guild.id)) if ctx.guild else None
    if admin_role_id and any(str(role.id) == admin_role_id for role in member.roles):
        return True
    perms = member.guild_permissions
    return perms.administrator or perms.manage_guild


async def require_admin(ctx: discord.ApplicationContext, storage: Storage) -> bool:
    if is_admin(ctx, storage):
        return True
    await safe_respond(ctx, "You need Manage Server permission to use this command.", ephemeral=True)
    return False
