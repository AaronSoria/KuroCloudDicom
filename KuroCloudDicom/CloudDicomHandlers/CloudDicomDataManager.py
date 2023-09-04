import boto3
import json
from .Preprocessor import Preprocessor
from .SubareaParameters import SubareaParameters
import os
import pydicom
import zlib
from PIL import Image

import tempfile
import gdcm
import json
import numpy as np
import pickle
import io

class CloudDicomDataManager:
    __client = None
    __preprocessor = None
    __bucket_name = ""
    __bucket_name_meta = ""
    __prefix_key = ""
    __runtime = ""

    def __init__(self, s3_config, bucket_name, dicom_chunks = 2, prefix_key = "", runtime='aarons28/kuro-dicom-v310:1.0'):
        self.__client = boto3.client(
            "s3",
            aws_access_key_id=s3_config["aws_access_key_id"],
            aws_secret_access_key=s3_config["aws_secret_access_key"],
            endpoint_url=s3_config['endpoint_url'],
            region_name=s3_config['region_name'])
        self.__preprocessor = Preprocessor(dicom_chunks = dicom_chunks)
        self.__bucket_name = bucket_name
        self.__bucket_name_meta = bucket_name + ".meta"
        self.__prefix_key = prefix_key
        self.__runtime = runtime

    def ObtainMetadata(self):
        meta = 'metadata.json'
        key = self.__prefix_key+'/'+meta
        with open(meta, 'wb') as f:
            self.__client.download_fileobj(self.__bucket_name_meta, key, f)
            f.close()

        with open(meta, 'r') as f:
            metadata = json.load(f)
            f.close()
        os.remove(meta)
        return metadata

    def S3Path(self):
        return 's3:///'+self.__bucket_name_meta+'/'+self.__prefix_key+'/'

    def UploadDicomCollection(self, files, output_format = 1): #custom = 1, np = 2
        for file in files:
            file_name = file.name
            dicom_dataset = pydicom.dcmread(file.file, force=True)
            with tempfile.NamedTemporaryFile(suffix=".dcm") as temp_file:
                pydicom.dcmwrite(temp_file.name, dicom_dataset)
                reader = gdcm.ImageReader()
                reader.SetFileName(temp_file.name)
                pixel_array = None
                if reader.Read():
                    pixel_buffer = reader.GetImage().GetBuffer()
                    pixel_array = np.frombuffer(pixel_buffer.encode(errors="replace"), dtype=np.uint16)
                    image_dims = reader.GetImage().GetDimensions()
                    pixel_array = pixel_array.reshape(image_dims)
                    if output_format == 1: self.UploadDicomAsCustom(pixel_array, file_name)
                    if output_format == 2: self.UploadDicomAsNp(pixel_array, file_name)

        meta = self.__preprocessor.GenerateDicomMetadataAsDict(dicom_dataset)
        metadata_file_name = "metadata.json"
        metaJson = json.dumps(meta)
        self.__client.put_object(Body=metaJson,Key=self.__prefix_key+"/"+metadata_file_name, Bucket=self.__bucket_name_meta)

    def UploadDicomAsNp(self, pixel_array, file_name):
        chunk_collection = self.__preprocessor.SplitDicomInChunks(pixel_array)
        i = 0
        file_meta = FileMetaDataset()
        for chunk in chunk_collection:
            key = self.__preprocessor.GenerateExtention(file_name,i)
            subMatrix_data = io.BytesIO()
            pickle.dump(chunk, subMatrix_data)
            subMatrix_data.seek(0)
            self.__client.put_object(Body=subMatrix_data,Key=self.__prefix_key+"/"+key, Bucket=self.__bucket_name_meta)
            i = i + 1

    def SplitDicomFileAsJson(self, file_path):
        result = self.__preprocessor.SplitDicomInChunks(file_path)
        file_colection = [ self.__preprocessor.SaveChunkedDicomAsMat(item) for item in result]
        return file_colection

    def UploadDicomAsMat(self, file):
        dicom_dataset = pydicom.dcmread(file.file, force=True)
        with tempfile.NamedTemporaryFile(suffix=".dcm") as temp_file:
            pydicom.dcmwrite(temp_file.name, dicom_dataset)
            meta = self.__preprocessor.GenerateDicomMetadata(temp_file.name)
            metadata_file_name = "metadata.json"
            with open(metadata_file_name, 'w') as fp:
                json.dump(meta, fp)

            self.__client.upload_file(metadata_file_name,
                self.__bucket_name_meta,
                self.__prefix_key+"/"+metadata_file_name)
            os.remove(metadata_file_name)

            file_colection_paths = self.SplitDicomFileAsMat(temp_file.name)
            i = 0
            for file_path in file_colection_paths:
                key = self.__preprocessor.GenerateExtention(file.name,i)
                self.__client.upload_file(file_path,
                    self.__bucket_name_meta,
                    self.__prefix_key+"/"+key)
                i = i + 1
                os.remove(file_path)
            
            self.__client.put_object(Bucket=self.__bucket_name,
                    Body=file.file,
                    Key=self.__prefix_key+"/"+file.name)

    def UploadDicomAsCustom(self, pixel_array, file_name):
        chunk_collection = self.__preprocessor.SplitDicomInChunks(pixel_array)
        i = 0
        suffix = ".dcm"
        for chunk in chunk_collection:
            key = self.__preprocessor.GenerateExtention(file_name,i)
            compressed_chunk = (chunk / 4095 * 255).astype(np.uint8)
            # contiguous_array = np.ascontiguousarray(compressed_chunk)
            # aux_chunk_compress = zlib.compress(contiguous_array.tobytes(), level=9)
            subMatrix_data = io.BytesIO()
            pickle.dump(compressed_chunk, subMatrix_data)
            subMatrix_data.seek(0)
            result = zlib.compress(subMatrix_data.getvalue(), level=9)
            self.__client.put_object(Body=result,Key=self.__prefix_key+"/"+key, Bucket=self.__bucket_name_meta)
            i = i + 1

    def SplitDicomFileAsMat(self, file_path):
        result = self.__preprocessor.SplitDicomInChunksAsMat(file_path)
        file_colection = [ self.__preprocessor.SaveChunkedDicomAsMat(item) for item in result]
        return file_colection