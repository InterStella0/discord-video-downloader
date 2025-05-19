from discord.ext import commands

class DisplayError(commands.CommandError):
    pass

class SomethingWentWrong(DisplayError):
    def __init__(self):
        super().__init__("Something went wrong. Please file a bug report for this error with the full traceback.")


class UserErrorUsage(DisplayError):
    pass


class ErrorProcessing(DisplayError):
    pass


class UploadError(DisplayError):
    pass
