"""Constant values used throughout the application."""

from __future__ import annotations

from typing import Any

MOSAIC_WIDTH = 2
MOSAIC_HEIGHT = 2
THUMBNAIL_WIDTH = 400
THUMBNAIL_HEIGHT = 400
DATE_FORMAT = "%Y:%m:%d %H:%M:%S"

# Branch the website manifest is published to on GitHub.
WEBSITE_BRANCH = "main"

# Subject prefix that marks an album triple in the CURIE-compressed manifest.
ALBUM_SUBJECT_PREFIX = "[i:album:"

# The only manifest files the GitHub publish step may delete or copy.
# Anything else in manifest/ is left untouched.
MANIFEST_PATTERNS = (
    "env.json",
    "stats.*.json",
    "triples.*.json",
    "tribbles.*.txt",
    "tribbles-expanded.*.txt",
    "atom/*.xml",
)

# Built website files that embed the publication id. They must ship in the
# same commit as the manifest, or the deployed site references deleted files.
WEBSITE_ARTIFACT_PATTERNS = (
    "index.html",
    "sw.js",
    "dist/js/*",
)

# Most album names listed in a derived commit message before "and N more".
COMMIT_MESSAGE_NAME_LIMIT = 3

# Lines of captured build output kept when a website build step fails.
BUILD_OUTPUT_TAIL_LINES = 30

# Sanity bounds on the published country count; outside this range the stats are broken.
STATS_MIN_COUNTRIES = 10
STATS_MAX_COUNTRIES = 50

# Contrasting-grey: true midpoint of the 0-255 lightness band.
LIGHTNESS_MIDPOINT = 128

# Contrasting-grey: minimum lightness separation (~43 L*) guaranteeing visible contrast.
CONTRAST_DELTA = 110

# URN prefix for albums, as referenced by trips in things.toml.
ALBUM_URN_PREFIX = "urn:ró:album:"

# Markdown metadata tables: column headers for albums.md.
ALBUM_TABLE_HEADERS = ("embedding", "title", "permalink", "country", "summary")

# Markdown metadata tables: shared column headers for photos.md and videos.md.
MEDIA_TABLE_HEADERS = (
    "embedding",
    "name",
    "genre",
    "rating",
    "places",
    "description",
    "subjects",
    "cover",
)

# Minimum pipe-separated cells for a parseable albums.md row.
ALBUM_ROW_MIN_CELLS = 5

# Minimum pipe-separated cells for a parseable photos.md / videos.md row.
MEDIA_ROW_MIN_CELLS = 8

# Albums with this folder name are hidden: photos publish, but no album page or albums.md row.
MISCELLANEOUS_ALBUM_NAME = "Miscellaneous"

# Shared album id given to every Miscellaneous album's photos.
MISCELLANEOUS_ALBUM_ID = "miscellaneous"

# Attr-Exif property associations
# these are the exif attributes we care about
EXIF_ATTR_ASSOCIATIONS = {
    "DateTimeOriginal": "created_at",
    "FNumber": "f_stop",
    "FocalLengthIn35mmFilm": "focal_length",
    "Model": "model",
    "ExposureTime": "exposure_time",
    "ISOSpeedRatings": "iso",
    "ExifImageWidth": "width",
    "ExifImageHeight": "height",
}

SUPPORTED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG")

MOSAIC_ENCODINGS = {
    "thumbnail_mosaic": {"width": 2, "height": 2},
    "mosaic_banner": {"width": 10, "height": 10},
}

