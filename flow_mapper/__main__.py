"""Command line entry point: python -m flow_mapper --data-dir DIR [--port N]."""

import argparse
import sqlite3
import sys

from .server import create_server


def _port(text):
    value = int(text)
    if not 0 <= value <= 65535:
        raise argparse.ArgumentTypeError("port must be between 0 and 65535")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(prog="flow_mapper", description="UX Flow Mapper server")
    parser.add_argument("--data-dir", required=True, help="directory for the SQLite database")
    parser.add_argument("--port", type=_port, default=8765, help="port on 127.0.0.1 (0 = any)")
    args = parser.parse_args(argv)

    try:
        server = create_server(args.data_dir, args.port)
    except (RuntimeError, OSError, sqlite3.Error) as exc:
        sys.stderr.write("Cannot start: %s\n" % exc)
        return 1

    print("Serving on http://127.0.0.1:%d/" % server.server_address[1], flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
