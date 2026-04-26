#!/usr/bin/env python3
"""
remove torrent (with data) if seeding for more than specified days
"""
import argparse
import logging
import os
import sys
import time
from datetime import timedelta

import coloredlogs

LOGGER = logging.getLogger(__name__)


def build_argparser():
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--host",
        default=os.environ.get('DELUGE_HOST'),
        help="deluge host, can be specified as ENV DELUGE_HOST (default: %(default)s)")
    parser.add_argument("--port",
        default=os.environ.get('DELUGE_PORT'),
        help="deluge port, can be specified as ENV DELUGE_PORT (default: %(default)s)")
    parser.add_argument("--user",
        default=os.environ.get('DELUGE_USER'),
        help="deluge user, can be specified as ENV DELUGE_USER (default: %(default)s)")
    parser.add_argument("--password",
        default=os.environ.get('DELUGE_PASSWORD'),
        help="deluge password, can be specified as ENV DELUGE_PASSWORD (default: %(default)s)")
    parser.add_argument("--days", "-d",
        default=25,
        help="delete torrents seeding for more than this amount of days (default: %(default)s)",
        type=int)
    parser.add_argument("--ratio", "-r",
        default='auto',
        help="delete torrents with a ratio equal greater than specified \
            (auto means compare to stop_ratio configured for torrent) (default: %(default)s)")
    parser.add_argument("--keep-label", "-l",
        default="keep",
        help="ignore torrents with this label (default: %(default)s)")
    parser.add_argument("--verbose", "-v",
        action='count',
        default=0)
    parser.add_argument("--dry-run",
        help="dry run, do not actually remove torrents",
        action="store_true")
    parser.add_argument("--keep-data",
        help="remove torrent but keep the downloaded data",
        action="store_true")
    parser.add_argument("--remove-error",
        help="remove torrents that are in error state",
        action="store_true")
    return parser


def cleanup_and_die(msg):
    """Log a critical message and exit with status 2."""
    LOGGER.critical(msg)
    sys.exit(2)


def convert(data):
    """Recursively decode bytes inside dicts/tuples to UTF-8 strings."""
    if isinstance(data, bytes):
        return data.decode('utf_8')
    if isinstance(data, dict):
        return dict(map(convert, data.items()))
    if isinstance(data, tuple):
        return tuple(map(convert, data))
    return data


def should_remove(torrent, seeding_days, ratio, keep_label, remove_error):
    """
    Decide whether a torrent should be removed.

    Returns a tuple (remove: bool, reason: str|None). reason is a short tag
    describing why ('seeding_days', 'ratio', 'stop_ratio') or None when keeping.
    """
    state = torrent.get('state')
    eligible_states = {'Seeding', 'Paused'}
    if remove_error:
        eligible_states = eligible_states | {'Error'}
    if state not in eligible_states:
        return (False, None)

    if torrent.get('label') == keep_label:
        return (False, None)

    if torrent.get('is_finished') is not True:
        return (False, None)

    seeding = torrent.get('seeding_time', 0) // (60 * 60 * 24)
    if seeding > seeding_days:
        return (True, 'seeding_days')

    if ratio != 'auto':
        ratio_f = float(ratio)
        if -1 < ratio_f < torrent.get('ratio', 0):
            return (True, 'ratio')
        return (False, None)

    if torrent.get('ratio', 0) > torrent.get('stop_ratio', float('inf')):
        if torrent.get('stop_at_ratio') is True:
            return (True, 'stop_ratio')
        return (False, 'stop_ratio_ignored')

    return (False, None)


def remove(client, torrent_id, keep_data, dry_run):
    """Remove a torrent by id (or just log it during a dry run)."""
    torrent_data_message = '' if keep_data else ' (with data)'
    if dry_run:
        LOGGER.info("[dry-run] _NOT_ removing torrent%s by id '%s'",
            torrent_data_message, torrent_id)
        return
    LOGGER.info("removing torrent%s by id '%s'", torrent_data_message, torrent_id)
    removed = convert(client.call('core.remove_torrent', torrent_id, not keep_data))
    if removed is not True:
        cleanup_and_die(f"something went wrong removing '{removed}'")
    LOGGER.debug("successfully removed torrent%s", torrent_data_message)


def _log_torrent_decision(torrent, reason, args):
    """Emit the verbose log line that explains why a torrent was selected."""
    name = torrent['name']
    if reason == 'seeding_days':
        seeding = torrent['seeding_time'] // (60 * 60 * 24)
        LOGGER.info("torrent '%s' surpassed seeding cut off time (%s > %s)",
            name, seeding, args.days)
        LOGGER.debug(torrent)
        LOGGER.debug("torrent added '%s'", time.ctime(torrent['time_added']))
        seeding_str = str(timedelta(seconds=torrent['seeding_time']))
        LOGGER.debug("seeding time %s", f"{seeding_str:0>8}")
    elif reason == 'ratio':
        LOGGER.info("torrent '%s' surpassed minimum ratio (%s > %s)",
            name, torrent['ratio'], args.ratio)
        LOGGER.debug(torrent)
    elif reason == 'stop_ratio':
        LOGGER.info("torrent '%s' surpassed stop_ratio (%s > %s)",
            name, torrent['ratio'], torrent['stop_ratio'])
        LOGGER.debug(torrent)
    elif reason == 'stop_ratio_ignored':
        LOGGER.debug("torrent '%s' surpassed stop_ratio (%s > %s) but stop_at_ratio is set to %s",
            name, torrent['ratio'], torrent['stop_ratio'], torrent.get('stop_at_ratio'))
        LOGGER.debug(torrent)


def _validate_required_args(parser, args):
    """Ensure host/port/user/password are present, otherwise die."""
    for var in ['host', 'port', 'user', 'password']:
        value = vars(args).get(var)
        if value:
            display = '***' if var == 'password' else value
            LOGGER.debug("%s set to %s", var, display)
        else:
            parser.print_help(sys.stderr)
            cleanup_and_die(f"argument '--{var}' is required, specify through ENV or CLI")


def _connect(args):
    """Build a DelugeRPCClient, connect, and return it (or die)."""
    # pylint: disable=import-outside-toplevel
    try:
        from deluge_client import DelugeRPCClient
    except ImportError:
        cleanup_and_die("please install the DelugeRPCClient library 'pip install -U deluge-client'")

    client = DelugeRPCClient(args.host, int(args.port), args.user, args.password,
        automatic_reconnect=False)

    try:
        client.connect()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        if 'BadLoginError' in str(exc):
            cleanup_and_die("wrong password supplied")
        else:
            cleanup_and_die(exc)

    if client.connected is True:
        LOGGER.debug("successfully connected to deluge")
    else:
        LOGGER.warning(client)
        cleanup_and_die("failed to connect")

    return client


def main(argv=None):
    """Entry point: parse args, connect, walk torrents, remove eligible ones."""
    parser = build_argparser()
    args = parser.parse_args(argv)

    levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    level = levels[min(len(levels) - 1, args.verbose)]
    coloredlogs.install(level=level)

    _validate_required_args(parser, args)
    client = _connect(args)

    torrents = convert(client.call('core.get_torrents_status', {}, {}))

    for torrent_id, torrent in torrents.items():
        decision, reason = should_remove(torrent,
            seeding_days=args.days,
            ratio=args.ratio,
            keep_label=args.keep_label,
            remove_error=args.remove_error)
        _log_torrent_decision(torrent, reason, args)
        if not decision:
            continue
        remove(client, torrent_id,
            keep_data=args.keep_data,
            dry_run=args.dry_run)


if __name__ == "__main__":
    main()
