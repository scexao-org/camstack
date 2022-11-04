'''
    Designed for Vampires

    This is for a EDT camera that we CANNOT control
    However, a teensy tiny bit better than the base EDTCamera
    because we use the polling threads to monitor the frame size.

    This is performed through the _FGDETS1, _FGDETS2 stream keywords
    that are obtained by polling framegrabber registers for
    pixels-per-line and line-per-frame respectively, and seem to function
    even when the FG config is mis-matching.

    One caveat is that pixel-per-line needs to be multiplied by the number of
    camera taps.
'''

import os
import logging as logg

from camstack.cams.edtcam import EDTCamera


class AutoDumbEDTCamera(EDTCamera):
    '''
        This class doesn't need to do much.

        poll_camera_for_keywords should inspect _FGDETS* keywords
        in the SHM.

        If they've changed, it should trigger a set_camera_size.
        HOWEVER
        Calling set_camera_mode from the thread will eventually try to join the thread.
        Resulting in a deadlock.
        So we need to change the camera mode without stopping and restarting the
        polling thread. That's done by using the bypass_aux_thread flag in
        _kill_taker_no_dependents and _start_taker_no_dependents.

        But there's no access to the serial port as a could-be shared resource.
        So I guess it's Okay?
    '''

    def _start_taker_no_dependents(self, reuse_shm: bool = False):
        logg.debug('_start_taker_no_dependents @ AutoDumbEDTCamera')
        EDTCamera._start_taker_no_dependents(self, reuse_shm,
                                             bypass_aux_thread=True)

    def _kill_taker_no_dependents(self):
        logg.debug('_kill_taker_no_dependents @ AutoDumbEDTCamera')
        EDTCamera._kill_taker_no_dependents(self, bypass_aux_thread=True)

    def poll_camera_for_keywords(self):
        kw_dict = self.camera_shm.get_keywords()

        detected_height = kw_dict['_FGDETS1']  # Lines per frame
        detected_width = kw_dict[
                '_FGDETS2'] * self.pdv_taps  # px per line * n_taps

        if (detected_height != self.height) or (detected_width != self.width):
            # Dang, the frame size has change behind our backs!
            # Just be chill about it yo.

            # Nah just nuke it.
            logg.warning(
                    f"AutoDumbEDTCamera: changing camera mode from "
                    f"({self.height},{self.width}) to ({detected_height},{detected_width})"
            )
            self.set_camera_size(detected_height, detected_width)
