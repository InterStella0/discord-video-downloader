import json
import logging
import os

import discord
from discord.ext import commands


VERSION = "0.0.1"


class StellaVideoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(os.environ.get("DISCORD_MESSAGE_PREFIX", "!"), intents=intents)

    def check_startup_once(self):
        current = None
        startup = ".startup.json"
        if not os.path.exists(startup):
            with open(startup, "w") as f:
                json.dump({"VERSION": VERSION}, f, indent=4)
        else:
            with open(startup, "r") as f:
                content = json.load(f)
                current = content.get('VERSION', VERSION)

        return current != VERSION

    async def setup_hook(self) -> None:
        if self.check_startup_once():
            cmds = await self.tree.sync()
            logging.info(f"Synced {len(cmds)}")

        logging.info(f"Bot version {VERSION}")

    def starting(self):
        try:
            token = os.environ["DISCORD_TOKEN"]
        except KeyError:
            raise RuntimeError("Discord token is missing!")

        super().run(token, root_logger=True)
