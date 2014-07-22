# Imports
from gilbertgrapesmom import build_help_and_info, CMND_PREFIX

class Plugin(object):
  '''
  Base class for all of GGM's plugins.

  Defines stubs for required methods
  that any plugin must define for 
  command parsing to function.
  '''
  def __init__(self):
    pass

  def commands(self):
    '''
    Return a list of the commands
    handled by the plugin.
    '''
    raise NotImplementedError

  def get_commands(self):
    '''
    Return a dictionary where

      k -> non-prefixed command
           name as a string
      v -> function responsible
           for handling the command
    '''
    raise NotImplementedError

  def has_command(self, msg):
    '''
    Return True if msg contains a 
    command handled by this plugin.

    Return False otherwise
    '''
    # Check for a command
    non_prefixed = map( lambda s: s[len(CMND_PREFIX):]
                      , self.commands()
                      )
    for cmnd in list(self.commands()) + build_help_and_info(non_prefixed):
      if msg.startswith(cmnd):
        return True

    # Otherwise, False
    return False

  def parse_command(self, msg):
    '''
    Parse a line of text for a command
    and returns a 2-tuple consisting
    of:

      string -> response to command
      bool -> whether response is
              to be sent in a PM
    '''
    # Check for standard commands
    # But first sort by longest
    # command name desc order
    cmnds = sorted( self.get_commands().iteritems()
                  , key=lambda x: len(x[0])
                  , reverse=True
                  )
    for cmnd, cmnd_cb in cmnds:
      if msg.startswith(cmnd):
        return cmnd_cb(msg)

  def info(self, cmd):
    '''
    Return detailed information 
    about a command handled by the
    plugin.
    '''
    raise NotImplementedError

  def help(self, cmd):
    '''
    Return a help message
    about a particular command
    handled by the plugin.
    '''
    raise NotImplementedError
