# Imports
import os
import time

from twisted.internet import protocol
from twisted.internet import ssl
from twisted.python import log
from twisted.words.protocols import irc

# Constants
CMND_PREFIX = '?'  # For the built-in commands for the bot

def build_help_and_info(cmnds, prefix=CMND_PREFIX):
  '''
  Takes a list of commands and
  returns a list of those commands
  plus all variants of help and info
  related to them.
  '''
  addtl_cmnds = [cmnd for cmnd in cmnds]
  for cmnd in cmnds:
    for pre_cmnd in ['help', 'info']:
      addtl_cmnds.append('{}{} {}'.format(CMND_PREFIX, pre_cmnd, cmnd))
  return addtl_cmnds

class GilbertGrapesMom(irc.IRCClient):
    '''
    GilbertGrapesMom class implements the
    event-driven functionality of the bot.
    '''
    #-------------------------------------#
    #                                     #
    #         CUSTOM METHODS              #
    #                                     #
    #-------------------------------------#
    def __init__(self):
      '''
      Constructor for GilbertGrapesMom
      '''
      # TO-DO: Check for duplicate commands
      #        from instantiated plugins

      # Dictionary of supported built-in
      # commands where
      #   key: command 
      #   val: method handling the command
      self.cmnds = { 'about': self.about
                   , 'help': self.help
                   , 'info': self.info
                   , 'commands': self.commands
                   }
      self.cmnds = dict((CMND_PREFIX+k, v) for k, v in self.cmnds.items())

    def sasl(self):
      '''
      SASL authentication code from:
        
        https://github.com/habnabit/txsocksx/blob/master/examples/tor-irc.py

      Currently only uses SASL PLAIN
      '''
      self.sendLine('CAP REQ :sasl')

    def auth(self):
      '''
      Method for authenticating the bot.

      Returns None
      '''
      self.sasl()

    #-------------------------------------#
    #                                     #
    #        BUILT-IN COMMANDS            #
    #                                     #
    #-------------------------------------#
    def about(self, msg):
      '''
      Method for returning info about this bot. 
      '''
      return 'Gilbert Grape\'s Mom developed by ' + \
             'genericpersona. ' + \
             'Use {0}help and {0}info '.format(CMND_PREFIX) + \
             'for additional information.', False

    def help(self, msg):
      '''
      Method for returning help about the about
      and commands command.
      '''
      return \
          '{}help [command] '.format(CMND_PREFIX)  + \
          'returns the command\'s syntax. ' + \
          'Use ' + CMND_PREFIX + 'commands to see all ' + \
          'available.', False

    def info(self, msg):
      '''
      Method for returning detailed info about
      a particular command.
      '''
      return \
          '{}info [command] (when implemented) returns '.format(CMND_PREFIX) + \
          'detailed info about a command', False

    def commands(self, msg):
      '''
      Method for returning a list of all the
      commands supported by the bot.
      '''
      commands = [cmnd for cmnd in self.cmnds.keys()]
      map( lambda x: commands.extend(x.commands())
         , [cb for cb in self.fact.callbacks \
             if not cb.__class__.__name__ == 'GilbertGrapesMom']
         )
      return ','.join(sorted(commands)), False

    def has_command(self, msg):
      '''
      Return True if one of the built-in 
      commands, i.e., about, help, info,
      commands, is in the passed in msg.
      '''
      for cmnd in self.cmnds:
        if msg.startswith(cmnd):
          return True
      return False

    def parse_command(self, msg):
      '''
      Return a 2-tuple (reply, priv) where:

        reply: str response to the command
        priv: boolean indicated wheter
              the reply should be sent 
              in a PM or to a channel
      '''
      return self.cmnds[msg.split()[0]](msg)

    #-------------------------------------#
    #                                     #
    #         EVENT CALLBACKS             #
    #                                     #
    #-------------------------------------#
    def connectionMade(self):
      '''
      Called when a connection is made.
      '''
      if self.fact.log:
        log.msg('Connection made')
      irc.IRCClient.connectionMade(self)

    def irc_CAP(self, prefix, params):
      if params[1] != 'ACK' or params[2].split() != ['sasl']:
        if self.fact.log:
          log.err('SASL not available')
        self.quit('')
      sasl = ('{0}\0{0}\0{1}'.format(
                  self.nickname, 
                  self.fact.password)).encode('base64').strip()
      self.sendLine('AUTHENTICATE PLAIN')
      self.sendLine('AUTHENTICATE ' + sasl)

    def irc_903(self, prefix, params):
      self.sendLine('CAP END')

    def irc_904(self, prefix, params):
      if self.fact.log:
        log.err('SASL AUTH Failed')
      self.quit('')
    irc_905 = irc_904

    def signedOn(self):
      ''' GilbertGrapesMom.signedOn(self)
      Called after initial sign on.
      '''
      # Authenticate the bot
      self.auth()
      if self.fact.log:
        log.msg('Authenticated the bot')

      # Join the specified channels
      for chan in self.fact.channels:
        chan = chan if chan.startswith('#') else '#' + chan
        self.join(chan)

    def joined(self, channel):
      '''
      Called when a channel is joined.
      '''
      if self.fact.log:
        log.msg('Joined {}'.format(channel))

    def kickedFrom(self, channel, kicker, message):
      '''
      Called when kicked from a channel.
      '''
      if self.fact.log:
        log.msg('Kicked from {} by {} [{}]'.format(
                                      channel, kicker, message))

    def privmsg(self, user, channel, msg):
      '''
      Called when the bot receives a message.
      '''
      # Grab basic information
      sendTo = None
      sender = user.split('!', 1)[0]
      reply = ''

      # Check for a private message
      if channel == self.nickname:
        sendTo = sender
      # Otherwise, send to the channel
      else:
        sendTo = channel

      # Log all commands received
      log.msg('[{}@{}]: {}'.format(user, channel, msg))

      # Check each plugin callback to see
      # if the current message has a command
      for cb in self.fact.callbacks:
        if cb.has_command(msg):
          reply, priv = cb.parse_command(msg)
          self.msg(sender if priv else sendTo, str(reply))
          break

