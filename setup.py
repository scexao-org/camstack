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

WHICHCOMP = os.environ.get('WHICHCOMP', '')


class PreInstallCommand(develop):

    def run(self):
        # Add custom make commands here !
        # Migration of compiled grabbers to hardwaresecrets repo.
        #os.system('cd src; ./compile_edt; cd ..')
        #os.system('cd src; ./compile_dcamusb; cd ..')
        develop.run(self)


with open("README.md", 'r') as f:
    long_description = f.read()

scripts_everyone = [
        './viewers/anycam.py',
        './scripts/cam-restartdeps',
]

scripts_allviewers = [
        './viewers/pueo.py',
        './viewers/apapane.py',
        './viewers/palila.py',
        './viewers/firstcam.py',
        './viewers/vcam1.py',
        './viewers/vcam2.py',
        './viewers/vpupcam.py',
]

scripts_sc5 = [
        './scripts/cam-apapanestart',
        './scripts/cam-palilastart',
        './scripts/cam-glintstart',
        './scripts/cam-ocamstart',
        './scripts/cam-kiwikiustart',
        './scripts/cam-vpupcamstart',
        './scripts/cam-vcamstart',
        './scripts/cam-vcam1start',
        './scripts/cam-vcam2start',
]

scripts_alala = [
        './scripts/cam-alalacamstart',
]

scripts_kamua = [
        './scripts/cam-firstpupstart',
        './scripts/cam-fircamstart',
]

scripts_aorts = ['./scripts/cam-apdstart', './scripts/cam-iiwistart']

what_scripts = scripts_allviewers + scripts_everyone

what_scripts += {
        'AORTS': scripts_aorts,
        '5': scripts_sc5,
        'K': scripts_kamua,
        'A': scripts_alala,
}.get(WHICHCOMP, [])

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
        scripts=what_scripts,
        cmdclass={'develop': PreInstallCommand},
)
