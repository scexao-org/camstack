from abc import ABC, abstractmethod


class OnOffMode(ABC):

    def __init__(self, frontend_obj) -> None:

        # The enabled flag is stored internally but not used internally
        # It's for the sake of the frontend & backend to know what to call.
        self.enabled = False

        self.frontend_obj = frontend_obj

        self.backend_obj = None
        self.has_backend = False

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False

    def register_backend(self, backend_obj) -> None:

        self.has_backend = True
        self.backend_obj = backend_obj

    @abstractmethod
    def process(self) -> None:
        '''
            Do computations for this onoff mode
        '''
        pass

    @abstractmethod
    def render_into_frontend(self) -> None:
        '''
            Do the proper graphical stuff in the frontend.
            I kinda don't like that this is in yet-another pygame file, but heck.
        '''
        pass
