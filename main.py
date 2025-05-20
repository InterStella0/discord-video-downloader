import datetime
import itertools
import tempfile

import discord
import humanize
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from core.client import StellaVideoBot
from core.errors import UploadError, SomethingWentWrong, DisplayError
from core.models import URLParsed, FileType, Progress
from core.types import Context
from core.utils import FIND_CAMEL, url_context

load_dotenv()
bot = StellaVideoBot()


@bot.hybrid_command(help="Download videos from popular platform via a URL.")
@app_commands.describe(
    link="Shared video link to be downloaded. Supports YouTube, TikTok, Instagram, Twitter (X), twitch, bilibili.",
    file_type="Supported Type (video, audio)"
)
async def download(ctx: Context, link: URLParsed, file_type: FileType) -> None:
    url_context.set(link)
    color = 0xffcccb
    embed = discord.Embed(title=link.type, description=f"**Link:** {link.url}\nFetching metadata...", color=color)
    msg = await ctx.send(embed=embed, ephemeral=True)
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