"""
Setup script for Humand SDK.

注意：本包仅发布 `humand_sdk/`，不包含服务端 `server/`。
"""

from setuptools import setup, find_packages
import os


def read_readme() -> str:
    """Read the project README file."""
    readme_path = os.path.join(os.path.dirname(__file__), "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

setup(
    name="humand-sdk",
    version="0.1.0",
    author="Humand Team",
    author_email="support@humand.io",
    description="Human-in-the-Loop Approval System for LangGraph",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/humand-io/humand-sdk",
    packages=find_packages(include=["humand_sdk*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.25.0",
        "typing-extensions>=4.0.0; python_version<'3.8'",
    ],
    extras_require={
        "langgraph": [
            "langgraph>=0.0.60",
            "langchain-core>=0.1.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "isort>=5.10.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0",
        ],
        "examples": [
            "langgraph>=0.0.60",
            "langchain-core>=0.1.0",
            "langchain-openai>=0.1.0",
            "python-dotenv>=1.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "humand=humand_sdk.cli:main",
        ],
    },
    keywords="approval, human-in-the-loop, langgraph, workflow, ai, automation",
    project_urls={
        "Bug Reports": "https://github.com/humand-io/humand-sdk/issues",
        "Source": "https://github.com/humand-io/humand-sdk",
        "Documentation": "https://docs.humand.io",
    },
    include_package_data=True,
    zip_safe=False,
)
