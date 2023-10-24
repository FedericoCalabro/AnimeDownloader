from core.anime import Anime
from core.anime_scraper import AnimeScraper
from core.url_generator import UrlGenerator
from core.anime_downloader import AnimeDownloader
from queue import Queue
import os

ANIME_PAGE = str(input("1. Inserire l'URL di download dell'anime: "))
LOWER_LIMIT = int(input("2. Scaricare gli episodi a partire dal numero:  "))
UPPER_LIMIT = int(input("3. Fino all'episodio numero: "))
MAX_PARALLEL_DOWNLOADS = int(input("4. Numero di downloads paralleli: "))

scraper = AnimeScraper()
DOWNLOAD_URL = scraper.scrape_download_url(ANIME_PAGE)

download_queue = Queue()
for i in range(LOWER_LIMIT, UPPER_LIMIT+1):
    download_queue.put(Anime(UrlGenerator.generate_ith(DOWNLOAD_URL, i)))

DIRECTORY_NAME = DOWNLOAD_URL.split('/')[5]
if not os.path.exists(DIRECTORY_NAME): 
    os.makedirs(DIRECTORY_NAME)

downloader = AnimeDownloader(download_queue, MAX_PARALLEL_DOWNLOADS)
downloader.execute()
