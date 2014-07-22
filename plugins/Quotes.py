# Imports
import subprocess as sp
import sys
import time

import bashquote as bq
import requests

from gilbertgrapesmom import build_help_and_info, CMND_PREFIX
from pluginbase import Plugin
from twisted.python import log

class Quotes(Plugin):
  def __init__(self, args):
    # Save the arguments
    for arg, val in args.iteritems():
      setattr(self, arg, val)

    # Chuck Norris API
    self.CHUCK_NORRIS_API = 'http://api.icndb.com/jokes/random/'

    # Keep a timer for how often quotes
    # will be retrieved by the bot
    self.max_quotes = 5             # self.max_quotes quotes per
    self.time_frame = 60            # self.time_frame seconds
    self.last_quote = None
    self.quote_counter = 0

    # Supported commands
    self.cmnds = { 'bash.org': self.bash_org
                 , 'bq': self.bash_org
                 , 'chuck-norris': self.chuck_norris
                 , 'cnq': self.chuck_norris
                 , 'fortune': self.fortune
                 }
    self.cmnds = dict((CMND_PREFIX + k, v) for k, v in self.cmnds.items())

  def commands(self):
    return self.cmnds.keys()

  def get_commands(self):
    return self.cmnds

  def parse_command(self, msg):
    # Call the super class
    parse_ret = super(Quotes, self).parse_command(msg)
    if parse_ret:
      if self.last_quote and self.too_soon():
        return 'To avoid spam, quotes cannot be requested ' + \
            '> {} times in {} seconds.'.format(self.max_quotes,
                    self.time_frame), True
      else:
        if self.last_quote is None:
          self.last_quote = time.time()
        self.quote_counter += 1
        return parse_ret

    # Check for help or info
    if msg.startswith(CMND_PREFIX + 'help'):
      return self.help(' '.join(msg.split()[1:]))
    elif msg.startswith(CMND_PREFIX + 'info'):
      return self.info(' '.join(msg.split()[1:]))

  def too_soon(self):
    '''
    Return bool based on whether
    too many quotes have been requested
    within a particular time period.
    '''
    # Get the seconds for now
    now = time.time()

    # See if within threshold time frame
    if now - self.last_quote <= float(self.time_frame):
      return self.quote_counter > self.max_quotes
    else:
      self.quote_counter = 0
      self.last_quote = now
      return False

  def help(self, msg):
    # Strip prefix for aliased commands
    # and the help command removed
    msg = msg.lstrip(CMND_PREFIX + 'help')

    if msg.startswith('bash.org'):
      reply = 'Returns a random quote from bash.org'
      return reply, False

    elif msg.startswith('bq'):
      reply = 'Alias for ' + CMND_PREFIX + 'bash.org'
      return reply, False

    elif msg.startswith('chuck-norris'):
      reply = 'Returns a random Chuck Norris joke'
      return reply, False

    elif msg.startswith('cnq'):
      reply = 'Alias for ' + CMND_PREFIX + 'chuck-norris'
      return reply, False

    elif msg.startswith('fortune'):
      reply = 'Returns a random fortune from the *NIX command'
      return reply, False

  def info(self, msg):
    ni = 'Not available for that command. Use help instead.'
    return ni, False

  #--------------------------------------------#
  #                                            #
  #             COMMAND METHODS                #
  #                                            #
  #--------------------------------------------#
  def bash_org(self, msg):
    while True:
      quote = bq.BashQuote(bq.getRandomQuoteNum())
      if quote.isExists():
        reply = quote.getText().encode('utf-8')
        return reply, False

  def chuck_norris(self, msg):
    # Make a request to the page
    try:
      r = requests.get(self.CHUCK_NORRIS_API)

      # Check for a successful GET
      if not r.status_code == 200:
        reply = '[Error]: Invalid response from Chuck Norris API.' + \
                ' Please contact bot maintainer.'
        return reply, True

      # Grab the quote now
      quote = str(r.json()['value']['joke'])
      return quote, False
    except:
      log.err('[Error]: {}'.format(sys.exc_info()[0]))
      reply = '[Error]: Cannot contact Chuck Norris API.' + \
              ' Please contact bot maintainer.'
      return reply, True

  def fortune(self, msg):
    off = True if self.fortune_off.lower() == 'yes' else False
    cmnd = 'fortune {} -s -n 180'.format('-a' if off else '')
    o = sp.check_output(cmnd.split())
    return o, False
