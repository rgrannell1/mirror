"""Ansi colour code inputted text"""

import os


class ANSI:
    GREY = "\033[90m"
    RESET = "\033[0m"

    @classmethod
    def colorise(cls, text, color):
        if os.getenv("NO_COLOR") is not None:
            return text
        return f"{color}{text}{cls.RESET}"

    @classmethod
    def grey(cls, text):
        return cls.colorise(text, cls.GREY)
