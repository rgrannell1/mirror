
import sys
from src.colours import Colour

class Log:
  @classmethod
  def info(self, text: str, clear: bool=False) -> None:
    """Print an info message to the terminal"""
    if clear:
      Log.clear()

    heading = Colour.red("[mirror 🪞 ]")
    print(f"{heading} {text}", file=sys.stderr)

  @classmethod
  def clear(self) -> None:
    """Clear the terminal screen"""
    print("\033c", end="", flush=True, file=sys.stderr)
