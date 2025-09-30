from setuptools import setup, find_packages

setup(
    name="subtitle-translator",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "aiohttp>=3.8.0",
        "langdetect>=1.0.9",
        "pysubs2>=1.8.0",
        "google-cloud-translate>=3.21.0",
        "deepl>=1.22.0",
        "google-generativeai>=0.8.0",
        "fastapi>=0.100.0",
        "uvicorn[standard]>=0.20.0",
        "websockets>=11.0.0",
        "python-multipart>=0.0.6",
    ],
    extras_require={
        'gui': ['PyQt6>=6.0.0'],
        'dev': [
            'pytest>=6.0',
            'black>=21.0',
            'isort>=5.0',
            'mypy>=0.900',
        ],
    },
    entry_points={
        'console_scripts': [
            'subtitle-translator=subtitle_translator.cli.main:main',
        ],
        'gui_scripts': [
            'subtitle-translator-gui=subtitle_translator.gui.main:main',
        ],
    },
    python_requires='>=3.8',
)
