#!/usr/bin/env python3
"""A: join the mDNS multicast group on awdl0, then DO NOTHING.

No frame is sent, nothing is read. The only thing this program changes on the
machine is membership of ff02::fb, which reconfigures the mt7921's hardware
receive filter.

That is the "state change" half of what opendrop adds, isolated from its
"traffic" half. If the link dies with this alone, the culprit is the filter
and not throughput.

    ./mcast-join.py [interface]      # Ctrl+C to quit
"""
import signal
import socket
import struct
import sys
import time

IFACE = sys.argv[1] if len(sys.argv) > 1 else "awdl0"
GROUP = "ff02::fb"          # mDNS, the group opendrop joins
IPV6_JOIN_GROUP = 20

idx = socket.if_nametoindex(IFACE)
s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("", 5353))

# ipv6_mreq: 16 address bytes followed by the interface index.
mreq = socket.inet_pton(socket.AF_INET6, GROUP) + struct.pack("@I", idx)
s.setsockopt(socket.IPPROTO_IPV6, IPV6_JOIN_GROUP, mreq)

print(f"joined {GROUP} on {IFACE} (index {idx})")
print("no frame will be sent. Ctrl+C to quit.", flush=True)

signal.signal(signal.SIGINT, lambda *_: (print("\nbye"), sys.exit(0)))
while True:
    time.sleep(3600)
