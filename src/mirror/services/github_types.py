"""Types for the GitHub manifest publish service."""

# album id -> serialised triples belonging to that album (its own, plus its photos')
type AlbumFingerprints = dict[str, set[str]]

# added, updated, and removed album ids, in that order
type AlbumChanges = tuple[list[str], list[str], list[str]]
