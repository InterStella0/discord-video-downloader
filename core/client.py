import asyncio
import json
import logging
import os

import discord
from discord.ext import commands

from core.errors import InvalidToken

VERSION = "0.0.2"


class StellaVideoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        self.startup_path = ".startup.json"
        super().__init__(os.environ.get("DISCORD_MESSAGE_PREFIX", "!"), intents=intents)

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
