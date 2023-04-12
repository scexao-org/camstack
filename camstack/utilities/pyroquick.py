import camstack.pyro_keys as pk
from swmain.network.pyroclient import connect

if __name__ == "__main__":

    try:
        ocam = pueo = connect(pk.PUEO)
    except:
        pass

    try:
        pa = palila = connect(pk.PALILA)
    except:
        pass
    try:
        ap = apapane = connect(pk.APAPANE)
    except:
        pass
    try:
        ki = kiwi = kiwikiu = connect(pk.KIWI)
    except:
        pass
    try:
        glint = connect(pk.GLINT)
    except:
        pass
