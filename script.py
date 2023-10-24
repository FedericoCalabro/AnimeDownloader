import wget
from threading import Thread, RLock
from queue import Queue
import re
from time import sleep
import os

MAX_PARALLEL_DOWNLOADS = int(input("Numero massimo di download paralleli (consigliato 3): "))
LOWER_LIMIT = int(input("Scaricare gli episodi a partire dal numero:  "))
UPPER_LIMIT = int(input("Fino all'episodio numero: "))
DOWNLOAD_URL_LIKE = str(input("Inserisci l'URL di download dell'anime: "))


class Anime:

    def __init__(self, url):
        self.url = url
        self.name = self.url.split('/')[6]


class Display(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.lock = RLock()
        self.output = ['' for i in range(0, MAX_PARALLEL_DOWNLOADS)]
        self.stopped = False

    def run(self):
        while not self.stopped:
            os.system('cls' if  os.name == 'nt' else 'clear')
            with self.lock:
                print('\n'.join(self.output), flush=True)
                sleep(1)


class Downloader(Thread):

    def __init__(self, queue, index, display):
        Thread.__init__(self)
        self.queue = queue
        self.index = index
        self.anime = None
        self.display = display

    def bar_progress(self, curr, tot, width=80):
        message = "%s: %d%% [%d / %d] bytes" % (self.anime.name, curr / tot * 100, curr, tot)
        self.display.output[self.index] = message

    def run(self):
        while not self.queue.empty():
            self.anime = self.queue.get()
            wget.download(self.anime.url, f"{self.anime.name}", self.bar_progress)


class AnimeDownloader():

    def __init__(self, queue):
        self.queue = queue
        self.display = Display()
        self.threads = []
        # Initialize downloaders threads
        for i in range(0, MAX_PARALLEL_DOWNLOADS):
            self.threads.append(Downloader(self.queue, i, self.display))

    def execute(self):
        # Start the execution of all threads
        self.display.start()
        for thread in self.threads:
            thread.start()

        # Make main thread wait for all other threads to finish
        for thread in self.threads:
            thread.join()

        # Stop display thread
        self.display.stopped = True


def index_formatter(i): return str(i) if i > 9 else f'0{str(i)}'
def url_generator(i): return re.sub( "Ep_\d+", f"Ep_{index_formatter(i)}", DOWNLOAD_URL_LIKE)

download_queue = Queue()
for i in range(LOWER_LIMIT, UPPER_LIMIT+1):
    download_queue.put(Anime(url_generator(i)))

downloader = AnimeDownloader(download_queue)
downloader.execute()
