from setuptools import setup, find_packages

setup(
    name="subtitle-translator",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "aiohttp>=3.8.0",
        "langdetect>=1.0.9",
        "PyQt6>=6.0.0; 'gui' in sys.argv or 'gui' in sys_platform",
    ],
    entry_points={
        'console_scripts': [
            'subtitle-translator=subtitle_translator.cli.main:main',
        ],
    },
    python_requires='>=3.8',
)
