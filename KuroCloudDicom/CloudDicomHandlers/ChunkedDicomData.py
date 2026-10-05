from __future__ import annotations

from typing import Any


class ChunkedDicomData:
    """One chunk of a DICOM image together with the image's ``ImagePositionPatient``."""

    matrix = None
    image_position = None

    def __init__(self, matrix: Any, image_position: Any) -> None:
        self.matrix = matrix
        self.image_position = image_position
