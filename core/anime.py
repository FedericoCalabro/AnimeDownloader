class Anime:

    def __init__(self, url : str):
        # Url of anime to download
        self.url = url
        # Directory where to store the anime
        self.name = self.url.split('/')[5]
        # Name of the ith episode
        self.episode = self.url.split('/')[6]