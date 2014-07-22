# Imports
import re

from ConfigParser import ConfigParser

class BotConfigParser:
  '''
  BotConfigParser handles the parsing of
  the configuration file for GilbertGrapesMom

  Only the main section of the config is known in
  advance and is the only section required

  All config options are added to a dictionary
  named after their section(s) where:
    
    k -> config variable
    v -> value of the variable
  '''
  FP_RE = re.compile(r'[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?')
  INT_RE = re.compile(r'^[+-]?\d+$')

  def __init__(self, conf='config/ggm.conf'):
    '''BotConfigParser.__init__(self, conf='config/ggm.conf')
    Sets up a ConfigParser object and reads in the
    config file specified in conf.

    Parses all sections in the config file.

    Returns None as all state is stored in dictionaries
    as specified in the top-level doc-string for the class.
    '''
    cp = ConfigParser()
    cp.read(conf)

    self.parse_opts(cp)

  def parse_opts(self, cp):
    '''BotConfigParser.parse_opts(self, cp)
    Uses the ConfigParser object passed in as cp to
    save all config sections in their own dictionary.

    Special treatment is made for main, whose values are
    known to be of particular types.
    '''
    # Create a list of all plugins found
    # in the parsed config file
    self.plugins = []

    for section in cp.sections():
      # Create a new dict for each section
      exec 'self.{} = dict()'.format(section)

      # Save the values in each section with
      # special treatment of the main section
      if section == 'main':
        self.main['server'] = cp.get('main', 'server')
        self.main['port'] = cp.getint('main', 'port')
        self.main['channels'] = cp.get('main', 'channels').split(',')
        self.main['nickname'] = cp.get('main', 'nickname')
        self.main['username'] = cp.get('main', 'username')
        self.main['realname'] = cp.get('main', 'realname')
        self.main['password'] = cp.get('main', 'password')
        self.main['lineRate'] = cp.getint('main', 'lineRate')
        self.main['log'] = cp.getboolean('main', 'log')
        self.main['logfile'] = cp.get('main', 'logfile')
      else:
        # Save the plugin's name
        self.plugins.append(section)

        # Store its values in a dict
        for opt, val in cp.items(section):
          if val.lower() == 'yes' or val.lower() == 'no':
            val = True if val.lower() == 'yes' else False
          elif self.INT_RE.match(val):
            val = int(val)
          elif self.FP_RE.match(val):
            val = float(val)

          exec 'self.{}["{}"] = "{}"'.format(section, opt, val)
