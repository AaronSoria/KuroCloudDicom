# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.0.3] - Unreleased

### Fixed
- `ComputeVolumenFullParallel` and `DicomOperations.ComputeVolumenParallel` counted every object in
  the bucket instead of only those under the requested prefix (`s3_path` was used as the
  `list_objects` delimiter). They now list only the prefix taken from `s3_path`.
- Volume functions only read the first 1000 keys of a listing; all pages are now read.
- Pixel spacing was applied twice in the volume computation (results were only correct for a pixel
  spacing of 1.0). **Volumes returned for any other spacing change with this release.**
- Pixel values stored by the upload functions were corrupted for bytes >= 0x80 when decoding the
  GDCM buffer. Array shapes, and therefore volumes, were not affected.
- `UploadDicomCollection(..., output_format=2)` raised `NameError`.
- `UploadDicomCollection([])` raised `UnboundLocalError`; it now raises `ValueError`.
- `UploadDicomAsMat` uploaded an empty/truncated copy of the original DICOM file.
- `Preprocessor.SplitDicomInChunksAsMat` stored `(index, array)` tuples instead of arrays and raised
  `UnboundLocalError` when GDCM could not read the file (now `ValueError`).
- `SplitDicomFileAsJson` passed a file path where an array was expected; it now behaves like
  `SplitDicomFileAsMat`.
- `ComputeVolumenSerial` ignored its `runtime` argument.
- `SplitListInSubList` created empty sublists when there were fewer items than workers and raised
  `ZeroDivisionError` for 0 workers (now `ValueError`); sublist sizes are now balanced.
- Uploading failed on Windows (temporary files reopened while still open).
- `ObtainMetadata` no longer writes `metadata.json` / `/tmp/temp` on the local machine.
- Removed a debug `print` of the number of keys.
- README: the volume example imported from `CloudDicomHandlers...`, which is not an installed
  package; the correct import is `KuroCloudDicom.CloudDicomHandlers...`.

### Changed
- An empty prefix in the volume functions now raises `ValueError` instead of `KeyError`.
- Packaging moved from `setup.py` to `pyproject.toml`.
- Dependencies now have version bounds; `pydicom` is limited to 2.x.
- Python 3.9 or newer is declared as required.

### Added
- MIT `LICENSE` file, included in the wheel and sdist.
- Type hints and docstrings for the public API.
- Unit tests (S3 mocked with moto, Lithops mocked) and a GitHub Actions workflow running ruff and
  pytest on Python 3.9–3.12.
- README rewritten in English, with configuration, usage, tested environment and limitations.

## [0.0.2] - 2023-09-04

- First functional release on PyPI: `CloudDicomHandlers` (upload of chunked CloudDicom files and
  `ComputeVolumenFullParallel`) and `DicomHandlers`.

## [0.0.1] - 2023-09-03

- Initial upload. The top-level `__init__.py` was missing, so the package modules were not
  included (fixed in 0.0.2).

[0.0.3]: https://github.com/AaronSoria/KuroCloudDicom/compare/v0.0.2...v0.0.3
[0.0.2]: https://github.com/AaronSoria/KuroCloudDicom/releases/tag/v0.0.2
[0.0.1]: https://github.com/AaronSoria/KuroCloudDicom/releases/tag/v0.0.1
