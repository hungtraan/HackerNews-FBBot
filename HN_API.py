import json, requests, pprint, urllib2, traceback, StringIO, gzip
from firebase import firebase
from bs4 import BeautifulSoup
from urlparse import urljoin
from flask import url_for

from ago import human
from datetime import timedelta
from datetime import datetime

try:
    ERROR_IMG = url_for('static', filename='assets/img/empty-placeholder.jpg', _external=True)
except Exception, e:
    ERROR_IMG = 'https://hacker-news-bot.herokuapp.com/static/assets/img/empty-placeholder.jpg'

firebase = firebase.FirebaseApplication('https://hacker-news.firebaseio.com', None)
LIMIT = 90

def get_stories(story_type='top', limit=LIMIT):
    # r = requests.get("/%sstories.json"%(story_type))
    results = firebase.get('/v0/%sstories'%(story_type), None)
    stories_list = results[:limit]
    num_stories = len(stories_list)
    i = 0
    stories = []

    for story_id in stories_list:
        i += 1
        try:
            story = firebase.get("/v0/item/%s"%(story_id), None)
            story['hn_url'] = 'https://news.ycombinator.com/item?id=%s'%(story_id)
            utc_time = datetime.utcfromtimestamp(story['time'])
            # story['datetime'] = utc_time.strftime("%Y-%m-%d")
            story['datetime'] = get_human_time(utc_time)
            # Only include news stories, not HN discussions
            if story_type == 'top' or story_type == 'best':
                if 'url' in story and story['type'] == 'story':
                    if story['url'] == '' or story['url'] is None:
                        story['url'] = story['hn_url']
                    story['image_url'] = get_og_img(story['url'])
                    stories.append(story)

            else:
                # Note: Job type does not have descendants
                stories.append(story)
            print "[Caching] %s/%s"%(i, num_stories)
        except Exception, e:
            print(e)
            # traceback.print_exc()

    return stories

def stories_from_search(query, search_type="top"):
    search_type = 'search' if search_type=="top" else 'search_by_date'
    url = "http://hn.algolia.com/api/v1/%s?query=%s&tags=story"%(search_type, query)

    r = requests.get(url)
    if r.status_code != requests.codes.ok:
        print r.text
        return
    stories_list = json.loads(r.content)['hits'][:9]

    stories = []

    for story in stories_list:
        story['hn_url'] = 'https://news.ycombinator.com/item?id=%s'%(story['objectID'])
        utc_time = datetime.utcfromtimestamp(story['created_at_i'])
        story['datetime'] = get_human_time(utc_time)
        if story['url'] == '' or story['url'] is None:
            story['url'] = story['hn_url']
        story['image_url'] = get_og_img(story['url'])
        stories.append(story)
        try:
            print "[Saved] %s"%(story['title'])
        except Exception, e:
            print e
    # pprint.pprint(stories_list)

    return stories

def get_og_img(url):

    try:
        fallback_img = url_for('static', filename="assets/img/empty-placeholder.jpg", _external=True)

    except Exception, e:
        fallback_img = ERROR_IMG

    img = fallback_img

    try:

        headers = [('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11'),
           ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
           ('Accept-Charset', 'ISO-8859-1,utf-8;q=0.7,*;q=0.3'),
           ('Accept-Encoding', 'gzip,deflate'),
           ('Accept-Language', 'en-US,en;q=0.8'),
           ('Connection', 'keep-alive')]
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor)
        opener.addheaders = headers
        page = opener.open(url, timeout=3)
        content = decode(page)
        # content = data.read()

        soup = BeautifulSoup(content, "html.parser")
        meta_tag = soup.select("meta[property='og:image']")

        if len(meta_tag) > 0:
            # found og:image
            img = meta_tag[0]['content']
        else:
            meta_tag = soup.select("meta[name='twitter:image']")
            if len(meta_tag) > 0:
                img = meta_tag[0]['content']
            else:
                img_tag = soup.find_all("img")

                img = img_tag[0]['src'] if len(img_tag) > 0 else ''
                if img[:2] == '//':
                    img = "http:" + img
                elif img != '' and 'http' not in img:
                    if 'data:image/' == img[:11]:
                        return ERROR_IMG
                    img = urljoin(url, img)

    except Exception, e:
        print "[get_og_img] ERROR: %s"%(url)
        print e
        traceback.print_exc()

    return img

