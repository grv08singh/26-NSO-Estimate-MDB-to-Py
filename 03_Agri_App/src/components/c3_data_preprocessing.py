import os

class DataProcessing:
    def __init__(self, data_dir):
        self.data_dir = data_dir

    def load_data(self, file_name):
        file_path = os.path.join(self.data_dir, file_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File {file_path} does not exist.")
        with open(file_path, 'r') as file:
            data = file.read()
        return data

    def process_data(self, data):
        # Placeholder for data processing logic
        processed_data = data.lower()  # Example processing
        return processed_data