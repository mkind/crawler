"""
This module indexes the found resources. This ought to be replace by what ever
you want to index with. Here Apache Lucene is used.

"""

__author__ = "sascha zinke and maximilian haeckel"
__version__ = 0.01
__license__ = "BSD-3-Clause, see LICENSE for details"

from org.apache.lucene.analysis.standard import StandardAnalyzer
from org.apache.lucene.index import IndexWriter, IndexWriterConfig
from org.apache.lucene.index import DirectoryReader
from org.apache.lucene.search import  IndexSearcher
from org.apache.lucene.queryparser.analyzing import AnalyzingQueryParser
from org.apache.lucene.store import FSDirectory, RAMDirectory
from org.apache.lucene.util import Version
from org.apache.lucene.document import Document, Field, TextField
import java.io.File

class Indexer(object):
    """
    The index class contains everything that is needed to index files.

    """

    def __init__(self, dest=None):
        """
        create a apache lucene indexer

        input:
            dest    destination to store index information. If not set, use
                    RAM.

        """
        # where to store information file or ram
        if dest:
            _dir = FSDirectory.open(java.io.File(dest))
        else:
            _dir = RAMDirectory()
        self.directory = _dir

        # analyser
        self.analyser = StandardAnalyzer(Version.LUCENE_CURRENT)

        # index writer
        cfg = IndexWriterConfig(Version.LUCENE_CURRENT, self.analyser)
        cfg.setDefaultWriteLockTimeout(6000)
        self.idx_writer = IndexWriter(self.directory, cfg)

    def add_document(self, url, field, text):
        """
        add a new document to index writer

        input:
            url     the url of the target to be indexed
            field   fieldname of the value that will be indexed
            text    text to be indexed

        """
        doc = Document()
        doc.add(Field('url', url, TextField.TYPE_STORED))
        doc.add(Field(field, text, TextField.TYPE_STORED))
        self.idx_writer.addDocument(doc)

    def close_indexer(self):
        self.idx_writer.close()

    def search(self, field, text):
        """
        search text within indexed data

        input:
            field   fieldname of the value that will be indexed
            text    text to search

        output:
            hits    return a list of hits

        """
        results = []
        idx_reader = DirectoryReader.open(self.directory)
        idx_searcher = IndexSearcher(idx_reader)

        # parse query
        parser = AnalyzingQueryParser(Version.LUCENE_CURRENT, field, self.analyser)
        query = parser.parse(text)

        # search
        hits = idx_searcher.search(query, 1000).scoreDocs.tolist()
        for hit in hits:
            doc = idx_searcher.doc(hit.doc)
            score = hit.score
            title = doc.get(field)
            url = doc.get("url")
            results.append((score, url, title))

        return results

