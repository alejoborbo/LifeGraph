from setuptools import setup, find_packages

setup(
    name="lifegraph",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "google-api-python-client",
        "google-auth-oauthlib",
        "click",
        "python-dotenv",
    ],
    entry_points={
        "console_scripts": [
            "lifegraph=lifegraph.cli:cli",
        ],
    },
)
