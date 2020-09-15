import scrapy
from scrapy.http import Request
import os
import shutil
import json
import logging

_logger = logging.getLogger(__name__)


class ProzorroSpider(scrapy.Spider):
    name = "prz"

    def start_requests(self):
        tender_url = self.settings['TENDER_URL']
        urls = [tender_url]
        for url in urls:
            yield scrapy.Request(url, callback=self.parse)

    def save_file(self, response, file_name, tender_uid):

        file_name = file_name.replace('\n', '').strip()
        if file_name == 'Електронний цифровий підпис':
            return

        tender_uid = tender_uid.replace('\n', '').strip()
        uid_filename = tender_uid + '-' + file_name

        data_dir = self.settings['DATA_PATH']
        dest_dir = os.path.join(data_dir, tender_uid)
        if not os.path.isdir(dest_dir):
            os.makedirs(dest_dir)

        path = os.path.join(dest_dir, uid_filename)
        self.logger.info('Saving to {}'.format(path))
        with open(path, 'wb') as f:
            f.write(response.body)

    def parse(self, response):

        data_type = self.settings['DOWNLOAD_DATA_TYPE']
        data_path = self.settings['DATA_PATH']

        parsed_url = str(response.url)
        tender_uid = parsed_url.split('/')[-1]

        if data_type == 'DESCRIPTION':

            # Tender head
            str_header = ''
            xpath_head = '//div[@class="tender--head--title col-sm-9"]/text()'
            for header_selector in response.xpath(xpath_head):
                str_header += header_selector.get().strip().replace('\n', ' ').strip()
                if not str_header:
                    continue
            # Expected value
            str_value = ''
            xpath_value = '//div[@class="green tender--description--cost--number"]//strong/text()'
            for value_selector in response.xpath(xpath_value):
                str_value = value_selector.get().replace(' ', '').strip()
                if not str_value:
                    continue

            # Purchasing body
            str_customer = ''
            xpath_customer = '//table[@class="tender--customer margin-bottom"]//tr'
            for customer_selector in response.xpath(xpath_customer).xpath('td')[1].xpath('text()'):
                str_customer = customer_selector.get()
                str_customer = str_customer.strip()
                if not str_customer:
                    continue

            # EDRPOU
            str_edrpou = ''
            xpath_edrpou = '//table[@class="tender--customer margin-bottom"]//tr'
            for edrpou_selector in response.xpath(xpath_edrpou)[1].xpath('td')[1].xpath('text()'):
                str_edrpou = edrpou_selector.get()
                str_edrpou = str_edrpou.strip()
                if not str_edrpou:
                    continue

            # Address
            str_address = ''
            xpath_address = '//table[@class="tender--customer margin-bottom"]//tr[3]//td[@class="col-sm-6"]//text()'
            for address_selector in response.xpath(xpath_address):
                str_address = address_selector.get()
                str_address = str_address.replace('\n', '').strip()
                if not str_address:
                    continue

            # Kind of item: Роботи, Послуги, Товари etc
            str_t = ''
            xpath_t = '//div[@class="col-sm-9 margin-bottom margin-bottom-more"]//p[1]/text()'
            for t_selector in response.xpath(xpath_t):
                str_t = t_selector.get()
                str_t = str_t.replace(':', '').strip()
                if not str_t:
                    continue

            # Description
            str_desc = ''
            xpath_t = '//div[@class="col-md-4 col-md-push-8"]//text()'
            for t_selector in response.xpath(xpath_t):
                selector_text = t_selector.get().replace('\n ', '\n').strip()
                if selector_text:
                    str_desc += selector_text + '\n'
                if not str_desc:
                    continue

            xpath_t = '//div[@class="col-md-8 col-md-pull-4 description-wr open"]//text()'
            for t_selector in response.xpath(xpath_t):
                selector_text = t_selector.get().replace('\n ', '\n').strip()
                if selector_text:
                    str_desc += selector_text+'\n'
                if not str_desc:
                    continue

            tender_desc = {
                'url': parsed_url,
                'header': str_header,
                'value': str_value,
                'procuring_entity_name': str_customer,
                'procuring_entity_id': str_edrpou,
                'address': str_address,
                'good_type': str_t,
                'description': str_desc.strip(),
                'auction_url': parsed_url,
                'tender_id': tender_uid,
            }

            # Dump description to json file
            dest_dir = os.path.join(data_path, tender_uid)
            if not os.path.isdir(dest_dir):
                os.makedirs(dest_dir)

            file_name = os.path.join(dest_dir, tender_uid+'.json')
            with open(file_name, 'w', encoding='utf8') as jf:
                json.dump(tender_desc, jf, ensure_ascii=False)

            yield tender_desc

        if data_type == 'FILES':

            # Tender documents
            xpath_file_row = '//table[@class="tender--customer"]//tr'
            for sel in response.xpath(xpath_file_row):
                file_name = str(sel.xpath('td[2]/a/text()').get())
                file_url = str(sel.xpath('td[2]/a/@href').get())
                if file_url is not None:
                    if file_url:
                        uid_filename = tender_uid + '-' + file_name
                        data_dir = data_path
                        dest_dir = os.path.join(data_dir, tender_uid)
                        path = os.path.join(dest_dir, uid_filename)
                        if not os.path.isfile(path):
                            yield Request(file_url, callback=self.save_file,
                                          cb_kwargs={
                                              'file_name': file_name,
                                              'tender_uid': tender_uid,
                                          })


def remove_file_or_folder(abs_path):
    """ param <path> could either be relative or absolute. """
    if os.path.isfile(abs_path) or os.path.islink(abs_path):
        os.remove(abs_path)  # remove the file
    elif os.path.isdir(abs_path):
        shutil.rmtree(abs_path)  # remove dir and all contains
    else:
        raise ValueError("file {} is not a file or dir.".format(abs_path))
