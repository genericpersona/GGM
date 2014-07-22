#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Imports
from datetime import datetime, timedelta
import os
import subprocess as sp
import sqlite3
import sys
import time
import zipfile

# 3-rd party libraries
import requests
import unicodecsv as csv

# Constants
CITIES_DB_URL = 'http://download.geonames.org/export/dump/allCountries.zip'

CITIES_DB_SQL = [
'''DROP TABLE IF EXISTS cities''',

'''CREATE TABLE cities (
    gid INTEGER NOT NULL UNIQUE,
    name TEXT,
    asciiname TEXT,
    alternate_names TEXT,
    latitude REAL,
    longitude REAL,
    feature_class TEXT,
    feature_code TEXT,
    iso TEXT,
    cc2 TEXT,
    admin1_code TEXT,
    admin2_code TEXT,
    admin3_code TEXT,
    admin4_code TEXT,
    population INTEGER,
    elevation INTEGER,
    dem INTEGER,
    timezone TEXT,
    updated TEXT
)
''']
CITIES_TXT = 'allCountries.txt'
NUM_CITIES = sp.check_output('wc -l {}'.format(CITIES_TXT).split())
NUM_CITIES = float(NUM_CITIES.split()[0].strip())

def download_file(url):
  local_filename = url.split('/')[-1]
  r = requests.get(url, stream=True)
  with open(local_filename, 'wb') as f:
    for chunk in r.iter_content(chunk_size=1024):
      if chunk:   # filter out keep-alive new chunks
        f.write(chunk)
        f.flush()
  return local_filename

#------------------------------------------------------------#
#                                                            #
#                            MAIN                            #  
#                                                            #
#------------------------------------------------------------#
# See if we need to download the file
if not os.path.exists(CITIES_TXT):
  if not os.path.exists(CITIES_TXT.replace('.txt', '.zip')):
    fname = download_file(CITIES_DB_URL)
  else:
    fname = CITIES_TXT.replace('.txt', '.zip')

  # Unzip the file
  with zipfile.ZipFile(fname, 'r') as zf:
    zf.extractall()
else:
  print '[+] Cities DB already exists.'

# Otherwise, add to the database
try:
  con = sqlite3.connect('cities.db')
  with con:
    # Get a cursor
    cur = con.cursor()

    # Delete all entries from table
    for stmnt in CITIES_DB_SQL:
      cur.execute(stmnt)

    csv.field_size_limit(sys.maxsize)
    reader = csv.reader(open('allCountries.txt'), delimiter='\t', quotechar='"')
    line_cnt = 0
    start = time.time()
    for row in reader:
      if len(row) != 19:
        #print 'Incorrect number of fields'
        line_cnt += 1
        continue
        #raise sqlite3.Error('Invalid number of fields for GeoNames cities db')
      
      cur.execute('INSERT INTO cities values (' + \
                  ','.join(['?' for n in range(19)]) + ')', row)
      line_cnt += 1
      percent_done = round(line_cnt / NUM_CITIES * 100, 2)
      time_elapsed = datetime.fromtimestamp(time.time()) - \
                      datetime.fromtimestamp(start)
      time_elapsed = str(time_elapsed)
      left = NUM_CITIES - line_cnt
      rate = line_cnt / float(time.time() - start)
      etr = timedelta(seconds=left/rate)
      progress = str(percent_done) + '% complete | ' + \
                 str(time_elapsed) + ' elapsed | ' + \
                 'Est. Time Remaining: ' + str(etr)

      print progress + ' ' * (80 - len(progress)) + '\r',
      
  print
  print 'Successfully created GeoNames cities DB'

except KeyboardInterrupt:
  if con:
    con.rollback()

except sqlite3.Error, e:
  if con:
    con.rollback()

  print 'Error %s:' % e.args[0]
  sys.exit(1)

finally:
  if con:
    con.close()
