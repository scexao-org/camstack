'''
    Most of the work is performed in the pyproject.toml

    The goal is to offer an equivalent binding to legacy scripts

    cam-<camname>start

    into the new syntax

    camname <camname>
'''

from camstack.core.utilities import enforce_whichcomp

from .depwarning import print_dep_warning
from camstack.cam_mains.main import main


def alala():
    enforce_whichcomp('A')
    print_dep_warning('cam-alalacamstart', 'camstart alala')
    main(cam_name_arg='ALALA')


def apapane():
    enforce_whichcomp('5')
    print_dep_warning('cam-apapanestart', 'camstart apapane')
    main(cam_name_arg='APAPANE')


def first():
    enforce_whichcomp('K')
    print_dep_warning('cam-fircamstart', 'camstart first')
    main(cam_name_arg='FIRST')


def first_pupil():
    enforce_whichcomp('K')
    print_dep_warning('cam-firstpupstart', 'camstart first_pupil')
    main(cam_name_arg='FIRST_PUPIL')


def glint():
    enforce_whichcomp('5')
    print_dep_warning('cam-glintstart', 'camstart glint')
    main(cam_name_arg='GLINT')


def kalao():
    # NO COMPUTER ENFORCE! NOT A SCEXAO CAMERA!
    print_dep_warning('cam-nuvustart', 'camstart kalaocam')
    main(cam_name_arg='KALAO')


def kiwikiu():
    enforce_whichcomp('5')
    print_dep_warning('cam-kiwikiustart', 'camstart kiwikiu')
    main(cam_name_arg='KIWIKIU')


def pueo():
    enforce_whichcomp('5')
    print_dep_warning('cam-ocamstart', 'camstart pueo')
    main(cam_name_arg='PUEO')


def vpup():
    enforce_whichcomp('V')
    print_dep_warning('cam-vpupcamstart', 'camstart vpupcam')
    main(cam_name_arg='VPUPCAM')


def vcam1():
    enforce_whichcomp('5')
    print_dep_warning('cam-vcam1start', 'camstart vcam1')
    main(cam_name_arg='VCAM1')


def vcam2():
    enforce_whichcomp('5')
    print_dep_warning('cam-vcam2start', 'camstart vcam2')
    main(cam_name_arg='VCAM2')


def iiwi_but_actually_apapane():
    enforce_whichcomp('AORTS')
    print_dep_warning('cam-iiwistart', 'camstart iiwi')
    main(cam_name_arg='IIWI')


def palila():
    enforce_whichcomp('5')
    print_dep_warning('cam-palilastart', 'camstart palila')
    main(cam_name_arg='PALILA')
