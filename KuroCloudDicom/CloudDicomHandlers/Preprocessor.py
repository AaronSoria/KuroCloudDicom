import numpy as np
import io
import os
import scipy.io
from scipy.io import savemat
import zlib
import pydicom
from pydicom import dcmread, dcmwrite
import gdcm
import json
import uuid
from .ChunkedDicomData import ChunkedDicomData

class Preprocessor:
    __dicom_chunks = 0
    
    def __init__(self, dicom_chunks):
        self.__dicom_chunks = dicom_chunks
        
    def __CreateSubmatrix(self, matrix, chunks):
        submatrix = np.array_split(matrix, chunks, axis=1)
        submatrix_uint16 = [chunk.astype('uint16') for chunk in submatrix]
        return submatrix

    def GenerateExtention(self, name, number):
        extention = str(number)
        if len(extention) == 1: return name+'.00'+extention
        if len(extention) == 2: return name+'.0'+extention
        if len(extention) == 3: return name+'.'+extention

    def SaveChunkedDicomAsMat(self, chunked_dicom: ChunkedDicomData):
        temp_file_name = str(uuid.uuid4())
        mdic = {"pixel_array": chunked_dicom.matrix, 
                "image_position": chunked_dicom.image_position }
        savemat(temp_file_name, mdic)
        return temp_file_name

    def GenerateDicomMetadata(self,file_path):
        dicom_dataset = dcmread(file_path, force=True)
        mdic = {
            "pixel_spacing": dicom_dataset.PixelSpacing._list, 
            "slice_thickness": dicom_dataset.SliceThickness, 
            "image_position":dicom_dataset.ImagePositionPatient._list,
            "image_orientation": dicom_dataset.ImageOrientationPatient._list,
            "number_of_chunks_per_file": self.__dicom_chunks }
        return mdic

    def GenerateDicomMetadataAsDict(self,dicom_dataset):
        mdic = {
            "pixel_spacing": dicom_dataset.PixelSpacing._list, 
            "slice_thickness": dicom_dataset.SliceThickness, 
            "image_position":dicom_dataset.ImagePositionPatient._list,
            "image_orientation": dicom_dataset.ImageOrientationPatient._list,
            "number_of_chunks_per_file": self.__dicom_chunks }
        return mdic
    
    def SplitDicomInChunksAsMat(self, file_path): # -> Lista de ChunkedDicomData:
        dicom_dataset = pydicom.dcmread(file_path, force=True)
        reader = gdcm.ImageReader()
        reader.SetFileName(file_path)
        pixel_array = None
        if reader.Read():
            pixel_buffer = reader.GetImage().GetBuffer()
            pixel_array = np.frombuffer(pixel_buffer.encode(errors="replace"), dtype=np.uint16)
            image_dims = reader.GetImage().GetDimensions()
            pixel_array = pixel_array.reshape(image_dims)
            submatrix_collection = self.__CreateSubmatrix(pixel_array, self.__dicom_chunks)
            chunked_collection = []
            for submatrix in enumerate(submatrix_collection):
                chunked_collection.append(ChunkedDicomData(image_position=dicom_dataset.ImagePositionPatient._list, 
                matrix=submatrix))
        return chunked_collection        
            # thow exception

    def SplitDicomInChunks(self, pixel_array): # -> Lista de np.arrays:
        submatrix_collection = self.__CreateSubmatrix(pixel_array, self.__dicom_chunks)
        chunked_collection = []
        for submatrix in enumerate(submatrix_collection):
            chunked_collection.append(submatrix[1])
        return chunked_collection
            
    