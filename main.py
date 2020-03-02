#!/usr/bin/env python3
"""
remove torrent (with data) if seeding for more than specified days
"""
from datetime import timedelta
import pprint, time, os, argparse, sys, coloredlogs, logging
LOGGER = logging.getLogger(__name__)
PP = pprint.PrettyPrinter(indent=2)

ARGPARSER = argparse.ArgumentParser()
ARGPARSER.add_argument("--host", \
    default=os.environ.get('DELUGE_HOST'), \
    help="deluge host, can be specified as ENV DELUGE_HOST (default: %(default)s)")
ARGPARSER.add_argument("--port", \
    default=os.environ.get('DELUGE_PORT'), \
    help="deluge port, can be specified as ENV DELUGE_PORT (default: %(default)s)")
ARGPARSER.add_argument("--user", \
    default=os.environ.get('DELUGE_USER'), \
    help="deluge user, can be specified as ENV DELUGE_USER (default: %(default)s)")
ARGPARSER.add_argument("--password", \
    default=os.environ.get('DELUGE_PASSWORD'), \
    help="deluge password, can be specified as ENV DELUGE_PASSWORD (default: %(default)s)")
ARGPARSER.add_argument("--days", "-d", \
    default=25, \
    help="delete torrents seeding for more than this amount of days (default: %(default)s)", \
    type=int)
ARGPARSER.add_argument("--ratio", "-r", \
    default='auto', \
    help="delete torrents with a ratio equal greater than specified \
        (auto means compare to stop_ratio configured for torrent) (default: %(default)s)")
ARGPARSER.add_argument("--keep-label", "-l", \
    default="keep", \
    help="ignore torrents with this label (default: %(default)s)")
ARGPARSER.add_argument("--verbose", "-v", \
    action='count', \
    default=0)
ARGPARSER.add_argument("--dry-run", \
    help="dry run, do not actually remove torrents", \
    action="store_true")
ARGS = ARGPARSER.parse_args()

LEVELS = [logging.WARNING, logging.INFO, logging.DEBUG]
LEVEL = LEVELS[min(len(LEVELS)-1, ARGS.verbose)]
coloredlogs.install(level=LEVEL)

KEEP_LABEL = ARGS.keep_label
SEEDING_DAYS = ARGS.days
RATIO = ARGS.ratio

def cleanup_and_die(msg):
    """
    cleanup and messages, then exit
    """
    LOGGER.critical(msg)
    sys.exit(2)

for var in ['host', 'port', 'user', 'password']:
    if vars(ARGS).get(var):
        LOGGER.debug("{} set to {}".format(var, vars(ARGS).get(var)))
    else:
        ARGPARSER.print_help(sys.stderr)
        cleanup_and_die("argument '--{}' is required, specify through ENV or CLI".format(var))

def convert(data):
    """
    convert bytes, dict tuples
    """
    if isinstance(data, bytes):
        return data.decode('ascii')
    if isinstance(data, dict):
        return dict(map(convert, data.items()))
    if isinstance(data, tuple):
        return map(convert, data)
    return data

def remove(torrent_id):
    """
    remove torrent by id
    """
    if vars(ARGS).get('dry_run'):
        LOGGER.info("[dry-run] _NOT_ removing torrent (with data) by id '{}'".format(torrent_id))
    else:
        LOGGER.info("removing torrent (with data) by id '{}'".format(torrent_id))
        removed = convert(CLIENT.call('core.remove_torrent', torrent_id, True))
        if removed is not True:
            cleanup_and_die("something went wrong removing '{}'".format(removed))
    LOGGER.debug("successfully removed torrent with data")

try:
    from deluge_client import DelugeRPCClient
except ImportError:
    cleanup_and_die("please install the DelugeRPCClient library 'pip install -U deluge-client'")

CLIENT = DelugeRPCClient(ARGS.host, int(ARGS.port), ARGS.user, ARGS.password)

CLIENT.connect()
if CLIENT.connected is True:
    LOGGER.debug("successfully connected to deluge")
else:
    LOGGER.warning(CLIENT)
    cleanup_and_die("failed to connect")

TORRENTS = convert(CLIENT.call('core.get_torrents_status', {}, {}))

for id in TORRENTS:
    if TORRENTS[id]['state'] != 'Seeding' and TORRENTS[id]['state'] != 'Paused':
        continue
    if TORRENTS[id]['label'] == KEEP_LABEL:
        continue
    if TORRENTS[id]['is_finished'] is not True:
        continue
    torrent = TORRENTS[id]

    seeding = torrent['seeding_time'] // (60*60*24)
    if seeding > SEEDING_DAYS:
        LOGGER.info("torrent '{}' surpassed seeding cut off time ({} > {})".\
            format(torrent['name'], seeding, SEEDING_DAYS))
        LOGGER.debug(torrent)
        LOGGER.debug("torrent added '{}'".format(time.ctime(torrent['time_added'])))
        LOGGER.debug("seeding time {:0>8}".format(str(timedelta(seconds=torrent['seeding_time']))))
        remove(id)
        continue
    if RATIO != 'auto':
        if torrent['ratio'] > float(RATIO) and float(RATIO) > -1:
            LOGGER.info("torrent '{}' surpassed minimum ratio ({} > {})".\
                format(torrent['name'], torrent['ratio'], RATIO))
            LOGGER.debug(torrent)
            remove(id)
            continue
    elif RATIO == 'auto' and torrent['ratio'] > torrent['stop_ratio']:
        if torrent['stop_at_ratio'] is True:
            LOGGER.info("torrent '{}' surpassed stop_ratio ({} > {})".\
                format(torrent['name'], torrent['ratio'], torrent['stop_ratio']))
            LOGGER.debug(torrent)
            remove(id)
            continue
        if torrent['stop_at_ratio'] is not True:
            LOGGER.debug("torrent '{}' surpassed stop_ratio ({} > {}) \
but stop_at_ratio is set to {}".\
                format(torrent['name'], torrent['ratio'], \
                    torrent['stop_ratio'], torrent['stop_at_ratio']))
            LOGGER.debug(torrent)
