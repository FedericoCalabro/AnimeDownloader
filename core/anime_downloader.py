from core.anime import Anime
from core.display import Display
from core.downloader import Downloader
from queue import Queue

class AnimeDownloader():

    def __init__(self, queue: Queue[Anime], mpd):
        # Queue of Animes to download
        self.queue = queue
        print(f'qsize {queue.qsize()}')
        # Initialization of threads
        self.display = Display(mpd)
        self.downloaders = [Downloader(self.queue, self.display, i) for i in range(mpd)]

    def execute(self):
        # Start the execution of all threads
        self.display.start()
        for thread in self.downloaders:
            thread.start()
        # Make main thread wait for all downloaders to finish
        # Display is not joined because has to keep printing download status while q is empty
        for thread in self.downloaders:
            thread.join()
        # Stop the display thread
        self.display.stopped = True
