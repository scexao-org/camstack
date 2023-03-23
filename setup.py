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
        # Migration of compiled grabbers to hardwaresecrets repo.
        #os.system('cd src; ./compile_edt; cd ..')
        #os.system('cd src; ./compile_dcamusb; cd ..')
        develop.run(self)


with open("README.md", 'r') as f:
    long_description = f.read()

scripts = [
        './camstack/viewers/viewers/anycam.py',
        './camstack/viewers/viewers/pueo.py',
        './camstack/viewers/viewers/apapane.py',
        './camstack/viewers/viewers/palila.py',
        './camstack/viewers/viewers/firstcam.py',
        './camstack/viewers/viewers/vpupcam.py',
        './scripts/cam-restartdeps',
        './scripts/cam-apapanestart',
        './scripts/cam-palilastart',
        './scripts/cam-glintstart',
        './scripts/cam-ocamstart',
        './scripts/cam-milesstart',
        './scripts/cam-kiwikiustart',
        './scripts/cam-fircamstart',
        './scripts/cam-firstpupstart',
        './scripts/cam-alalacamstart',
        './scripts/cam-vpupcamstart',
        './scripts/cam-vcamautostart',
]

setup(
        name='camstack',
        version='0.01',
        description='SCExAO unified EDT cameras to streams',
        long_description=long_description,
        author='Vincent Deo',
        author_email='vdeo@naoj.org',
        url="http://www.github.com/scexao-org/camstack",
        packages=['camstack'],  # same as name
        install_requires=['docopt', 'libtmux', 'pygame'],
        scripts=scripts,
        cmdclass={'develop': PreInstallCommand},
)
