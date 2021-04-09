#
# 11-2020: This file reduced to ONLY manage the DLL import and binding
# See the original in hardw-cred2
#
#
# Former EDTIf code (python implementation of CRED2) moved to various files: edtcamera.py, cred2.py.
#

from ctypes import (CDLL, POINTER, c_char, c_int, c_int64, c_uint, c_void_p, c_char_p, c_short, c_uint16, c_ulong, 
                    create_string_buffer, byref)

try:
    EdtDLL = CDLL("/opt/EDTpdv/libpdv.so")
except OSError as e:
    print('=============')
    print("OSError: maybe can't locate libpdv.so")
    print("If /opt/EDTpdv/libpdv.so does not exist")
    print("It can be built with a 'make libpdv.so' at that location.")
    print('\nRe-raising error:')
    raise e


def initEdtDLL():
    '''
        Initialize the API signatures

        Dec 2020 - using driver version 5.5.10.0 [Nov 4th 2020 release]
        - may need to check signatures if some stuff is broken
        https://edt.com/api/group__dv.html

    '''

    EdtDLL.pdv_close.argtypes = [c_void_p]

    EdtDLL.pdv_enable_external_trigger.argtypes = [c_void_p, c_int]

    EdtDLL.pdv_flush_fifo.argtypes = [c_void_p]

    EdtDLL.pdv_get_height.argtypes = [c_void_p]
    EdtDLL.pdv_get_height.restype = c_int

    EdtDLL.pdv_set_width.argtype = [c_void_p, c_int64]
    EdtDLL.pdv_set_width.restype = c_int
    
    EdtDLL.pdv_set_height.argtype = [c_void_p, c_int64]
    EdtDLL.pdv_set_height.restype = c_int

    EdtDLL.pdv_get_timeout.argtypes = [c_void_p, c_int]
    EdtDLL.pdv_get_timeout.restype = c_int

    EdtDLL.pdv_get_width.argtypes = [c_void_p]
    EdtDLL.pdv_get_width.restype = c_int

    EdtDLL.pdv_last_image_timed.argtypes = [c_void_p, c_void_p]
    EdtDLL.pdv_last_image_timed.restype = POINTER(c_short)

    EdtDLL.pdv_multibuf.argtypes = [c_void_p, c_int]

    EdtDLL.pdv_open_channel.argtypes = [c_char_p, c_int, c_int]
    EdtDLL.pdv_open_channel.restype = c_void_p

    EdtDLL.pdv_serial_command.argtypes = [c_void_p, c_char_p]
    EdtDLL.pdv_serial_command.restype = c_int

    EdtDLL.pdv_serial_read.argtypes = [c_void_p, c_char_p, c_int]
    EdtDLL.pdv_serial_read.restype = c_int

    EdtDLL.pdv_serial_wait.argtypes = [c_void_p, c_int, c_int]
    EdtDLL.pdv_serial_wait.restype = c_int

    EdtDLL.pdv_set_exposure.argtypes = [c_void_p, c_int]

    EdtDLL.pdv_set_timeout.argtypes = [c_void_p, c_int]

    EdtDLL.pdv_start_images.argtypes = [c_void_p, c_int]

    EdtDLL.pdv_timeout_restart.argtypes = [c_void_p, c_int]

    EdtDLL.pdv_timeouts.argtypes = [c_void_p]
    EdtDLL.pdv_timeouts.restype = c_int

    EdtDLL.pdv_wait_image_timed.argtypes = [c_void_p, c_void_p]
    EdtDLL.pdv_wait_image_timed.restype = POINTER(c_short)

    EdtDLL.pdv_wait_last_image.argtypes = [c_void_p, c_void_p]
    EdtDLL.pdv_wait_last_image.restype = POINTER(c_short)

    '''
    # Autogen (plus some manual replacing) using
    from pyclibrary.c_parser import CParser
    p = CParser(['/opt/EDTpdv/libpdv.h'])
    p.process_all()
    functionSignatures = p.defs['functions']
    for func_name in functionSignatures: 
        sign = functionSignatures[func_name] 
        print(f'# {func_name}') 
        print(f'EdtDLL.{func_name}.restype = {sign[0]}') 
        largs = str([s[1] for s in sign[1]]) 
        print(f'EdtDLL.{func_name}.argtype = {largs}') 
        print('')
    '''

    '''
    # ALL OF THE SUBSEQUENT IS A BIT BROKEN - POSSIBLY BECAUSE
    # libpdv.so is a C++ DLL and CDLL doesn't support it
    # Will try to keep the set of functions to a minimum to
    # Try and navigate between segfaults.

    # pdv_open
    EdtDLL.pdv_open.restype = c_void_p
    EdtDLL.pdv_open.argtype = [c_char_p, c_int]

    # pdv_open_device
    EdtDLL.pdv_open_device.restype = c_void_p
    EdtDLL.pdv_open_device.argtype = [c_char_p, c_int, c_int, c_int]

    # pdv_open_channel
    EdtDLL.pdv_open_channel.restype = c_void_p
    EdtDLL.pdv_open_channel.argtype = [c_char_p, c_int, c_int]

    # pdv_serial_txrx
    EdtDLL.pdv_serial_txrx.argtype = [c_void_p, c_char_p, c_int, c_char_p, c_int, c_int, c_char_p]

    # pdv_close
    EdtDLL.pdv_close.restype = c_int
    EdtDLL.pdv_close.argtype = [c_void_p]

    # pdv_read
    EdtDLL.pdv_read.restype = c_int
    EdtDLL.pdv_read.argtype = [c_void_p, c_char_p, c_ulong]

    # pdv_image
    EdtDLL.pdv_image.restype = c_char_p
    EdtDLL.pdv_image.argtype = [c_void_p]

    # pdv_start_image
    EdtDLL.pdv_start_image.argtype = [c_void_p]

    # pdv_start_images
    EdtDLL.pdv_start_images.argtype = [c_void_p, c_int]

    # pdv_perror
    EdtDLL.pdv_perror.argtype = [c_char_p]

    # pdv_setdebug
    EdtDLL.pdv_setdebug.argtype = [c_void_p, c_int]

    # pdv_new_debug
    EdtDLL.pdv_new_debug.argtype = [c_int]

    # pdv_start_hardware_continuous
    EdtDLL.pdv_start_hardware_continuous.argtype = [c_void_p]

    # pdv_stop_hardware_continuous
    EdtDLL.pdv_stop_hardware_continuous.argtype = [c_void_p]

    # pdv_flush_fifo
    EdtDLL.pdv_flush_fifo.argtype = [c_void_p]

    # pdv_flush_channel_fifo
    EdtDLL.pdv_flush_channel_fifo.argtype = [c_void_p]

    # pdv_set_interlace
    EdtDLL.pdv_set_interlace.argtype = [c_void_p, c_int]

    # pdv_wait_image
    EdtDLL.pdv_wait_image.restype = c_char_p
    EdtDLL.pdv_wait_image.argtype = [c_void_p]

    # pdv_last_image_timed
    EdtDLL.pdv_last_image_timed.restype = c_char_p
    EdtDLL.pdv_last_image_timed.argtype = [c_void_p, POINTER(c_uint)]

    # pdv_wait_last_image_timed
    EdtDLL.pdv_wait_last_image_timed.restype = c_char_p
    EdtDLL.pdv_wait_last_image_timed.argtype = [c_void_p, POINTER(c_uint)]

    # pdv_wait_image_timed
    EdtDLL.pdv_wait_image_timed.restype = c_char_p
    EdtDLL.pdv_wait_image_timed.argtype = [c_void_p, POINTER(c_uint)]

    # pdv_wait_images_timed
    EdtDLL.pdv_wait_images_timed.restype = c_char_p
    EdtDLL.pdv_wait_images_timed.argtype = [c_void_p, c_int, POINTER(c_uint)]

    # pdv_wait_images
    EdtDLL.pdv_wait_images.restype = c_char_p
    EdtDLL.pdv_wait_images.argtype = [c_void_p, c_int]

    # pdv_wait_image_raw
    EdtDLL.pdv_wait_image_raw.restype = c_char_p
    EdtDLL.pdv_wait_image_raw.argtype = [c_void_p]

    # pdv_last_image_timed_raw
    EdtDLL.pdv_last_image_timed_raw.restype = c_char_p
    EdtDLL.pdv_last_image_timed_raw.argtype = [c_void_p, POINTER(c_uint), c_int]

    # pdv_wait_last_image_timed_raw
    EdtDLL.pdv_wait_last_image_timed_raw.restype = c_char_p
    EdtDLL.pdv_wait_last_image_timed_raw.argtype = [c_void_p, POINTER(c_uint), c_int]

    # pdv_wait_image_timed_raw
    EdtDLL.pdv_wait_image_timed_raw.restype = c_char_p
    EdtDLL.pdv_wait_image_timed_raw.argtype = [c_void_p, POINTER(c_uint), c_int]

    # pdv_wait_images_timed_raw
    EdtDLL.pdv_wait_images_timed_raw.restype = c_char_p
    EdtDLL.pdv_wait_images_timed_raw.argtype = [c_void_p, c_int, POINTER(c_uint), c_int]

    # pdv_wait_images_raw
    EdtDLL.pdv_wait_images_raw.restype = c_char_p
    EdtDLL.pdv_wait_images_raw.argtype = [c_void_p, c_int]

    # pdv_get_cameratype
    EdtDLL.pdv_get_cameratype.restype = c_char_p
    EdtDLL.pdv_get_cameratype.argtype = [c_void_p]

    # pdv_get_camera_class
    EdtDLL.pdv_get_camera_class.restype = c_char_p
    EdtDLL.pdv_get_camera_class.argtype = [c_void_p]

    # pdv_get_camera_model
    EdtDLL.pdv_get_camera_model.restype = c_char_p
    EdtDLL.pdv_get_camera_model.argtype = [c_void_p]

    # pdv_get_camera_info
    EdtDLL.pdv_get_camera_info.restype = c_char_p
    EdtDLL.pdv_get_camera_info.argtype = [c_void_p]

    # pdv_camera_type
    EdtDLL.pdv_camera_type.restype = c_char_p
    EdtDLL.pdv_camera_type.argtype = [c_void_p]

    # pdv_get_width
    EdtDLL.pdv_get_width.restype = c_int
    EdtDLL.pdv_get_width.argtype = [c_void_p]

    # pdv_get_pitch
    EdtDLL.pdv_get_pitch.restype = c_int
    EdtDLL.pdv_get_pitch.argtype = [c_void_p]

    # pdv_get_height
    EdtDLL.pdv_get_height.restype = c_int
    EdtDLL.pdv_get_height.argtype = [c_void_p]

    # pdv_get_interleave_data
    EdtDLL.pdv_get_interleave_data.restype = c_char_p
    EdtDLL.pdv_get_interleave_data.argtype = [c_void_p, c_char_p, c_int]

    # pdv_bytes_per_line
    EdtDLL.pdv_bytes_per_line.restype = c_int
    EdtDLL.pdv_bytes_per_line.argtype = [c_int, c_int]

    # pdv_setsize
    EdtDLL.pdv_setsize.restype = c_int
    EdtDLL.pdv_setsize.argtype = [c_void_p, c_int, c_int]

    # pdv_get_depth
    EdtDLL.pdv_get_depth.restype = c_int
    EdtDLL.pdv_get_depth.argtype = [c_void_p]

    # pdv_get_extdepth
    EdtDLL.pdv_get_extdepth.restype = c_int
    EdtDLL.pdv_get_extdepth.argtype = [c_void_p]

    # pdv_set_depth
    EdtDLL.pdv_set_depth.restype = c_int
    EdtDLL.pdv_set_depth.argtype = [c_void_p, c_int]

    # pdv_set_extdepth
    EdtDLL.pdv_set_extdepth.restype = c_int
    EdtDLL.pdv_set_extdepth.argtype = [c_void_p, c_int]

    # pdv_set_depth_extdepth
    EdtDLL.pdv_set_depth_extdepth.restype = c_int
    EdtDLL.pdv_set_depth_extdepth.argtype = [c_void_p, c_int, c_int]

    # pdv_set_depth_extdepth_dpath
    EdtDLL.pdv_set_depth_extdepth_dpath.restype = c_int
    EdtDLL.pdv_set_depth_extdepth_dpath.argtype = [c_void_p, c_int, c_int, c_uint]

    # pdv_cl_set_base_channels
    EdtDLL.pdv_cl_set_base_channels.argtype = [c_void_p, c_int, c_int]

    # pdv_get_imagesize
    EdtDLL.pdv_get_imagesize.restype = c_int
    EdtDLL.pdv_get_imagesize.argtype = [c_void_p]

    # pdv_image_size
    EdtDLL.pdv_image_size.restype = c_int
    EdtDLL.pdv_image_size.argtype = [c_void_p]

    # pdv_get_dmasize
    EdtDLL.pdv_get_dmasize.restype = c_int
    EdtDLL.pdv_get_dmasize.argtype = [c_void_p]

    # pdv_get_rawio_size
    EdtDLL.pdv_get_rawio_size.restype = c_int
    EdtDLL.pdv_get_rawio_size.argtype = [c_void_p]

    # pdv_get_allocated_size
    EdtDLL.pdv_get_allocated_size.restype = c_int
    EdtDLL.pdv_get_allocated_size.argtype = [c_void_p]

    # pdv_get_fulldma_size
    EdtDLL.pdv_get_fulldma_size.restype = c_int
    EdtDLL.pdv_get_fulldma_size.argtype = [c_void_p, POINTER(c_int)]

    # pdv_set_shutter_method
    EdtDLL.pdv_set_shutter_method.restype = c_int
    EdtDLL.pdv_set_shutter_method.argtype = [c_void_p, c_int, c_uint]

    # pdv_set_exposure
    EdtDLL.pdv_set_exposure.restype = c_int
    EdtDLL.pdv_set_exposure.argtype = [c_void_p, c_int]

    # pdv_set_exposure_mcl
    EdtDLL.pdv_set_exposure_mcl.restype = c_int
    EdtDLL.pdv_set_exposure_mcl.argtype = [c_void_p, c_int]

    # pdv_set_gain
    EdtDLL.pdv_set_gain.restype = c_int
    EdtDLL.pdv_set_gain.argtype = [c_void_p, c_int]

    # pdv_set_blacklevel
    EdtDLL.pdv_set_blacklevel.restype = c_int
    EdtDLL.pdv_set_blacklevel.argtype = [c_void_p, c_int]

    # pdv_set_binning
    EdtDLL.pdv_set_binning.restype = c_int
    EdtDLL.pdv_set_binning.argtype = [c_void_p, c_int, c_int]

    # pdv_set_mode
    EdtDLL.pdv_set_mode.restype = c_int
    EdtDLL.pdv_set_mode.argtype = [c_void_p, c_char_p, c_int]

    # pdv_get_exposure
    EdtDLL.pdv_get_exposure.restype = c_int
    EdtDLL.pdv_get_exposure.argtype = [c_void_p]

    # pdv_get_gain
    EdtDLL.pdv_get_gain.restype = c_int
    EdtDLL.pdv_get_gain.argtype = [c_void_p]

    # pdv_get_blacklevel
    EdtDLL.pdv_get_blacklevel.restype = c_int
    EdtDLL.pdv_get_blacklevel.argtype = [c_void_p]

    # pdv_set_aperture
    EdtDLL.pdv_set_aperture.restype = c_int
    EdtDLL.pdv_set_aperture.argtype = [c_void_p, c_int]

    # pdv_get_aperture
    EdtDLL.pdv_get_aperture.restype = c_int
    EdtDLL.pdv_get_aperture.argtype = [c_void_p]

    # pdv_set_timeout
    EdtDLL.pdv_set_timeout.restype = c_int
    EdtDLL.pdv_set_timeout.argtype = [c_void_p, c_int]

    # pdv_auto_set_timeout
    EdtDLL.pdv_auto_set_timeout.restype = c_int
    EdtDLL.pdv_auto_set_timeout.argtype = [c_void_p]

    # pdv_get_timeout
    EdtDLL.pdv_get_timeout.restype = c_int
    EdtDLL.pdv_get_timeout.argtype = [c_void_p]

    # pdv_update_values_from_camera
    EdtDLL.pdv_update_values_from_camera.restype = c_int
    EdtDLL.pdv_update_values_from_camera.argtype = [c_void_p]

    # pdv_overrun
    EdtDLL.pdv_overrun.restype = c_int
    EdtDLL.pdv_overrun.argtype = [c_void_p]

    # pdv_timeouts
    EdtDLL.pdv_timeouts.restype = c_int
    EdtDLL.pdv_timeouts.argtype = [c_void_p]

    # pdv_timeout_cleanup
    EdtDLL.pdv_timeout_cleanup.restype = c_int
    EdtDLL.pdv_timeout_cleanup.argtype = [c_void_p]

    # pdv_timeout_restart
    EdtDLL.pdv_timeout_restart.restype = c_int
    EdtDLL.pdv_timeout_restart.argtype = [c_void_p, c_int]

    # pdv_in_continuous
    EdtDLL.pdv_in_continuous.restype = c_int
    EdtDLL.pdv_in_continuous.argtype = [c_void_p]

    # pdv_serial_write
    EdtDLL.pdv_serial_write.restype = c_int
    EdtDLL.pdv_serial_write.argtype = [c_void_p, c_char_p, c_int]

    # pdv_serial_read
    EdtDLL.pdv_serial_read.restype = c_int
    EdtDLL.pdv_serial_read.argtype = [c_void_p, c_char_p, c_int]

    # pdv_serial_read_blocking
    EdtDLL.pdv_serial_read_blocking.restype = c_int
    EdtDLL.pdv_serial_read_blocking.argtype = [c_void_p, c_char_p, c_int]

    # pdv_serial_read_nullterm
    EdtDLL.pdv_serial_read_nullterm.restype = c_int
    EdtDLL.pdv_serial_read_nullterm.argtype = [c_void_p, c_char_p, c_int, c_int]

    # pdv_serial_read_enable
    EdtDLL.pdv_serial_read_enable.restype = c_int
    EdtDLL.pdv_serial_read_enable.argtype = [c_void_p]

    # pdv_serial_read_disable
    EdtDLL.pdv_serial_read_disable.restype = c_int
    EdtDLL.pdv_serial_read_disable.argtype = [c_void_p]

    # pdv_serial_check_enabled
    EdtDLL.pdv_serial_check_enabled.restype = c_int
    EdtDLL.pdv_serial_check_enabled.argtype = [c_void_p]

    # pdv_serial_term
    EdtDLL.pdv_serial_term.restype = c_char_p
    EdtDLL.pdv_serial_term.argtype = [c_void_p]

    # pdv_set_serial_delimiters
    EdtDLL.pdv_set_serial_delimiters.argtype = [c_void_p, c_char_p, c_char_p]

    # pdv_serial_prefix
    EdtDLL.pdv_serial_prefix.restype = c_char_p
    EdtDLL.pdv_serial_prefix.argtype = [c_void_p]

    # pdv_reset_serial
    EdtDLL.pdv_reset_serial.argtype = [c_void_p]

    # pdv_serial_command
    EdtDLL.pdv_serial_command.restype = c_int
    EdtDLL.pdv_serial_command.argtype = [c_void_p, c_char_p]

    # pdv_serial_command_flagged
    EdtDLL.pdv_serial_command_flagged.restype = c_int
    EdtDLL.pdv_serial_command_flagged.argtype = [c_void_p, c_char_p, c_uint]

    # pdv_serial_binary_command
    EdtDLL.pdv_serial_binary_command.restype = c_int
    EdtDLL.pdv_serial_binary_command.argtype = [c_void_p, c_char_p, c_int]

    # pdv_serial_binary_command_flagged
    EdtDLL.pdv_serial_binary_command_flagged.restype = c_int
    EdtDLL.pdv_serial_binary_command_flagged.argtype = [c_void_p, c_char_p, c_int, c_uint]

    # pdv_send_basler_frame
    EdtDLL.pdv_send_basler_frame.restype = c_int
    EdtDLL.pdv_send_basler_frame.argtype = [c_void_p, c_char_p, c_int]

    # pdv_read_basler_frame
    EdtDLL.pdv_read_basler_frame.restype = c_int
    EdtDLL.pdv_read_basler_frame.argtype = [c_void_p, c_char_p, c_int]

    # pdv_read_duncan_frame
    EdtDLL.pdv_read_duncan_frame.restype = c_int
    EdtDLL.pdv_read_duncan_frame.argtype = [c_void_p, c_char_p]

    # pdv_send_duncan_frame
    EdtDLL.pdv_send_duncan_frame.restype = c_int
    EdtDLL.pdv_send_duncan_frame.argtype = [c_void_p, c_char_p, c_int]

    # pdv_serial_command_hex
    EdtDLL.pdv_serial_command_hex.restype = c_int
    EdtDLL.pdv_serial_command_hex.argtype = [c_void_p, c_char_p, c_int]

    # pdv_serial_wait
    EdtDLL.pdv_serial_wait.restype = c_int
    EdtDLL.pdv_serial_wait.argtype = [c_void_p, c_int, c_int]

    # pdv_serial_get_numbytes
    EdtDLL.pdv_serial_get_numbytes.restype = c_int
    EdtDLL.pdv_serial_get_numbytes.argtype = [c_void_p]

    # pdv_serial_wait_next
    EdtDLL.pdv_serial_wait_next.restype = c_int
    EdtDLL.pdv_serial_wait_next.argtype = [c_void_p, c_int, c_int]

    # pdv_serial_write_available
    EdtDLL.pdv_serial_write_available.restype = c_int
    EdtDLL.pdv_serial_write_available.argtype = [c_void_p]

    # pdv_get_serial_block_size
    EdtDLL.pdv_get_serial_block_size.restype = c_int
    EdtDLL.pdv_get_serial_block_size.argtype = []

    # pdv_set_serial_block_size
    EdtDLL.pdv_set_serial_block_size.argtype = [c_int]

    # pdv_interlace_method
    EdtDLL.pdv_interlace_method.restype = c_int
    EdtDLL.pdv_interlace_method.argtype = [c_void_p]

    # pdv_read_response
    EdtDLL.pdv_read_response.restype = c_int
    EdtDLL.pdv_read_response.argtype = [c_void_p, c_char_p]

    # pdv_debug_level
    EdtDLL.pdv_debug_level.restype = c_int
    EdtDLL.pdv_debug_level.argtype = []

    # pdv_buffer_addresses
    EdtDLL.pdv_buffer_addresses.restype = POINTER(c_char_p)
    EdtDLL.pdv_buffer_addresses.argtype = [c_void_p]

    # pdv_alloc
    EdtDLL.pdv_alloc.restype = c_char_p
    EdtDLL.pdv_alloc.argtype = [c_int]

    # pdv_free
    EdtDLL.pdv_free.argtype = [c_char_p]

    # pdv_multibuf
    EdtDLL.pdv_multibuf.restype = c_int
    EdtDLL.pdv_multibuf.argtype = [c_void_p, c_int]

    # pdv_set_serial_parity
    EdtDLL.pdv_set_serial_parity.restype = c_int
    EdtDLL.pdv_set_serial_parity.argtype = [c_void_p, c_char]

    # pdv_set_baud
    EdtDLL.pdv_set_baud.restype = c_int
    EdtDLL.pdv_set_baud.argtype = [c_void_p, c_int]

    # pdv_get_baud
    EdtDLL.pdv_get_baud.restype = c_int
    EdtDLL.pdv_get_baud.argtype = [c_void_p]

    # pdv_check_fpga_rev
    EdtDLL.pdv_check_fpga_rev.argtype = [c_void_p]

    # pdv_check
    EdtDLL.pdv_check.argtype = [c_void_p]

    # pdv_checkfrm
    EdtDLL.pdv_checkfrm.argtype = [c_void_p, POINTER(c_uint16), c_uint, c_int]

    # pdv_set_roi
    EdtDLL.pdv_set_roi.restype = c_int
    EdtDLL.pdv_set_roi.argtype = [c_void_p, c_int, c_int, c_int, c_int]

    # pdv_get_roi_enabled
    EdtDLL.pdv_get_roi_enabled.restype = c_int
    EdtDLL.pdv_get_roi_enabled.argtype = [c_void_p]

    # pdv_auto_set_roi
    EdtDLL.pdv_auto_set_roi.restype = c_int
    EdtDLL.pdv_auto_set_roi.argtype = [c_void_p]

    # pdv_enable_roi
    EdtDLL.pdv_enable_roi.restype = c_int
    EdtDLL.pdv_enable_roi.argtype = [c_void_p, c_int]

    # pdv_set_cam_width
    EdtDLL.pdv_set_cam_width.restype = c_int
    EdtDLL.pdv_set_cam_width.argtype = [c_void_p, c_int]

    # pdv_set_cam_height
    EdtDLL.pdv_set_cam_height.restype = c_int
    EdtDLL.pdv_set_cam_height.argtype = [c_void_p, c_int]

    # pdv_access
    EdtDLL.pdv_access.restype = c_int
    EdtDLL.pdv_access.argtype = [c_char_p, c_int]

    # pdv_strobe
    EdtDLL.pdv_strobe.restype = c_int
    EdtDLL.pdv_strobe.argtype = [c_void_p, c_int, c_int]

    # pdv_set_strobe_dac
    EdtDLL.pdv_set_strobe_dac.restype = c_int
    EdtDLL.pdv_set_strobe_dac.argtype = [c_void_p, c_uint]

    # pdv_set_strobe_counters
    EdtDLL.pdv_set_strobe_counters.restype = c_int
    EdtDLL.pdv_set_strobe_counters.argtype = [c_void_p, c_int, c_int, c_int]

    # pdv_enable_strobe
    EdtDLL.pdv_enable_strobe.restype = c_int
    EdtDLL.pdv_enable_strobe.argtype = [c_void_p, c_int]

    # pdv_strobe_method
    EdtDLL.pdv_strobe_method.restype = c_int
    EdtDLL.pdv_strobe_method.argtype = [c_void_p]

    # pdv_setup_continuous
    EdtDLL.pdv_setup_continuous.argtype = [c_void_p]

    # pdv_setup_continuous_channel
    EdtDLL.pdv_setup_continuous_channel.argtype = [c_void_p]

    # pdv_stop_continuous
    EdtDLL.pdv_stop_continuous.argtype = [c_void_p]

    # pdv_get_min_shutter
    EdtDLL.pdv_get_min_shutter.restype = c_int
    EdtDLL.pdv_get_min_shutter.argtype = [c_void_p]

    # pdv_get_max_shutter
    EdtDLL.pdv_get_max_shutter.restype = c_int
    EdtDLL.pdv_get_max_shutter.argtype = [c_void_p]

    # pdv_get_min_gain
    EdtDLL.pdv_get_min_gain.restype = c_int
    EdtDLL.pdv_get_min_gain.argtype = [c_void_p]

    # pdv_get_max_gain
    EdtDLL.pdv_get_max_gain.restype = c_int
    EdtDLL.pdv_get_max_gain.argtype = [c_void_p]

    # pdv_get_min_offset
    EdtDLL.pdv_get_min_offset.restype = c_int
    EdtDLL.pdv_get_min_offset.argtype = [c_void_p]

    # pdv_get_max_offset
    EdtDLL.pdv_get_max_offset.restype = c_int
    EdtDLL.pdv_get_max_offset.argtype = [c_void_p]

    # pdv_invert
    EdtDLL.pdv_invert.argtype = [c_void_p, c_int]

    # pdv_get_invert
    EdtDLL.pdv_get_invert.restype = c_int
    EdtDLL.pdv_get_invert.argtype = [c_void_p]

    # pdv_set_firstpixel_counter
    EdtDLL.pdv_set_firstpixel_counter.argtype = [c_void_p, c_int]

    # pdv_get_firstpixel_counter
    EdtDLL.pdv_get_firstpixel_counter.restype = c_int
    EdtDLL.pdv_get_firstpixel_counter.argtype = [c_void_p]

    # pdv_send_break
    EdtDLL.pdv_send_break.argtype = [c_void_p]

    # pdv_get_last_image
    EdtDLL.pdv_get_last_image.restype = c_char_p
    EdtDLL.pdv_get_last_image.argtype = [c_void_p]

    # pdv_wait_last_image
    EdtDLL.pdv_wait_last_image.restype = c_char_p
    EdtDLL.pdv_wait_last_image.argtype = [c_void_p, POINTER(c_int)]

    # pdv_wait_next_image
    EdtDLL.pdv_wait_next_image.restype = c_char_p
    EdtDLL.pdv_wait_next_image.argtype = [c_void_p, POINTER(c_int)]

    # pdv_wait_last_image_raw
    EdtDLL.pdv_wait_last_image_raw.restype = c_char_p
    EdtDLL.pdv_wait_last_image_raw.argtype = [c_void_p, POINTER(c_int), c_int]

    # pdv_wait_next_image_raw
    EdtDLL.pdv_wait_next_image_raw.restype = c_char_p
    EdtDLL.pdv_wait_next_image_raw.argtype = [c_void_p, POINTER(c_int), c_int]

    # pdv_set_buffers
    EdtDLL.pdv_set_buffers.restype = c_int
    EdtDLL.pdv_set_buffers.argtype = [c_void_p, c_int, POINTER(c_char_p)]

    # pdv_set_buffers_x
    EdtDLL.pdv_set_buffers_x.restype = c_int
    EdtDLL.pdv_set_buffers_x.argtype = [c_void_p, c_int, c_int, POINTER(c_char_p)]

    # pdv_get_cam_width
    EdtDLL.pdv_get_cam_width.restype = c_int
    EdtDLL.pdv_get_cam_width.argtype = [c_void_p]

    # pdv_get_cam_height
    EdtDLL.pdv_get_cam_height.restype = c_int
    EdtDLL.pdv_get_cam_height.argtype = [c_void_p]

    # pdv_force_single
    EdtDLL.pdv_force_single.restype = c_int
    EdtDLL.pdv_force_single.argtype = [c_void_p]

    # pdv_variable_size
    EdtDLL.pdv_variable_size.restype = c_int
    EdtDLL.pdv_variable_size.argtype = [c_void_p]

    # pdv_pause_for_serial
    EdtDLL.pdv_pause_for_serial.restype = c_int
    EdtDLL.pdv_pause_for_serial.argtype = [c_void_p]

    # pdv_get_shutter_method
    EdtDLL.pdv_get_shutter_method.restype = c_int
    EdtDLL.pdv_get_shutter_method.argtype = [c_void_p, POINTER(c_uint)]

    # pdv_shutter_method
    EdtDLL.pdv_shutter_method.restype = c_int
    EdtDLL.pdv_shutter_method.argtype = [c_void_p]

    # pdv_set_defaults
    EdtDLL.pdv_set_defaults.argtype = [c_void_p]

    # pdv_is_atmel
    EdtDLL.pdv_is_atmel.restype = c_int
    EdtDLL.pdv_is_atmel.argtype = [c_void_p]

    # pdv_enable_external_trigger
    EdtDLL.pdv_enable_external_trigger.argtype = [c_void_p, c_int]

    # pdv_set_fval_done
    EdtDLL.pdv_set_fval_done.argtype = [c_void_p, c_int]

    # pdv_get_fval_done
    EdtDLL.pdv_get_fval_done.restype = c_int
    EdtDLL.pdv_get_fval_done.argtype = [c_void_p]

    # pdv_get_lines_xferred
    EdtDLL.pdv_get_lines_xferred.restype = c_int
    EdtDLL.pdv_get_lines_xferred.argtype = [c_void_p]

    # pdv_get_width_xferred
    EdtDLL.pdv_get_width_xferred.restype = c_int
    EdtDLL.pdv_get_width_xferred.argtype = [c_void_p]

    # pdv_cl_get_fv_counter
    EdtDLL.pdv_cl_get_fv_counter.restype = c_int
    EdtDLL.pdv_cl_get_fv_counter.argtype = [c_void_p]

    # pdv_cl_reset_fv_counter
    EdtDLL.pdv_cl_reset_fv_counter.argtype = [c_void_p]

    # pdv_cl_camera_connected
    EdtDLL.pdv_cl_camera_connected.restype = c_int
    EdtDLL.pdv_cl_camera_connected.argtype = [c_void_p]

    # pdv_reset_dma_framecount
    EdtDLL.pdv_reset_dma_framecount.restype = c_int
    EdtDLL.pdv_reset_dma_framecount.argtype = [c_void_p]

    # pdv_set_frame_period
    EdtDLL.pdv_set_frame_period.restype = c_int
    EdtDLL.pdv_set_frame_period.argtype = [c_void_p, c_int, c_int]

    # pdv_get_frame_period
    EdtDLL.pdv_get_frame_period.restype = c_int
    EdtDLL.pdv_get_frame_period.argtype = [c_void_p]

    # pdv_is_cameralink
    EdtDLL.pdv_is_cameralink.restype = c_int
    EdtDLL.pdv_is_cameralink.argtype = [c_void_p]

    # pdv_is_simulator
    EdtDLL.pdv_is_simulator.restype = c_int
    EdtDLL.pdv_is_simulator.argtype = [c_void_p]

    # pdv_start_expose
    EdtDLL.pdv_start_expose.argtype = [c_void_p]

    # pdv_set_exposure_basler202k
    EdtDLL.pdv_set_exposure_basler202k.restype = c_int
    EdtDLL.pdv_set_exposure_basler202k.argtype = [c_void_p, c_int]

    # pdv_set_gain_basler202k
    EdtDLL.pdv_set_gain_basler202k.restype = c_int
    EdtDLL.pdv_set_gain_basler202k.argtype = [c_void_p, c_int, c_int]

    # pdv_set_offset_basler202k
    EdtDLL.pdv_set_offset_basler202k.restype = c_int
    EdtDLL.pdv_set_offset_basler202k.argtype = [c_void_p, c_int, c_int]

    # pdv_set_exposure_duncan_ch
    EdtDLL.pdv_set_exposure_duncan_ch.restype = c_int
    EdtDLL.pdv_set_exposure_duncan_ch.argtype = [c_void_p, c_int, c_int]

    # pdv_set_gain_duncan_ch
    EdtDLL.pdv_set_gain_duncan_ch.restype = c_int
    EdtDLL.pdv_set_gain_duncan_ch.argtype = [c_void_p, c_int, c_int]

    # pdv_process_inplace
    EdtDLL.pdv_process_inplace.restype = c_int
    EdtDLL.pdv_process_inplace.argtype = [c_void_p]

    # pdv_deinterlace
    EdtDLL.pdv_deinterlace.restype = c_int
    EdtDLL.pdv_deinterlace.argtype = [c_void_p, c_void_p, c_char_p, c_char_p]

    # pdv_check_framesync
    EdtDLL.pdv_check_framesync.restype = c_int
    EdtDLL.pdv_check_framesync.argtype = [c_void_p, c_char_p, POINTER(c_uint)]

    # pdv_enable_framesync
    EdtDLL.pdv_enable_framesync.restype = c_int
    EdtDLL.pdv_enable_framesync.argtype = [c_void_p, c_int]

    # pdv_framesync_mode
    EdtDLL.pdv_framesync_mode.restype = c_int
    EdtDLL.pdv_framesync_mode.argtype = [c_void_p]

    # pdv_set_binning_dvc
    EdtDLL.pdv_set_binning_dvc.restype = c_int
    EdtDLL.pdv_set_binning_dvc.argtype = [c_void_p, c_int, c_int]

    # pdv_set_mode_dvc
    EdtDLL.pdv_set_mode_dvc.restype = c_int
    EdtDLL.pdv_set_mode_dvc.argtype = [c_void_p, c_char_p]

    # pdv_is_dvc
    EdtDLL.pdv_is_dvc.restype = c_int
    EdtDLL.pdv_is_dvc.argtype = [c_void_p]

    # pdv_update_from_dvc
    EdtDLL.pdv_update_from_dvc.restype = c_int
    EdtDLL.pdv_update_from_dvc.argtype = [c_void_p]

    # pdv_get_dvc_state
    EdtDLL.pdv_get_dvc_state.restype = c_int
    EdtDLL.pdv_get_dvc_state.argtype = [c_void_p, c_void_p]

    # pdv_set_waitchar
    EdtDLL.pdv_set_waitchar.restype = c_int
    EdtDLL.pdv_set_waitchar.argtype = [c_void_p, c_int, c_char_p]

    # pdv_get_waitchar
    EdtDLL.pdv_get_waitchar.restype = c_int
    EdtDLL.pdv_get_waitchar.argtype = [c_void_p, c_char_p]
    '''





initEdtDLL()  # Called once and for all upon module import