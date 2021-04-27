'''
camstack setup.py

deps:
    libtmux
    pyMilk
    docopt
'''

from setuptools import setup
from setuptools.command.install import install
from setuptools.command.develop import develop
from subprocess import check_call

import os

class PreInstallCommand(develop):
    def run(self):
        os.system('cd camstack/core; sudo make clean all; cd ../..')
        # A manual copy to the PATH maybe necessary - it doesn't seem the script line works for this.
        develop.run(self)

with open("README.md", 'r') as f:
    long_description = f.read()

scripts = [
    './viewers/buffycam.py',
    './viewers/chuckcam.py',
    './scripts/startOCAM',
    './scripts/startChuck',
    './scripts/startBuffy',
]

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
        scripts = scripts,#, './camstack/core/make_cset_and_rt'],
        cmdclass={'develop': PreInstallCommand},
    )

