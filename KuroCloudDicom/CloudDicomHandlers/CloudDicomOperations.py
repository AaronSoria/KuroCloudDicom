from .SubareaParameters import SubareaParameters
from .SubareaFullParallelParameters import SubareaFullParallelParameters
import lithops
import numpy as np
import boto3
import io
import pickle
import math

def ComputeSubarea(params: SubareaParameters):
    import pickle    
    import boto3
    import io
    import os
    import logging
    import zlib
    import numpy as np

    client = boto3.client(
            "s3",
            aws_access_key_id=params.s3_config["aws_access_key_id"],
            aws_secret_access_key=params.s3_config["aws_secret_access_key"],
            endpoint_url=params.s3_config['endpoint_url'],
            region_name=params.s3_config['region_name'])

    subarea = 0
    for key in params.keys:
        response = client.get_object(Bucket=params.bucket_name, Key=key)
        compressed_data = response['Body'].read()
        uncompressed_data = zlib.decompress(compressed_data)
        result = io.BytesIO(uncompressed_data)
        pixel_array = pickle.load(result)
        subarea = subarea + (pixel_array.shape[0] * params.pixel_spacing[0] * pixel_array.shape[1] * params.pixel_spacing[1])
    return subarea

def ComputeSubareaFullParallel(params: SubareaParameters):
    import pickle    
    import boto3
    import io
    import os
    import logging
    import multiprocessing

    parameters = [SubareaFullParallelParameters(params.s3_config, params.pixel_spacing, params.bucket_name, item ) for item in params.keys]
    num_cores = multiprocessing.cpu_count()
    with multiprocessing.Pool(num_cores) as p:
        results = p.map(ObtainArea, parameters)
        return sum(results)

def ObtainArea(parameters: SubareaFullParallelParameters):
    import zlib
    import numpy as np
    client = boto3.client(
            "s3",
            aws_access_key_id=parameters.s3_config["aws_access_key_id"],
            aws_secret_access_key=parameters.s3_config["aws_secret_access_key"],
            endpoint_url=parameters.s3_config['endpoint_url'],
            region_name=parameters.s3_config['region_name'])

    response = client.get_object(Bucket=parameters.bucket_name, Key=parameters.key)
    compressed_data = response['Body'].read()
    uncompressed_data = zlib.decompress(compressed_data)
    result = io.BytesIO(uncompressed_data)
    pixel_array = pickle.load(result)
    return (pixel_array.shape[0] * parameters.pixel_spacing[0] * pixel_array.shape[1] * parameters.pixel_spacing[1])

def SumSubareas(results):
    total = 0
    for map_result in results:
        total = total + map_result
    return total

def ComputeVolumenFullParallel(metadata, s3_config, s3_path, bucket_name, workers = 8, runtime='aarons28/kuro-dicom-v310:1.0'):
    # get separation between layers
    pixel_spacing = metadata["pixel_spacing"]
    slice_thickness = metadata["slice_thickness"]
    spacing = []
    spacing.append(slice_thickness)
    spacing = spacing + pixel_spacing
    separation = np.prod(spacing)
    
    client = boto3.client(
            "s3",
            aws_access_key_id=s3_config["aws_access_key_id"],
            aws_secret_access_key=s3_config["aws_secret_access_key"],
            endpoint_url=s3_config['endpoint_url'],
            region_name=s3_config['region_name'])

    bucket_name_meta = bucket_name + ".meta"
    result = client.list_objects(Bucket=bucket_name_meta, Delimiter=s3_path)
    cloud_dicom_keys = result['Contents']
    keys = []
    for file in cloud_dicom_keys:
        if 'metadata.json' not in file['Key']:
            keys.append(file['Key'])
    
    params = []
    print(len(keys))
    keySubLists = SplitListInSubList(keys,workers)
    for sublist in keySubLists:
        param = SubareaParameters(sublist, pixel_spacing, bucket_name_meta, s3_config)
        params.append(param)

    # Compute Volume
    p = lithops.FunctionExecutor(runtime=runtime)
    p.map_reduce(ComputeSubarea, params, SumSubareas, spawn_reducer=0)
    area = p.get_result()
    return area * separation


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

# expected 72000.0