from __future__ import annotations

from typing import Any, Mapping, Sequence


class SubareaParameters:
    """Input of one Lithops task: the DICOM keys to read and how to reach them."""

    keys = None
    bucket_name = ""
    s3_config = ""

    def __init__(self, keys: Sequence[str], bucket_name: str, s3_config: Mapping[str, Any]) -> None:
        self.keys = keys
        self.bucket_name = bucket_name
        self.s3_config = s3_config