def decode (page):
    encoding = page.info().get("Content-Encoding")
    if encoding in ('gzip', 'x-gzip', 'deflate'):
        content = page.read()
        if encoding == 'deflate':
            data = StringIO.StringIO(zlib.decompress(content))
        else:
            data = gzip.GzipFile('', 'rb', 9, StringIO.StringIO(content))
        page = data.read()

    return page

# =================== RESTful methods ==============
def get_stories_rest(story_type='top', limit=9):
    r = requests.get("/%sstories.json"%(story_type))

    if r.status_code != requests.codes.ok:
        print r.text
        return
    stories_list = json.loads(r.content)[:limit]
    stories = []

    for story_id in stories_list:
        item = requests.get("https://hacker-news.firebaseio.com/v0/item/%s.json"%(story_id))
        story = json.loads(item.content)
        story['hn_url'] = 'https://news.ycombinator.com/item?id=%s'%(story_id)
        utc_time = datetime.utcfromtimestamp(story['time'])
        story['datetime'] = get_human_time(utc_time)
        story['image_url'] = get_og_img(story['url'])

        # Only include news stories, not HN discussions
        if story_type == 'top' or story_type == 'best':
            if 'url' in story and story['type'] == 'story':
                stories.append(story)
        else:
            # Note: Job does not have descendants
            stories.append(story)
    return stories

def get_human_time(time):
    ts = datetime.utcnow() - time
    return human(ts, precision=1)

"""
To do:

For Show, Ask:
- Aggregate and rank by score
-
"""

# print("Top")
# get_stories('top', 10)
# print("Best")
# get_stories('best', 10)
# print("New")
# get_stories('new', 10)
# print("Ask")
# get_stories('ask', 10)
# print("Show")
# get_stories('show', 10)
# print("Job")
# get_stories('job', 10)


"""
Sample json result

Object keys:
    - by
    - descendants
    - hn_url
    - id
    - kids [ids, ids, ids, ...]
    - score
    - time
    - title
    - type
    - url


Firebase item:
{u'by': u'JumpCrisscross',
 u'descendants': 29,
 'hn_link': 'https://news.ycombinator.com/item?id=13556714',
 u'id': 13556714,
 u'kids': [13570707,
           13570550,
           13570901,
           13570711,
           13570745,
           13570751,
           13570667],
 u'score': 27,
 u'time': 1486083805,
 u'title': u'Spotify may delay IPO to 2018 as it rethinks licensing deals',
 u'type': u'story',
 u'url': u'https://techcrunch.com/2017/02/02/sources-spotify-may-delay-ipo-to-2018-as-it-rethinks-licensing-deals/'}

Search API object:

{u'_highlightResult': {u'author': {u'matchLevel': u'none',
                                   u'matchedWords': [],
                                   u'value': u'gmays'},
                       u'story_text': {u'matchLevel': u'none',
                                       u'matchedWords': [],
                                       u'value': u''},
                       u'title': {u'fullyHighlighted': False,
                                  u'matchLevel': u'full',
                                  u'matchedWords': [u'tesla',
                                                    u'model',
                                                    u'3'],
                                  u'value': u"<em>Tesla</em>'s <em>Model</em> <em>3</em>"},
                       u'url': {u'fullyHighlighted': False,
                                u'matchLevel': u'partial',
                                u'matchedWords': [u'model', u'3'],
                                u'value': u'http://www.economist.com/blogs/schumpeter/2014/07/teslas-<em>model</em>-<em>3</em>'}},
 u'_tags': [u'story', u'author_gmays', u'story_8096483'],
 u'author': u'gmays',
 u'comment_text': None,
 u'created_at': u'2014-07-28T13:12:35.000Z',
 u'created_at_i': 1406553155,
 u'num_comments': 115,
 u'objectID': u'8096483',
 u'parent_id': None,
 u'points': 135,
 u'story_id': None,
 u'story_text': u'',
 u'story_title': None,
 u'story_url': None,
 u'title': u"Tesla's Model 3",
 u'url': u'http://www.economist.com/blogs/schumpeter/2014/07/teslas-model-3'}

"""