# How should we encode our photos? Currently uses
# - thumbnail: a lossy thumbnail for fast loading
# - full_image_lossless: a lossless webp image for high quality
# - full_image_png: a png image so I can share images to Signal and other non-webp apps
IMAGE_ENCODINGS = {
    "thumbnail_lossy": {
        "format": "avif",
        "quality": 90,
        "subsampling": "4:4:4",
        "width": THUMBNAIL_WIDTH,
        "height": THUMBNAIL_HEIGHT,
    },
    # WebP thumbnail for TUI viewers that don't support avif
    "thumbnail_webp": {
        "format": "webp",
        "lossless": True,
        "width": THUMBNAIL_WIDTH,
        "height": THUMBNAIL_HEIGHT,
    },
    "full_image_lossless": {
        "format": "webp",
        "lossless": True,
    },
    "full_image_png": {
        "format": "png",
        "quality": 100,
        "method": 6,
    },
    "mid_image_lossy": {
        "format": "webp",
        "quality": 85,
        "method": 6,
        "width": 1444,
        "height": 1084,
    },
    "mid_image_png": {
        "format": "png",
        "quality": 100,
        "method": 6,
        "width": 1444,
        "height": 1084,
    },
    "social_card": {"format": "webp", "quality": 85, "method": 6, "width": 1200, "height": 630},
    "preview_jpeg": {"format": "jpeg", "quality": 80, "width": 800, "height": 600},
    # High-res hero for full-width page banners (about/albums). Larger than
    # mid_image so it stays sharp on wide/4K displays; only generated for the
    # banner sources in things.toml (see SELECTIVE_ROLE_FILTERS).
    "banner": {
        "format": "webp",
        "quality": 80,
        "method": 6,
        "width": 2560,
        "height": 1920,
    },
}

# Source files used as full-width page banners. The `banner` rendition above is
# only generated for these, so we don't produce a 2560px hero for every photo.
# How should we encode our videos? Currently uses unscaled + various
# scaling of libx264 encoding
VIDEO_ENCODINGS: list[Any] = [
    (
        "video_libx264_unscaled",
        {
            "bitrate": "30M",
            "width": None,
            "height": None,
        },
    ),
    (
        "video_libx264_1080p",
        {
            "bitrate": "5000k",
            "width": 1920,
            "height": 1080,
        },
    ),
    (
        "video_libx264_720p",
        {
            "bitrate": "2500k",
            "width": 1280,
            "height": 720,
        },
    ),
    (
        "video_libx264_480p",
        {
            "bitrate": "1000k",
            "width": 854,
            "height": 480,
        },
    ),
]

FULL_SIZED_VIDEO_ROLE = "video_libx264_unscaled"

VIDEO_THUMBNAIL_FORMAT = ".webp"
VIDEO_CONTENT_TYPE = "video/mp4"
URN_PREFIX = "urn:ró:"


class KnownRelations:
    COUNTRY = "country"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"
    NAME = "name"
    WIKIDATA = "wikidata"
    WIKIPEDIA = "wikipedia"
    BIRDWATCH_URL = "birdwatch_url"
    SHORT_NAME = "short_name"
    FEATURE = "feature"
    IN = "in"
    UNESCO_ID = "unesco_id"


# things.toml keys kept for reference but never published as triples
UNPUBLISHED_THINGS_RELATIONS = frozenset({"near"})

# Subject detection: the GroundingDINO checkpoint used to find subject boxes.
DETECTION_MODEL_ID = "IDEA-Research/grounding-dino-base"

# Subject detection: minimum GroundingDINO confidence for a box to be stored.
DETECTION_CONFIDENCE_THRESHOLD = 0.35

# Subject detection: torch threads per worker process. Keeps one inference from
# taking every core, so parallel detection jobs share the CPU budget.
DETECTION_TORCH_THREADS = 4

# Subject detection: at most this many detection jobs run at once.
DETECTION_CONCURRENCY_LIMIT = 15

# Cover selection: a subject filling under this share of the image is too small to cover.
COVER_MIN_SUBJECT_FILL = 0.05

# Subject detection: pause before each photo while system CPU use is above this.
DETECTION_CPU_MAX_PERCENT = 80.0

# Subject detection: pause before each photo while system memory use is above this.
DETECTION_MEMORY_MAX_PERCENT = 80.0

# Subject detection: URN types whose raw word is a poor detection prompt.
# GroundingDINO accepts several prompts split by ".". Types not listed use the raw type word.
DETECTION_PROMPT_OVERRIDES = {
    "arthropod": "insect. spider. crab.",
    "cnidaria": "jellyfish",
    "ctenophore": "jellyfish",
    "plane": "airplane",
    "spacecraft": "rocket. spacecraft.",
}


class KnownTypes:
    GEONAME = "geoname"


class KnownWikiProperties:
    TAXON_NAME = "P225"
