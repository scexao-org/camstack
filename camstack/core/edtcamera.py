from .edtlib import _EdtLib


class EDTCamera:
    '''
        Standard basic stuff that is common over EDT framegrabbers

        Written with the mindset "What should be common between CRED2 and OCAM ?"

        And implements the server side management of the imgtake
    '''
    
    EDTTAKE_CAST = False # Only OCAM overrides that

    def __init__(self):
        '''
            Run an SYSTEM init_cam with the cfg file

            Grab the desired/default camera mode

            Prepare the tmux

            Prepare the serial handles (also, think it MAY be overloaded for the Andors)

        '''
        pass

    def is_take_running(self):
        pass

    def start_acquisition(self):
        # Reach to the edttake and start it
        # grab the new SHM pointer, populate the keywords
        pass

    def stop_acquisition(self):
        # Reach to the edttake and kill it
        pass


    def set_camera_mode(self):
        stop_acq

        change_fg_parameters

        change_camera_parameters # Serial OR other
        
        start_acq

    def get_fg_parameters(self):
        pass

    def set_fg_parameters(self):
        pass

    def change_camera_parameters(self):
        raise NotImplementedError("Set camera mode should have a camera-specific implementation")

    def communicate(self):
        '''
            To be overloaded by cameras that dont do serial
        '''
        self._pdv_serial(la_meme_chose)
        return status # Or raise ?

    def _pdv_serial(self):
        pass

    def 


    