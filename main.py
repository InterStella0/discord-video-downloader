import datetime
import itertools
import tempfile

import discord
import humanize
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from core.client import StellaVideoBot
from core.errors import UploadError, SomethingWentWrong, DisplayError, UserErrorUsage
from core.models import URLParsed, FileType, Progress, ViewFormatType
from core.types import Context, Interaction
from core.utils import FIND_CAMEL, url_context

load_dotenv()
bot = StellaVideoBot()


async def download_flow(sender: Context, link: URLParsed, file_type: FileType):
    url_context.set(link)
    color = 0xffcccb
    embed = discord.Embed(title=link.type, description=f"**Link:** {link.url}\nFetching metadata...", color=color)
    msg = await sender.send(embed=embed, ephemeral=True)

    last_update: datetime.datetime | None = None
    loading = itertools.cycle([".", "..", "..."])
    async def listen(progress: Progress):
        nonlocal last_update
        if last_update is not None and (discord.utils.utcnow() - last_update) < datetime.timedelta(seconds=1):
            return

        last_update = discord.utils.utcnow()
        current = humanize.naturalsize(progress.current)
        total = humanize.naturalsize(progress.total)
        desc = f"[{current}/**{total}**] ({progress.percent:.2%}) ETA {progress.eta}"

        embed_ = discord.Embed(title=f"{progress.type.capitalize()} `[{next(loading)}]`", description=desc, color=color)
        await msg.edit(embed=embed_)

    link.add_listener(listen)
    with tempfile.TemporaryDirectory() as tmp:
        filename = f"{tmp}/file.{file_type}"
        await link.download(filename, file_type)
        embed = discord.Embed(title=f"Uploading `[{next(loading)}]`", description="Please be nice...", color=color)
        try:
            await msg.edit(embed=embed)
            await msg.edit(content=None, attachments=[discord.File(filename, filename=f"file.{file_type}")], embed=None)
        except discord.HTTPException as e:
            if e.status == 413:
                raise UploadError("File is too large to be uploaded to Discord.")

            await msg.delete(delay=0)


@bot.hybrid_command(help="Download videos from popular platform via a URL.")
@app_commands.describe(
    link="Shared video link to be downloaded. Supports YouTube, TikTok, Instagram, Twitter (X), twitch, bilibili.",
    file_type="Supported Type (video, audio)"
)
@app_commands.user_install()
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def download(ctx: Context, link: URLParsed, file_type: FileType) -> None:
    await download_flow(ctx, link, file_type)


@bot.tree.context_menu(name="download video")
@app_commands.user_install()
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def context_download(interaction: Interaction, message: discord.Message) -> None:
    try:
        url_parsed = await URLParsed.transform(interaction, message.content)
    except UserErrorUsage:
        if not message.embeds:
            raise UserErrorUsage("No URL with a compatible parser found in this message!")

        try:
            embed_data = str([e.to_dict() for e in message.embeds])
            url_parsed = await URLParsed.transform(interaction, embed_data)
        except UserErrorUsage:
            raise UserErrorUsage("No URL with a compatible parser found in this message!")

    ctx = await bot.get_context(interaction)
    view = ViewFormatType()
    msg = await ctx.send(f"Found `{url_parsed.url}` compatible with **{url_parsed.type}**."
                   f"\nSelect a format:", view=view, ephemeral=True)
    file_type = await view.wait_for()
    await msg.delete(delay=0)
    await download_flow(ctx, url_parsed, file_type)


@bot.tree.error
async def tree_on_error(interaction: Interaction,error: app_commands.AppCommandError):
    ori_error = error
    error = getattr(error, "original", error)
    async def try_send(*args, **kwargs):
        if interaction.response.is_done():
            kwargs.pop('ephemeral', None)
            await interaction.edit_original_response(*args, **kwargs)
        else:
            try:
                kwargs.pop('view', None)
                await interaction.response.send_message(*args, **kwargs)
            except discord.InteractionResponded:
                kwargs.pop('ephemeral', None)
                await interaction.edit_original_response(*args, **kwargs)
            except Exception as e:
                raise SomethingWentWrong() from e

    if isinstance(error, DisplayError):
        title = FIND_CAMEL.sub(' ', error.__class__.__name__)
        embed = discord.Embed(color=discord.Color.red(), title=title, description=str(error))
        await try_send(embed=embed, ephemeral=True, view=None, content=None)
    else:
        embed = discord.Embed(color=discord.Color.red(), title="Something went wrong", description=str(ori_error))
        await try_send(embed=embed, ephemeral=True, view=None, content=None)
        raise SomethingWentWrong() from ori_error


@bot.event
async def on_command_error(ctx: Context, error: commands.CommandError) -> None:
    ori_error = error
    error = getattr(error, "original", error)
    if isinstance(error, DisplayError):
        title = FIND_CAMEL.sub(' ', error.__class__.__name__)
        embed = discord.Embed(color=discord.Color.red(), title=title, description=str(error))
        await ctx.send(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(color=discord.Color.red(), title="Something went wrong", description=str(ori_error))
        await ctx.send(embed=embed, ephemeral=True)
        raise SomethingWentWrong() from ori_error

if __name__ == "__main__":
    bot.starting()