# coding=UTF-8
"""Setuptools package definition"""
import sys

from setuptools import setup
from setuptools import find_packages

_install_requires = [
    "binaryornot",
    "six",
    "chardet",
    "termcolor",
]

if sys.version_info < (2, 7):
    _install_requires.append("argparse")

__version__  = None
version_file = "finja/version.py"
with open(version_file) as f:
    code = compile(f.read(), version_file, 'exec')
    exec(code)

with open('README.rst', 'r') as f:
    README_TEXT = f.read()

setup(
    name = "finja",
    version = __version__,
    packages = find_packages(),
    entry_points = {
        'console_scripts': [
            "finja=finja:main",
            "finjacol=finja:col_main",
            "finjagrep=finja:grep_main",
            "finjadup=finja:dup_main"
        ]
    },
    install_requires = _install_requires,
    author = "Jean-Louis Fuchs, David Vogt, Stefan Heinemann, Pablo Vergés",
    author_email = "ganwell@fangorn.ch",
    description = (
        "Index stuff and find it fast and without bloat"
    ),
    long_description = README_TEXT,
    keywords = "code index find text open",
    url = "https://www.adfinis-sygroup.ch",
    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: "
        "GNU Affero General Public License v3",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: PyPy"
    ]
)
