#!/usr/bin/env python
'''
    spinnaker USB3 camera framegrabber

    Usage:
        simcam_framegen <name> <size_x> <size_y> [options]

    Options:
        -s <stream_name> SHM name
        -l <loops>       Number of images to take (0 for free run) [default: 0]
        -R               Attempt SHM reuse if possible
        -t <type>      datatype (see below) [default: f32].

Types: f32, f64, c64, c128, u8, u16, u32, u64, i8, i16, i32, i64
'''
import time
from threading import Timer

from pyMilk.interfacing.shm_functions import creashmim
import numpy as np

TYPE_DICT = {
        'f32': np.float32,
        'f64': np.float64,
        'c64': np.csingle,
        'c128': np.cdouble,
        'i8': np.int8,
        'i16': np.int16,
        'i32': np.int32,
        'i64': np.int64,
        'u8': np.uint8,
        'u16': np.uint16,
        'u32': np.uint32,
        'u64': np.uint64,
}


def make_data_circ_buff(r: int, c: int, type: np.dtype) -> np.ndarray:
    row_ramp_01 = np.linspace(0, 1, r, True)
    extended_cols = np.arange(2 * c - 1)

    freq1, freq2 = np.random.randint(c // 10) / c, np.random.randint(
            c // 10) / c

    sine1 = np.sin(2 * np.pi * extended_cols * freq1).astype(np.float32)
    sine2 = np.sin(2 * np.pi * extended_cols * freq2).astype(np.float32)

    buffer_float = row_ramp_01[:, None] * sine1[None, :] + (
            1 - row_ramp_01[:, None]) * sine2[None, :]

    return ((buffer_float + 1.) * 63.5).astype(type)


if __name__ == '__main__':
    import docopt

    args = docopt.docopt(__doc__)

    arg_stream_name = args['<name>']
    arg_size_x = int(args['<size_x>'])
    arg_size_y = int(args['<size_y>'])

    arg_n_loops = int(args['-l'])
    arg_attempt_reuse = args['-R']

    data_type = TYPE_DICT[args['-t']]

    # Create the target SHM
    shm = creashmim(arg_stream_name, (arg_size_x, arg_size_y), data_type,
                    nb_kw=50, attempt_reuse=arg_attempt_reuse)

    shm.set_keywords({
            'MFRATE': (0.0, "Measured frame rate (Hz)"),
            '_MAQTIME': (int(time.time() * 1e6),
                         "Frame acq time (us, CLOCK_REALTIME)"),
            '_FGSIZE1': (arg_size_x,
                         "Size of frame grabber for the X axis (pixel)"),
            '_FGSIZE2': (arg_size_y,
                         "Size of frame grabber for the Y axis (pixel)"),
            '_ETIMEUS': (10000, "Period for the sim frame generation (us).")
    })

    data_circ_buff = make_data_circ_buff(arg_size_x, arg_size_y, data_type)

    data_circ_buff = np.random.poisson(data_circ_buff).astype(data_type)

    exptime = shm.get_keywords()['_ETIMEUS']
    count = 1
    mfrate = 1e6 / exptime
    mfrate_gain = 0.01

    t = 0
    t_new = 0
    t_next = 0

    while count != arg_n_loops:
        if count > 1:
            while t_next - time.time() > 1e-3:  # Horrible semi-busy wait...
                time.sleep(1e-9)  # Wall time is ~50 us
            while t_next - time.time() > 0:  # Horrible busy wait.
                pass

        t_new = time.time()
        t_next = t_new + exptime * 1e-6

        t_us = int(t_new * 1e6)
        dt_s_float = t_new - t
        t = t_new

        exptime = shm.get_keywords()['_ETIMEUS']  # If any change.
        mfrate = (1 - mfrate_gain) * mfrate + 1 / dt_s_float * mfrate_gain
        shm.update_keyword('MFRATE', mfrate)
        shm.update_keyword('_MAQTIME', t_us)

        shm.set_data(data_circ_buff[:,
                                    (count % arg_size_y):(count % arg_size_y) +
                                    arg_size_y])

        count += 1
