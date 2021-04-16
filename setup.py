'''
camstack setup.py

deps:
    libtmux
    pyMilk
    docopt
'''

from setuptools import setup

with open("README.md", 'r') as f:
    long_description = f.read()

setup(
        name = 'camstack',
        version = '0.01',
        description = 'SCExAO unified EDT cameras to streams',
        long_description = long_description,
        author = 'Vincent Deo',
        author_email = 'vdeo@naoj.org',
        url = "http://www.github.com/milk-org/camstack",
        packages = ['camstack'],  # same as name
        install_requires = ['docopt', 'libtmux', 'pygame'],
        scripts = ['./buffycam.py', './chuckcam.py'])
