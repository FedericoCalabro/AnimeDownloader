from threading import Thread, RLock
from time import sleep
import os

class Display(Thread):

    def __init__(self, mpd):
        Thread.__init__(self)
        self.daemon = True
        # List of output, each l[i] is assigned to a Downloader
        self.output = [None for i in range(0, mpd)]
        # Global lock to manage priting
        self.lock = RLock()
        # Control variable to stop the running thread
        self.stopped = False

    def run(self):
        # AnimeDownloader will take care of stopping 
        while not self.stopped:
            os.system('cls' if  os.name == 'nt' else 'clear')
            with self.lock:
                print('\n'.join(filter(lambda x : x is not None, self.output)), flush=True)
                sleep(1)

