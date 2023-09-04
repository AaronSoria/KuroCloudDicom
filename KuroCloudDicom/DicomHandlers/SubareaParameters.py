class SubareaParameters:
    keys = None
    bucket_name = ""
    s3_config = ""

    def __init__(self, keys, bucket_name, s3_config):
        self.keys = keys
        self.bucket_name = bucket_name
        self.s3_config = s3_config