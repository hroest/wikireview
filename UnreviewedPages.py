#!/usr/bin/python
# -*- coding: utf-8  -*-
"""
Unreviewed Pages

Code to get unreviewed pages from Wikipedia (by category or all)
"""

import re
from string import Template
import urllib, urllib2  #Internet libs
from xml.dom import minidom   #XML Parsing for API

# Importing pywikibot
import pywikibot

import socket, time, Queue
import threading

toolserver_url = 'https://tools.wmflabs.org'
hroest_url = toolserver_url + '/hroest/'

def send_request(webpage):
    request = urllib2.Request(webpage.encode('utf8'))
    request.add_header('User-Agent',
       u'de:HRoestBot by de-user Hannes Röst'.encode('utf8'))
    opener = urllib2.build_opener()
    data = opener.open(request).read()

    data = urllib.unquote(data)
    data = unicode(data, 'utf8')
    return data

class UnreviewedPage():

    def __init__(self, wikipedia_page, title, thisid, stable_revision, last_revision, pending_since):
        self.wikipedia_page   = wikipedia_page  
        self.title            = title           
        self.thisid           = thisid          
        self.stable_revision  = stable_revision 
        self.last_revision    = last_revision   
        self.pending_since    = pending_since   

def getAllUnreviewed():
    """Get all unreviewed pages

    This function uses the toolserver to get these pages, using the tool by hroest 
    """

    webpage = hroest_url + 'cgi-bin/bot_only/all_unflagged.py'
    try:
        data = send_request( webpage)
    except:
        #try again, at least now the query is in MySQL cache
        data = send_request( webpage)

    articles = data.split('\n')
    numberArticles = len( articles)

    unstable = []
    for a in articles:
        if len(a) == 0: continue
        mysplit = a.split( '||;;;')
        thisTitle       = mysplit[0].strip()
        thisID          = mysplit[1].strip()
        stable_rev      = mysplit[2].strip()
        last_rev        = mysplit[3].strip()
        pending_since   = mysplit[4].strip()
        unstable.append([pywikibot.Page(pywikibot.getSite(), thisTitle),
                 thisTitle, thisID, stable_rev, last_rev, pending_since ] )
    return unstable, [], []

def getAllUnreviewedinCat(cat_name, depth=1, sortby='title', exclude = ''):
    """Get all unreviewed pages in a category
    
    This function uses the toolserver to get these pages, using the tool by hroest 
    """

    webpage = hroest_url + 'flagged.php'
    cat_temp = Template('%s?category=$cat&depth=$depth' % webpage +
        '&sortby=$sortby&exclude=$exclude&doit=Los!' )
    webpage = cat_temp.substitute(cat=urllib.quote_plus(cat_name), depth=depth,
                      sortby = sortby, exclude = exclude)
    data = send_request( webpage)

    numberArticles = '(\d*) nachzusichtende Artikel gefunden.'
    m = re.search(numberArticles, data)
    number = int(m.group(1))
    data = data[:m.end()]

    unstable = []
    for q in re.finditer("target\" href=\"http://de.wikipedia.org/" + \
            "w/index.php\?title=(.*?)\&diffonly=\d*\&oldid=(\d*)", data):
        thisTitle = q.group(1)
        thisID = -1
        stable_rev = q.group(2)
        last_rev = -1
        pending_since = -1
        page = UnreviewedPage(pywikibot.Page(pywikibot.getSite(), thisTitle),
             thisTitle, thisID, stable_rev, last_rev, pending_since )
        unstable.append(page)

    return unstable

def _magnus_getAllUnreviewedinCat(cat_name, depth=1):
    """Get all unreviewed pages in a category; using magnus tool
    """

    magnus = 'http://toolserver.org/~magnus/deep_out_of_sight.php'
    cat_temp = Template('%s?category=$cat&depth=$depth&doit=Los!' % magnus)
    webpage = cat_temp.substitute(cat=cat_name, depth=depth)
    data = send_request( webpage)

    numberArticles = '(\d*) nachzusichtende Artikel gefunden.'
    m = re.search(numberArticles, data)
    number = int(m.group(1))
    data = data[:m.end()]

    unstable = []
    for q in re.finditer("target\" href=\"http://de.wikipedia.org/" + \
            "w/index.php\?title=(.*?)\&diffonly=\d*\&oldid=(\d*)", data):
        thisTitle = q.group(1)
        thisID = -1
        stable_rev = q.group(2)
        last_rev = -1
        pending_since = -1
        unstable.append([pywikibot.Page(pywikibot.getSite(), thisTitle),
             thisTitle, thisID, stable_rev, last_rev, pending_since ] )

    return unstable, [], []

