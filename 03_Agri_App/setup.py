from setuptools import setup, find_packages
from typing import List

HYPHEN_E_DOT = '-e .'
def get_requirements(file_path:str) -> list:
    # This function reads the requirements from the specified file and returns them as a list.
    try:
        with open(file_path, 'r') as f:
            requirements = f.read().splitlines()
            if HYPHEN_E_DOT in requirements:
                requirements.remove(HYPHEN_E_DOT)
            return requirements
    except FileNotFoundError:
        print(f"{file_path} not found.")
        return []
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return []


setup(
    name="Agri App for AS 2.0",
    version="1.0",
    author='NSO (FOD) AS Wing',
    author_email='fodhq.as.fbd@gmail.com',
    packages=find_packages(),
    install_requires=get_requirements('requirements.txt')
)