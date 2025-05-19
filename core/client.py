import os

import discord
from discord.ext import commands


class StellaVideoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(os.environ.get("DISCORD_MESSAGE_PREFIX", "!"), intents=intents)

    def starting(self):
        try:
            token = os.environ["DISCORD_TOKEN"]
        except KeyError:
            raise RuntimeError("Discord token is missing!")

        super().run(token)
