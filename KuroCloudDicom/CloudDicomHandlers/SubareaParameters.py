from __future__ import annotations

from typing import Any, Mapping, Sequence


class SubareaParameters:
    """Input of one Lithops task: the chunk keys to read and how to reach them."""

    keys = None
    pixel_spacing = None
    bucket_name = ""
    s3_config = ""

    def __init__(self, keys: Sequence[str], pixel_spacing: Sequence[float], bucket_name: str,
                 s3_config: Mapping[str, Any]) -> None:
        self.keys = keys
        self.pixel_spacing = pixel_spacing
        self.bucket_name = bucket_name
        self.s3_config = s3_config
