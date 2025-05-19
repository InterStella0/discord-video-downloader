import discord
from discord.ext import commands

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.client import StellaVideoBot
    Context = commands.Context[StellaVideoBot]
    Interaction = discord.Interaction[StellaVideoBot]
else:
    Context = commands.Context
    Interaction = discord.Interaction
