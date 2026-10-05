from __future__ import annotations

from typing import Any, Mapping

import boto3


class DicomDataManager:
    """Describe the location of raw DICOM files in S3-compatible storage.

    Args:
        s3_config: Mapping with ``aws_access_key_id``, ``aws_secret_access_key``, ``endpoint_url``
            and ``region_name``.
        bucket_name: Bucket holding the DICOM files.
        prefix_key: Key prefix (folder) of the collection.
        runtime: Stored for API compatibility; not used by this class.
    """

    __client = None
    __bucket_name = ""
    __bucket_name_meta = ""
    __prefix_key = ""
    __runtime = ""

    def __init__(self, s3_config: Mapping[str, Any], bucket_name: str, prefix_key: str = "",
                 runtime: str = 'aarons28/kuro-dicom-v310:1.0') -> None:
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

    def S3Path(self) -> str:
        """Return the collection location as ``s3:///<bucket_name>/<prefix_key>/``."""
        return 's3:///'+self.__bucket_name+'/'+self.__prefix_key+'/'
