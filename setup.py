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
        # Add custom make commands here !
        os.system('cd src; ./compile; cd ..')
        develop.run(self)

with open("README.md", 'r') as f:
    long_description = f.read()

scripts = [
    './viewers/buffycam.py',
    './viewers/chuckcam.py',
    './scripts/startOCAM',
    './scripts/startChuck',
    './scripts/startBuffy',
    './scripts/startVampires',
    './scripts/startRajni',
    './scripts/startGLINT', # FIXME change names - "start" is too vague for something available system-wide
]

setup(
        name = 'camstack',
        version = '0.01',
        description = 'SCExAO unified EDT cameras to streams',
        long_description = long_description,
        author = 'Vincent Deo',
        author_email = 'vdeo@naoj.org',
        url = "http://www.github.com/scexao-org/camstack",
        packages = ['camstack'],  # same as name
        install_requires = ['docopt', 'libtmux', 'pygame'],
        scripts = scripts,
        cmdclass={'develop': PreInstallCommand},
    )

