from typing import Optional, Tuple, TypedDict


class VideoEncodingConfig(TypedDict):
    bitrate: str
    width: Optional[int]
    height: Optional[int]


VideoEncoding = Tuple[str, VideoEncodingConfig]
