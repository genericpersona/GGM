# Imports 
import argparse
from csv import DictReader
import datetime
import itertools
from operator import itemgetter
from string import ascii_uppercase
import sys

import requests

from gilbertgrapesmom import build_help_and_info, CMND_PREFIX
from pluginbase import Plugin
from twisted.python import log

class ArgParserError(Exception): pass

class ArgParser(argparse.ArgumentParser):
  def error(self, message):
    raise ArgParserError(message)

class EvenAndMinMaxPairs(argparse.Action):
  min_pairs = 1
  max_pairs = 5
  def __call__(self, parser, args, values, option_string=None):
    def even(num):
      return num % 2 == 0

    # Get the number of values and pairs
    num_values = len(values)
    num_pairs = num_values / 2

    # Don't do tests if availabe argument selected
    if args.available or args.coins or args.long_name:
      pass
    elif not even(num_values):
      msg = 'Must supply an even number of currencies to get rates ' + \
            'of, as the rate is of one currency relative to another'
      parser.error(msg)
    elif num_pairs < self.min_pairs or num_pairs > self.max_pairs:
      msg = 'Can only specify between {} and {} pairs, inclusive, '.\
                      format(self.min_pairs, self.max_pairs)
      msg += 'of currency codes. Use {}help rate for full usage.'.\
                      format(CMND_PREFIX)
      parser.error(msg)

    setattr(args, self.dest, values)

