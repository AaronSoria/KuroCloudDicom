import io
import pickle

import boto3
import lithops

from .._s3utils import ListKeys, SplitS3Path
from .SubareaFullParallelParameters import SubareaFullParallelParameters
from .SubareaParameters import SubareaParameters


def ComputeSubarea(params: SubareaParameters):
    import io
    import pickle
    import zlib

    import boto3

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
        subarea = subarea + (pixel_array.shape[0] * params.pixel_spacing[0]
                             * pixel_array.shape[1] * params.pixel_spacing[1])
    return subarea

def ComputeSubareaFullParallel(params: SubareaParameters):
    import multiprocessing

    parameters = [SubareaFullParallelParameters(params.s3_config, params.pixel_spacing, params.bucket_name, item)
                  for item in params.keys]
    num_cores = multiprocessing.cpu_count()
    with multiprocessing.Pool(num_cores) as p:
        results = p.map(ObtainArea, parameters)
        return sum(results)

def ObtainArea(parameters: SubareaFullParallelParameters):
    import zlib
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

def ComputeVolumenFullParallel(metadata, s3_config, s3_path, bucket_name, workers = 8,
                               runtime='aarons28/kuro-dicom-v310:1.0'):
    # ComputeSubarea already scales by pixel spacing, so only the slice thickness is left to apply
    pixel_spacing = metadata["pixel_spacing"]
    separation = float(metadata["slice_thickness"])

    client = boto3.client(
            "s3",
            aws_access_key_id=s3_config["aws_access_key_id"],
            aws_secret_access_key=s3_config["aws_secret_access_key"],
            endpoint_url=s3_config['endpoint_url'],
            region_name=s3_config['region_name'])

    bucket_name_meta = bucket_name + ".meta"
    _, prefix = SplitS3Path(s3_path)
    keys = [key for key in ListKeys(client, bucket_name_meta, prefix) if 'metadata.json' not in key]
    if not keys:
        raise ValueError(f"No CloudDicom chunks found in bucket {bucket_name_meta!r} under prefix {prefix!r}")

    params = []
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
    if subListQuantity < 1:
        raise ValueError("subListQuantity must be at least 1")
    if not mylist:
        return []
    # Never create empty sublists, and keep sizes within one element of each other
    quantity = min(subListQuantity, len(mylist))
    size, extra = divmod(len(mylist), quantity)
    sublists = []
    start_element = 0
    for i in range(quantity):
        end_element = start_element + size + (1 if i < extra else 0)
        sublists.append(mylist[start_element:end_element])
        start_element = end_element
    return sublists