class ChunkedDicomData:
    matrix = None
    image_position = None
    
    def __init__(self, matrix, image_position):
        self.matrix = matrix
        self.image_position = image_position