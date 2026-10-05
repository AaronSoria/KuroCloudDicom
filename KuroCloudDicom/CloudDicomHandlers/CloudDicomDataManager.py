"""Upload DICOM collections to S3-compatible storage as chunked CloudDicom objects."""
from __future__ import annotations

import io
import json
import os
import pickle
import tempfile
import zlib
from contextlib import contextmanager
from typing import Any, BinaryIO, Iterable, Iterator, Mapping, Protocol

import boto3
import gdcm
import numpy as np
import pydicom

from .Preprocessor import Preprocessor


class DicomUpload(Protocol):
    """An uploaded DICOM file: anything with a ``name`` and a readable binary ``file``.

    Starlette/FastAPI ``UploadFile`` objects satisfy this.
    """

    name: str
    file: BinaryIO


@contextmanager
def _TemporaryDicomFile(dicom_dataset: pydicom.Dataset) -> Iterator[str]:
    # NamedTemporaryFile cannot be reopened by name on Windows while open, so use a closed temp file
    fd, path = tempfile.mkstemp(suffix=".dcm")
    os.close(fd)
    try:
        pydicom.dcmwrite(path, dicom_dataset)
        yield path
    finally:
        os.remove(path)

class CloudDicomDataManager:
    """Preprocess DICOM files into CloudDicom chunks and upload them, plus collection metadata.

    Chunks and ``metadata.json`` are stored in the bucket ``<bucket_name>.meta`` under ``<prefix_key>/``.
    Both ``<bucket_name>`` and ``<bucket_name>.meta`` must already exist.

    Args:
        s3_config: Mapping with ``aws_access_key_id``, ``aws_secret_access_key``, ``endpoint_url``
            and ``region_name``.
        bucket_name: Base bucket name.
        dicom_chunks: Number of chunks each image is split into (along its second axis).
        prefix_key: Key prefix (folder) for this collection.
        runtime: Stored for API compatibility; not used by this class.
    """

    __client = None
    __preprocessor = None
    __bucket_name = ""
    __bucket_name_meta = ""
    __prefix_key = ""
    __runtime = ""

    def __init__(self, s3_config: Mapping[str, Any], bucket_name: str, dicom_chunks: int = 2, prefix_key: str = "",
                 runtime: str = 'aarons28/kuro-dicom-v310:1.0') -> None:
        self.__client = boto3.client(
            "s3",
            aws_access_key_id=s3_config["aws_access_key_id"],
            aws_secret_access_key=s3_config["aws_secret_access_key"],
            endpoint_url=s3_config['endpoint_url'],
            region_name=s3_config['region_name'])
        self.__preprocessor = Preprocessor(dicom_chunks = dicom_chunks)
        self.__bucket_name = bucket_name
        self.__bucket_name_meta = bucket_name + ".meta"
        self.__prefix_key = prefix_key
        self.__runtime = runtime

    def ObtainMetadata(self) -> dict[str, Any]:
        """Download and parse ``<prefix_key>/metadata.json`` from the ``.meta`` bucket."""
        key = self.__prefix_key+'/metadata.json'
        response = self.__client.get_object(Bucket=self.__bucket_name_meta, Key=key)
        return json.loads(response['Body'].read())

    def S3Path(self) -> str:
        """Return the collection location as ``s3:///<bucket_name>.meta/<prefix_key>/``."""
        return 's3:///'+self.__bucket_name_meta+'/'+self.__prefix_key+'/'

    def UploadDicomCollection(self, files: Iterable[DicomUpload], output_format: int = 1) -> None:
        """Split every DICOM file into chunks, upload them, then upload ``metadata.json``.

        Each chunk is stored as ``<prefix_key>/<file.name>.NNN``. The metadata (pixel spacing,
        slice thickness, image position/orientation, chunks per file) is taken from the last file.

        Args:
            files: Uploaded DICOM files (see :class:`DicomUpload`).
            output_format: ``1`` stores zlib-compressed pickled uint8 arrays (the format read by
                ``ComputeVolumenFullParallel``); ``2`` stores uncompressed pickled arrays.

        Raises:
            ValueError: If ``files`` is empty.
        """
        files = list(files)
        if not files:
            raise ValueError("files must contain at least one DICOM file")
        for file in files:
            file_name = file.name
            dicom_dataset = pydicom.dcmread(file.file, force=True)
            with _TemporaryDicomFile(dicom_dataset) as temp_file_name:
                reader = gdcm.ImageReader()
                reader.SetFileName(temp_file_name)
                pixel_array = None
                if reader.Read():
                    pixel_buffer = reader.GetImage().GetBuffer()
                    pixel_array = np.frombuffer(pixel_buffer.encode("utf-8", errors="surrogateescape"), dtype=np.uint16)
                    image_dims = reader.GetImage().GetDimensions()
                    pixel_array = pixel_array.reshape(image_dims)
                    if output_format == 1:
                        self.UploadDicomAsCustom(pixel_array, file_name)
                    if output_format == 2:
                        self.UploadDicomAsNp(pixel_array, file_name)

        meta = self.__preprocessor.GenerateDicomMetadataAsDict(dicom_dataset)
        metadata_file_name = "metadata.json"
        metaJson = json.dumps(meta)
        self.__client.put_object(Body=metaJson, Key=self.__prefix_key+"/"+metadata_file_name,
            Bucket=self.__bucket_name_meta)

    def UploadDicomAsNp(self, pixel_array: np.ndarray, file_name: str) -> None:
        """Upload ``pixel_array`` split into chunks, each as an uncompressed pickled array."""
        chunk_collection = self.__preprocessor.SplitDicomInChunks(pixel_array)
        i = 0
        for chunk in chunk_collection:
            key = self.__preprocessor.GenerateExtention(file_name,i)
            subMatrix_data = io.BytesIO()
            pickle.dump(chunk, subMatrix_data)
            subMatrix_data.seek(0)
            self.__client.put_object(Body=subMatrix_data,Key=self.__prefix_key+"/"+key, Bucket=self.__bucket_name_meta)
            i = i + 1

    def SplitDicomFileAsJson(self, file_path: str) -> list[str]:
        """Same as :meth:`SplitDicomFileAsMat` (kept for compatibility; it never produced JSON)."""
        # Despite the name, this always produced .mat files; it passed a path where an array was expected.
        return self.SplitDicomFileAsMat(file_path)

    def UploadDicomAsMat(self, file: DicomUpload) -> None:
        """Upload one DICOM file as MATLAB ``.mat`` chunks plus ``metadata.json``, and the original file.

        Chunks and metadata go to the ``.meta`` bucket; the original file goes to ``bucket_name``.
        This format is not read by ``ComputeVolumenFullParallel``.
        """
        dicom_dataset = pydicom.dcmread(file.file, force=True)
        with _TemporaryDicomFile(dicom_dataset) as temp_file_name:
            meta = self.__preprocessor.GenerateDicomMetadata(temp_file_name)
            self.__client.put_object(Body=json.dumps(meta),
                Key=self.__prefix_key+"/metadata.json",
                Bucket=self.__bucket_name_meta)

            file_colection_paths = self.SplitDicomFileAsMat(temp_file_name)
            i = 0
            for file_path in file_colection_paths:
                key = self.__preprocessor.GenerateExtention(file.name,i)
                self.__client.upload_file(file_path,
                    self.__bucket_name_meta,
                    self.__prefix_key+"/"+key)
                i = i + 1
                os.remove(file_path)

            # dcmread consumed the stream; rewind so the original file is uploaded in full
            file.file.seek(0)
            self.__client.put_object(Bucket=self.__bucket_name,
                    Body=file.file,
                    Key=self.__prefix_key+"/"+file.name)

    def UploadDicomAsCustom(self, pixel_array: np.ndarray, file_name: str) -> None:
        """Upload ``pixel_array`` split into chunks, each as a zlib-compressed pickled uint8 array.

        Values are rescaled with ``value / 4095 * 255``, which assumes 12-bit pixel data.
        """
        chunk_collection = self.__preprocessor.SplitDicomInChunks(pixel_array)
        i = 0
        for chunk in chunk_collection:
            key = self.__preprocessor.GenerateExtention(file_name,i)
            compressed_chunk = (chunk / 4095 * 255).astype(np.uint8)
            # contiguous_array = np.ascontiguousarray(compressed_chunk)
            # aux_chunk_compress = zlib.compress(contiguous_array.tobytes(), level=9)
            subMatrix_data = io.BytesIO()
            pickle.dump(compressed_chunk, subMatrix_data)
            subMatrix_data.seek(0)
            result = zlib.compress(subMatrix_data.getvalue(), level=9)
            self.__client.put_object(Body=result,Key=self.__prefix_key+"/"+key, Bucket=self.__bucket_name_meta)
            i = i + 1

    def SplitDicomFileAsMat(self, file_path: str) -> list[str]:
        """Split the DICOM file at ``file_path`` and save each chunk as a ``.mat`` file in the current directory.

        Returns:
            The paths of the written files; the caller is responsible for removing them.
        """
        result = self.__preprocessor.SplitDicomInChunksAsMat(file_path)
        file_colection = [ self.__preprocessor.SaveChunkedDicomAsMat(item) for item in result]
        return file_colection
