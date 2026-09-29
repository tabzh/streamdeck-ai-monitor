#!/usr/bin/env python3
"""Double-fork daemonizer: start a command fully detached (own session, reparented to launchd).

Usage: python daemonize.py <logfile> <cmd...>
"""
import os
import sys


def main() -> None:
    log, cmd = sys.argv[1], sys.argv[2:]
    if not cmd:
        print("usage: daemonize.py <logfile> <cmd...>")
        sys.exit(1)

    if os.fork() > 0:
        return  # parent exits immediately
    os.setsid()  # new session, escape process group kills
    if os.fork() > 0:
        os._exit(0)

    # grandchild: redirect stdio, exec the command
    sys.stdout.flush()
    sys.stderr.flush()
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    os.dup2(fd, 1)
    os.dup2(fd, 2)
    devnull = os.open(os.devnull, os.O_RDONLY)
    os.dup2(devnull, 0)
    os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    main()
