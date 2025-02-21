from abc import ABC, abstractmethod

class BaseScraper(ABC):
    @abstractmethod
    def scrape(self, url):
        pass

    @property
    @abstractmethod
    def base_url(self):
        pass