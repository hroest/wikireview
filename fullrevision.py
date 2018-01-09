# -*- coding: utf-8  -*-
"""
Code to get access to the full history of an page

TODO: implement query-continue
"""

# Importing pywikibot
import pywikibot
import api

from xml.dom import minidom   #XML Parsing for API

class TextDiff:

    def __init__(self, old, new, users, comments, title, revStart, revEnd):
        self.old        = old
        self.new        = new
        self.users      = users
        self.comments   = comments
        self.prepared   = None
        self.latestID   = None
        self.latestTimestamp = None
        self.title = title
        self.revStart = revStart
        self.revEnd = revEnd

    def equal(self):
        return self.new == self.old

    def __unicode__(self):
        if self.equal():
          return u"Difference object of '%s' between revisions %s and %s (%s revisions, equal)" % (
              self.title, self.revStart, self.revEnd, len(self.users))
        else:
          return u"Difference object of '%s' between revisions %s and %s (%s revisions, not equal)" % (
              self.title, self.revStart, self.revEnd, len(self.users))

def getUnreviewedandComments(pageTitle, revStart = '', revEnd= ''):
    """Returns a TextDiff object containing all diffs between start and end.
    This function returns the content of the two revisions given as arguments.
    In addition the comments of all revisions IN BETWEEN are returned as well as
    the id and timestamp of the latest revision.
    """

    data = getFullHistory(pageTitle, revStart, revEnd)
    dom = minidom.parseString(data.encode('utf8'))
    query_continue = dom.getElementsByTagName('query-continue')
    members = dom.getElementsByTagName('rev')

    if len(query_continue) != 0:
        # TODO  - too many queries
        raise Exception("Could not retrieve full history in one query.")

    comments = []
    for node in members:
        comments.append(node.getAttribute('comment'))

    users = []
    for node in members:
        users.append(node.getAttribute('user'))

    if len(comments) == 0:
        raise Exception("No History could be found between %s and %s for page '%s'" % (revStart, revEnd, pageTitle))

    comments.pop()

    new = members[0].firstChild.data
    old = members[-1].firstChild.data
    latestID = members[0].getAttribute('revid')
    latestTimestamp = members[0].getAttribute('timestamp')
    diff = TextDiff(old, new, users, comments, pageTitle, revStart, revEnd)
    diff.latestID = latestID
    diff.latestTimestamp = latestTimestamp

    return diff

def getFullHistory(pageTitle, revEnd = '', revStart= ''):
    """Get all revision from start to end using API

    We get the full history starting at revStart (newest rvid) and ending at
    revEnd (oldest rvid). If revStart == -1 we just start at the current revision.

    We return an XML text string with all the requested revisions.
    Note that the maximum we are allowed to get is 50 pages with content.
    """
    predata = {
                'action'    : 'query',
                'format'    : 'xml',
                'prop'      : 'revisions',
                'rvprop'    : 'ids|timestamp|user|comment|content',
                'rvendid'   : str(revEnd),
                'titles'    : pageTitle.encode("utf8")
    }

    # sometimes we don't know the number of the newest revision
    # it should be set to -1 and will not be considered
    if not revStart == -1:
        predata['rvstartid'] = str(revStart)

    address = pywikibot.getSite().family.apipath(pywikibot.getSite().lang)
    return api.postForm(pywikibot.getSite(), address, predata=predata)

