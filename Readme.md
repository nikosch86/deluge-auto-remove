# Deluge Torrent Remover based on Seed time and/or Ratio

Connects to a Deluge daemon over RPC and removes finished torrents that
have either been seeding longer than a configured number of days or have
exceeded a configured share ratio. Useful when an automated download
system feeds Deluge and you want completed work cleaned up automatically.

## Usage

```
usage: main.py [-h] [--host HOST] [--port PORT] [--user USER]
               [--password PASSWORD] [--days DAYS] [--ratio RATIO]
               [--keep-label KEEP_LABEL] [--verbose] [--dry-run] [--keep-data]
               [--remove-error]

options:
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
  --ratio RATIO, -r RATIO
                        delete torrents with a ratio equal greater than
                        specified (auto means compare to stop_ratio configured
                        for torrent) (default: auto)
  --keep-label KEEP_LABEL, -l KEEP_LABEL
                        ignore torrents with this label (default: keep)
  --verbose, -v
  --dry-run             dry run, do not actually remove torrents
  --keep-data           remove torrent but keep the downloaded data
  --remove-error        remove torrents that are in error state
```

Connection details and credentials can come from the environment
(`DELUGE_HOST`, `DELUGE_PORT`, `DELUGE_USER`, `DELUGE_PASSWORD`); CLI
flags override env. A torrent labelled with `--keep-label` (default
`keep`) is always skipped. A failed removal of a single torrent is
logged and the run continues — one bad torrent does not abort the
sweep.

## Docker

```
docker build . -t remover
docker run --rm \
  -e DELUGE_HOST -e DELUGE_PORT -e DELUGE_USER -e DELUGE_PASSWORD \
  remover --days 7 --dry-run
```

The image runs as a non-root user and uses Python 3.12-slim. CI publishes
multi-arch images (`linux/amd64`, `linux/arm64`) to
`ghcr.io/<owner>/<repo>` on every push to `master` and on `v*.*.*` tags.

## Standalone binaries

CI also builds standalone PyInstaller binaries for every push and PR
(uploaded as workflow artifacts). On `v*.*.*` tags they are attached to
the corresponding GitHub Release. Targets:

- Linux: `amd64`, `arm64`
- macOS: `arm64` (Apple Silicon), `amd64` (Intel)
- Windows: `amd64`

## Development

The project uses a `Makefile` for all dev tasks — do not invoke pytest /
ruff / pylint directly.

```
make install-dev    # install runtime + dev dependencies
make test           # run pytest
make coverage       # pytest with coverage report; fails under 85%
make lint           # ruff
make pylint         # pylint
```

Tests live in `tests/` and run against a fake `DelugeRPCClient` — no
real daemon needed. CI runs `make lint`, `make pylint`, and
`make coverage` on every push and PR across Python 3.9, 3.11, and
3.12.
