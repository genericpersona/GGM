# Imports
import argparse
import datetime
import functools
import itertools as it
import json
import sys

import requests

from gilbertgrapesmom import build_help_and_info, CMND_PREFIX
from pluginbase import Plugin
from twisted.python import log

class ArgParserError(Exception): pass

class ArgParser(argparse.ArgumentParser):
  def error(self, message):
    usage = self.format_usage().rstrip()
    raise ArgParserError(usage + ' ' + message)

class BitcoinAverage(Plugin):
  def __init__(self, args):

    '''
    Constructor for the BitcoinAverage
    class which uses the API from
    bitcoinaverage.com to calculate 
    various averages for the price of
    BTC denominated in fiat currency.
    '''
    # Save the args
    for arg, val in args.iteritems():
      setattr(self, arg, val)

    # Cache the time of the last
    # update so no more than a 
    # given number of API calls
    # occur in a particular time
    self.last_update = None

    # API link for average data
    self.api = 'https://api.bitcoinaverage.com/exchanges/all'

    # Ignored exchanges
    self.api_ignored = 'https://api.bitcoinaverage.com/ignored'

    # Types of averages
    self.types = ('weighted', 'mean')

    # Rates for average
    self.rates = ('ask', 'bid', 'last')

    # All supported currencies (filled in later)
    self.currencies = set()

    # All supported exchanges (filled in later)
    self.exchanges = {}

    # Get fresh data
    self.get_fresh_data()

    # Build a dictionary of commands
    self.cmnds = { 'avg': self.parse_avg
                 , 'avg-exchanges': self.avg_exchanges
                 , 'avg-ignored': self.avg_ignored
                 , 'avg-rates': self.avg_rates
                 , 'avg-types': self.avg_types
                 }
    self.cmnds = dict((CMND_PREFIX + k, v) for k, v in self.cmnds.items())

  def commands(self):
    '''
    Returns the supported commands
    '''
    return self.cmnds.keys()

  def get_commands(self):
    '''
    Return the command dicts
    '''
    return self.cmnds

  def parse_command(self, msg):
    '''
    Parses the command and returns
    the reply and a boolean indicating
    whether the reply is private or not.
    '''
    # Call the super class
    has_reply = super(BitcoinAverage, self).parse_command(msg)
    if has_reply:
      return has_reply

    # Look for help or info message
    pre_len = len(CMND_PREFIX)
    if msg.startswith(CMND_PREFIX + 'help'):
      return self.help(' '.join(msg.split()[pre_len:]))
    elif msg.startswith(CMND_PREFIX + 'info'):
      return self.info(' '.join(msg.split()[pre_len:]))
    
  def help(self, msg):
    '''
    Returns help about a a particular 
    command.
    '''
    # Strip prefix for aliased commands
    # and the help command removed
    msg = msg.lstrip(CMND_PREFIX + 'help')

    # Help for currencies
    if msg.startswith('avg-currencies'):
      reply = '[Supported currencies]: {}'.format(' | '.join(self.currencies))
      return reply, False

    # Help for exchanges
    elif msg.startswith('avg-exchanges'):
      reply = 'Exchanges are specific to a currency. Use the ' + \
              '{}avg-exchanges command to view all'.format(CMND_PREFIX) + \
              ' available (defaults to USD). Can provide a space delmited' + \
              ' list of currency codes\nUse ' + CMND_PREFIX + 'help' + \
              ' {cp}info {cp}avg-exchanges'.format(cp=CMND_PREFIX) + \
              ' displays more detailed info on how to control the' + \
              ' exchanges used in the avg.'
      return reply, True
          
    # Help for ignored exchanges
    elif msg.startswith('avg-ignored'):
      reply = 'Gives a list of ignored exchanges. The ' + \
              CMND_PREFIX + 'info {}avg-ignored'.format(CMND_PREFIX) + \
              'command provides reasons why they are ignored.'
      return reply, False

    # Help for offered rates
    elif msg.startswith('avg-rates'):
      reply = '[Supported rates]: {}'.format(' | '.join(self.rates))
      return reply, False

    # Help for average types
    elif msg.startswith('avg-types'):
      reply = '[Supported average types]: {}'.format(' | '.join(self.types))
      return reply, False

    # Help for avg
    elif msg.startswith('avg'):
      usage = self.parser.format_usage().rstrip().split()
      usage[0] = CMND_PREFIX + 'avg'
      usage[1] = '[exchanges]'
      extra = '(Defaults: exchanges = all for the currency ' + \
                '| currency = USD | rate = last | type = weighted)' + \
                ' (Related commands: {})'.format(\
                         ', '.join([c for c in self.cmnds.keys() \
                                      if c != CMND_PREFIX + 'avg']
                                              ))
      return '{} {}'.format(' '.join(usage), extra), False

  def info(self, msg):
    '''
    Returns detailed information about
    a particular command.

    The CMND_PREFIX + info part of the msg
    is removed before processing.
    '''
    # Remove info from front
    msg = msg.lstrip(CMND_PREFIX + 'info')
    if msg.startswith('avg-ignored'):
      reply = map( lambda x: '{} ignored because {}'.format(x[0], x[-1])
                 , self.ignored.items()
                 )
      reply = '\n'.join(reply)
    elif msg.startswith('avg-rates'):
      reply = '''The bid price is the highest price a buyer is willing to pay.
      The ask price is the price a buyer will accept.
      The last is the last price a sale was made for.

      Full order book data is not available, so be mindful of the
      resultant inaccuracies introduced by using any of these rates
      for pricing large quanities of BTC.
      '''
    # Info for avg
    elif msg.startswith('avg'):
      reply = '''Averages are calculated using data provided
      by https://bitcoinaverage.com. Data used to calculate
      averages is pulled no more than once per minute, so
      more up-to-date data must be obtained from an alternate
      source.

      By default, volume-weighted averages are provided, but a
      plain mean-based average can be obtained using the -t/--type
      argument.

      An average can be calculated for a number of different 
      currencies and a number of different exchanges.  Use the
      currencies and exchanges command to view each, respectively.
      By default, USD as the currency and all available
      exchanges are used.

      For calculating the average, either weighted or mean, exchanges
      can be specified in one of two ways:
        1) As a whitespace delimited list of exchanges, meaning use
           ONLY those exchanges in the calculation.
        2) As  whitespace delimited list of exchanges each prefaced
           by a - symbol, meaning use all exchanges EXCEPT for the
           ones specified.
      For example, to get an average of just btce and bitstamp, use
        {pre}avg btce bitstamp
      Or, to get an average not including btce and bitstamp, use
        {pre}avg -btce -bitstamp

      Some exchanges are potentially ignored.  To see which exchanges
      fall under that category use ignored command; to see the reasons
      why those exchanges are ignored use the info ignored command.
      '''.format(pre=CMND_PREFIX)
    else:
      ni = 'Not available for that command. Use help instead.'
      return ni, False

    # Return the reply privately
    return reply, True


  def stale(self):
    '''
    Return True if API data is stale.
    '''
    # See if a pull from the API
    # has never been made
    if not self.last_update:
      return True

    return (datetime.datetime.utcnow() - self.last_update).seconds > 60

  def get_fresh_data(self):
    '''
    Pulls fresh API data and saves it as a 
    dictionary. 

    Returns True if pull was successful and
    False otherwise.
    '''
    try:
      # Grab average data
      r = requests.get(self.api)
      if r.status_code != 200:
        log.err('[Error]: Status code {} during API pull'.format(
                                                      r.status_code))
        return False
      else:
        self.api_data = r.json()
        self.last_update = datetime.datetime.utcnow() 

      # Grab ignored exchanges
      r = requests.get(self.api_ignored)
      if r.status_code != 200:
        log.err('[Error]: Status code {} during API pull'.format(
                                                      r.status_code))
        return False
      else:
        self.ignored = r.json()

      # Get supported currencies
      self.get_currencies()

      # Get supported exchanges
      self.get_exchanges()

      # Build a parser
      self.build_parser()

      return True
    # Connection problems
    except:
      log.err('[Error]: {}'.format(sys.exc_info()[0]))
      return False

  def get_currencies(self):
    '''
    Save all supported currencies
    in self.currencies
    '''
    if not self.currencies:
      self.currencies = set([str(cur) for cur in \
                                 self.api_data.keys() if cur != 'timestamp'])

  def get_exchanges(self):
    '''
    Save all exchanges in the dict
    self.exchanges where:

      k -> currency code
      v -> list of exchanges
    '''
    if not self.exchanges:
      for currency in self.currencies:
        self.exchanges[currency] = self.api_data[currency].keys()

  #--------------------------------------------#
  #                                            #
  #             COMMAND METHODS                #
  #                                            #
  #--------------------------------------------#
  def avg_exchanges(self, msg):
    '''
    Handles the CMND_PREFIX + avg-exchanges
    command.

    Returns available exchanges for the given
    currencies.
    '''
    # Remove prefix and command
    clist = msg.lstrip(CMND_PREFIX + 'avg-exchanges').split()

    # Create a currencies list
    clist = clist or ['USD']

    # Build a reply to each currency
    reply = []
    error = False   # Whether an invalid currency was entered
    for currency in clist:
      # Case-insensitive
      currency = currency.upper()
      if currency in self.exchanges:
        exchgs = sorted(map(str, self.exchanges[currency]))
        reply.append('[{}]: {}'.format(currency, ' '.join(exchgs)))
      else:
        reply.append('[{}]: Invalid. '.format(currency))
        error = True

    if error:
      reply.append('Use avg-currencies or avg -a command ' + \
                   'to check for supported currency codes')

    return '\n'.join(reply), len(reply) > 160

  def avg_ignored(self, msg):
    '''
    Handles the CMND_PREFIX + avg_ignored
    command.

    Which ignores its msg component
    and returns the current ignored 
    exchanges.

    Returns the typical 2-tuple of:
      (reply str, bool whether priv msg or not)
    '''
    reply = '[Ignored exchanges]: '
    log.msg('Ignored: {}'.format(self.ignored))
    replies = map( lambda x: '{} b/c {}'.format(x[0], x[1])
                 , self.ignored.iteritems() 
                 )
    reply = [reply] + replies
    return ' | '.join(reply if not reply.endswith(']: ') \
                                        else 'None'), False

  def avg_rates(self, msg):
    '''
    Handles the CMND_PREFIX + avg_rates
    command.
    '''
    return self.help(msg)

  def avg_types(self, msg):
    '''
    Handles the CMND_PREFIX + avg_types
    command.
    '''
    return self.help(msg)

  def parse_avg(self, msg):
    '''
    Parses the options for calculating
    an average for the Bitcoin price.
    '''
    # Grab the command line options
    if msg.startswith(CMND_PREFIX + 'avg'):
      opts = msg.split()[1:]
    else:
      opts = msg.split()

    # Get fresh data
    if self.stale():
      if not self.get_fresh_data():
        log.err('Failed to obtain fresh API average data')
        return '[Error]: Cannot access bitcoin average API. ' + \
                                      'Contact bot maintainer.', True

    # Parse the command
    try:
      args, opts = self.parser.parse_known_args(opts)
      log.msg('args: {}'.format(repr(args)))
      log.msg('opts: {}'.format(repr(opts)))
    except ArgParserError, exc:
      return exc, True

    # See if want help on available currencies
    if args.available:
      reply = self.are_available(args.available)
      return reply if reply else \
          '[Error]: Need a currency code to check.', False

    # Check for correct currency code
    args.currency = args.currency.upper()
    if args.currency not in self.currencies:
      return '[Error]: argument -c /--currency: invalid choice: \'{}\''.\
                                        format(args.currency), True

    # Pull out all available exchanges exchanges
    all_exchanges = self.exchanges[args.currency]

    # Lower case the exchanges
    opts = map(lambda s: s.lower(), opts)

    # See if we have all or a blank list
    if not opts:
      opts = all_exchanges

    # Check for only valid exchanges
    for exchg in opts:
      if (exchg if exchg[0].isalpha() else exchg[1:]) not in all_exchanges:
        return '[Error]: {} is not a valid exchange'.format(exchg), True

    # Decide which ones to keep and 
    # which ones are not desired
    minus_exchanges = set(exchg.lstrip('-') for exchg in opts \
                                              if exchg.startswith('-'))
    plus_exchanges = set(exchg.lstrip('+') for exchg \
                              in minus_exchanges if \
                                exchg.lstrip('-') not in minus_exchanges)

    # See if only have minus exchanges
    if not plus_exchanges:
      exchanges = [exchg for exchg in all_exchanges \
                                      if not exchg in minus_exchanges]

    # See if only have plus or a mixture
    else:
      exchanges = [exchg for exchg in plus_exchanges]
      
    # Finally, calculate the average
    return self.avg(exchanges, args.currency, args.rate, args.type), False

  def build_parser(self):
    '''
    Builds a parser for the program

    Return None.
    '''
    # Build an argument parser
    self.parser = ArgParser( description='Calculate the Bitcoin average'
                           , add_help=False
                           )
    
    self.parser.add_argument( '-a '
                            , '--available'
                            )
    self.parser.add_argument( '-c '
                            , '--currency'
                            , default='USD'
                            )
    self.parser.add_argument( '-r '
                            , '--rate'
                            , default='last'
                            , choices=('bid', 'last', 'ask')
                            )
    self.parser.add_argument( '-t '
                            , '--type'
                            , default='weighted'
                            , choices=('weighted', 'mean')
                            )

  def are_available(self, cs):
    '''
    Returns a string response
    to the passed in currencies.

    Params:
      @cs: list of currency codes
    '''
    if type(cs) != list:
      cs = [c.strip() for c in cs.split() if c.strip()]
    reply = []
    for c in cs:
      c = c.upper()
      if c in self.currencies:
        reply.append('{} is supported'.format(c))
      else:
        reply.append('{} is not supported'.format(c))
    return ' | '.join(reply)

  def avg(self, markets, currency='USD', rate='last', atype='weighted'):
    '''
    Calculate the average BTC price.

    Params:
      @markets: list of markets to calc the avg for
      @currency: currency to denominate avg in
      @rate: ask, bid, last
      @atype: type of avg, either weighted or mean

    Returns a float of the average or -1 in the case
    of an error.
    '''
    # Start with a dict for each market where:
    #   key -> market name
    #   val -> [volume, weight, price]
    avg_data = dict((m, [0, 0, 0]) for m in markets)
    VOL = 0; WEIGHT = 1; PRICE = 2

    # First need the total volume
    total_vol = sum( map( lambda mkt: self.api_data[currency][mkt]['volume_btc']
                        , markets
                        )
                   )

    # Now obtain the data for each market
    for market in markets:
      # The volume
      avg_data[market][VOL] = self.api_data[currency][market]['volume_btc']

      # The weight as a percentage
      avg_data[market][WEIGHT] = avg_data[market][VOL] / total_vol
  
      # The price
      avg_data[market][PRICE] = self.api_data[currency][market]['rates'][rate]

    # Weighted average
    if atype == 'weighted':
      return self.weighted_avg( map( lambda x: (x[WEIGHT], x[PRICE])
                                   , avg_data.values()
                                   )
                              )
    # Mean (weighted average with equal weights) 
    else:
      total_prices = sum(map(lambda x: x[PRICE], avg_data.values()))
      return round(total_prices / float(len(markets)), 2)

  def weighted_avg(self, values):
    '''
    Return the weighted average
    of the passed in values.

    Params:
      @values: list of 2-tuples where
                (weight, value)
               
               weight must be a float
               expressing the percentage
               that its corresponding value
               should have in the final avg
    '''
    WEIGHT = 0; VALUE = 1
    return round(sum(map(lambda x: x[WEIGHT] * x[VALUE], values)), 2)
