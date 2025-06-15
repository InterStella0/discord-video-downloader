from discord.ext import commands

class DisplayError(commands.CommandError):
    pass

class SomethingWentWrong(DisplayError):
    def __init__(self):
        super().__init__("Something went wrong. Please file a bug report for this error with the full traceback.")


class UserErrorUsage(DisplayError):
    pass

class TimeoutResponding(DisplayError):
    pass


class ErrorProcessing(DisplayError):
    pass


class UploadError(DisplayError):
    pass


class InvalidToken(RuntimeError):
    def __init__(self, message: str):
        super().__init__(
            f"{message}. Please refer to the guide: "
            f"https://github.com/InterStella0/discord-video-downloader/blob/main/docs/discord-setup.md#token-generation"
        )
