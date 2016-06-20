import logging as log
import os
from pipes import quote
import subprocess
import time
import urlparse
from urllib import basejoin

import requests
from lxml import html


def convert_size(size):
    units = {'KB': 1024, 'MB': 1024 ** 2, 'GB': 1024 ** 3}
    for unit in units:
        if unit in size:
            size, = size.replace(unit, '').split()
            return float(size) * units[unit]
    return None


def get_file_size(filename):
    return os.stat(filename).st_size


def download_requests(url, filename):
    req = requests.get(url, stream=True)
    with open(filename, 'wb') as f:
        for chunk in req.iter_content(chunk_size=1024*10):
            if chunk:
                f.write(chunk)
        f.flush()
    return get_file_size(filename)


def download_curl(url, filename):
    subprocess.call('curl %s -o %s' % (quote(url), quote(filename)), shell=True)
    return get_file_size(filename)


def get_available_transfer(tree):
    try:
        size, = tree.xpath('//div[@class="info login-info-box"]/table/tr[3]/td[2]/small/text()')
    except ValueError:
        size = "0 MB"
    return convert_size(size)


def get_filename_for_url(root, url):
    _, filename = os.path.split(urlparse.urlparse(url).path)
    return os.path.join(root, filename)


def download_size_matches(expected_size, actual_size):
    # maximum difference should not be greater than 0.01 MB, as this is the unit of size for files
    return abs(expected_size - actual_size) <= 10240


def get_download_groups(tree):
    d = {}
    for file_list in tree.xpath('//div[@class="file-list"]'):
        folder_id, = file_list.xpath('./div/input/@value')
        folder_name, = file_list.xpath('./div/button/text()')
        files = []
        for tr in file_list.xpath('./table[@class="files-list"]/tbody')[0]:
            try:
                url = tr[0][0].get('href')
                size = tr[3].text
                files.append((url.strip(), convert_size(size)))
            except IndexError:
                pass
        d[(folder_id, folder_name)] = files
    return d


class RapidhostAPI(object):
    URL = "http://rapidhost.pl/"
    LOGIN_URL = basejoin(URL, '/account/login')
    DELETE_URL = basejoin(URL, '/download/delete')

    def __init__(self, username, password, root=None):
        self.session = requests.Session()
        self.username = username
        self.password = password
        self.root = root or os.getcwd()
        self.filter = None
        self.transfer = 0
        self.groups = []
        self.login()

    def set_filter(self, value):
        self.filter = value

    def login(self):
        self.session.post(self.LOGIN_URL, data={'username': self.username, 'password': self.password})
        self.refresh()

    def refresh(self):
        page = self.session.get(self.URL).text
        tree = html.fromstring(page)
        self.transfer = get_available_transfer(tree)
        self.groups = get_download_groups(tree)

    def download_file(self, url):
        _, filename = os.path.split(urlparse.urlparse(url).path)
        filename = os.path.join(self.root, filename)
        log.info('Downloading "%s"', url)
        #size = download_requests(url, filename)
        size = download_curl(url, filename)
        log.info('Download "%s" complete', url)
        if size < 7000:
            os.remove(filename)
        return size

    def delete_group(self, group_id):
        log.debug('Removing group: %s', group_id)
        self.session.post(self.DELETE_URL, data={'ids[]': group_id})

    def download_group(self, key):
        err = False
        group_id, name = key
        files = self.groups[key]
        log.debug('Group id=%s, name=%s', group_id, name)
        for url, size in files:
            filename = get_filename_for_url(self.root, url)
            if os.path.exists(filename) and download_size_matches(size, get_file_size(filename)):
                continue
            if size <= self.transfer:
                downloaded_size = self.download_file(url)
                if not download_size_matches(size, downloaded_size):
                    log.error('Mismatch in size: expected=%d, actual=%d', size, downloaded_size)
                    err = True
            else:
                log.error('Not enough available transfer: required=%d, actual=%d', size, self.transfer)
                err = True
        return err

    def download_all(self):
        for key in self.groups:
            group_id, name = key
            if self.filter:
                if callable(self.filter) and not self.filter(name):
                    continue
                elif isinstance(self.filter, basestring) and self.filter not in name:
                    continue
                if not self.download_group(key):
                    self.delete_group(group_id)

    def run_service(self, repeat_time=None):
        log.info('Running as service...')
        while True:
            try:
                self.download_all()
                if not repeat_time:
                    break
                time.sleep(repeat_time)
                self.refresh()
            except KeyboardInterrupt:
                break
            except:
                log.exception('Error during downloading')
