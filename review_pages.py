#!/usr/bin/python
# -*- coding: utf-8  -*-
"""
This bot can be used to review single edits in Wikipedia in an interactive,
semi-automatic manner.

Arguments for the Review Bot:

-category:         Which category to review

-depth:            Depth with which to retrieve subcategories

-exclude:          Subcategories to exclude from the search (separated by semicolon)

-sortby:           Order in which to process the pages to review. Valid options
                   are: size, size_reverse, title, title_reverse, time,
                   time_reverse. If you want the oldest non-reviewed changes
                   first, time_reverse is the option you need.
"""

import threading
import socket, time, Queue

import wikipedia as pywikibot 
import UnreviewedPages
import ReviewPage
import UndoPage

msg_empty_review = {
    'de' : u'Sichte automatisch eine leere Änderung'
}
msg_review_comment = {
    'de' : u'Sichte halbautomatisch per pywikipedia'
}

msg_revert_to = {
    'de' : u"Revert auf letzte gesichtete Version %s."
}
msg_default = {
    'de' : u"Bitte beachte [[WP:WWNI]] und [[WP:Q]] sowie [[WP:WEB]]. " 
}
msg_vandalism = {
    'de' : u"Entferne Vandalismus. "
}
msg_advertisement = {
    'de' : u"Entferne Werbung. "
}
msg_source = {
    'de' : u"Entferne Änderung ohne Quelle. Bitte [[WP:Q|alle Änderungen mit einer reputablen Quelle belegen]]. "
}
msg_whatIsNot = {
    'de' : u"Entferne Ankündigung gemäss [[WP:WWNI]] Punkt 8. "
}
msg_weblink = {
    'de' :  u"Entferne Weblink gemäss [[WP:WEB]]. " 
}
msg_pov = {
    'de' :  u"Entferne wertende Äusserung gemäss [[WP:NPOV]]. " 
}
msg_reason = {
    'de' :  u"Bitte Änderung in der [[WP:ZQ|Zusammenfassungszeile]] begründen. " 
}

verbose = 0

class Counter:
    def __init__(self):
        self.review_counter = 0
        self.accepted_counter = 0
        self.reverted_counter = 0

def runBot(pagesToGet, Callbacks, didAlready, UndoCallbacks, automatically_reviewed):
    """For a set of pages, it will prompt the user to set a flag for revision.

    This will automate the review process in wikipedia.
    All there is to do is give a Queue with pages to review. This can be
    obtained from a function like getAllUnreviewed or getAllUnreviewedinCat.
    It will obtain the revisions, make a diff and ask the user to revert, flag
    or ignore that page. The pages are fetched asynchronously and stored on a
    Queue.
    """
    start = time.time()
    counter = Counter()
    language = pywikibot.getSite().lang
    wp_api = 'http://%s.wikipedia.org/w/index.php?' % language
    try:
        while UnreviewedPages.page_is_available(pagesToGet):
            counter.review_counter += 1
            diff = UnreviewedPages.get_next_reviewed_page(pagesToGet, min_review_size=40)
            page = diff.page
            if page.title in didAlready: continue
            pywikibot.output('\03{lightpurple}' + '*'*45 + '\n' + '*'*45 );
            print "pageTitle = '%s'" % page.title
            print "revEnd = '%s'" % page.last_revision
            print "revStart = '%s'" % page.stable_revision
            if diff.prepared: 
                pywikibot.output( diff.prepared )
            else: 
                pywikibot.showDiff(diff.old, diff.new)
            print("="*35 + "\nComments:")
            for c, u in zip(diff.comments, diff.users):
                print u, c
            print("="*35)
            print("Pending since:", page.pending_since) 
            print("Page title:", page.title) 
            if diff.equal():
                print('They are equal, review automatically')
                callb = UndoPage.CallbackObject()
                Callbacks.append(callb)
                ReviewPage.review_async(page.last_revision, msg_empty_review[language], callb)
                automatically_reviewed.append([page, wp_api + 'diff=%s&oldid=%s' % ( page.last_revision, page.stable_revision) ])
                continue
            print(wp_api + 'diff=%s&oldid=%s' % ( page.last_revision, page.stable_revision) )
            print(wp_api + 'title=%s&action=edit&oldid=%s' % (page.title, page.stable_revision))
            print(wp_api + 'title=%s&action=edit' % ( page.title) )
            ask_user_input(page, diff, Callbacks, UndoCallbacks, counter)
            didAlready[page.title] = ''
    except KeyboardInterrupt:
        print "\n", "="*75, "\nKeyboard interrupt stopped review"
    end = time.time()
    print "-exclude_pages:\"%s\"" % ";".join(didAlready.keys())
    print_stats( counter.review_counter, counter.accepted_counter,
                counter.reverted_counter, end-start)

    # Wait until all queues are empty...
    i = 0
    while True:
        finished_callbacks = [c.called for c in Callbacks]
        print "Waiting for all calls to finish (%s out of %s have finished)" % ( 
            sum(finished_callbacks), len(finished_callbacks) )
        if not all(finished_callbacks):
          time.sleep(2)
          i += 1
        else:
            return

        if i > 200:
            print "Aborting wait for all callbacks - this is likely a bug, please inform the developer!"
            return

