#!/usr/bin/python3
"""Forward only explicit PTT events from Hyprland IPC to XWayland."""
from __future__ import annotations

import fcntl
import os
from pathlib import Path
import signal
import socket
import time

from .config import Paths, fingerprint, load

PREFIX = b"custom>>omarchy-ptt:"


class HoldState:
    def __init__(self, inject, persist=lambda mode: None):
        self.inject = inject
        self.persist = persist
        self.mode = None

    def handle(self, action):
        if action in ("down", "native-down"):
            if self.mode is not None:
                return
            self.mode = "bridge" if action == "down" else "native"
            self.persist(self.mode)
            if self.mode == "bridge":
                self.inject(True)
            print(f"down {self.mode}", flush=True)
        elif action == "promote" and self.mode == "native":
            self.mode = "bridge"
            self.persist(self.mode)
            self.inject(True)
            print("held: native -> bridge", flush=True)
        elif action in ("up", "reset") and self.mode is not None:
            # A native press needs explicit release if focus moved or the
            # lock screen consumed the physical release.
            self.inject(False)
            self.mode = None
            self.persist(None)
            print(action, flush=True)

    def accept_line(self, line):
        if line.startswith(PREFIX):
            self.handle(line[len(PREFIX):].decode("ascii", errors="ignore"))
        elif line == b"configreloaded>>":
            self.handle("reset")


def main():
    from Xlib import X, display
    from Xlib.ext import xtest

    config = load(Paths.discover().profile)
    runtime = Path(os.environ["XDG_RUNTIME_DIR"])
    signature = os.environ["HYPRLAND_INSTANCE_SIGNATURE"]
    ready = runtime / "omarchy-ptt.ready"
    lock_path = runtime / "omarchy-ptt.lock"
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock_fd)
        return

    d = display.Display()
    if not d.has_extension("XTEST"):
        raise RuntimeError("XWayland does not expose XTEST")

    def inject(pressed, button=None):
        xtest.fake_input(d, X.ButtonPress if pressed else X.ButtonRelease,
                         config['x11_button'] if button is None else button)
        d.sync()

    # Recover our held button after a crash. Never generate a startup press.
    if ready.exists():
        previous = ready.read_text().splitlines()
        if len(previous) >= 6 and previous[0] == signature and previous[2] in ("bridge", "native"):
            button = int(previous[5])
            if 8 <= button <= 32:
                inject(False, button)
        ready.unlink(missing_ok=True)

    def publish(mode):
        tmp = ready.with_name(ready.name + ".tmp")
        data = (f"{signature}\n{int(time.time())}\n{mode or 'idle'}\n{os.getpid()}\n"
                f"{fingerprint(config)}\n{config['x11_button']}\n")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(data)
        os.replace(tmp, ready)

    state = HoldState(inject, publish)
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    try:
        sock.connect(str(runtime / "hypr" / signature / ".socket2.sock"))
        publish(None)
        print(f"ready: Hyprland IPC -> XWayland Mouse {config['x11_button']}", flush=True)
        buffer = b""
        while not stopping:
            try:
                data = sock.recv(16384)
            except socket.timeout:
                publish(state.mode)
                continue
            if not data:
                raise ConnectionError("Hyprland event socket disconnected")
            buffer += data
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                state.accept_line(line)
            publish(state.mode)
    finally:
        try:
            state.handle("reset")
        finally:
            ready.unlink(missing_ok=True)
            sock.close()
            d.close()
            os.close(lock_fd)


if __name__ == "__main__":
    main()
