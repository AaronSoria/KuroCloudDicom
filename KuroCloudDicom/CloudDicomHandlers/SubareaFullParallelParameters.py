class SubareaFullParallelParameters:
    s3_config = None
    pixel_spacing = None
    bucket_name = ""
    key = ""

    def __init__(self, s3_config, pixel_spacing, bucket_name, key):
        self.s3_config = s3_config
        self.pixel_spacing = pixel_spacing
        self.bucket_name = bucket_name
        self.key = key