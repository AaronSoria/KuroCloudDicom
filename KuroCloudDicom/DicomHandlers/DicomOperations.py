import io
import os

import boto3
import lithops
import numpy as np
from pydicom import dcmread

from .._s3utils import ListKeys, SplitS3Path
from ..CloudDicomHandlers.CloudDicomOperations import SplitListInSubList
from .SubareaParameters import SubareaParameters


def ComputeSubarea(params: SubareaParameters):
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

def SumSubareas(results):
    total = 0
    for map_result in results:
        total = total + map_result
    return total

def ObtainMetadata(key, s3_config, bucket_name):
    client = boto3.client(
            "s3",
            aws_access_key_id=s3_config["aws_access_key_id"],
            aws_secret_access_key=s3_config["aws_secret_access_key"],
            endpoint_url=s3_config['endpoint_url'],
            region_name=s3_config['region_name'])
    # Read in memory: this runs on the caller's machine, where /tmp may not exist (Windows)
    response = client.get_object(Bucket=bucket_name, Key=key)
    return dcmread(io.BytesIO(response['Body'].read()), force=True)

def ComputeVolumenParallel(s3_config, s3_path, bucket_name, workers = 8, runtime='aarons28/kuro-dicom-v310:1.0'):    
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

def ComputeVolumenSerial(s3_config, s3_path, bucket_name, runtime='aarons28/kuro-dicom-v310:1.0'):    
    return ComputeVolumenParallel(s3_config, s3_path, bucket_name, workers = 1, runtime=runtime)