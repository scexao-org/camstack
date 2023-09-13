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
        './viewers/anycam.py',
        './viewers/pueo.py',
        './viewers/apapane.py',
        './viewers/palila.py',
        './viewers/firstcam.py',
        './viewers/vcam1.py',
        './viewers/vcam2.py',
        './viewers/vpupcam.py',
        './scripts/cam-restartdeps',
        './scripts/cam-apapanestart',
        './scripts/cam-palilastart',
        './scripts/cam-iiwistart',
        './scripts/cam-glintstart',
        './scripts/cam-ocamstart',
        './scripts/cam-kiwikiustart',
        './scripts/cam-fircamstart',
        './scripts/cam-firstpupstart',
        './scripts/cam-alalacamstart',
        './scripts/cam-vpupcamstart',
        './scripts/cam-vcamstart',
        './scripts/cam-vcam1start',
        './scripts/cam-vcam2start',
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
        install_requires=['docopt', 'libtmux', 'pygame', "rich"],
        scripts=scripts,
        cmdclass={'develop': PreInstallCommand},
)
