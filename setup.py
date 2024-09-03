from setuptools import setup, find_packages

setup(
    name="mirror",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "python-dotenv",
        "Flask",
        "flask-cors",
        "Pillow",
        "boto3",
        "botocore",
        "opencv-python",
        "ffmpeg-python",
        "jsonschema",
        "numpy",
        "pyxattr",
        "PyYAML",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
