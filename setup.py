from setuptools import setup, find_packages

setup(
    name="subtitle-translator",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "aiohttp>=3.8.0",
        "langdetect>=1.0.9",
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
    },
    python_requires='>=3.8',
)
