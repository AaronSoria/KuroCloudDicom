"""Helpers that split DICOM pixel data into chunks and extract collection metadata."""
from __future__ import annotations

import uuid
from typing import Any

import gdcm
import numpy as np
import pydicom
from pydicom import dcmread
from scipy.io import savemat

from .ChunkedDicomData import ChunkedDicomData


class Preprocessor:
    """Split images into ``dicom_chunks`` pieces along their second axis and build metadata dicts."""

    __dicom_chunks = 0

    def __init__(self, dicom_chunks: int) -> None:
        self.__dicom_chunks = dicom_chunks

    def __CreateSubmatrix(self, matrix, chunks):
        return np.array_split(matrix, chunks, axis=1)

    def GenerateExtention(self, name: str, number: int) -> str | None:
        """Return ``name`` with a zero-padded three-digit chunk suffix, e.g. ``img.dcm.007``.

        Returns ``None`` for ``number >= 1000``.
        """
        extention = str(number)
        if len(extention) == 1:
            return name+'.00'+extention
        if len(extention) == 2:
            return name+'.0'+extention
        if len(extention) == 3:
            return name+'.'+extention

    def SaveChunkedDicomAsMat(self, chunked_dicom: ChunkedDicomData) -> str:
        """Save a chunk and its image position as a MATLAB file in the current directory; return its name."""
        temp_file_name = str(uuid.uuid4())
        mdic = {"pixel_array": chunked_dicom.matrix,
                "image_position": chunked_dicom.image_position }
        savemat(temp_file_name, mdic)
        return temp_file_name

    def GenerateDicomMetadata(self, file_path: str) -> dict[str, Any]:
        """Read the DICOM file at ``file_path`` and return its metadata (see :meth:`GenerateDicomMetadataAsDict`)."""
        dicom_dataset = dcmread(file_path, force=True)
        mdic = {
            "pixel_spacing": list(dicom_dataset.PixelSpacing),
            "slice_thickness": dicom_dataset.SliceThickness,
            "image_position":list(dicom_dataset.ImagePositionPatient),
            "image_orientation": list(dicom_dataset.ImageOrientationPatient),
            "number_of_chunks_per_file": self.__dicom_chunks }
        return mdic

    def GenerateDicomMetadataAsDict(self, dicom_dataset: pydicom.Dataset) -> dict[str, Any]:
        """Return pixel spacing, slice thickness, image position/orientation and chunks per file."""
        mdic = {
            "pixel_spacing": list(dicom_dataset.PixelSpacing),
            "slice_thickness": dicom_dataset.SliceThickness,
            "image_position":list(dicom_dataset.ImagePositionPatient),
            "image_orientation": list(dicom_dataset.ImageOrientationPatient),
            "number_of_chunks_per_file": self.__dicom_chunks }
        return mdic

    def SplitDicomInChunksAsMat(self, file_path: str) -> list[ChunkedDicomData]:
        """Read the DICOM file at ``file_path`` with GDCM and split its pixels into chunks.

        Raises:
            ValueError: If GDCM cannot read the pixel data.
        """
        dicom_dataset = pydicom.dcmread(file_path, force=True)
        reader = gdcm.ImageReader()
        reader.SetFileName(file_path)
        if not reader.Read():
            raise ValueError(f"GDCM could not read pixel data from {file_path!r}")
        pixel_buffer = reader.GetImage().GetBuffer()
        pixel_array = np.frombuffer(pixel_buffer.encode(errors="replace"), dtype=np.uint16)
        image_dims = reader.GetImage().GetDimensions()
        pixel_array = pixel_array.reshape(image_dims)
        submatrix_collection = self.__CreateSubmatrix(pixel_array, self.__dicom_chunks)
        chunked_collection = []
        for submatrix in submatrix_collection:
            chunked_collection.append(ChunkedDicomData(image_position=list(dicom_dataset.ImagePositionPatient),
            matrix=submatrix))
        return chunked_collection

    def SplitDicomInChunks(self, pixel_array: np.ndarray) -> list[np.ndarray]:
        """Split ``pixel_array`` into ``dicom_chunks`` arrays along its second axis."""
        submatrix_collection = self.__CreateSubmatrix(pixel_array, self.__dicom_chunks)
        chunked_collection = []
        for submatrix in enumerate(submatrix_collection):
            chunked_collection.append(submatrix[1])
        return chunked_collection
