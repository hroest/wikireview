#!/usr/bin/python
# -*- coding: utf-8  -*-
"""
UndoPAge

code to perform the undo-action for a given series of revisions
"""

import wikipedia as pywikibot
import threading, Queue
from xml.dom import minidom   #XML Parsing for API
from ReviewPage import review

class CallbackObject(object):
    """Callback object after an asynchronous function call.
    """
    def __init__(self):
        self.called = False

    def __call__(self, page, error, optReturn1 = None, optReturn2 = None):
        self.page = page
        self.error = error
        self.optReturn1 = optReturn1
        self.optReturn2 = optReturn2
        self.called = True

def UndoWorker():
    """Undo worker to work on queue
    
    Will rake take pages from the queue and try to undo them on the wiki.
    """
    print('started undo daemon')
    while True:
        (page, revisionOld, revisionNew, comment, do_review, callback) = page_undo_queue.get()
        if page is None:
            # an explicit end-of-Queue marker is needed for compatibility
            # with Python 2.4; in 2.5, we could use the Queue's task_done()
            # and join() methods
            return
        callb = CallbackObject()
        try:
            result, newrevid = undo(page, revisionOld, revisionNew, comment)
            error = None
            if do_review: 
                review(newrevid, 'Automatisches nachsichten nach Revert', callb)
        except Exception, error:
            result = None
            print("Error in undo worker:")
            print error

        if callback is not None:
            # if callback is provided, it is responsible for exception handling
            callback(page, error, optReturn1=result, optReturn2=callb)

_undothread = threading.Thread(target=UndoWorker)
_undothread.setName('Undo-Thread')
_undothread.setDaemon(True)
page_undo_queue = Queue.Queue()

def undo_async(thisPage, revisionOld, revisionNew,
               comment=None, review = False, callback=None):
    """Put page on queue to be undone to wiki asynchronously.

    callback: a callable object that will be called after the page put
                operation; this object must take two arguments:
                (1) a Page object, and (2) an exception instance, which
                will be None if the page was saved successfully.

    The callback is intended to be used by bots that need to keep track
    of which reviews were successful.

    """

    try:
        page_undo_queue.mutex.acquire()
        try:
            _undothread.start()
        except (AssertionError, RuntimeError):
            print('Error occured when starting the undothread')
            pass
    finally:
        page_undo_queue.mutex.release()

    page_undo_queue.put((thisPage, revisionOld, revisionNew, comment, review, callback))

def undo(pagetitle, revisionOld, revisionNew, comment = '', getagain = False):
    """"
    This function will try to undo the page to the old revision ID
    If getagain is set, it will get a new token (not necessary since it will
    try to get a new token automatically if the old one is broken)
    """
    predata = {
            'action'        : 'edit',
            'format'        : 'xml',
            'title'         : pagetitle,
            'undo'          : str(revisionOld),
            'undoafter'     : str(revisionNew),
            'token'         : pywikibot.getSite().getToken(),
            'summary'       : comment,
    }
    address = pywikibot.getSite().family.api_address(pywikibot.getSite().lang)
    response, data = pywikibot.getSite().postForm(address, predata=predata)
    dom = minidom.parseString(data.encode('utf8'))

    # print('undo data posted, page %s' % pagetitle)
    error = dom.getElementsByTagName('error')
    if not len(error) ==0:
        if not data.find('Invalid token') == -1:
            if getagain: raise pywikibot.Error('Invalid Token')
            else: undo(pagetitle, revisionOld, revisionNew, comment = '', getagain = True)
        else: raise pywikibot.Error('%s : %s' % (error[0].getAttribute('code'), error[0].getAttribute('info')))

    edit = dom.getElementsByTagName('edit')
    result = edit[0].getAttribute('result')
    newrevid = edit[0].getAttribute('newrevid')
    return result, newrevid

