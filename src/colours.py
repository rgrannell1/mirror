class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


class Colour:
    """Construct ANSI colour strings for terminal output."""

    @classmethod
    def blue(cls, text: str) -> str:
        return f"{bcolors.OKBLUE}{text}{bcolors.ENDC}"

    @classmethod
    def cyan(cls, text: str) -> str:
        return f"{bcolors.OKCYAN}{text}{bcolors.ENDC}"

    @classmethod
    def green(cls, text: str) -> str:
        return f"{bcolors.OKGREEN}{text}{bcolors.ENDC}"

    @classmethod
    def red(cls, text: str) -> str:
        return f"{bcolors.FAIL}{text}{bcolors.ENDC}"

    @classmethod
    def yellow(cls, text: str) -> str:
        return f"{bcolors.WARNING}{text}{bcolors.ENDC}"

    @classmethod
    def bold(cls, text: str) -> str:
        return f"{bcolors.BOLD}{text}{bcolors.ENDC}"
