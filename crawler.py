# -*- coding: utf-8 -*-
"""
This module provides a crawler, that returns a list of links/urls.

The crawling algorithm mainly consists of the following steps:


          provide initial target
                  |
      ----------- |
     /            \
    |             |
    |             v
    |     __________________
    |    |                  | The crawler provides an internal target queue
    |    | fill target queue| which contains the url it has not visited yet.
    |    |__________________|
    |             |
    |             | get a target from queue
    |             | drop if invalid media type
    |             v
    |     __________________
    |    |                  |
    |    | request website  | get requested target website
    |    |__________________|
    |             |
    |             |
    |             v
    |     __________________
    |    |                  | extract interesting information
    |    |  extract inform. | (links, metadata, mail addresses)
    |    |__________________|
    |           /   \
     \         /     \
      ---------      |
   fill in target    v
  if not in result__________________
                 |                  | information are stored
                 | fill result queue| in a result queue
                 |__________________|



The crawler provides an interactive mode('-i'). If used, the crawler takes
input to build indexer queries. The result is written to stdout. Also you can
set the crawling depth ('--depth') and the amount of threads crawling
('--threads').

Indexing:
This setup uses the apache lucene indexer in java. To get it working, you need
to run the crawler with jython - otherwise the import of the indexer will. This
has no effect on the crawling itself.

"""

__author__ = "sascha zinke and maximilian haeckel"
__version__ = 0.03
__license__ = "BSD-3-Clause, see LICENSE for details"

import sys
import threading
import time
import logging
from datetime import datetime,timedelta
import argparse

logging.basicConfig(
        format="%(threadName)s [%(levelname)s]: %(message)s",
        level=logging.INFO
        )

from src import scn
try:
    from src.idx import Indexer
except Exception, err:
    logging.warning("failed to import lucene indexer!")
    Indexer = None

def secs(start_time):
    dt = datetime.now() - start_time
    secs = (dt.days * 24 * 60 * 60 + dt.seconds*1000 + dt.microseconds/1000) / 1000.0
    return secs

class Crawler(object):
    """
    The crawler actually provides crawling functionality. It takes an intial
    target, requests it and extracts information that might be crawled, too.

    """

    def __init__(self, initial_target, threads=10, max_depth=2):
        """
        create a new crawler

        input:
            initial_target      the target that ought to be scanned.
            threads             the max amount of threads crawling pages
            max_depth           the link depth, the crawler follows maximally

        output:
            crawler object instance

        """
        logging.info("creating new Crawler..")
        self.target_queue = scn.UniqueQueue()
        self.result_queue = scn.UniqueQueue()
        self.max_threads = threads
        self.max_depth = max_depth

        if Indexer:
            self.idx = Indexer("/tmp/crawler_indexer")
            self.idx_lock = threading.Lock()
        else:
            self.idx = None
            self.idx_lock = None
        try:
            normalised_link = scn._normalise_target(initial_target)
        except:
            raise Exception("Failed to parse initial target. Make sure, the "
                            "target has the form <scheme>://<path>.")

        if not normalised_link:
            raise Exception("Got invalid url to scan!")

        self.target_queue.put((normalised_link, 0))

    def start(self):
        """ start crawling """
        logging.info("starting crawling..")
        start_time = datetime.now()

        # store created threads
        threads = []

        # indexer
        if self.idx and self.idx_lock:
            indexer = (self.idx, self.idx_lock)
        else:
            indexer = None

        while True:
            # create crawling threads as long as targets are
            # in the target queue - do no so, if max threads
            # is reached
            if not self.target_queue.empty() and \
               len(threads) < self.max_threads:

                t = threading.Thread(
                                target = scn.scan_pages,
                                args = (self.target_queue,
                                        self.result_queue,
                                        self.max_depth,
                                        indexer)
                            )
                threads.append(t)
                t.start()

            # if there are not targets anymore and every thread
            # finished, stop
            elif self.target_queue.empty() and \
                 len(threads) == 0:
                break

            time.sleep(0.1)

            # remove threads from thread queue that already
            # finished
            threads = filter(lambda x: x.is_alive(), threads)

        if self.idx_lock:
            with self.idx_lock:
                self.idx.close_indexer()

        # print results
        self._print_results()
        print("finished in %fs" % secs(start_time))

    def _print_results(self):
        """ print results in result queue """

        while not self.result_queue.empty():
            result = self.result_queue.get()
            print(result)

    def search(self, term, field=scn.FIELD):
        """
        search

        """
        if not (self.idx and self.idx_lock):
            logging.warning("no index existing!")
            return []

        with self.idx_lock:
            hits = self.idx.search(field, term)

        return hits

def main():
    parser = argparse.ArgumentParser(description='webcrawler')
    parser.add_argument('--depth', type=int, default=1,
                        help='depth the crawler follows links')
    parser.add_argument('--threads', type=int, default=10,
                        help='amount of threads that crawl the web')
    parser.add_argument('-i', action="store_true", default=False,
                        help='use an interactive shell to query crawled pages')
    args, unknown = parser.parse_known_args(sys.argv[1:])

    if not unknown:
        print("Please provide a webpage to crawl!")
        sys.exit(1)
    else:
        page = unknown[-1]

    try:
        crawler = Crawler(page, args.threads, args.depth)
        crawler.start()

        if args.i:
            while True:
                _input = raw_input("> ")
                if  _input == "exit":
                    break
                elif not _input:
                    continue
                hits = crawler.search(_input)

                for score, url, content in hits:
                    print("\t-> (%f) %s\n\t%s" % (score, url,
                          repr(content[:100])))

    except Exception, err:
        logging.error(err)

if __name__ == "__main__":
    main()
