# KuroCloudDicom

KuroCloudDicom computes volumes over DICOM image collections stored in S3-compatible object
storage, running the work in parallel with [Lithops](https://lithops-cloud.github.io/).

It works in two steps:

1. **Preprocess and upload.** Each DICOM image is decoded, split into chunks and uploaded as a
   compressed "CloudDicom" object, together with a `metadata.json` describing the collection.
2. **Compute the volume.** The chunk keys are distributed across Lithops workers, each worker sums
   the physical area of its chunks, and the results are reduced and multiplied by the slice thickness.

The computed volume is the full image extent of every slice
(`Σ rows · cols · pixel_spacing[0] · pixel_spacing[1] · slice_thickness`), in the units of the DICOM
spacing attributes (normally mm³). No segmentation is performed.

## Installation

```bash
pip install KuroCloudDicom
```

Python 3.9 or newer is required. The dependencies include `lithops`, `boto3`, `pydicom` (2.x),
`python-gdcm`, `numpy` and `scipy`.

## Lithops configuration

Lithops reads its configuration from a `.lithops_config` file (see the
[Lithops configuration docs](https://lithops-cloud.github.io/docs/source/configuration.html) for where
it is looked up). The project was tested with the Kubernetes backend and MinIO storage, for example:

```yaml
lithops:
    backend: k8s
    storage: minio

k8s:
    docker_server: docker.io
    docker_user: <your-docker-user>
    docker_password: <your-docker-password-or-token>
    runtime_timeout: 3600
    max_workers: 12
    runtime_memory: 256

minio:
    storage_bucket: <existing-lithops-bucket>
    endpoint: <http://your-minio-host:9000>
    access_key_id: <your-access-key-id>
    secret_access_key: <your-secret-access-key>
```

Never commit real credentials to version control.

The default Lithops runtime image used by the volume functions is `aarons28/kuro-dicom-v310:1.0`. You
can pass your own image with the `runtime=` argument. Lithops generally expects the Python version of
your local environment to match the one in the runtime image.

## Usage

### S3 configuration

Both steps take an `s3_config` mapping with these keys:

```python
s3_config = {
    "aws_access_key_id": "<your-access-key-id>",
    "aws_secret_access_key": "<your-secret-access-key>",
    "endpoint_url": "<http://your-minio-host:9000>",  # None for AWS S3
    "region_name": "<your-region>",
}
```

### 1. Upload a collection

```python
from KuroCloudDicom.CloudDicomHandlers.CloudDicomDataManager import CloudDicomDataManager

bucket_name = "dicom"      # chunks are stored in the bucket "dicom.meta"
prefix_key = "patient-01"  # folder for this collection

data_manager = CloudDicomDataManager(
    s3_config=s3_config,
    bucket_name=bucket_name,
    prefix_key=prefix_key,
)

# Each item needs a `.name` (str) and a binary, readable `.file`,
# e.g. Starlette/FastAPI UploadFile objects.
files = [...]

data_manager.UploadDicomCollection(files)
```

The chunks are written to `<bucket_name>.meta/<prefix_key>/<file name>.000`, `.001`, and so on.
`metadata.json` is written next to them. The `<bucket_name>.meta` bucket must already exist.

### 2. Compute the volume

```python
from KuroCloudDicom.CloudDicomHandlers.CloudDicomOperations import ComputeVolumenFullParallel

volume = ComputeVolumenFullParallel(
    metadata=data_manager.ObtainMetadata(),
    s3_config=s3_config,
    s3_path=data_manager.S3Path(),
    bucket_name=bucket_name,
    workers=8,
)
print(volume)
```

`workers` is the maximum number of Lithops tasks the chunks are split across.

## Tested environment

The library was tested by the author with:

- Lithops with the Kubernetes backend on k3s
- MinIO as the S3-compatible storage

Other Lithops backends and storage providers have not been tested.

## Limitations

- Bucket names: chunks are stored in a second bucket named `<bucket_name>.meta`. It must exist
  beforehand. Bucket names containing dots can cause TLS errors on AWS S3 with virtual-hosted
  addressing. MinIO is not affected.
- Pixel data is read as 16-bit unsigned integers. The default upload format rescales values
  assuming 12-bit data and stores them as 8-bit. This does not affect the volume, which only depends
  on image shape and spacing.
- `metadata.json` (pixel spacing and slice thickness) is taken from the last file of the upload, so
  all files of a collection are assumed to share the same spacing.
- `s3_config` is sent to the Lithops workers as part of the task arguments.
- The unit tests mock S3 and Lithops. End-to-end behaviour is only verified in the tested
  environment above.

## License

MIT. See [LICENSE](https://github.com/AaronSoria/KuroCloudDicom/blob/master/LICENSE).
