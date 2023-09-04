import boto3
import json
import os
import pydicom
import tempfile

class DicomDataManager:
    __client = None
    __bucket_name = ""
    __bucket_name_meta = ""
    __prefix_key = ""
    __runtime = ""

    def __init__(self, s3_config, bucket_name, prefix_key = "", runtime='aarons28/kuro-dicom-v310:1.0'):
        self.__client = boto3.client(
            "s3",
            aws_access_key_id=s3_config["aws_access_key_id"],
            aws_secret_access_key=s3_config["aws_secret_access_key"],
            endpoint_url=s3_config['endpoint_url'],
            region_name=s3_config['region_name'])
        
        self.__bucket_name = bucket_name
        self.__bucket_name_meta = bucket_name + ".meta"
        self.__prefix_key = prefix_key
        self.__runtime = runtime

    def S3Path(self):
        return 's3:///'+self.__bucket_name+'/'+self.__prefix_key+'/'