def ask_user_input(page, diff, Callbacks, UndoCallbacks, counter):
    while True:
        choice = pywikibot.inputChoice('Review this?', ['Yes',
            'Yes', 'Yes',  'No', 'No',
            'Revert', 'Revert (no source)', 'Revert Vandalism',
            'Revert Advertisement', 'Revert crystal ball',
            'Revert with own Comment', 'Revert Weblink', 'Reason', 'NPOV',
            'Show Full Diff', 'review with own comment'],
            ['y', '\\',"'", 'n', ']', 'r', 's', 'v',
             'ad', 'c', 'rc', 'web', 'reason',
             'pov', 'd', 'ac'])
        if choice in ['y', '$', ';', "'", '\\', 'ac']:
            print "review this edit"
            callb = UndoPage.CallbackObject()
            Callbacks.append(callb)
            review_comment = msg_review_comment[pywikibot.getSite().lang]
            if choice == 'ac':
                review_comment = pywikibot.input(u"What comment would you like?")
            ReviewPage.review_async(page.last_revision, review_comment, callb)
            counter.accepted_counter += 1
            return
        if choice in ['r', 'rc', 'v', 'ad', 's', 'c', 'web', 'pov', 'reason']:
            print "revert this edit"
            counter.reverted_counter +=1
            comm = get_revert_message(choice, page.stable_revision)
            callb = UndoPage.CallbackObject()
            UndoCallbacks.append(callb)
            UndoPage.undo_async(page.title, page.stable_revision, page.last_revision, comment=comm,
                                 review = True, callback=callb)
            return
        if choice == 'd':
            pywikibot.showDiff(diff.old, diff.new)
            print("==========================\n")
        else:
            return

def get_revert_message(choice, revision_number):
    language = pywikibot.getSite().lang
    revert_to =  msg_revert_to[language] % revision_number
    comm = msg_default[language] + revert_to
    if choice == 'rc':     comm = pywikibot.input(u"What comment would you like?") + " " + revert_to
    if choice == 'v':      comm = msg_vandalism[ language ] + revert_to 
    if choice == 'ad':     comm = msg_advertisement[ language ] + revert_to 
    if choice == 's':      comm = msg_source[ language ] + revert_to 
    if choice == 'c':      comm = msg_whatIsNot[ language ] + revert_to 
    if choice == 'web':    comm = msg_weblink[ language ] + revert_to 
    if choice == 'pov':    comm = msg_pov[ language ] + revert_to 
    if choice == 'reason': comm = msg_reason[ language ] + revert_to 
    return comm

def print_stats(total, acc, rev, time):
    unrev = total - rev - acc
    print "\n\n", "=" * 75, "\n"
    print "done %s" % total
    if total < 1: return
    print "accepted %s, %0.1f%%" % (acc, acc*100.0/total)
    print "reverted %s, %0.1f%%" % (rev, rev*100.0/total)
    print "not reviewed %s, %0.1f%%" % (unrev, unrev*100.0/total)
    print "time: total %d s (%d min) ; per page %0.1f s" % (time, time/60, time/total)

def main(*args):

    Callbacks = []
    UndoCallbacks = []
    didAlready = {}
    automatically_reviewed = []
    cat_name = None
    unstable = []
    sortby = 'time_reverse'
    depth = 99

    # read command line parameters
    for arg in pywikibot.handleArgs(*args):
        if arg.startswith('-category:'):
            cat_name = arg[len('-category:'):]
        if arg.startswith('-sortby:'):
            sortby = arg[len('-sortby:'):]
        if arg.startswith('-depth:'):
            depth = int(arg[len('-depth:'):])
        if arg.startswith('-exclude:'):
            exclude = arg[len('-exclude:'):]
        if arg.startswith('-exclude_pages:'):
            didAlready = arg[len('-exclude_pages:'):].split(";")
            didAlready = dict( [(a,'') for a in didAlready] )
        if arg.startswith('-h') or arg.startswith('--help'):
          pywikibot.showHelp()
          return

    # timeout in seconds
    # increase when urllib2.URLError: <urlopen error timed out> occurs
    timeout = 99
    socket.setdefaulttimeout(timeout)

    start = time.time()
    if cat_name is not None: 
      unstable = UnreviewedPages.getAllUnreviewedinCat(cat_name, depth, sortby)
    else:
      unstable, u, s = UnreviewedPages.getAllUnreviewed()
    end = time.time()

    # Add all candidates to the queue, dont include pages in didAlready
    pagesToGet = Queue.Queue()
    for candidate in unstable:
        if candidate.title in didAlready: continue
        pagesToGet.put( candidate )

    print "I found %s pages (out of %s) to review in %s s using a depth of %s" % (
        pagesToGet.qsize(), len(unstable), end - start, depth)

    runBot(pagesToGet, Callbacks, didAlready, UndoCallbacks, automatically_reviewed)

if __name__ == "__main__":
    try:
        main()
    finally:
        pywikibot.stopme()
