# -*- coding: utf-8 -*-

"""
This module provides scanning functionality for websites. To do so, the module
extracts information, puts new http links on the target queues while storing
informations in the result queue.

"""

__author__ = "sascha zinke and maximilian haeckel"
__version__ = 0.02
__license__ = "BSD-3-Clause, see LICENSE for details"

import Queue
import logging
from urlparse import urlsplit
from urllib import unquote
from urllib2 import urlopen
import re
from HTMLParser import HTMLParser

VALID_MIME_TYPES = ("html", "xhtml", "htm")
VALID_ATTR = ("href")
SCHEME_HTTP = "http"

TIMEOUT = 5
FIELD = "html"

# regex that matches urls
# by john gruber
# http://daringfireball.net/2010/07/improved_regex_for_matching_urls
regex_urls = re.compile(r"(?i)\b((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?""'']))")

class UniqueQueue(Queue.Queue):
    """
    provide a queue that only puts elements, if they are not already
    stored. To do so, use the Queue.Queue's hooks for _init, _put, _get and
    replace the internal data type with the builtin sets(). This is quit cool,
    since it does not affect the multithreading functionality of Queue.Queue.

    """

    def _init(self, maxsize):
        self.queue = set()

    def _put(self, item):
        self.queue.add(item)

    def _get(self):
        return self.queue.pop()

    def __contains__(self, item):
        with self.mutex:
            return item in self.queue

class Extractor(HTMLParser):
    """
    The extractor class extracts everything of a website that might contain
    interesting information.

    """

    def __init__(self):
        HTMLParser.__init__(self)
        self.links = []
        self.base_page = ""

    def reset(self):
        HTMLParser.reset(self)
        self.links = []
        self.base_page = ""

    def handle_starttag(self, tag, attrs):
        """
        a new start tag will be searched for link in its attributes

        input:
            tag     tag that begins
            attrs   attributes of the tag

        """
        for key, value in attrs:
            if not key in VALID_ATTR:
                continue

            # search for links within an attribute
            links = regex_urls.findall(value)
            for l in links:
                link = l[0]
                if link and link.startswith("/"):
                    link = self.base_page + link
                self.links.append(l[0])


def scan_pages(target_queue, result_queue, max_depth, indexer=None):
    """
    take a target from the target queue and get its resource. extract
    information and store new targets and information in the corresponding
    queue. Repeat until target queue is empty.

    input:
        target_queue    a UniqueQueue that contains targets to scan. new targets are
                        put her.e
        result_queue    a UniqueQueue that contains the final result of a scan
        max_depth       the link depth, the crawler follows maximally
        indexer         a tuple containining the indexer object and a lock to
                        access with. is used to index found pages.

    """
    try:
        indexer, lock = indexer
    except:
        pass

    # our html parser object to get links of a site
    extractor = Extractor()

    while not target_queue.empty():

        # get target
        target, depth = target_queue.get()
        logging.info("target(%d): %s", depth, target)

        # tag the target as found
        result_queue.put(target)

        # get page and extract urls
        try:
            conn = urlopen(target, timeout=TIMEOUT)
            encoding = conn.headers.getparam('charset')
            if not encoding:
                encoding = "utf8"
            page = conn.read().decode(encoding)

            if indexer:
                # add to indexer
                with lock:
                    indexer.add_document(target, FIELD, page)

        except Exception, err:
            logging.warning("Failed to fetch '%s':'%s'", target, err)
            continue

        extractor.reset()
        extractor.base_page = target

        # extract urls
        try:
            extractor.feed(page)
        except Exception, err:
            logging.error("Failed to extract links from %s:'%s'",
                           extractor.base_page, err)
            continue

        # store links as results and for rescanning.
        # before putting into target queue, check
        # whether link is already in result queue.
        # if so, we already went there.
        for link in extractor.links:

            # preprocess target (check mime type, etc)
            # if failed to preprocess - maybe invalid type
            # drop target and continue with next one
            try:
                normalised_link = _normalise_target(link)
            except Exception as err:
                logging.debug("Failed to normalise '%s'!", link)
                continue

            if normalised_link in result_queue:
                continue

            result_queue.put(normalised_link)

            # only scan new link, if not max depth is reached
            if depth < max_depth:
                target_queue.put((normalised_link, depth+1))

def _normalise_target(target):
    """
    check whether target is of valid mime type. if not (e.g. multimedia stuff,
    etc), raise an Exception.
    further, remove anchors, bla .. do normalising stuff

    input:
        target      the link to normalise

    output:
        link        a new, normalised link if target is valid - otherwise raise
                    an Exception

    """
    logging.debug("normalising '%s'", target)

    # fix encoding
    # http://mi.fu-berlin.de/%7Efoobar -> http://mi.fu-berlin.de/~foobar
    link = unquote(target)

    # remove trailing slash
    link = link.rstrip("/")

    # so normalise url parts
    url = urlsplit(link)
    logging.debug("url:%s", url)

    # return None if link leads to invalid resource (like jpg, etc)
    if url.fragment and not url.fragment in VALID_MIME_TYPES:
        raise Exception("Invalid mime type!")

    # if hostname starts with 'www', remove
    if url.hostname.startswith("www."):
        hostname = url.hostname[4:]
    else:
        hostname = url.hostname

    # ensure that a scheme is given
    scheme = url.scheme if url.scheme else SCHEME_HTTP

    # build link
    link = scheme + "://" + hostname + url.path + url.fragment

    return link
