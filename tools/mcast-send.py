#!/usr/bin/env python3
"""B: send periodic multicast on awdl0, WITHOUT joining any group.

The exact mirror of mcast-join.py. Here the hardware filter is left alone and
only traffic goes out, at the rate opendrop re-announces its service.

If the link dies with this and not with A, then traffic is to blame and the
remedy lives in opendrop, which is code we control.

    ./mcast-send.py [interface] [period_s]
"""
import signal
import socket
import struct
import sys
import time

IFACE = sys.argv[1] if len(sys.argv) > 1 else "awdl0"
PERIOD = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
GROUP = "ff02::fb"

idx = socket.if_nametoindex(IFACE)
s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
# Pick the outgoing interface without joining the group: that is the whole
# difference from A.
s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, struct.pack("@I", idx))
s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, 255)

# Comparable in size to one of opendrop's re-announcements, so the comparison
# is about the nature of the traffic and not its volume.
payload = b"\x00" * 200
n = 0
signal.signal(signal.SIGINT, lambda *_: (print(f"\nbye after {n} sends"), sys.exit(0)))

print(f"sending to {GROUP} via {IFACE} every {PERIOD}s, without joining")
print("Ctrl+C to quit.", flush=True)
while True:
    try:
        s.sendto(payload, (GROUP, 5353, 0, idx))
        n += 1
    except OSError as e:
        print(f"send {n}: {e}", flush=True)
    time.sleep(PERIOD)
