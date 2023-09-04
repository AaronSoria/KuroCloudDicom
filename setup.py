import pathlib
from setuptools import find_packages, setup

HERE = pathlib.Path(__file__).parent

VERSION = '0.0.1'
PACKAGE_NAME = 'KuroCloudDicom'
AUTHOR = 'Luis Aaron Maximiliano'
AUTHOR_EMAIL = 'soria_aaron@outlook.com'
URL = 'https://github.com/AaronSoria/KuroCloudDicom'

LICENSE = 'MIT'
DESCRIPTION = 'A new library for compute volume using lithops and a new kind of Dicom Files stored in cloud'
LONG_DESCRIPTION = (HERE / "README.md").read_text(encoding='utf-8')
LONG_DESC_TYPE = "text/markdown"


#Paquetes necesarios para que funcione la libreía. Se instalarán a la vez si no lo tuvieras ya instalado
INSTALL_REQUIRES = [
        'python-gdcm',
        'boto3',
        'numpy',
        'cloudpickle',
        'pydicom',
        'Pillow',
        'lithops',
        'scipy'
      ]

setup(
    name=PACKAGE_NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    long_description_content_type=LONG_DESC_TYPE,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    url=URL,
    install_requires=INSTALL_REQUIRES,
    license=LICENSE,
    packages=find_packages(),
    include_package_data=True
)