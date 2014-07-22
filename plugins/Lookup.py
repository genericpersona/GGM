# Imports
import argparse
from operator import itemgetter
import shlex
import sqlite3 as lite
import sys

import requests

from areacodes import areacodes
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
    if args.available or args.long_name:
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

class CitiesDB(object):
  def __init__(self, cities_db_fname, cities_db_table):
    # Save basic DB information
    self.db = cities_db_fname
    self.table = cities_db_table

    # Create a database connection
    self.connected = False
    self.make_connection()

  def make_connection(self):
    if not self.connected:
      self.con = lite.connect(self.db)
      self.connected = True
      return self.connected
    return False

  def query_city(self, asciiname, limit, **kwargs):
    # Make a connection if needed
    if not self.connected:
      self.make_connection()

    # Query the database based on 
    # which arguments were passed in
    self.con.row_factory = lite.Row

    # Get a dictionary cursor 
    cur = self.con.cursor()

    # Perform a SELECT statement
    col_names = sorted([col_name for col_name in kwargs.iterkeys()])
    have_cc = not (type(kwargs['iso']) == bool)
    sql = '''
       SELECT {col_names} 
       FROM {table}
       WHERE asciiname=?
       AND population > 0
       {and_clause}
       ORDER BY population DESC
       LIMIT {limit}
    '''.format( col_names=','.join(col_names)
              , table=self.table
              , and_clause='AND iso=?' if have_cc else ''
              , limit=int(limit)
              )

    # Get the results and return a reply
    cur.execute(sql, (asciiname,) if not have_cc \
                                  else (asciiname, kwargs['iso']))
    rows = cur.fetchall()

    preface = '[About {}]:\n'.format(asciiname)
    replies = []
    for row in rows:
      vals = []
      for col_name in col_names:
        if col_name == 'population':
          vals.append('{}: {:,}'.format(col_name.title(), 
            int(row[col_name])))
        else:
          vals.append('{}: {}'.format(col_name.title() if \
              col_name != 'iso' else 'Country Code', row[col_name]))

      replies.append('\t' + ' | '.join(vals))

    return preface + '\n'.join(replies)