def _getAllUnreviewedinCat_api(cat_name, recursive=False, recursionlevel = 0,
    parentCats = [], qContinue=None, parent=None, excludeSubcats=[]):
    """Get all unreviewed pages in a category; using the API
    """
    import copy
    catregex = 'Kategorie:(.*)'

    print('input: %s, %s, %s, %s, %s' % (cat_name, recursive, recursionlevel, parentCats, qContinue))
    if parent:
        parentCats.append(parent)
    if cat_name in parentCats: #it is recursive...STOP
        print('recursion %s' % parentCats)
        return []
    if recursionlevel < 0: 
        return []

    #this is a little hack to make the two versions compatible
    if not re.search(catregex, cat_name): cat_name = 'Kategorie:' + cat_name
    print('getting %s on recursion level %s' % (cat_name, recursionlevel) )

    predata = {
                'action'        : 'query',
                'format'        : 'xml',
                'generator'     : 'categorymembers',
                'gcmtitle'      : cat_name,
                'gcmlimit'      : 'max',
                'prop'          : 'flagged|info'
    }
    if qContinue: predata['gcmcontinue'] = qContinue
    #
    address = pywikibot.getSite().family.api_address(pywikibot.getSite().lang)
    response, data = pywikibot.getSite().postForm(address, predata=predata)
    dom = minidom.parseString(data.encode('utf8'))
    #
    try:
        if (dom.getElementsByTagName('error')[0].getAttribute('code') == 'gcminvalidcategory'):
            print('category is not valid')
            raise pywikibot.InvalidTitle('%s is not a valid category name' % cat_name)
    except IndexError:
        pass
    #
    members = dom.getElementsByTagName('page')
    unstable = []

    for node in members:
        thisTitle = node.getAttribute('title')
        if node.getAttribute('ns') == '0':
            thisID = node.getAttribute('pageid')
            last_rev = node.getAttribute('lastrevid')
            flagged = node.getElementsByTagName('flagged')
            #
            if len(flagged) == 0: continue
            else: flagged = flagged[0]
            stable_rev = flagged.getAttribute('stable_revid')
            if not last_rev == stable_rev:
                pending_since = flagged.getAttribute('pending_since')
                page = UnreviewedPage(pywikibot.Page(pywikibot.getSite(), thisTitle),
                     thisTitle, thisID, stable_rev, last_rev, pending_since )
                unstable.append(page)
        #
        #here we have a subcategory
        if node.getAttribute('ns') == '14':
            if recursive and not thisTitle in excludeSubcats:
                #we get all pages in subcategorie 
                sub_unstable = _getAllUnreviewedinCat_api(thisTitle, recursive, recursionlevel - 1, copy.copy(parentCats), parent=cat_name, excludeSubcats=excludeSubcats)
                if len(sub_unstable) > 0: unstable.extend(nextunstable)
                unstable.extend(sub_unstable)

    # If there are more than a certain number of pages, we get a
    # "query-continue" signal returned.
    cont = dom.getElementsByTagName('query-continue')
    if not len(cont) == 0:
        #if not here already TODO
        nextStart = cont[0].getElementsByTagName('categorymembers')[0].getAttribute('gcmcontinue')
        nextunstable = _getAllUnreviewedinCat_api(cat_name, recursive, recursionlevel, parentCats, qContinue=nextStart)
        if len(nextunstable) > 0: unstable.extend(nextunstable)
    return unstable


#
# History retrieval (async)
#

def RetrieveHistoryWorker():
    """Daemon; take pages from the queue and get the latest and the
    last reviewed version as well as the comments for the revision.
    It will get a diffobject and put this one on the review_done queue."""
    print('started RetrieveHistoryWorker (retrieving daemon)')
    while True:
        page = review_not_done.get()
        if page is None:
            # an explicit end-of-Queue marker is needed for compatibility
            # with Python 2.4; in 2.5, we could use the Queue's task_done()
            # and join() methods
            return
        try:
            import fullrevision
            diffobject = fullrevision.getUnreviewedandComments(page.title, page.stable_revision, page.last_revision)
            diffobject.page = page
            if page.last_revision == -1: page.last_revision  = diffobject.latestID
            if page.pending_since == -1: page.pending_since  = diffobject.latestTimestamp
            review_done.put( diffobject )
            error = None
        except Exception as error:
            print('Encountered an error when retrieving full revision history for "%s":' % (page.title))
            print error
            pass

#this thread is started to get the history
_reviewgetthread = threading.Thread(target=RetrieveHistoryWorker)
_reviewgetthread.setName('Retrieve History Worker')
_reviewgetthread.setDaemon(True)

review_not_done = Queue.Queue()     # of these we don't have the history yet
review_done = Queue.Queue()         # of these we have the history, we can give it back

def get_next_reviewed_page(pagesToGet, min_review_size=40):
    """
    This function will return the next page to be reviewed.
    If there are not enough pages to be reviewed it will take some pages from the
    input queue and add them to the TO DO queue.

    global/full TODO queue: pagesToGet
    current TODO queue: review_not_done queue
    fetched text queue: review_done queue
    """

    if not page_is_available(pagesToGet): raise Exception('No more pages are available')

    if review_done.qsize() < min_review_size and not pagesToGet.empty():
        for i in xrange(10):
            if not pagesToGet.empty(): putpageonreviewqueue( pagesToGet.get() )

    # Wait until at least one page is on the review_done queue. This terminates
    # because we checked that at least one page is still on one of the queues. 
    while review_done.empty():
        print('Not ready yet, sleeping for 3 s')
        time.sleep(3)
    return review_done.get()

def putpageonreviewqueue(page):
    """Put page on queue to get the texts.
    """
    try:
        review_not_done.mutex.acquire()
        try:
            _reviewgetthread.start()
        except (AssertionError, RuntimeError):
            pass
    finally:
        review_not_done.mutex.release()
    review_not_done.put(page)

def page_is_available(pagesToGet):
  return not (pagesToGet.empty() and review_done.empty() and review_not_done.empty() )


