from requests_html import HTML
import cloudscraper

class AnimeScraper:
    def __init__(self):
        # Url request maker recicled from MonsterScraper Project
        self.__scraper = cloudscraper.create_scraper()

    def getDom(self, url, loadJS=False):
        # Make the request to the URL and get the DOM like element
        response = self.__scraper.get(url)
        dom = HTML(html=response.content)
        if loadJS:
            dom.render()
        return dom
    
    def scrape_download_url(self, url):
        try:
            download_url = self.__scrape_download_url(url)
            return download_url
        except:
            return str(input("Errore nel recupero del link di download, inserirlo manualmente: "))

    def __scrape_download_url(self, url):
        # XPath to retrieve download URL
        dom = self.getDom(url, loadJS=False)
        query = "//*[contains(@href, 'Ep_')][contains(@id, 'alt')]"
        a = dom.xpath(query, first=True)
        link = a.attrs.get('href') if a else None
        return link