from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [
        line.strip() for line in fh if line.strip() and not line.startswith("#")
    ]

setup(
    name="fastrict",
    version="0.0.3",
    author="Mohammad Mahdi Samei",
    author_email="9259samei@gmail.com",
    description="A comprehensive rate limiting system for FastAPI with Redis backend",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/msameim181/fastrict",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Framework :: FastAPI",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-asyncio>=0.18.0",
            "pytest-cov>=2.0",
            "black>=22.0",
            "flake8>=4.0",
            "mypy>=0.950",
            "pre-commit>=2.0",
        ],
        "docs": [
            "mkdocs>=1.4",
            "mkdocs-material>=8.0",
            "mkdocstrings[python]>=0.19",
        ],
    },
    keywords="fastapi rate limiting redis middleware decorator throttle",
    project_urls={
        "Bug Reports": "https://github.com/msameim181/fastrict/issues",
        "Source": "https://github.com/msameim181/fastrict",
        "Documentation": "https://fastrict.readthedocs.io/",
    },
)
