#!/usr/bin/python
# -*- coding: utf-8  -*-
"""
ReviewPage

code to perform the review-action for a given revision
"""

import threading, Queue
import api

# Importing pywikibot
import pywikibot

# ensure that we are logged in
pywikibot.getSite().login()

def ReviewWorker():
    """Review worker to work on queue
    
    Will rake take pages from the queue and try to review them on the wiki.
    """
    print('started review daemon')
    while True:
        (oldid, comment, callback) = page_review_queue.get()
        if oldid is None:
            # an explicit end-of-Queue marker is needed for compatibility
            # with Python 2.4; in 2.5, we could use the Queue's task_done()
            # and join() methods
            return

        try:
            review(oldid, comment)
            error = None
        except Exception, error:
            print("Error in review worker:")
            print error

        if callback is not None:
            callback(oldid, error)

# This queue will contain all pages to be reviewed
page_review_queue = Queue.Queue()

# This thread will periodically check the page_review_queue and initiate a
# review as soon as a new item appears on the queue
_reviewthread = threading.Thread(target=ReviewWorker)
_reviewthread.setName('Review-Thread')
_reviewthread.setDaemon(True)

def review_async(oldid, comment=None, callback=None):
    """Put page on queue to be reviewed to wiki asynchronously.

    callback: a callable object that will be called after the page put
                operation; this object must take two arguments:
                (1) a Page object, and (2) an exception instance, which
                will be None if the page was saved successfully.

    The callback is intended to be used by bots that need to keep track
    of which reviews were successful.
    """
    try:
        page_review_queue.mutex.acquire()
        try:
            _reviewthread.start()
        except (AssertionError, RuntimeError):
            pass
    finally:
        page_review_queue.mutex.release()
    page_review_queue.put((oldid, comment, callback))

def review(revisionID, comment = '', getagain = False):
    """
    This function will review the given revision ID with the given comment.
    If getagain is set, it will get a new token (not necessary since it will
    try to get a new token automatically if the old one is broken)
    """
    # print('review will start id: %s - %s' % (revisionID, getagain))
    predata = {
                'action'        : 'review',
                'format'        : 'xml',
                'revid'         :  str(revisionID),
                'token'         :  pywikibot.getSite().getToken(getagain = getagain),
                'comment'       :  comment,
    }

    address = pywikibot.getSite().family.apipath(pywikibot.getSite().lang)
    data = api.postForm( pywikibot.getSite(), address, predata)

    if data.find('review result=\"Success\"') == -1:
        if not data.find('Invalid token') == -1:
            if getagain:
                raise pywikibot.Error('Invalid Token')
            else:
                review(revisionID, comment = '', getagain = True)
        else:
            raise pywikibot.Error('Review unsuccessful %s' %data)

