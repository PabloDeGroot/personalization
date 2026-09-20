#!/usr/bin/env python3
"""Identify which Commander Pro fan tachometer channel drives which RGB fan.

Each step lights all four fans in one colour, then stops one fan channel for a
few seconds. The user notes which fan stops during which colour.

Stop CoolerControl and the monitor first, and start CoolerControl again afterwards (the test
leaves the fans at a fixed 100 %):
    systemctl --user stop rgb-monitor; sudo systemctl stop coolercontrold
    .venv/bin/python fan_test.py
    sudo systemctl start coolercontrold; systemctl --user start rgb-monitor
"""
import glob
import subprocess
import sys
import time

from openrgb import OpenRGBClient
from openrgb.utils import RGBColor

CHANNELS = [3, 4, 5, 6]              # fan2 is the pump and is never touched
COLORS = [("red", RGBColor(255, 0, 0)), ("green", RGBColor(0, 255, 0)),
          ("blue", RGBColor(0, 0, 255)), ("white", RGBColor(255, 255, 255))]
LEAD_IN, BEFORE, STOPPED, RECOVER, PASSES = 30, 3, 8, 6, 2

hwmon = next(h for h in glob.glob("/sys/class/hwmon/hwmon*")
             if open(f"{h}/name").read().strip() == "corsaircpro")


def set_pwm(channel, value):
    subprocess.run(["sudo", "tee", f"{hwmon}/pwm{channel}"], input=f"{value}\n",
                   text=True, stdout=subprocess.DEVNULL, check=True)


def rpm(channel):
    return int(open(f"{hwmon}/fan{channel}_input").read())


client = OpenRGBClient("127.0.0.1", 6742, "rgb-monitor-fan-test")
fans = next(d for d in client.devices if d.name == "Corsair Commander Pro").zones[0]
try:
    fans.set_color(RGBColor(0, 0, 0))
    print(f"lead-in: fans dark for {LEAD_IN}s", flush=True)
    time.sleep(LEAD_IN)
    for p in range(PASSES):
        for channel, (name, color) in zip(CHANNELS, COLORS):
            fans.set_color(color)
            time.sleep(BEFORE)
            before = rpm(channel)
            set_pwm(channel, 0)
            low = before
            for _ in range(STOPPED * 2):
                time.sleep(0.5)
                low = min(low, rpm(channel))
            set_pwm(channel, 255)
            print(f"pass {p + 1}: {name:5} -> fan{channel}: {before} rpm, dropped to {low} rpm", flush=True)
            time.sleep(RECOVER)
finally:
    for channel in CHANNELS:
        set_pwm(channel, 255)
    client.load_profile("Synthwave")
    client.disconnect()
    print("restored: fans pwm 255, Synthwave profile", {c: rpm(c) for c in CHANNELS}, flush=True)
    sys.stdout.flush()
