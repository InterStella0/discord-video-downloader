from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import functools
import re
import time
from abc import abstractmethod
from enum import StrEnum
from typing import Self, Callable, Awaitable, Any, Literal

import yt_dlp
from discord import app_commands
from discord.ext import commands

from core.errors import UserErrorUsage, ErrorProcessing
from core.types import Context, Interaction
from yt_dlp import YoutubeDL

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
        self._last_dispatch_time = 0

    @property
    def type(self):
        return FIND_CAMEL.sub(' ', self.__class__.__name__)

    def add_listener(self, call: DownloadListener):
        self.listeners.append(call)

    async def dispatch_progress(self, progress: Progress):
        async with asyncio.TaskGroup() as group:
            for listen in self.listeners:
                group.create_task(listen(progress))

    @abstractmethod
    async def download(self, file: str, file_type: FileType):
        pass

    @classmethod
    def from_url(cls, url: str):
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

    def _progress_hook(self, event_loop: asyncio.BaseEventLoop, d: dict[str, Any]):
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


    async def download(self, file: str, file_type: FileType):
        video_bitrate = '800k'
        audio_bitrate = '64k'
        event_loop = asyncio.get_running_loop()
        ydl_opts = {}
        if file_type is FileType.video:
            ydl_opts = {
                'outtmpl': file,
                'noplaylist': True,
                'quiet': True,
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best',
                'merge_output_format': 'mp4',

                'postprocessor_args': [
                    '-c:v', 'libx264',
                    '-b:v', video_bitrate,
                    '-preset', 'medium',
                    '-profile:v', 'main',
                    '-c:a', 'aac',
                    '-b:a', audio_bitrate,
                    '-movflags', '+faststart'
                ],
            }
        elif file_type is FileType.audio:
            if file.endswith(".mp3"):
                file, *_ = file.rpartition(".")
            ydl_opts = {
                'outtmpl': file,
                'noplaylist': True,
                'quiet': True,
                'format': 'bestaudio/best',
                'postprocessors': [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }
                ],
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
    pattern = re.compile(r'https?:\/\/(?:www\.)?twitch\.tv\/(?:[a-zA-Z0-9_]+\/)?clip\/([a-zA-Z0-9_-]+)')


class BiliBiliDownloader(YouTubeDownloader):
    pattern = re.compile(r'https?:\/\/(?:www\.)?bilibili\.com\/video\/(av\d+|BV[a-zA-Z0-9]+)\/?')


class FileType(StrEnum):
    video = "mp4"
    audio = "mp3"



PARSERS = [
    YouTubeDownloader,
    TikTokDownloader,
    TwitchClipsDownloader,
    TwitterDownloader,
    BiliBiliDownloader
]

