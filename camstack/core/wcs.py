import typing as t
from math import cos, sin

from camstack.core.utilities import KWType

WCSDictType = t.Dict[str, t.Tuple[KWType, str, str, str]]


def wcs_dict_init(
        wcs_num: int,
        pix: t.Tuple[float, float],
        delt_val: float,
        cd_rot_rad: float = 0.0,
        double_with_subaru_fake_standard: bool = True,
) -> WCSDictType:

    assert wcs_num < 10 and wcs_num >= 0

    if wcs_num == 0:
        wcsl = ''
    else:  # 1 - 25 # We start at 'B' and skip 'A'
        wcsl = chr(65 + wcs_num)

    # WARNING: per-camera WCS keys are capped to 4 chars... cause
    # we use 3 for x_B, 1 at the end for WCS number...

    # Other warning: the WCS keys that change with telescope pointing (CRVAL1,2)
    # Will always come from the aux header.

    # yapf: disable
    wcs_kw_basedict: t.Dict[str, t.Tuple[KWType, str, str, str]] = {
        'CDELT1': (delt_val, 'X Scale projected on detector (#/pix)', '%20.8f', 'CDE1'),
        'CDELT2': (delt_val, 'Y Scale projected on detector (#/pix)', '%20.8f', 'CDE2'),
        'CUNIT1': ('DEGREE    ', 'Units used in both CRVAL1 and CDELT1', '%-10s', 'CUN1'),
        'CUNIT2': ('DEGREE    ', 'Units used in both CRVAL2 and CDELT2', '%-10s', 'CUN2'),
        'CTYPE1': ('RA---TAN  ', 'Pixel coordinate system', '%-10s', 'CTP1'),
        'CTYPE2': ('DEC--TAN  ', 'Pixel coordinate system', '%-10s', 'CTP2'),
        'CRPIX1': ( pix[0], 'Reference pixel in X (pixel)', '%20.1f', 'CPX1'),
        'CRPIX2': ( pix[1], 'Reference pixel in Y (pixel)', '%20.1f', 'CPX2'),
        'CD1_1': (delt_val * cos(cd_rot_rad),
                  'Pixel coordinate translation matrix', '%20.8f', 'CD11'),
        'CD1_2': (-delt_val * sin(cd_rot_rad),
                  'Pixel coordinate translation matrix', '%20.8f', 'CD12'),
        'CD2_1': (delt_val * sin(cd_rot_rad),
                  'Pixel coordinate translation matrix', '%20.8f', 'CD21'),
        'CD2_2': (delt_val * cos(cd_rot_rad),
                  'Pixel coordinate translation matrix', '%20.8f', 'CD22'),
    }
    # yapf: enable

    wcs_kw_final_dict: t.Dict[str, t.Tuple[KWType, str, str, str]] = {}

    for key in wcs_kw_basedict:
        val, comment, fmt, subkey = wcs_kw_basedict[key]
        new_key = key + wcsl  # CD1_1 -> CD1_1B
        new_subkey = subkey + wcsl  # CD11 -> CD11B
        wcs_kw_final_dict[new_key] = (val, comment, fmt, new_subkey)

        if double_with_subaru_fake_standard and wcs_num > 0:
            subaru_key = f'{key[0]:s}{wcs_num+1:1d}{key[2:]:s}'  # CD1_1 -> C21_1
            subaru_subkey = subkey + f'{wcs_num+1:1d}'  # CD11 -> C211
            wcs_kw_final_dict[subaru_key] = (val, comment, fmt, subaru_subkey)

    return wcs_kw_final_dict


def wcs_dummy_dict(
        wcs_num: int,
        double_with_subaru_fake_standard: bool = True,
) -> WCSDictType:

    return wcs_dict_init(
            wcs_num, (12345.6, 12345.6), -0.654321,
            double_with_subaru_fake_standard=double_with_subaru_fake_standard)
