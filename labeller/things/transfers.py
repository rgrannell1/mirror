"""Parse [[transfers]] from things.toml into TransferRow objects."""

from dataclasses import dataclass

from .loader import load_raw

TRANSFER_MODES = ("train", "plane", "bus", "ferry", "car")


@dataclass
class TransferRow:
    transfer_id: str
    source: str
    destination: str
    mode: str


def _parse_entry(entry: dict) -> TransferRow | None:
    try:
        return TransferRow(
            transfer_id=entry["id"],
            source=entry["source"],
            destination=entry["destination"],
            mode=entry["mode"],
        )
    except KeyError:
        return None


def load_transfers() -> list[TransferRow]:
    data = load_raw()
    return [
        row
        for entry in data.get("transfers", [])
        if (row := _parse_entry(entry)) is not None
    ]
