from __future__ import annotations

import asyncio
import dataclasses
import functools
import re
import time
from abc import abstractmethod
from enum import StrEnum
from typing import Self, Callable, Awaitable, Any, Literal, TypeVar, Generic

import discord.ui
import yt_dlp

from core.errors import UserErrorUsage, ErrorProcessing, TimeoutResponding
from core.types import Context, Interaction
from core.utils import FIND_CAMEL


@dataclasses.dataclass
class Progress:
    type: Literal["downloading", "processing"]
    filename: str | None
    percent: float
    total: float
    current: float
    speed: float | None
    eta: str | None


DownloadListener = Callable[[Progress], Awaitable[None]]
class URLParsed:
    pattern: re.compile
    def __init__(self, url: str, groups: re.Match[str]):
        self.listeners: list[DownloadListener] = []
        self.url: str = url
        self.groups: re.Match = groups
        self.preset: CompressionType = CompressionType.hd
        self._last_dispatch_time = 0

    @property
    def type(self) -> str:
        return FIND_CAMEL.sub(' ', self.__class__.__name__)

    def add_listener(self, call: DownloadListener) -> None:
        self.listeners.append(call)

    async def dispatch_progress(self, progress: Progress) -> None:
        async with asyncio.TaskGroup() as group:
            for listen in self.listeners:
                group.create_task(listen(progress))

    @abstractmethod
    async def download(self, file: str, file_type: FileType) -> None:
        pass

    @classmethod
    def from_url(cls, url: str) -> Self:
        matched = cls.pattern.search(url)
        return cls(url=url, groups=matched)

    @staticmethod
    async def parse(url: str) -> URLParsed:
        for Parser in PARSERS:
            if Parser.pattern.search(url):
                return Parser.from_url(url)

        raise UserErrorUsage(f"Could not find a downloader with this URL: `{url}`")

    @classmethod
    async def convert(cls, ctx: Context, argument: str) -> Self:
        return await cls.parse(argument)

    @classmethod
    async def transform(cls, interaction: Interaction, value: str, /) -> Self:
        return await cls.parse(value)


class YouTubeDownloader(URLParsed):
    pattern = re.compile(r"(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})")

    @property
    def type(self) -> str:
        if self.__class__ is YouTubeDownloader:
            return "YouTube Downloader"
        return super().type

    def _progress_hook(self, event_loop: asyncio.BaseEventLoop, d: dict[str, Any]) -> None:
        if d['status'] != 'downloading':
            if d['status'] == 'finished':
                event_loop.create_task(
                    self.dispatch_progress(Progress(
                        type="processing",
                        eta=None,
                        filename=None,
                        percent=1,
                        speed=1,
                        total=1,
                        current=1
                    ))
                )
            return

        now = time.monotonic()
        if now - self._last_dispatch_time < 0.5:
            return

        self._last_dispatch_time = now

        filename = d.get('filename', 'N/A')
        downloaded_bytes = d.get('downloaded_bytes', 0)
        total = d.get('total_bytes_estimate', downloaded_bytes)
        percent = downloaded_bytes / (total or downloaded_bytes)
        speed = d.get('speed')
        eta_str = d.get('_eta_str', 'N/A')

        event_loop.create_task(
            self.dispatch_progress(Progress(
                type="downloading",
                eta=eta_str,
                filename=filename,
                percent=percent,
                speed=speed,
                total=total,
                current=downloaded_bytes
            ))
        )

    def get_video_compression_preset(self) -> list[str]:
        audio_bitrate: str = '128k'
        if self.preset is CompressionType.low:
            return [
                '-c:v', 'libx264',
                '-preset', 'veryfast',
                '-crf', '32',
                '-profile:v', 'baseline',
                '-pix_fmt', 'yuv420p',
                '-c:a', 'aac',
                '-b:a', audio_bitrate,
                '-movflags', '+faststart'
            ]
        elif self.preset is CompressionType.medium:
            return [
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '28',
                '-profile:v', 'main',
                '-pix_fmt', 'yuv420p',
                '-c:a', 'aac',
                '-b:a', audio_bitrate,
                '-movflags', '+faststart'
            ]
        elif self.preset is CompressionType.hd:
            return [
                '-c:v', 'libx264',
                '-preset', 'slow',
                '-crf', '23',
                '-profile:v', 'high',
                '-pix_fmt', 'yuv420p',
                '-c:a', 'aac',
                '-b:a', audio_bitrate,
                '-movflags', '+faststart'
            ]
        elif self.preset is CompressionType.original:
            return [
                '-c', 'copy'
            ]
        else:
            raise RuntimeError("Unregistered compression.")

    def get_audio_compression_preset(self) -> dict[str, str]:
        if self.preset is CompressionType.low:
            return {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '64',
            }
        elif self.preset is CompressionType.medium:
            return {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }
        elif self.preset is CompressionType.hd:
            return {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '256',
            }
        elif self.preset is CompressionType.original:
            return {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }
        else:
            raise RuntimeError("Unregistered compression.")

    async def download(self, file: str, file_type: FileType) -> None:
        event_loop = asyncio.get_running_loop()
        ydl_opts = {}
        if file_type is FileType.video:
            ydl_opts = {
                'outtmpl': file,
                'noplaylist': True,
                'quiet': True,
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best',
                'merge_output_format': 'mp4',
                'postprocessor_args': self.get_video_compression_preset(),
            }
        elif file_type is FileType.audio:
            if file.endswith(".mp3"):
                file, *_ = file.rpartition(".")
            ydl_opts = {
                'outtmpl': file,
                'noplaylist': True,
                'quiet': True,
                'format': 'bestaudio/best',
                'postprocessors': [self.get_audio_compression_preset()],
            }

        ydl_opts['progress_hooks'] = [functools.partial(self._progress_hook, event_loop)]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            error_code = await asyncio.to_thread(lambda: ydl.download([self.url]))
            if error_code:
                raise ErrorProcessing(f"Couldn't download {self.url}.")


