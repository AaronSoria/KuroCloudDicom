"""Volume computation directly over raw DICOM files stored in S3-compatible storage, using Lithops."""
from __future__ import annotations

import io
import os
from typing import Any, Iterable, Mapping

import boto3
import lithops
import numpy as np
import pydicom
from pydicom import dcmread

from .._s3utils import ListKeys, SplitS3Path
from ..CloudDicomHandlers.CloudDicomOperations import SplitListInSubList
from .SubareaParameters import SubareaParameters


def ComputeSubarea(params: SubareaParameters) -> float:
    """Sum the physical area (``rows * cols * PixelSpacing``) of every DICOM file in ``params.keys``.

    Runs on a Lithops worker; each file is downloaded to ``/tmp/temp`` and read with GDCM.
    Files GDCM cannot read are skipped.
    """
    import gdcm

    client = boto3.client(
            "s3",
            aws_access_key_id=params.s3_config["aws_access_key_id"],
            aws_secret_access_key=params.s3_config["aws_secret_access_key"],
            endpoint_url=params.s3_config['endpoint_url'],
            region_name=params.s3_config['region_name'])

    subarea = 0
    tmp_name = '/tmp/temp'
    for key in params.keys:
        client.download_file(params.bucket_name, key, tmp_name)
        dicom_file = dcmread(tmp_name, force=True)
        reader = gdcm.ImageReader()
        reader.SetFileName(tmp_name)
        if reader.Read():
            pixel_buffer = reader.GetImage().GetBuffer()
            pixel_array = np.frombuffer(pixel_buffer.encode(errors="replace"), dtype=np.uint16)
            image_dims = reader.GetImage().GetDimensions()
            pixel_array = pixel_array.reshape(image_dims)
            pixel_spacing = list(dicom_file.PixelSpacing)
            subarea = subarea + (pixel_array.shape[0] * pixel_spacing[0] * pixel_array.shape[1] * pixel_spacing[1])
        os.remove(tmp_name)
    return subarea

def SumSubareas(results: Iterable[float]) -> float:
    """Reducer for Lithops ``map_reduce``: sum the partial areas."""
    total = 0
    for map_result in results:
        total = total + map_result
    return total

def ObtainMetadata(key: str, s3_config: Mapping[str, Any], bucket_name: str) -> pydicom.Dataset:
    """Download the DICOM object ``key`` from ``bucket_name`` and return it as a pydicom ``Dataset``."""
    client = boto3.client(
            "s3",
            aws_access_key_id=s3_config["aws_access_key_id"],
            aws_secret_access_key=s3_config["aws_secret_access_key"],
            endpoint_url=s3_config['endpoint_url'],
            region_name=s3_config['region_name'])
    # Read in memory: this runs on the caller's machine, where /tmp may not exist (Windows)
    response = client.get_object(Bucket=bucket_name, Key=key)
    return dcmread(io.BytesIO(response['Body'].read()), force=True)

def ComputeVolumenParallel(s3_config: Mapping[str, Any], s3_path: str, bucket_name: str, workers: int = 8,
                           runtime: str = 'aarons28/kuro-dicom-v310:1.0') -> float:
    """Compute the volume covered by the raw DICOM files under a prefix of ``bucket_name``.

    The volume is the sum of every slice's ``rows * cols * PixelSpacing`` multiplied by the
    ``SliceThickness`` of the first file listed.

    Args:
        s3_config: Mapping with ``aws_access_key_id``, ``aws_secret_access_key``, ``endpoint_url``
            and ``region_name``. It is passed to the Lithops workers.
        s3_path: Location of the files, as returned by ``DicomDataManager.S3Path()``. Only its
            key prefix is used. Every object under the prefix is treated as a DICOM file.
        bucket_name: Bucket holding the DICOM files.
        workers: Maximum number of Lithops tasks the keys are split across.
        runtime: Lithops runtime (container image) to execute the workers in.

    Returns:
        The volume in the units of the DICOM spacing attributes (normally mm^3).

    Raises:
        ValueError: If no objects are found under the prefix, or ``workers < 1``.
    """
    client = boto3.client(
            "s3",
            aws_access_key_id=s3_config["aws_access_key_id"],
            aws_secret_access_key=s3_config["aws_secret_access_key"],
            endpoint_url=s3_config['endpoint_url'],
            region_name=s3_config['region_name'])

    bucket_name_meta = bucket_name
    _, prefix = SplitS3Path(s3_path)
    keys = ListKeys(client, bucket_name_meta, prefix)
    if not keys:
        raise ValueError(f"No DICOM files found in bucket {bucket_name_meta!r} under prefix {prefix!r}")
    params = []
    keySubLists = SplitListInSubList(keys,workers)
    for sublist in keySubLists:
        param = SubareaParameters(sublist, bucket_name_meta, s3_config)
        params.append(param)

    # ComputeSubarea already scales by pixel spacing, so only the slice thickness is left to apply
    dicom_data = ObtainMetadata(keys[0], s3_config, bucket_name)
    separation = float(dicom_data.SliceThickness)

    # Compute Volume
    p = lithops.FunctionExecutor(runtime=runtime)
    p.map_reduce(ComputeSubarea, params, SumSubareas, spawn_reducer=0)
    area = p.get_result()

    return area * separation

def ComputeVolumenSerial(s3_config: Mapping[str, Any], s3_path: str, bucket_name: str,
                         runtime: str = 'aarons28/kuro-dicom-v310:1.0') -> float:
    """Same as :func:`ComputeVolumenParallel` with a single Lithops task."""
    return ComputeVolumenParallel(s3_config, s3_path, bucket_name, workers = 1, runtime=runtime)
