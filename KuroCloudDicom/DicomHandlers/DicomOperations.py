import lithops
import numpy as np
import boto3
from .SubareaParameters import SubareaParameters
from pydicom import dcmread
import os
import math

def ComputeSubarea(params: SubareaParameters):
    import numpy as np
    import io
    import os
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
            pixel_spacing = dicom_file.PixelSpacing._list
            subarea = subarea + (pixel_array.shape[0] * pixel_spacing[0] * pixel_array.shape[1] * pixel_spacing[1])
        os.remove(tmp_name)
    return subarea
    

    # os.remove(tmp_name)
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
    tmp_name = '/tmp/temp'
    client.download_file(bucket_name, key, tmp_name)
    dicom_data = dcmread(tmp_name, force=True)
    os.remove(tmp_name)
    return dicom_data

def ComputeVolumenParallel(s3_config, s3_path, bucket_name, workers = 8, runtime='aarons28/kuro-dicom-v310:1.0'):    
    client = boto3.client(
            "s3",
            aws_access_key_id=s3_config["aws_access_key_id"],
            aws_secret_access_key=s3_config["aws_secret_access_key"],
            endpoint_url=s3_config['endpoint_url'],
            region_name=s3_config['region_name'])

    bucket_name_meta = bucket_name
    result = client.list_objects(Bucket=bucket_name_meta, Delimiter=s3_path)
    cloud_dicom_keys = result['Contents']

    # params = [SubareaParameters(file['Key'], bucket_name_meta, s3_config)
    #     for file in cloud_dicom_keys]
    keys = [file['Key'] for file in cloud_dicom_keys]
    params = []
    keySubLists = SplitListInSubList(keys,workers)
    for sublist in keySubLists:
        param = SubareaParameters(sublist, bucket_name_meta, s3_config)
        params.append(param)

    dicom_data = ObtainMetadata(keys[0], s3_config, bucket_name)
    pixel_spacing = dicom_data.PixelSpacing
    slice_thickness = dicom_data.SliceThickness
    spacing = []
    spacing.append(slice_thickness)
    spacing = spacing + pixel_spacing._list
    separation = np.prod(spacing)

    # Compute Volume
    p = lithops.FunctionExecutor(runtime=runtime)
    p.map_reduce(ComputeSubarea, params, SumSubareas, spawn_reducer=0)
    area = p.get_result()

    return area * separation

def ComputeVolumenSerial(s3_config, s3_path, bucket_name, runtime='aarons28/kuro-dicom-v310:1.0'):    
    return ComputeVolumenParallel(s3_config, s3_path, bucket_name, workers = 1, runtime='aarons28/kuro-dicom-v310:1.0')
    
    # client = boto3.client(
    #         "s3",
    #         aws_access_key_id=s3_config["aws_access_key_id"],
    #         aws_secret_access_key=s3_config["aws_secret_access_key"],
    #         endpoint_url=s3_config['endpoint_url'],
    #         region_name=s3_config['region_name'])

    # bucket_name_meta = bucket_name
    # result = client.list_objects(Bucket=bucket_name_meta, Delimiter=s3_path)
    # cloud_dicom_keys = result['Contents']
    # params = [SubareaParameters(file['Key'], bucket_name_meta, s3_config)
    #     for file in cloud_dicom_keys]

    # dicom_data = ObtainMetadata(params[0].key, s3_config, bucket_name)
    # pixel_spacing = dicom_data.PixelSpacing
    # slice_thickness = dicom_data.SliceThickness
    # spacing = []
    # spacing.append(slice_thickness)
    # spacing = spacing + pixel_spacing._list
    # separation = np.prod(spacing)
    # area = 0
    # for item in params:
    #     area = area + ComputeSubarea(item)
    # return area * separation

def SplitListInSubList(mylist, subListQuantity):
    subListSize = math.trunc(len(mylist) / subListQuantity)
    sublists = []
    start_element = 0
    for i in range(0, subListQuantity):
        if i != subListQuantity-1:
            sublists.append(mylist[start_element:start_element+subListSize])
        else:
            sublists.append(mylist[start_element:])
        start_element = start_element + subListSize
    return sublists