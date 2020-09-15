# -*- coding: utf-8 -*-

from ..libcat import prz
from scrapy.crawler import CrawlerRunner
from twisted.internet import reactor
from multiprocessing import Process, Queue
import os
import json


class TenderSource:
    """A common base class for other tender sources"""

    def ids(self, count=None):
        pass

    def tenders(self, ids=None):
        pass

    def tender_url(self, tender_id):
        pass


class TenderSourceProzorroWeb(TenderSource):

    base_url = 'https://prozorro.gov.ua/tender/'

    def __init__(self, data_path=None):
        self.data_path = data_path

    def tender_url(self, tender_id):
        return self.base_url+str(tender_id).strip()

    def tender_files(self, tender_id):

        # todo: validate tender_id

        spider_settings = {
            'TENDER_URL': self.tender_url(tender_id),
            'DOWNLOAD_DATA_TYPE': 'FILES',
            'DATA_PATH': self.data_path}

        run_spider(prz.spiders.prz_spider.ProzorroSpider, spider_settings)

    def tender_desc(self, tender_id):

        # todo: validate tender_id

        spider_settings = {
            'TENDER_ID': tender_id,
            'TENDER_URL': self.tender_url(tender_id),
            'DOWNLOAD_DATA_TYPE': 'DESCRIPTION',
            'DATA_PATH': self.data_path}

        run_spider(prz.spiders.prz_spider.ProzorroSpider, spider_settings)

        tender_desc = {}

        # read from json file
        dest_dir = os.path.join(self.data_path, tender_id)
        file_name = os.path.join(dest_dir, tender_id + '.json')
        if os.path.isfile(file_name):
            with open(file_name, 'r') as f:
                tender_desc = json.load(f)
            os.remove(file_name)

        return tender_desc


# the wrapper to make it run more times
def run_spider(spider, spider_settings):

    def f(queue):
        try:
            runner = CrawlerRunner(spider_settings)
            deferred = runner.crawl(spider)
            deferred.addBoth(lambda _: reactor.stop())
            reactor.run()
            queue.put(None)
        except Exception as e:
            queue.put(e)

    q = Queue()
    p = Process(target=f, args=(q,))
    p.start()
    result = q.get()
    p.join()

    if result is not None:
        raise result
