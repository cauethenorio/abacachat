#!/usr/bin/env python
# coding: utf-8

"""
Setup script for abacachat.
"""

import setuptools

from abacachat import __project__, __version__

import os
README = open('README.rst').read() if os.path.exists('README.rst') else ''
CHANGES = open('CHANGES.md').read()


setuptools.setup(
    name=__project__,
    version=__version__,

    description="A simple but extensible gevent websocket chat.",
    url='https://github.com/cauethenorio/abacachat',
    author='Cauê Thenório',
    author_email='cauelt@gmail.com',

    packages=setuptools.find_packages(),

    entry_points={'console_scripts': []},
    zip_safe=False,

    long_description=(README + '\n' + CHANGES),
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
    ],

    install_requires=open('requirements.txt').readlines(),
)
