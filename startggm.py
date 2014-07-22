#!/usr/bin/env python2
import grp
import os
import pwd

from twisted.internet import reactor
from twisted.internet import ssl

from config.botconfigparser import BotConfigParser
from gilbertgrapesmom import GilbertGrapesMom, GilbertGrapesMomFactory

def drop_privs(uid_name='ggm', gid_name='ggm'):
  if os.getuid() != 0:
    # We're not root, so ...
    return

  # Get the uid/gid from the name
  running_uid = pwd.getpwnam(uid_name).pw_uid
  running_gid = grp.getgrnam(gid_name).gr_gid

  # Remove group privileges
  os.setgroups([])

  # Try setting the new uid/gid
  os.setgid(running_gid)
  os.setuid(running_uid)

  # Ensure a very conservative mask
  old_umask = os.umask(077)



if __name__ == '__main__':
  # Drop privileges
  drop_privs()

  # Parse the config file
  bcp = BotConfigParser()

  # Create GGM factory 
  f = GilbertGrapesMomFactory(bcp)

  # Connect factory to this host and port
  reactor.connectSSL(f.server, f.port, f, ssl.ClientContextFactory())

  # Enter the reactor loop
  reactor.run()
