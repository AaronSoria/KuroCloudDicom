import io
from types import SimpleNamespace

import boto3
import lithops
import numpy as np
import pytest
from moto import mock_aws
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

BUCKET = "dicom"
REGION = "us-east-1"


@pytest.fixture
def s3_config():
    return {
        "aws_access_key_id": "testing",
        "aws_secret_access_key": "testing",
        "endpoint_url": None,
        "region_name": REGION,
    }


@pytest.fixture
def s3(monkeypatch):
    """In-memory S3 (moto) with the base bucket and its ``.meta`` companion created."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    with mock_aws():
        client = boto3.client("s3", region_name=REGION)
        client.create_bucket(Bucket=BUCKET)
        client.create_bucket(Bucket=BUCKET + ".meta")
        yield client


class FakeFunctionExecutor:
    """Stand-in for lithops.FunctionExecutor that runs map_reduce in-process."""

    def __init__(self, registry, **kwargs):
        self.kwargs = kwargs
        self.map_iterdata = None
        self._result = None
        registry.append(self)

    def map_reduce(self, map_function, map_iterdata, reduce_function, **kwargs):
        self.map_iterdata = list(map_iterdata)
        self._result = reduce_function([map_function(item) for item in self.map_iterdata])

    def get_result(self):
        return self._result


@pytest.fixture
def fake_lithops(monkeypatch):
    """Replace lithops.FunctionExecutor; returns the list of executors created during the test."""
    executors = []
    monkeypatch.setattr(lithops, "FunctionExecutor", lambda **kwargs: FakeFunctionExecutor(executors, **kwargs))
    return executors


def make_dicom_bytes(pixels, pixel_spacing=(0.5, 0.25), slice_thickness=2.0):
    """Build a minimal uncompressed 16-bit CT DICOM file and return its bytes."""
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = Dataset()
    ds.file_meta = meta
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.SOPClassUID = meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.Modality = "CT"
    ds.Rows, ds.Columns = pixels.shape
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 12
    ds.HighBit = 11
    ds.PixelRepresentation = 0
    ds.PixelSpacing = list(pixel_spacing)
    ds.SliceThickness = slice_thickness
    ds.ImagePositionPatient = [0, 0, 0]
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    ds.PixelData = np.asarray(pixels, dtype="<u2").tobytes()

    buffer = io.BytesIO()
    ds.save_as(buffer, write_like_original=False)
    return buffer.getvalue()


def make_upload(name, data):
    """Mimic an UploadFile-like object: ``.name`` and a binary ``.file``."""
    return SimpleNamespace(name=name, file=io.BytesIO(data))
