from setuptools import setup, find_packages
from typing import List

HYPHEN_E_DOT = "-e ."


def get_requirements(file_path: str) -> List[str]:
    """This function will return the list of requirements"""
    try:
        with open(file_path) as f:
            requirements = [r.strip() for r in f.readlines()]
            if HYPHEN_E_DOT in requirements:
                requirements.remove(HYPHEN_E_DOT)
            return requirements
    except FileNotFoundError:
        print(f"The file {file_path} doesn't exist.")
        return []
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return []


SRC_NAME = "Agri-App-for-AS-2.0-v1"
VERSION = "1.0"
AUTHOR = "AS Wing"
AUTHOR_EMAIL = "fodhq.as.fbd@gmail.com"
AUTHOR_USERNAME = "AS Wing"

setup(
    name=SRC_NAME,
    version=VERSION,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    package_dir={"": "04_src"},
    packages=find_packages(where="04_src"),
    install_requires=get_requirements("requirements.txt"),
    python_requires=">=3.8",
)