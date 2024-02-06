from __future__ import annotations

import threading


class HackedExitJoinThread(threading.Thread):
    '''
    A hacky subclass of threading.Thread
    
    When the interpreter exits, it tries to join all threads.
    
    Problem:
        Our camstack poller thread will not join, and you need to fire a Ctrl+C to kill the joiner
        That'd be the case for every forever-while-loop thread.
        
    Solution:
        Subclass, and pass explicitly the Event that will eventually be used in
        BaseCamera::auxiliary_thread_run_function.
        
    Calling join explicitly sets that Event from the main thread.
    '''
    
    def __init__(self, *args, event: threading.Event, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        
    def join(self):
        self.event.set()
        super().join()