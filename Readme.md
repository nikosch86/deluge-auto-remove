# Deluge Torrent Remover based on Seed time

This script uses the deluge-client library to get the torrent list.  
Torrents that have been seeding longer than the configured amount of days  
and are in the finished state will be removed (with data)  

This is useful in a scenario where an automated system is used to handle downloads.  

```
usage: main.py [-h] [--host HOST] [--port PORT] [--user USER]
               [--password PASSWORD] [--days DAYS] [--keep-label KEEP_LABEL]
               [--verbose] [--dry-run]

optional arguments:
  -h, --help            show this help message and exit
  --host HOST           deluge host, can be specified as ENV DELUGE_HOST
                        (default: None)
  --port PORT           deluge port, can be specified as ENV DELUGE_PORT
                        (default: None)
  --user USER           deluge user, can be specified as ENV DELUGE_USER
                        (default: None)
  --password PASSWORD   deluge password, can be specified as ENV
                        DELUGE_PASSWORD (default: None)
  --days DAYS, -d DAYS  delete torrents seeding for more than this amount of
                        days (default: 25)
  --keep-label KEEP_LABEL, -l KEEP_LABEL
                        ignore torrents with this label (default: keep)
  --verbose, -v
  --dry-run             dry run, do not actually remove torrents
  ```

the connection details and credentials can be provided from the environment.  
a Dockerfile is provided and can be used as follows:  
`docker build . -t remover && docker run -it remover`

Environment variables can be used with the Dockerfile as shown:  
`docker build . -t remover && docker run -it -e DELUGE_HOST -e DELUGE_PORT -e DELUGE_USER -e DELUGE_PASSWORD remover`
