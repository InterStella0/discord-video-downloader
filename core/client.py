import asyncio
import json
import logging
import os

import aiohttp
import discord
from discord.ext import commands

from core.errors import InvalidToken, SomethingWentWrong, UploadError

VERSION = "0.0.3"


class StellaVideoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        self.startup_path: str = ".startup.json"
        super().__init__(os.environ.get("DISCORD_MESSAGE_PREFIX", "!"), intents=intents)
        self.session: aiohttp.ClientSession | None = None
        self.upload_url: str = os.environ.get("UPLOAD_URL", "https://tmpfiles.org/api/v1/upload")

    async def close(self) -> None:
        if self.session:
            await self.session.close()

        await super().close()

    async def upload_file(self, file_path: str):
        if self.session is None:
            self.session = aiohttp.ClientSession()

        with open(file_path, 'rb') as f:
            data = aiohttp.FormData()
            data.add_field('file', f, filename=file_path.split('/')[-1])

            async with self.session.post(self.upload_url, data=data) as response:
                result = await response.json()
                try:
                    if result['status'] != 'success':
                        raise UploadError("Couldn't upload to `tmpfiles.org`")
                    return result['data']['url']
                except Exception:
                    raise UploadError("Weird response from tmpfiles.org")

    def check_startup_once(self):
        current = None
        startup = self.startup_path
        if not os.path.exists(startup):
            with open(startup, "w") as f:
                json.dump({"VERSION": VERSION}, f, indent=4)
        else:
            with open(startup, "r") as f:
                content = json.load(f)
                current = content.get('VERSION', VERSION)

        return current != VERSION

    def update_versioning(self):
        with open(self.startup_path, "w") as f:
            json.dump({"VERSION": VERSION}, f, indent=4)

    async def after_ready(self):
        await self.wait_until_ready()
        link_auth = discord.utils.oauth_url(self.user.id, scopes=None)
        logging.info("Success!")
        logging.info(f"You can install your discord bot into your discord client by this link: {link_auth}")

    async def setup_hook(self) -> None:
        if self.check_startup_once():
            cmds = await self.tree.sync()
            logging.info(f"Synced {len(cmds)}")
            self.update_versioning()

        logging.info(f"Bot version {VERSION}")
        asyncio.create_task(self.after_ready())

    def starting(self):
        try:
            token = os.environ["DISCORD_TOKEN"]
        except KeyError:
            raise InvalidToken("Discord token is missing")

        try:
            super().run(token, root_logger=True)
        except discord.LoginFailure:
            raise InvalidToken(f'"{token}" is an invalid discord token') from None
