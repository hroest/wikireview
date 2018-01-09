
def postForm(site, address, predata, method="POST"):
    # replaces:
    # data = pywikibot.getSite().postForm(address, predata=predata)

    address = site.family.apipath(site.lang)

    from pywikibot.comms import http
    from urllib import urlencode

    urldata = urlencode(predata)
    data = http.request(site, uri=address, method=method, body=urldata)
    return data


