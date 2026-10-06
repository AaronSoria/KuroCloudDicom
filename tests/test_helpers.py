import pytest

from KuroCloudDicom._s3utils import ListKeys, SplitS3Path
from KuroCloudDicom.CloudDicomHandlers.CloudDicomOperations import SplitListInSubList, SumSubareas
from KuroCloudDicom.CloudDicomHandlers.Preprocessor import Preprocessor
from KuroCloudDicom.DicomHandlers import DicomOperations


@pytest.mark.parametrize(
    "items, quantity, expected",
    [
        (list(range(10)), 3, [[0, 1, 2, 3], [4, 5, 6], [7, 8, 9]]),
        (list(range(4)), 2, [[0, 1], [2, 3]]),
        ([1, 2], 8, [[1], [2]]),
        ([1, 2, 3], 1, [[1, 2, 3]]),
        ([], 4, []),
    ],
)
def test_split_list_in_sublists(items, quantity, expected):
    assert SplitListInSubList(items, quantity) == expected


def test_split_list_rejects_zero_quantity():
    with pytest.raises(ValueError):
        SplitListInSubList([1, 2], 0)


def test_dicom_operations_reuses_split_list():
    assert DicomOperations.SplitListInSubList is SplitListInSubList


def test_sum_subareas():
    assert SumSubareas([1.5, 2.5, 6]) == 10


@pytest.mark.parametrize(
    "path, expected",
    [
        ("s3:///dicom.meta/study/", ("dicom.meta", "study/")),
        ("s3://dicom.meta/a/b/", ("dicom.meta", "a/b/")),
        ("s3:///dicom.meta//", ("dicom.meta", "/")),
        ("study/", ("", "study/")),
    ],
)
def test_split_s3_path(path, expected):
    assert SplitS3Path(path) == expected


def test_list_keys_paginates_and_filters_by_prefix(s3):
    for i in range(1005):
        s3.put_object(Bucket="dicom", Key=f"study/{i}", Body=b"")
    s3.put_object(Bucket="dicom", Key="study2/x", Body=b"")
    keys = ListKeys(s3, "dicom", "study/")
    assert len(keys) == 1005
    assert all(key.startswith("study/") for key in keys)


@pytest.mark.parametrize(
    "number, expected",
    [(0, "img.dcm.000"), (7, "img.dcm.007"), (42, "img.dcm.042"), (123, "img.dcm.123"), (1000, None)],
)
def test_generate_extension(number, expected):
    assert Preprocessor(2).GenerateExtention("img.dcm", number) == expected
