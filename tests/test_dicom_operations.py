import os

import numpy as np
import pytest
from conftest import BUCKET, make_dicom_bytes

from KuroCloudDicom.DicomHandlers import DicomOperations
from KuroCloudDicom.DicomHandlers.DicomDataManager import DicomDataManager

ROWS, COLS = 4, 5
SPACING = (0.5, 0.5)
THICKNESS = 3.0

# The worker function downloads to the hard-coded path /tmp/temp (it runs inside the Lithops runtime).
needs_tmp = pytest.mark.skipif(not os.path.isdir("/tmp"), reason="ComputeSubarea writes to /tmp/temp")


def put_study(s3, prefix, count):
    for i in range(count):
        data = make_dicom_bytes(np.full((ROWS, COLS), 300), SPACING, THICKNESS)
        s3.put_object(Bucket=BUCKET, Key=f"{prefix}/slice{i}.dcm", Body=data)


def test_obtain_metadata_reads_in_memory(s3, s3_config):
    put_study(s3, "raw", 1)
    dataset = DicomOperations.ObtainMetadata("raw/slice0.dcm", s3_config, BUCKET)
    assert float(dataset.SliceThickness) == THICKNESS


@needs_tmp
def test_volume_parallel(s3, s3_config, fake_lithops):
    put_study(s3, "raw", 3)
    put_study(s3, "raw-other", 2)
    s3_path = DicomDataManager(s3_config, BUCKET, prefix_key="raw").S3Path()

    volume = DicomOperations.ComputeVolumenParallel(s3_config, s3_path, BUCKET, workers=2)

    assert volume == pytest.approx(3 * ROWS * COLS * SPACING[0] * SPACING[1] * THICKNESS)


@needs_tmp
def test_volume_serial_passes_runtime(s3, s3_config, fake_lithops):
    put_study(s3, "raw", 2)

    DicomOperations.ComputeVolumenSerial(s3_config, "s3:///dicom/raw/", BUCKET, runtime="my/runtime:2")

    (executor,) = fake_lithops
    assert executor.kwargs == {"runtime": "my/runtime:2"}
    assert len(executor.map_iterdata) == 1


def test_volume_parallel_raises_when_prefix_is_empty(s3, s3_config, fake_lithops):
    with pytest.raises(ValueError, match="No DICOM files"):
        DicomOperations.ComputeVolumenParallel(s3_config, "s3:///dicom/missing/", BUCKET)
