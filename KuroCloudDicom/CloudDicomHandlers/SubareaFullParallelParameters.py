from __future__ import annotations

from typing import Any, Mapping, Sequence


class SubareaFullParallelParameters:
    """Input of one ``ObtainArea`` call: a single chunk key and how to reach it."""

    s3_config = None
    pixel_spacing = None
    bucket_name = ""
    key = ""

    def __init__(self, s3_config: Mapping[str, Any], pixel_spacing: Sequence[float], bucket_name: str,
                 key: str) -> None:
        self.s3_config = s3_config
        self.pixel_spacing = pixel_spacing
        self.bucket_name = bucket_name
        self.key = key
