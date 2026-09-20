#!/usr/bin/env python3
"""AirDrop Continuity BLE advert, via bluetoothd's D-Bus API.

Why this exists alongside tools/blewake.sh: on this machine `btmgmt add-adv`
(what blewake.sh and airdrop-helper both use) FAILS outright once airdrop.sh's
layer 1 has swept the radio - "failed to register the advertising instance" -
and where it does succeed, the phone never reacts to it. bluetoothd owns
advertising on a system where it runs; going through LEAdvertisingManager1
lets it enable the advertising itself, which is the path BlueZ expects.

Payload is byte-identical to the project's:
    17 FF 4C00 05 12 00*8 01 00*9
i.e. manufacturer 0x004C (Apple) with the AirDrop subtype and empty hashes,
which is what "Everyone" mode needs - no contact match is possible.

Run it in its own terminal and leave it there:
    tools/blewake-dbus.py
    ./airdrop.sh send <file>
"""
import signal
import sys

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

PATH = "/org/bluez/airdrop/adv0"
ADAPTER = "/org/bluez/hci0"
PAYLOAD = bytes.fromhex("0512000000000000000001000000000000000000")


class Advertisement(dbus.service.Object):
    def __init__(self, bus, path, on_release):
        super().__init__(bus, path)
        self.on_release = on_release

    @dbus.service.method("org.freedesktop.DBus.Properties",
                         in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != "org.bluez.LEAdvertisement1":
            raise dbus.exceptions.DBusException(
                "org.freedesktop.DBus.Error.InvalidArgs")
        return {
            "Type": dbus.String("broadcast"),
            "ManufacturerData": dbus.Dictionary(
                {dbus.UInt16(0x004C): dbus.Array(PAYLOAD, signature="y")},
                signature="qv"),
            # Left off deliberately: the legacy advert is 31 bytes total and
            # ours already spends 24. TX power would risk the overflow.
            "IncludeTxPower": dbus.Boolean(False),
        }

    @dbus.service.method("org.bluez.LEAdvertisement1")
    def Release(self):
        # THE ONLY NOTICE WE GET that the advert is gone. When the controller
        # goes away, BlueZ's manager_destroy runs client_destroy on every
        # registered advert, which calls Release here and frees the object
        # (src/advertising.c). The controller comes back with no adverts at
        # all. Without clearing the flag, arm() below still believes we are up
        # and never registers again.
        #
        # Not observed on this hardware: across three reset events the advert
        # was never released. Kept because it is the only notice BlueZ gives,
        # and an advert that is gone without one is expensive to diagnose.
        self.on_release()


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    # follow_name_owner_changes: a bluetoothd restart hands org.bluez to a new
    # owner, and a proxy bound to the old one throws on every later call.
    manager = dbus.Interface(
        bus.get_object("org.bluez", ADAPTER, follow_name_owner_changes=True),
        "org.bluez.LEAdvertisingManager1")
    loop = GLib.MainLoop()
    state = {"up": False}

    def ok():
        if not state["up"]:
            print("advert up", flush=True)
        state["up"] = True

    def ko(error):
        if state["up"]:
            print("advert lost (%s) - re-arming" % error, flush=True)
        state["up"] = False

    def released():
        if state["up"]:
            print("advert released by BlueZ - re-arming", flush=True)
        state["up"] = False

    # THE REFERENCE IS LOAD-BEARING: without it Python collects the object, its
    # D-Bus path disappears, and BlueZ drops the advert without a word.
    adv = Advertisement(bus, PATH, released)

    # A SAFEGUARD, NOT A FIX FOR A KNOWN FAILURE. The combo-chip argument this
    # started from does not survive measurement: across three separate reset
    # events on the MT7922 - a layer 1 radio sweep, an `hci0` power cycle and a
    # `modprobe -r mt7921e` - the advert stayed registered every time, and
    # `Release` was never called. Resetting the Wi-Fi side does not take
    # bluetoothd's advert down here.
    #
    # What is measured, and what actually motivates this script, is on the
    # btmgmt side: after layer 1 `btmgmt add-adv` fails outright with "failed to
    # register the advertising instance", and on the occasions it does register,
    # the phone still does not react to it. Going through
    # LEAdvertisingManager1 avoids both.
    #
    # The timer and the Release handler stay because neither costs anything and
    # an advert that disappears without a word is expensive to diagnose - not
    # because either is answering a failure observed on this hardware.
    def arm():
        if not state["up"]:
            try:
                manager.RegisterAdvertisement(
                    PATH, dbus.Dictionary({}, signature="sv"),
                    reply_handler=ok, error_handler=ko)
            except Exception as exc:
                print("register: %s" % exc, file=sys.stderr, flush=True)
        return True

    arm()
    GLib.timeout_add_seconds(3, arm)

    def stop(*_):
        try:
            manager.UnregisterAdvertisement(PATH)
        except Exception:
            pass
        loop.quit()
        return False

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, stop)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, stop)
    loop.run()


if __name__ == "__main__":
    main()
