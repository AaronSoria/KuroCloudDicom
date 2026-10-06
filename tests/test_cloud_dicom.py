import io
import json
import pickle
import zlib

import numpy as np
import pytest
from conftest import BUCKET, make_dicom_bytes, make_upload

from KuroCloudDicom.CloudDicomHandlers.CloudDicomDataManager import CloudDicomDataManager
from KuroCloudDicom.CloudDicomHandlers.CloudDicomOperations import ComputeVolumenFullParallel

ROWS, COLS = 8, 6
SPACING = (0.5, 0.25)
THICKNESS = 2.0


def pixels(seed):
    # 12-bit values, most of them with bytes >= 0x80
    return (np.arange(ROWS * COLS).reshape(ROWS, COLS) * 85 + seed) % 4096


def read_chunk(s3, key, compressed=True):
    body = s3.get_object(Bucket=BUCKET + ".meta", Key=key)["Body"].read()
    return pickle.load(io.BytesIO(zlib.decompress(body) if compressed else body))


def upload_collection(s3_config, prefix, count, output_format=1, chunks=2):
    manager = CloudDicomDataManager(s3_config=s3_config, bucket_name=BUCKET, prefix_key=prefix, dicom_chunks=chunks)
    files = [make_upload(f"slice{i}.dcm", make_dicom_bytes(pixels(i), SPACING, THICKNESS)) for i in range(count)]
    manager.UploadDicomCollection(files, output_format=output_format)
    return manager


def test_upload_writes_chunks_and_metadata(s3, s3_config):
    manager = upload_collection(s3_config, "study", count=3)

    keys = sorted(item["Key"] for item in s3.list_objects_v2(Bucket=BUCKET + ".meta")["Contents"])
    expected_chunks = [f"study/slice{i}.dcm.00{c}" for i in range(3) for c in range(2)]
    assert keys == sorted(expected_chunks + ["study/metadata.json"])

    metadata = manager.ObtainMetadata()
    assert metadata["pixel_spacing"] == list(SPACING)
    assert metadata["slice_thickness"] == THICKNESS
    assert metadata["number_of_chunks_per_file"] == 2
    assert manager.S3Path() == "s3:///dicom.meta/study/"


def test_upload_preserves_pixel_values(s3, s3_config):
    upload_collection(s3_config, "study", count=1)

    chunks = [read_chunk(s3, f"study/slice0.dcm.00{c}") for c in range(2)]
    stored = np.concatenate(chunks, axis=1).ravel()
    expected = (pixels(0).ravel() / 4095 * 255).astype(np.uint8)
    np.testing.assert_array_equal(stored, expected)


def test_upload_numpy_format(s3, s3_config):
    upload_collection(s3_config, "study", count=1, output_format=2)

    chunks = [read_chunk(s3, f"study/slice0.dcm.00{c}", compressed=False) for c in range(2)]
    np.testing.assert_array_equal(np.concatenate(chunks, axis=1).ravel(), pixels(0).ravel())


def test_upload_empty_collection_raises(s3, s3_config):
    manager = CloudDicomDataManager(s3_config=s3_config, bucket_name=BUCKET, prefix_key="study")
    with pytest.raises(ValueError):
        manager.UploadDicomCollection([])


def test_upload_as_mat_uploads_full_original(s3, s3_config, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = make_dicom_bytes(pixels(0), SPACING, THICKNESS)
    manager = CloudDicomDataManager(s3_config=s3_config, bucket_name=BUCKET, prefix_key="study")

    manager.UploadDicomAsMat(make_upload("slice0.dcm", data))

    original = s3.get_object(Bucket=BUCKET, Key="study/slice0.dcm")["Body"].read()
    assert original == data
    meta_keys = {item["Key"] for item in s3.list_objects_v2(Bucket=BUCKET + ".meta")["Contents"]}
    assert meta_keys == {"study/metadata.json", "study/slice0.dcm.000", "study/slice0.dcm.001"}
    assert list(tmp_path.iterdir()) == []


def test_volume_end_to_end(s3, s3_config, fake_lithops):
    manager = upload_collection(s3_config, "study", count=5)
    upload_collection(s3_config, "other-study", count=4)

    volume = ComputeVolumenFullParallel(
        metadata=manager.ObtainMetadata(),
        s3_config=s3_config,
        s3_path=manager.S3Path(),
        bucket_name=BUCKET,
        workers=3,
        runtime="my/runtime:1",
    )

    assert volume == pytest.approx(5 * ROWS * COLS * SPACING[0] * SPACING[1] * THICKNESS)
    (executor,) = fake_lithops
    assert executor.kwargs == {"runtime": "my/runtime:1"}
    assert [len(params.keys) for params in executor.map_iterdata] == [4, 3, 3]
    assert all(key.startswith("study/") for params in executor.map_iterdata for key in params.keys)


def test_volume_reads_more_than_one_listing_page(s3, s3_config, fake_lithops):
    chunk = zlib.compress(pickle.dumps(np.zeros((10, 20), np.uint8)))
    for i in range(1200):
        s3.put_object(Bucket=BUCKET + ".meta", Key=f"big/f{i}.000", Body=chunk)
    s3.put_object(Bucket=BUCKET + ".meta", Key="big/metadata.json", Body=b"{}")

    metadata = {"pixel_spacing": [1.0, 1.0], "slice_thickness": 1.0}
    volume = ComputeVolumenFullParallel(metadata, s3_config, "s3:///dicom.meta/big/", BUCKET, workers=8)

    assert volume == 1200 * 10 * 20


def test_volume_raises_when_prefix_is_empty(s3, s3_config, fake_lithops):
    metadata = {"pixel_spacing": [1.0, 1.0], "slice_thickness": 1.0}
    with pytest.raises(ValueError, match="No CloudDicom chunks"):
        ComputeVolumenFullParallel(metadata, s3_config, "s3:///dicom.meta/missing/", BUCKET)
    assert fake_lithops == []


def test_metadata_json_round_trip(s3, s3_config):
    manager = upload_collection(s3_config, "study", count=1)
    raw = s3.get_object(Bucket=BUCKET + ".meta", Key="study/metadata.json")["Body"].read()
    assert json.loads(raw) == manager.ObtainMetadata()
