"""Ansi colour code inputted text"""

import os


class ANSI:
    GREY = "\033[90m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"

    @classmethod
    def colorise(cls, text, color):
        if os.getenv("NO_COLOR") is not None:
            return text
        return f"{color}{text}{cls.RESET}"

    @classmethod
    def green(cls, text):
        return cls.colorise(text, cls.GREEN)

    @classmethod
    def grey(cls, text):
        return cls.colorise(text, cls.GREY)

    @classmethod
    def bold(cls, text):
        return cls.colorise(text, cls.BOLD)
