# coding=UTF-8
"""Setuptools package definition"""
import sys

from setuptools import setup

_install_requires = [
    "binaryornot",
    "six",
    "chardet",
    "termcolor",
]

if sys.version_info < (2, 7):
    _install_requires.append("argparse")

with open('README.rst', 'r') as f:
    README_TEXT = f.read()

setup(
    name = "finja",
    version = "1.0.8",
    py_modules = ["finja"],
    entry_points = {
        'console_scripts': [
            "finja=finja:main",
            "finjacol=finja:col_main",
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
    ]
)
