from setuptools import setup, find_packages

setup(
    name="telegram_view",
    version="0.1",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=["aiogram", "python-dotenv"],
    include_package_data=True,  # Ensure package includes non-code files
    author="Ozernoy",
    description="Telegram integration for smart-orchestrator",
)
