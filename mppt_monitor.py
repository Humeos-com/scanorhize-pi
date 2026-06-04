#!/usr/bin/env python3
"""
Monitor a Victron BlueSolar MPPT 75/10 via VE.Direct.
Usage: sudo python3 mppt_monitor.py [options]
"""

import argparse
import sys
from MPPT_utilities import MPPTReader, SolarLogger, read_mppt, monitor_mppt, LOG_PATH


def cmd_read(args):
    """Read one frame and print it."""
    try:
        frame = read_mppt(port=args.port, timeout=args.timeout)
    except (TimeoutError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.raw:
        for k, v in frame.raw.items():
            print(f"{k}\t{v}")
    else:
        print(frame.summary())
        if args.log:
            logger = SolarLogger(path=args.log_path)
            logger.log(frame, force=True)
            print(f"\nLogged to {args.log_path}")


def cmd_monitor(args):
    """Monitor continuously."""
    log_path = args.log_path if args.log else None
    monitor_mppt(
        port=args.port,
        interval=args.interval,
        count=args.count,
        log_path=log_path,
        log_every=args.log_every,
    )


def cmd_ports(args):
    """List available serial ports."""
    ports = MPPTReader.list_ports()
    if not ports:
        print("No USB serial ports found.")
        return
    for p in ports:
        tag = " ← VE.Direct (FTDI)" if p.get("vid") == "0x0403" else ""
        print(f"  {p['device']:<16} {p['description']:<30} VID:{p['vid']} PID:{p['pid']}{tag}")

    detected = MPPTReader.find_vedirect_port()
    if detected:
        print(f"\nAuto-detected VE.Direct port: {detected}")


def main():
    parser = argparse.ArgumentParser(
        prog="mppt_monitor.py",
        description="Victron BlueSolar MPPT 75/10 — VE.Direct monitor",
    )
    parser.add_argument("--port", default=None, help="Serial port (default: auto-detect)")
    parser.add_argument("--log-path", default=LOG_PATH, metavar="PATH", help=f"CSV log file (default: {LOG_PATH})")
    parser.add_argument("--no-log", dest="log", action="store_false", default=True, help="Disable CSV logging")

    sub = parser.add_subparsers(dest="cmd", required=True)

    # read: one-shot
    p_read = sub.add_parser("read", help="Read one frame and exit")
    p_read.add_argument("--timeout", type=float, default=10.0, help="Seconds to wait for a frame (default: 10)")
    p_read.add_argument("--raw", action="store_true", help="Print raw key-value pairs")
    p_read.set_defaults(func=cmd_read)

    # monitor: continuous
    p_mon = sub.add_parser("monitor", help="Monitor continuously (Ctrl+C to stop)")
    p_mon.add_argument("--interval", type=float, default=5.0, help="Display interval in seconds (default: 5)")
    p_mon.add_argument("--count", type=int, default=0, help="Number of readings (0 = infinite)")
    p_mon.add_argument("--log-every", type=int, default=10, metavar="N", help="Log one data row every N frames (default: 10)")
    p_mon.set_defaults(func=cmd_monitor)

    # ports: list serial ports
    p_ports = sub.add_parser("ports", help="List available serial ports")
    p_ports.set_defaults(func=cmd_ports)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
