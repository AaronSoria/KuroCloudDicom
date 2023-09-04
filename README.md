
# KuroCloudDicom

A new library for compute volume using lithops and a new kind of Dicom Files stored in cloud. You can use lithops in a simple way for process your dicom files with generall functions



## Installation

Install KuroCloudDicom with pip

```bash
pip install KuroCloudDicom==0.0.2
```

also you must create a file named 
.lithops_config in order to use this project. You can config the file like this.


```bash
lithops:
   backend : k8s
   storage: minio

k8s:
   docker_server : docker.io
   docker_user : some_docker_user
   docker_password : some_docker_password
   runtime_timeout : 3600
   max_workers : 12
   runtime_memory : 256

minio:
   storage_bucket: some_storage_bucket_previously_created
   endpoint: your_minio_endpoint
   access_key_id: your_access_key_id
   secret_access_key: your_secret
```

This project was mainly tested using k8s and minio, so we encourage you to use it. You can use local implementations like k3s for testing and deployment pursposes also.
## Usage

Before start using CloudDicomOperations first you have to apply a preprocessing task

```python
from KuroCloudDicom.CloudDicomHandlers import Preprocessor

s3_config = {
    'aws_access_key_id': 'your_aws_access_key_id',
    'aws_secret_access_key':'your_secret',
    'region_name': 'your_region',
    'endpoint_url': 'your_url_enpoint',
    'botocore_config_kwargs': {'signature_version': 'some_signature'},
    'role_arn': 'some_role_arn'
    }

prefix_key = 'test'
bucket_name = 'your_bucket_name'

dataManager = CloudDicomDataManager(s3_config = s3_config, bucket_name = bucket_name, prefix_key = prefix_key)

files = [] # an array with your dicom files as binary object

# upload your dicom files
dataManager.UploadDicomCollection(files)

```
When you preprocess a collection of Dicom files, you have a collection of CloudDicomFiles stored in your S3. Also, you have metadata.json file with common data of the previous collection.

For compute the volume you should proceed in this way

```python
from CloudDicomHandlers.CloudDicomOperations import ComputeVolumenFullParallel


s3_path = dataManager.S3Path()
metadata = dataManager.ObtainMetadata()
bucket_name = 'your_bucket_name'

result = ComputeVolumenFullParallel(metadata=metadata, s3_config=s3_config, s3_path=s3_path, bucket_name = bucket_name)

```

