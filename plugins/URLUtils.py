import httplib
import json
import re
import sys
import time
import urlparse

from mechanize import Browser
import pafy
import requests

from gilbertgrapesmom import build_help_and_info, CMND_PREFIX
from pluginbase import Plugin

class URLUtils(Plugin):
  URL_RE = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+')

  def __init__(self, args):
    '''URLUtils.__init__(self, args)
    Constructor for URLUtils, a GGM plugin
    used for:

      - Shortening URLs
      - Unshortening URLs
      - Listing titles of URLs
        - Plus viewcount and duration for YouTube
    '''
    self.yt = True if args['youtube'].lower() == 'yes' else False
    self.cmnds = { 'shorten': self.shorten_cmnd
                 , 'unshorten': self.unshorten_cmnd
                 }
    self.cmnds = dict((CMND_PREFIX + k, v) for k, v in self.cmnds.items())

  def shorten(self, url):
    '''
    Return a shortened version of the URL
    passed in using Google's URL shortening
    service.
    '''
    headers = {'Content-Type': 'application/json'
              , 'User-Agent': 'ggm IRC bot'
              }
    data = json.dumps({'longUrl': url})
    shortener = 'https://www.googleapis.com/urlshortener/v1/url'
    try:
      r = requests.post(shortener, headers=headers, data=data)
    except:
      return '[Error]: Invalid URL', True

    if r.status_code != 200:
      return '[Error]: Invalid status code {}'.format(r.status_code), True
    else:
      return bytes(r.json()['id']), False

  def shorten_cmnd(self, msg):
    '''
    Method to handle the shortening of
    URLs.
    '''
    try:
      url = self.URL_RE.findall(msg)[0]
    except IndexError:
      return '[Error]: Invalid URL', True
    if self.valid_url(url):
      return self.shorten(url)
    else:
      return '[Error]: Cannot reach URL', True

  def unshorten_cmnd(self, msg):
    '''
    Method to handle the un-shortenining
    of URLs.
    '''
    try:
      url = self.URL_RE.findall(msg)[0]
    except IndexError:
      return '[Error]: Invalid URL', True

    try:
      unshortened_url = self.unshorten(url)
      return unshortened_url, False
    except:
      return '[Error]: Couldn\'t reach URL', True

  def unshorten(self, url):
    '''
    Return an unshortened version of the
    URL passed in.

    Code from:
      http://ow.ly/ttH5j
    '''
    parsed = urlparse.urlparse(url)
    h = httplib.HTTPConnection(parsed.netloc)
    resource = parsed.path
    if parsed.query != '':
      resource += '?' + parsed.query
    h.request('HEAD', resource)
    response = h.getresponse()
    if response.status/100 == 3 and response.getheader('Location'):
      return self.unshorten(response.getheader('Location'))
    else:
      return url

  def get_title(self, url):
    '''
    Return the title of the passed
    in URL.
    '''
    br = Browser()
    br.set_handle_robots(False)
    br.open(url)
    return 'Title: {}'.format(br.title())

  def youtube_data(self, url):
    '''
    Return the video title, duration
    and view count for a YouTube URL.
    '''
    video = pafy.new(url)
    title = video.title
    duration = time.strftime('%H:%M:%S', time.gmtime(video.length))
    views = video.viewcount

    return 'Title: {} | Duration: {} | Views: {:,}'.format(\
                                          title, duration, views)
  
  def valid_url(self, url):
    '''
    Return True if the url parameter
    can be reached and returns a 200
    status code.
    '''
    try:
      return requests.head(url).status_code < 400
    except:
      return False

  def commands(self):
    return self.cmnds.keys()

  def get_commands(self):
    return self.cmnds

  def has_command(self, msg):
    # Call super class
    if super(URLUtils, self).has_command(msg):
      return True

    # Parse for a URL
    url = self.URL_RE.findall(msg)
    if url and self.valid_url(url[0]):
      return True

    # Otherwise, False
    return False

  def parse_command(self, msg):
    # Call the super class
    parse_ret = super(URLUtils, self).parse_command(msg)
    if parse_ret:
      return parse_ret

    # Check for help or info
    if msg.startswith(CMND_PREFIX + 'help'):
      return self.help(' '.join(msg.split()[1:]))
    elif msg.startswith(CMND_PREFIX + 'info'):
      return self.info(' '.join(msg.split()[1:]))

    # Grab a URL from the passed in message
    url = self.URL_RE.findall(msg)[0]
    unshortened = self.unshorten(url)

    # Check if we need to worry about YouTube info
    if self.yt:
      if 'youtube.com' in unshortened.lower():
        return self.youtube_data(unshortened), False

    # Check for a URL in the msg
    return '{}'.format(self.get_title(unshortened), url), False

  def help(self, cmd):
    # Strip prefix for aliased commands
    # and the help command removed
    msg = msg.lstrip(CMND_PREFIX + 'help')

    if msg.startswith('shorten'):
      reply = ''
      return reply, False

    elif msg.startswith('unshorten'):
      reply = ''
      return reply, False

  def info(self, cmd):
    # Strip prefix for aliased commands
    # and the help command removed
    msg = msg.lstrip(CMND_PREFIX + 'info')

    if msg.startswith('shorten'):
      reply = ''
      return reply, False

    elif msg.startswith('unshorten'):
      reply = ''
      return reply, False

    ni = 'Not available for that command. Use help instead.'
    return ni, False
