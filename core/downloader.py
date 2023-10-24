from core.anime import Anime
from core.display import Display
from threading import Thread
import wget
from queue import Queue

class Downloader(Thread):

    def __init__(self, queue : Queue[Anime], display : Display, i):
        Thread.__init__(self)
        self.daemon = True
        # Each worker has access to the shared queue
        self.queue = queue
        # Current downloading anime, used in bar_progress
        self.anime = None
        # Display object onto which thread will write its output to
        self.display = display
        # Index used by the thread to write into Display list
        self.index = i

    def bar_progress(self, curr, tot, width=80):
        # message = Name of the anime: progress bar, x/y bytes 
        message = "%s: %d%% [%d / %d] bytes" % (self.anime.episode, curr / tot * 100, curr, tot)
        self.display.output[self.index] = message

    def run(self):
        # While queue is not empty grab an anime and download it
        while not self.queue.empty():
            # TryCatch to handle wrong URLs
            try:
                self.anime = self.queue.get()
                wget.download(self.anime.url, f"{self.anime.name}/{self.anime.episode}", self.bar_progress)
            except:
                continue