class SubareaParameters:
    keys = None
    pixel_spacing = None
    bucket_name = ""
    s3_config = ""

    def __init__(self, keys, pixel_spacing, bucket_name, s3_config):
        self.keys = keys
        self.pixel_spacing = pixel_spacing
        self.bucket_name = bucket_name
        self.s3_config = s3_config