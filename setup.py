from setuptools import setup, find_packages

setup(
    name="telegram_view",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'aiogram',
        'python-dotenv'
    ]
)