class GilbertGrapesMomFactory(protocol.ClientFactory):
  '''
  GilbertGrapesMomFactory stores persistent 
  data for instances of GilbertGrapesMom.
  '''
  def __init__(self, opts):
    # First, save the main config options as vars 
    for k, v in opts.main.items():
      if type(v) == str:
        exec 'self.{} = "{}"'.format(k, v)
      else:
        exec 'self.{} = {}'.format(k, v)

    # Start logging if appropriate
    if self.log:
      log.startLogging(open(self.logfile, 'w'), setStdout=False)

    # Next, save the list of plugins 
    # and their associated dict args,
    # modules and callbacks
    self.imports = set()
    self.args = {}
    for plugin in opts.plugins:
      exec 'self.{p} = opts.{p}'.format(p=plugin)
      self.imports.add('from plugins.{} import {}'.format(
                                      eval('opts.{}["module"]'.format(plugin)),
                                      eval('opts.{}["callback"]'.format(plugin))))

      # Use the rest of the options as the dict
      # argument to the callback's constructor
      cb_name = eval('opts.{}'.format(plugin))['callback']
      args_dict = dict((k, v) for k,v in \
                        eval('opts.{}'.format(plugin)).items() \
                          if k not in ('module', 'callback'))
      if not cb_name in self.args:
        self.args[cb_name] = args_dict
      else:
        self.args[cb_name].update(args_dict)

    # Import the plugin modules
    # and instantiate objects for
    # each of the callbacks
    self.callbacks = []
    for import_stmt in self.imports:
      exec import_stmt

      for cb in import_stmt.split()[-1].split(','):
        self.callbacks.append(eval('{}({})'.format(cb, self.args[cb])))

  def buildProtocol(self, addr):
    '''
    Saves the factory for later reference.
    '''
    # Instantiate a GGM object
    ggm = GilbertGrapesMom()

    # Save a refrence to the factory
    ggm.fact = self

    # Save basic IRC Client info
    for info in ['nickname', 'username', 'realname', 'lineRate']:
      exec 'ggm.{0} = self.{0}'.format(info)

    # Save the GGM object as a callback
    self.callbacks.append(ggm)

    return ggm

  def clientConnectionLost(self, connector, reason):
    '''
    Called when a previously active connection
    is lost.

    Keeps reconnecting until a connection is made.
    '''
    if self.log:
      log.err('Connection lost: re-trying')
    connector.connect()

  def clientConnectionFailure(self, connector, reason):
    '''
    Called when the connection cannot be made.

    The reactor loop stops and the program exits.
    '''
    if self.log:
      log.err('Connection Failed: {!r}'.format(reason))
    reactor.stop()