class Lookup(Plugin):
  def __init__(self, args):
    # Save the arguments
    for arg, val in args.iteritems():
      setattr(self, arg, val)

    # For the cities database
    self.cdb = CitiesDB(self.cities_db, self.cities_db_table)
    self.build_city_parser()

    # For accurate forex data
    self.FOREX_LATEST = 'http://openexchangerates.org/api/latest.json?app_id={}'
    self.FOREX_CS = 'http://openexchangerates.org/api/currencies.json?app_id={}'
    self.FOREX_API_KEY = '37413eb872754802ac87b1a3044fae7e' 
    self.FOREX_LATEST_URL = self.FOREX_LATEST.format(self.FOREX_API_KEY)
    self.FOREX_CS_URL = self.FOREX_CS.format(self.FOREX_API_KEY)
    self.forex_updates_secs = int(self.forex_update_secs) * 60
    self.forex_last_get = None
    self.forex_cs = []  # List of forex currencies
    self.build_forex_parser() # Create an argparse instance for forex queries

    # For GeoIP lookups
    self.GEOIP_API = 'https://freegeoip.net/json/{}'

    # Supported commands
    self.cmnds = { 'areacode': self.areacode
                 , 'ac':  self.areacode
                 , 'city': self.city
                 , 'forex': self.forex
                 , 'geoip': self.geoip 
                 }
    self.cmnds = dict((CMND_PREFIX + k, v) for k, v in self.cmnds.items())

  def commands(self):
    return self.cmnds.keys()

  def get_commands(self):
    return self.cmnds

  def parse_command(self, msg):
    # Call the super class
    parse_ret = super(Lookup, self).parse_command(msg)
    if parse_ret:
      return parse_ret

    # Check for help or info
    if msg.startswith(CMND_PREFIX + 'help'):
      return self.help(' '.join(msg.split()[1:]))
    elif msg.startswith(CMND_PREFIX + 'info'):
      return self.info(' '.join(msg.split()[1:]))

  def help(self, msg):
    # Strip prefix for aliased commands
    # and the help command removed
    msg = msg.lstrip(CMND_PREFIX + 'help')

    if msg.startswith('ac'):
      reply = 'Alias for ' + CMND_PREFIX + 'areacode command'
      return reply, False

    elif msg.startswith('areacode'):
      reply = 'Gives city information for a space delimited ' + \
          'list of area codes. Only contains US data.'
      return reply, False

    elif msg.startswith('city'):
      reply = self.city_parser.format_usage().rstrip()
      reply = reply.split()
      reply[1] = CMND_PREFIX + 'city'
      reply.append(' | Use ' + CMND_PREFIX + 'info for more details.')
      return ' '.join(reply), False

    elif msg.startswith('forex'):
      reply = self.forex_parser.format_usage().rstrip()
      reply = reply.split()
      reply[1] = CMND_PREFIX + 'forex'
      return ' '.join(reply), False

    elif msg.startswith('geoip'):
      reply = 'Returns GeoIP information for a space delimited ' + \
              'list of either hostnames or IP addresses. See ' + \
              CMND_PREFIX + 'info geoip for more extensive info.'
      return reply, False

    elif msg.startswith('timezone'):
      reply = 'Returns the timezone(s) for a space delimited ' + \
          'list of cities'
      return reply, False

  def info(self, msg):
    # Strip prefix for aliased commands
    # and the help command removed
    msg = msg.lstrip(CMND_PREFIX + 'info')

    if msg.startswith('city'):
      reply = '''
        City data is from GeoNames' allCountries
        database @ http://download.geonames.org/export/dump/.

        Without any arguments the command takes a space 
        delimited list of city names, with any whitespace 
        in the name(s) included in double quotes, and returns 
        their:

          - ISO-3166 Country code
          - Population
          - Time zone

        The only required argument is a city or a space
        delimited list of cities.

        The command also takes a number of arguments 
        corresponding to the fields in the database.

        The inclusion of most arguments tells the bot which
        pieces of information to include in its output.

        All supported arguments of this type are:

          --latitude    
          --longitude  
          --feature-class
          --feature-code
          --cc2           (for alternative country codes)
          --admin1-code
          --admin2-code
          --admin3-code
          --admin4-code
          --population
          --elevation
          --timezone

        However, some arguments require the addition of more
        information and are used to narrow the search of
        cities in the database.

        All supported arguments of this type are:

          --country-code  
      '''
      return reply, True
    elif msg.startswith('forex'):
      reply = '''
        Forex data obtained from openexchangerates.org.
        Data is obtained once per hour, so if increased
        temporal granularity is desired, it must be sought
        elsewhere.

        The forex command takes a space delmited list of 
        ISO currency codes in pairs and a rate is returned
        of the first code in the pair in terms of the second.
        E.g., {}forex USD EUR returns the rate of US dollars
        in Euros.

        To test if a currency code is supported, use the -a
        switch. 
        To get the long name for a currency code, use the -n
        switch.
      '''
      return reply, True

    elif msg.startswith('geoip'):
      reply = '''
      GeoIP data is obtained from freegeoip.net, which is
      based on the MaxMind and ipinfo.db databases primarily.
      '''

    ni = 'Not available for that command. Use help instead.'
    return ni, False

  #--------------------------------------------#
  #                                            #
  #             COMMAND METHODS                #
  #                                            #
  #--------------------------------------------#
  def areacode(self, msg):
    # Treat the non-command part of msg
    # as a list of areacodes
    if msg.startswith(CMND_PREFIX):
      acodes = msg.split()[1:]
    else:
      acodes = msg.split()

    # Change the type of acodes
    acodes = [int(c) for c in acodes if \
                                  c.isdigit()]

    # Generate a reply to each of the codes
    replies = []
    for code in acodes:
      if code in areacodes:
        cities, state = areacodes[code][:-1], areacodes[code][-1]
        reply = '[{}]: {}'.format(code, state if not cities \
            else state + ': ' + ', '.join(cities))
      else:
        reply = '[{}]: Invalid NANP area code'.format(code)

      replies.append(reply)

    return ' | '.join(replies), len(replies) > 3

  def city(self, msg):
    # Treat the non-command part of msg
    # as the portion to be parsed
    if msg.startswith(CMND_PREFIX + 'city'):
      opts = msg.split()[1:]
    else:
      opts = msg.split()

    try:
      # Parse the command
      args = self.city_parser.parse_args(opts)
      cities = shlex.split(' '.join(args.cities))
    except ArgParserError, exc:
      return exc, True

    # See if any country code was passed in

    # Default fields
    defaults = { 'iso': True
               , 'population': True
               , 'timezone': True
               }

    # Check for passed in arguments
    kwargs = {k: v for k, v in vars(args).iteritems() \
                   if v and k != 'cities'}

    # Check if a country code is specified
    if not type(kwargs['iso']) == bool:
      defaults['iso'] = kwargs['iso']
      del kwargs['iso']

    # See if we have the default or not
    if not kwargs:
      kwargs = defaults

    # Get data about the city passed in
    replies = []
    for city in cities:
      reply = self.cdb.query_city(city, self.cities_select_limit, **kwargs)
      replies.append(reply)

    # Return the information
    return '\n'.join(replies), \
                any(map(lambda x: len(x) > 80, replies)) or len(replies) > 2

  def build_city_parser(self):
    # Build a parser object
    self.city_parser = ArgParser( description='Calculate the rate of two coins'
                                , add_help=False
                                )

    # Add supported arguments
    self.city_parser.add_argument( '--latitude'
                                 , action='store_true'
                                 )
    self.city_parser.add_argument( '--longitude'
                                 , action='store_true'
                                 )
    self.city_parser.add_argument( '--feature-class'
                                 , action='store_true'
                                 )
    self.city_parser.add_argument( '--feature-code'
                                 , action='store_true'
                                 )
    self.city_parser.add_argument( '--country-code'
                                 , dest='iso'
                                 , metavar='ISO-3166_COUNTRY_CODE'
                                 )
    self.city_parser.add_argument( '--cc2'
                                 , action='store_true'
                                 )
    self.city_parser.add_argument( '--admin1-code'
                                 , action='store_true'
                                 , dest='admin1_code'
                                 )
    self.city_parser.add_argument( '--admin2-code'
                                 , action='store_true'
                                 , dest='admin2_code'
                                 )
    self.city_parser.add_argument( '--admin3-code'
                                 , action='store_true'
                                 , dest='admin3_code'
                                 )
    self.city_parser.add_argument( '--admin4-code'
                                 , action='store_true'
                                 , dest='admin4_code'
                                 )
    self.city_parser.add_argument( '-p'
                                 , '--population'
                                 , action='store_true'
                                 )
    self.city_parser.add_argument( '-e'
                                 , '--elevation'
                                 , action='store_true'
                                 )
    self.city_parser.add_argument( '-t'
                                 , '--timezone'
                                 , action='store_true'
                                 )
    self.city_parser.add_argument( 'cities'
                                 , nargs='+'
                                 , metavar='ASCII_CITY_NAME'
                                 )

  def forex(self, msg):
    # See if we need to get new data
    if self.forex_data_stale():
      if not self.forex_get_fresh_data():
        reply = 'Cannot obtain fresh forex API data. ' + \
            'Please contact bot maintainer.', True

    # Break out the options
    if msg.startswith(CMND_PREFIX + 'forex'):
      opts = msg.split()[1:]
    else:
      opts = msg.split()

    try:
      # Parse the command
      args = self.forex_parser.parse_args(opts)
      currencies = args.currencies
    except ArgParserError, exc:
      return exc, True

    if args.available:
      reply = []
      for ccode in args.available:
        reply.append('{} is{} supported'.format(ccode, 
                                          '' if ccode.upper() \
                                              in self.forex_cs \
                                                else ' NOT'))

      return ' | '.join(reply), False

    # Check for long name checking
    if args.long_name:
      reply = map( lambda x: '[{}]: {}'.format(x, self.forex_cs[x]) \
                             if x in self.forex_cs
                             else ''
                 , args.long_name
                 )
      return ' | '.join(x for x in reply if x), False

    # Get the pairs in a useable format
    pairs = [(currencies[i], currencies[i+1]) \
                         for i in range(0, len(currencies), 2)]

    # Build the reply
    replies = []
    for pair in pairs:
      reply = ''
      cfrom, cto = pair

      error = False
      if not cfrom.upper() in self.forex_cs:
        reply = '[{}]: Invalid currency code '.format(cfrom)
        error = True

      if not cto.upper() in self.forex_cs:
        reply += '[{}]: Invalid currency code'.format(cto)
        error = True

      if error:
        replies.append(reply)
        continue

      reply += '1 {cfrom} equals {rate} {cto}'.format(\
          cfrom=self.long_name(cfrom),
          cto=self.long_name(cto), 
          rate=self.get_forex_rate(cfrom.upper(), cto.upper()))

      replies.append(reply)

    return ' | '.join(replies), False

  def long_name(self, cur):
    '''
    Return long name of a currency code.

    Return cur argument if cur is not
    a supported currency code.
    '''
    
    return self.forex_cs.get(cur, cur)

  def get_forex_rate(self, cfrom, cto):
    '''
    Return rate of converting from
    cfrom to cto.
    '''
    # Check for the easy cases
    if cto == self.forex_base:
      return round(float(1 /self.forex_rates[cfrom]), 2)
    elif cfrom == self.forex_base:
      return round(float(self.forex_rates[cto]), 2)

    from_frac = float(1 / self.forex_rates[cfrom])
    to_frac = float(self.forex_rates[cto])
    return round(from_frac * to_frac, 2)

  def build_forex_parser(self):
    '''
    Return a parser for calculating forex
    rates.
    '''
    # Build a parser object
    self.forex_parser = ArgParser( description='Calculate the rate of two coins'
                                  , add_help=False
                                  )

    self.forex_parser.add_argument( '-a'
                                  , '--available'
                                  , nargs='+'
                                  , help='Find out if particular coin(s) are available'
                                  )
    self.forex_parser.add_argument( '-n'
                                  , '--long-name'
                                  , dest='long_name'
                                  , nargs='*'
                                  , help='Get long name for currency codes'
                                  )
    self.forex_parser.add_argument( 'currencies'
                                  , help='Currencies to find the rate of'
                                  , nargs='*'
                                  , action=EvenAndMinMaxPairs
                                  )

  def forex_data_stale(self):
    '''
    Return True if we need to get fresh
    data from the forex API. False 
    otherwise.
    '''
    # See if this is the first check
    if not self.forex_last_get:
      return True

    now = time.time()
    return (now - self.forex_last_get) > self.forex_update_secs

  def forex_get_fresh_data(self):
    '''
    Return True if fresh data was
    successfully obtained. False 
    otherwise.
    '''
    try:
      # Get the latest forex data
      r = requests.get(self.FOREX_LATEST_URL)

      # Save the forex data
      for k, v in r.json().iteritems():
        setattr(self, 'forex_'+k, v)

      # Get currencies if necessary
      if not self.forex_cs:
        r = requests.get(self.FOREX_CS_URL)

        self.forex_cs = r.json()

      return True
    except:
      log.err('[Error]: {}'.format(sys.exc_info()[0]))
      return False

  def geoip(self, msg):
    # Strip off the command
    ips = msg.lstrip(CMND_PREFIX + 'geoip').split()

    # Loop through IPs and get information
    replies = []
    for ip in ips:
      try:
        # Make the request
        r = requests.get(self.GEOIP_API.format(ip), verify=False)

        # Check for a status code
        if r.status_code == 403:
          reply = '[Error]: Maxed out GeoIP per hour limit'
          log.err(reply)
          return reply, True
        elif r.status_code != 200:
          reply = 'Invalid status code from GeoIP API. ' + \
                  'Please contact bot maintainer.'
          return reply, True

        # With success, grab some information for reply
        geoip_dict = r.json()
        reply = []
        for k in ('ip', 'city', 'country_code'):
          if geoip_dict[k]:
            info = '[{}]: {}'.format(k, geoip_dict[k])
            reply.append(str(info))
        replies.append(', '.join(reply))
      except:
        log.err('[Error]: {}'.format(sys.exc_info()[0]))
        reply = '[Error]: Cannot contact GeoIP API.' + \
                ' Please contact bot maintainer.'
        return reply, True

    return ' | '.join(replies), len(replies) > 3
