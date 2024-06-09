from setuptools import setup, find_packages

setup(
    name='mirror',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'python-dotenv',  # for dotenv
        'Flask',  # for Flask
        'flask-cors',  # for Flask-CORS
        'Pillow',  # for PIL
        'boto3',  # for boto3
        'botocore',  # for botocore
        'opencv-python',  # for cv2
        'ffmpeg-python',  # for ffmpeg
        'jsonschema',  # for jsonschema
        'numpy',  # for np
        'pyxattr',  # for xattr
        'PyYAML',  # for yaml
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)