class CryptoCoinCharts(Plugin):
  def __init__(self, args):
    # Save the args
    for arg, val in args.iteritems():
      setattr(self, arg, val)

    # Cache the time of the last
    # update so no more than a 
    # given number of API calls
    # occur in a particular time
    self.last_update = None

    # API URLs
    self.max_pairs = 5 # Max pairs to look up at a time with above API
    self.api_pair = 'http://www.cryptocoincharts.info/v2/api/tradingPair/'
    self.api_pairs = 'http://www.cryptocoincharts.info/v2/api/tradingPairs/'
    self.api_list_coins = 'http://www.cryptocoincharts.info/v2/api/listCoins'

    # Build a parser
    self.build_parser()

    # Initialize containers for API data
    self.coins = {}
    self.pairs = {}
    self.currencies = set()

    # Get fresh data
    self.get_fresh_data()

    # Get a list of currencies
    self.get_currencies()

    # Commands supported
    self.cmnds = { 'rate': self.parse_rate
                 }
    self.cmnds = dict((CMND_PREFIX + k, v) for k, v in self.cmnds.items())

  def commands(self):
    '''
    Return a list of the commands
    handled by the plugin.
    '''
    return self.cmnds.keys()

  def get_commands(self):
    '''
    Return a dict mapping 
    command names to their
    respective callbacks.
    '''
    return self.cmnds

  def parse_command(self, msg):
    '''
    Parses the command and returns
    the reply and a boolean indicating
    whether the reply is private or not.
    '''
    # Call the super class
    parse_ret = super(CryptoCoinCharts, self).parse_command(msg)
    if parse_ret:
      return parse_ret

    # Look for help or info message
    pre_len = len(CMND_PREFIX)
    if msg.startswith(CMND_PREFIX + 'help'):
      return self.help(' '.join(msg.split()[pre_len:]))
    elif msg.startswith(CMND_PREFIX + 'info'):
      return self.info(' '.join(msg.split()[pre_len:]))

  def help(self, cmnd):
    '''
    Return a help message
    about a particular command
    handled by the plugin.
    '''
    # Remove command prefix just in case
    cmnd = cmnd.lstrip(CMND_PREFIX + 'help')

    if cmnd.startswith('rate'):
      reply = self.parser.format_usage().rstrip()
      reply = reply.split()
      reply[1] = CMND_PREFIX + 'rate'
      return ' '.join(reply), False

  def info(self, cmnd):
    '''
    Return detailed information 
    about a command handled by the
    plugin.
    '''
    cmnd = cmnd.lstrip(CMND_PREFIX + 'info')

    if cmnd.startswith('rate'):
      reply = '''
      The {cp}rate command gets its information from
      cryptocoincharts.info. Fresh data will be obtained
      every minute, so if more temporal granularity is
      desired it must be found elsewhere.

      Cryptocoin charts' API returns a rate from the best
      market, i.e., the one with the highest volume, for
      a given pair of currencies. Currencies include 
      altcoins and fiat. The -v switch will display the
      best market in the bot's output.

      Rates are of one currency to another so they should
      be supplied to the command in pairs, where the pairs
      are specified as a space delimited list of currency
      codes. If you merely provide a single altcoin the
      bot will provide its rate in USD.
      
      You can find whether certain currencies are
      available by using the -a switch. You can see all
      available coins by using the -c switch. As a courtesy,
      the -n switch takes a list of space delimited currency
      codes and returns their long name, e.g., USD -> US
      dollar.  
      '''.format(cp=CMND_PREFIX)
      return reply, True
    else:
      ni = 'Not available for that command. Use help instead.'
      return ni, False

  def parse_rate(self, msg):
    '''
    Parse the msg for the calculation
    of a rate.
    '''
    # Grab the command line options
    if msg.startswith(CMND_PREFIX + 'rate'):
      opts = msg.split()[1:]
    else:
      opts = msg.split()

    # Get fresh data if needed
    if self.stale():
      if not self.get_fresh_data():
        log.err('Failed to obtain fresh API average data')
        return '[Error]: Cannot access CryptoCoinCharts API. ' + \
                                      'Contact bot maintainer.', True

    # Parse the command
    try:
      # Allow for a default currency
      if len(opts) == 1 or \
          (len(opts) == 2 and \
          '-v' in opts or '--verbose' in opts):
        opts.append(self.default_currency)

      # Parse the command
      args = self.parser.parse_args(opts)
      currencies = args.currencies
    except ArgParserError, exc:
      return exc, True

    # Check if we need to provide some help
    if args.coins:
      # Return the list of coins privately
      replies = {char: sorted([cur.upper() for cur in \
                               self.coins.keys() \
                               if cur.upper().startswith(char)]) \
                              for char in ascii_uppercase}
      reply = ['Altcoins Available:']
      for char in ascii_uppercase:
        reply.append(' | '.join(replies[char]))
      return '\n'.join(reply), True

    # Check if we're checking for coin support
    if args.available:
      reply = []
      for coin in args.available:
        reply.append('{} is{} supported'.format(coin, 
                                          '' if self.supported(coin) \
                                             else ' NOT'))

      return ' | '.join(reply), False

    # Check for long name checking
    if args.long_name:
      reply = map( lambda x: '[{}]: '.format(x) + self.coins[x]['name'] \
                             if x in self.coins 
                             else self.name_currencies[x] \
                                  if x in self.currencies
                                  else ''
                 , args.long_name
                 )
      return ' | '.join(x for x in reply if x), False

    # Get the pairs in a useable format
    pairs = [(currencies[i], currencies[i+1]) \
                for i in range(0, len(currencies), 2)]
    payload = ','.join(map(lambda x: '{}_{}'.format(x[0], x[1]), pairs))

    # Figure out if you need to use pair or pairs
    if len(pairs) > 1:
      post = True
    else:
      post = False

    # Make sure all the pairs are supported
    if not all(map(self.supported, currencies)):
      reply = '[Error]: Invalid coin specified.'
      reply += ' | Use the -c/--coins option to see all supported' 
      return reply, False
          
    # Set up data for a request
    try:
      # Make the proper request
      if post:
        r = requests.post(self.api_pairs, data=payload)
      else:
        r = requests.get('{}{}'.format(self.api_pair, payload))

      # Check for valid status code
      if r.status_code != 200:
        log.err('[Error]: Status code {} for pairs API'.format(r.status_code))
        return '[Error]: Cannot contact pairs API. Please ' + \
                  'contact bot maintainer.', True

      # Get all returned pair(s)
      ret_pairs = r.json if type(r.json) == list else [r.json()]

      # Build the reply
      replies = []
      for i, pair in enumerate(ret_pairs):
        if pair['id'] is None:
          reply = '[Error]: No response for {}. Try {}'.\
              format( ' '.join(pairs[i])
                    , '{} {}'.format(pairs[i][-1].upper(), pairs[i][0].upper())
                    )
        else:
          reply = '{pair}{price}{convert} {v}'.\
              format( pair='[{}]: '.format(str(pair['id'].upper()))
                    , price=round(float(pair['price']), 8)
                    , convert=' | {} {} for 1 {}'.\
                        format( round(1.0 / float(pair['price']), 8)
                              , pairs[i][0].upper()
                              , pairs[i][1].upper()
                              ) if not (pairs[i][0] in self.currencies or \
                                        pairs[i][1] in self.currencies) \
                                else ''
                    , v=' | [Best Market]: {}'.format(str(pair['best_market'])) \
                            if args.verbose else ''
                    )
        replies.append(reply)

      return ' | '.join(replies), False if not post else True
    except:
      log.err('[Error]: {}'.format(sys.exc_info()[0]))
      return '[Error]: Cannot contact pairs API. Please ' + \
                  'contact bot maintainer.', True

  def supported(self, code, include_currencies=True):
    '''
    Tests if the passed in code is supported in the
    CryptoCoin API.

    Can toggle whether currencies are included in the
    check.

    Return True if supported and False otherwise.
    '''
    if include_currencies:
      return code.upper() in self.names or code.upper() in self.currencies
    else:
      return code.upper() in self.names

  def build_parser(self):
    '''
    Builds a parser for the program.

    Return None.
    '''
    # Build an argument parser
    self.parser = ArgParser( description='Calculate the rate of two coins'
                           , add_help=False
                           )
    
    self.parser.add_argument( '-a'
                            , '--available'
                            , nargs='+'
                            , help='Find out if particular coin(s) are available'
                            )
    self.parser.add_argument( '-c'
                            , '--coins'
                            , action='store_true'
                            , help='List all coins available'
                            )
    self.parser.add_argument( '-n'
                            , '--long-name'
                            , dest='long_name'
                            , nargs='*'
                            , help='Get long name for currency codes'
                            )
    self.parser.add_argument( '-v'
                            , '--verbose'
                            , action='store_true'
                            , help='Get additional information on rates'
                            )
    self.parser.add_argument( 'currencies'
                            , help='Currencies to find the rate of'
                            , nargs='*'
                            , action=EvenAndMinMaxPairs
                            )

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
    Grab fresh data from the API and saves
    it in class attributes.

    Returns True if grab was successful
    and False if an error occurred.
    '''
    try:
      # Now, grab the pairs data
      r = requests.get(self.api_list_coins)
      if r.status_code != 200:
        log.err('[Error]: Status code {} for listing coins'.\
                    format(r.status_code))
        return False
      else:
        self.coins = {}
        for coind in r.json():
          # Don't take any coins with zero volume
          if not float(coind['volume_btc']):
            continue
          # Otherwise, save the information
          self.coins[coind['id']] = {k: v for k,v in coind.iteritems() \
                                                  if k != 'id'}

        # Also save a list of coin names
        self.names = {str(x.upper()) for x in self.coins.iterkeys()}

        # Finally, get some currencies
        self.get_currencies()

        return True
    # Any error that occurs connecting to the API    
    except:
      log.err('[Error]: {}'.format(sys.exc_info()[0]))
      return False

  def get_currencies(self):
    '''
    Obtain a list of currencies
    used for calculating rates of
    various CryptoCoins. Store this
    list
    '''
    if not self.currencies:
      with open(self.currencies_csv) as csvf:
        # Create a reader object and save the dicts
        reader = DictReader(csvf)

        # Save the dictionaries
        reader = [cd for cd in reader]

        # Save the currencies as a set
        self.currencies = sorted(set(map(itemgetter('AlphabeticCode'),
                                                            reader)))
        self.currencies = [c for c in self.currencies if c.strip()]

        # Also, save mapping of currencies
        # to a longer name for them
        self.name_currencies = {d['AlphabeticCode']: d['Currency'] \
                                for d in reader \
                                  if d['AlphabeticCode'] in \
                                      self.currencies}
    
    return self.currencies