class TikTokDownloader(YouTubeDownloader):
    pattern = re.compile(r'https?://((?:vm|vt|www)\.)?tiktok\.com/.*')


class TwitterDownloader(YouTubeDownloader):
    pattern = re.compile(r'https?://(x\.com|twitter\.com)/(i/)?[^/]+/status/\d+')


class TwitchClipsDownloader(YouTubeDownloader):
    pattern = re.compile(r'https?://(?:www\.)?twitch\.tv/(?:[a-zA-Z0-9_]+/)?clip/([a-zA-Z0-9_-]+)')


class BiliBiliDownloader(YouTubeDownloader):
    pattern = re.compile(r'https?://(?:www\.)?bilibili\.com/video/(av\d+|BV[a-zA-Z0-9]+)/?')


class FileType(StrEnum):
    video = "mp4"
    audio = "mp3"


class CompressionType(StrEnum):
    low = "low"
    medium = "medium"
    hd = "hd"
    original = "original"


PARSERS = [
    YouTubeDownloader,
    TikTokDownloader,
    TwitchClipsDownloader,
    TwitterDownloader,
    BiliBiliDownloader
]
T = TypeVar('T', bound=StrEnum)

class ViewAnswer(discord.ui.View, Generic[T]):
    def __init__(self):
        super().__init__()
        self.answer: T | None = None

    @classmethod
    async def ask(cls, ctx: Context, content: str, delete_timeout=False) -> T:
        self = cls()
        msg = await ctx.send(content, view=self, ephemeral=True)
        try:
            value = await self.wait_for()
        except TimeoutResponding:
            if delete_timeout:
                await msg.delete(delay=0)
            raise

        await msg.delete(delay=0)
        return value

    async def wait_for(self) -> T:
        await self.wait()
        if self.answer is None:
            raise TimeoutResponding("Timeout waiting for user to respond.")

        return self.answer

    async def responded(self, interaction: discord.Interaction, file_type: T) -> None:
        await interaction.response.defer()
        self.answer = file_type
        self.stop()

class ViewFormatType(ViewAnswer[FileType]):
    @discord.ui.button(label='Video', style=discord.ButtonStyle.blurple)
    async def vid(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.responded(interaction, FileType.video)

    @discord.ui.button(label='Audio', style=discord.ButtonStyle.blurple)
    async def aud(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.responded(interaction, FileType.audio)


class ViewCompressionType(ViewAnswer[CompressionType]):
    @discord.ui.button(label='low', style=discord.ButtonStyle.blurple)
    async def low(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.responded(interaction, CompressionType.low)

    @discord.ui.button(label='medium', style=discord.ButtonStyle.blurple)
    async def med(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.responded(interaction, CompressionType.medium)

    @discord.ui.button(label='HD', style=discord.ButtonStyle.blurple)
    async def hd(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.responded(interaction, CompressionType.hd)

    @discord.ui.button(label='Original', style=discord.ButtonStyle.blurple)
    async def ori(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.responded(interaction, CompressionType.original)
