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


def alala() -> None:
    print_dep_warning('cam-alalacamstart', 'camstart alala')
    enforce_whichcomp('A')
    main(cam_name_arg='ALALA')


def apapane() -> None:
    print_dep_warning('cam-apapanestart', 'camstart apapane')
    enforce_whichcomp('5')
    main(cam_name_arg='APAPANE')


def first() -> None:
    print_dep_warning('cam-fircamstart', 'camstart first')
    enforce_whichcomp('K')
    main(cam_name_arg='FIRST')


def first_pupil() -> None:
    print_dep_warning('cam-firstpupstart', 'camstart first_pupil')
    enforce_whichcomp('K')
    main(cam_name_arg='FIRST_PUPIL')


def glint() -> None:
    print_dep_warning('cam-glintstart', 'camstart glint')
    enforce_whichcomp('5')
    main(cam_name_arg='GLINT')


def kalao() -> None:
    # NO COMPUTER ENFORCE! NOT A SCEXAO CAMERA!
    print_dep_warning('cam-nuvustart', 'camstart kalaocam')
    main(cam_name_arg='KALAO')


def kiwikiu() -> None:
    print_dep_warning('cam-kiwikiustart', 'camstart kiwikiu')
    enforce_whichcomp('5')
    main(cam_name_arg='KIWIKIU')


def pueo() -> None:
    print_dep_warning('cam-ocamstart', 'camstart pueo')
    enforce_whichcomp('5')
    main(cam_name_arg='PUEO')


def vpup() -> None:
    print_dep_warning('cam-vpupcamstart', 'camstart vpupcam')
    enforce_whichcomp('V')
    main(cam_name_arg='VPUPCAM')


def vcam1() -> None:
    print_dep_warning('cam-vcam1start', 'camstart vcam1')
    enforce_whichcomp('5')
    main(cam_name_arg='VCAM1')


def vcam2() -> None:
    print_dep_warning('cam-vcam2start', 'camstart vcam2')
    enforce_whichcomp('5')
    main(cam_name_arg='VCAM2')


def iiwi_but_actually_apapane() -> None:
    print_dep_warning('cam-iiwistart', 'camstart iiwi')
    enforce_whichcomp('AORTS')
    main(cam_name_arg='IIWI')


def palila() -> None:
    print_dep_warning('cam-palilastart', 'camstart palila')
    enforce_whichcomp('5')
    main(cam_name_arg='PALILA')


def simucam() -> None:
    print_dep_warning('cam-simucamstart', 'camstart simucam')
    main(cam_name_arg='SIMUCAM')
