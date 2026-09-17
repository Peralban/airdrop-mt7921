#!/bin/bash
# Follows what happens to the AP's beacons, one sample a second.
#
# WHY THIS EXISTS. We could already measure THAT the station dies while
# AirDrop runs, never WHY: a gateway sampler says the network stopped
# answering, wpa_supplicant says it is losing beacons, and neither
# distinguishes the mechanisms. Three hypotheses were chased and dropped for
# want of anything that could tell them apart.
#
# `iw station dump` exposes the three counters that separate them, and needs
# no privilege at all:
#
#   beacon_loss climbs, rx_drop_misc flat -> beacons stop arriving entirely;
#                                            the chip is not listening
#   rx_drop_misc climbs                   -> they arrive and are discarded,
#                                            so it is the receive filter
#   tx_retries / tx_failed climb          -> the transmit path is saturated
#                                            and the station cannot ACK
#
# Without that distinction you can only guess, and guessing has already cost
# several wrong answers here.
#
#   ./beaconwatch.sh [interface] [logfile]
set -u
IFACE="${1:-wlan0}"
LOG="${2:-$HOME/.cache/beaconwatch.log}"

mkdir -p "$(dirname "$LOG")"
[ -s "$LOG" ] || printf 'when\tassoc\tsignal\tinactive_ms\tbeacon_loss\trx_drop_misc\ttx_retries\ttx_failed\trx_pkts\ttx_pkts\ttx_bitrate\tconnected_s\n' > "$LOG"

field() { printf '%s' "$1" | awk -F: -v k="$2" '$0 ~ "^[[:space:]]*"k":" {gsub(/^[[:space:]]+|[[:space:]]+$/,"",$2); print $2; exit}'; }

while :; do
  d=$(iw dev "$IFACE" station dump 2>/dev/null)
  if [ -z "$d" ]; then
    printf '%s\tno\t-\t-\t-\t-\t-\t-\t-\t-\t-\t-\n' "$(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG"
    sleep 1; continue
  fi
  # `signal` reads "-40 [-44, -41] dBm": keep the first number only, the
  # per-chain values teach us nothing here.
  sig=$(field "$d" "signal" | awk '{print $1}')
  br=$(field "$d" "tx bitrate" | awk '{print $1}')
  printf '%s\tyes\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$(date '+%Y-%m-%d %H:%M:%S')" \
    "${sig:--}" \
    "$(field "$d" "inactive time" | awk '{print $1}')" \
    "$(field "$d" "beacon loss")" \
    "$(field "$d" "rx drop misc")" \
    "$(field "$d" "tx retries")" \
    "$(field "$d" "tx failed")" \
    "$(field "$d" "rx packets")" \
    "$(field "$d" "tx packets")" \
    "${br:--}" \
    "$(field "$d" "connected time" | awk '{print $1}')" >> "$LOG"
  sleep 1
done
