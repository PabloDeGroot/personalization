#!/usr/bin/env python3
"""Apply the Synthwave theme (cyan -> violet -> pink) through the running OpenRGB server.

The "Synthwave" profile is what openrgb.service loads at startup and what rgb_monitor.py
restores when it stops. SDK clients can't save profiles on this OpenRGB version (the
server only allows its own app to), so to keep a changed theme: open the OpenRGB app,
Profiles, save as "Synthwave" (overwrite).

Stop the monitor first, or it paints over the theme within a frame:
    systemctl --user stop rgb-monitor && .venv/bin/python theme.py
"""
from openrgb import OpenRGBClient
from openrgb.utils import DeviceType, RGBColor

CYAN, VIOLET, PINK = (0x00, 0xD4, 0xFF), (0x7A, 0x00, 0xFF), (0xFF, 0x2B, 0xD6)
OFF = (0, 0, 0)


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def gradient(stops, n):
    """n colours spread evenly over a list of colour stops."""
    if n == 1:
        return [stops[0]]
    out = []
    for i in range(n):
        pos = i / (n - 1) * (len(stops) - 1)
        seg = min(int(pos), len(stops) - 2)
        out.append(lerp(stops[seg], stops[seg + 1], pos - seg))
    return out


def fan(outer):
    return [PINK] * 4 + [outer] * 12        # 4 inner-ring LEDs, then the 12-LED outer ring


# Outer rings go cyan -> violet from the top of the case down, exhaust last
outer = dict(zip(["Top Radiator", "Middle Radiator", "Bottom Radiator", "Exhaust"], gradient([CYAN, VIOLET], 4)))
segment_colors = {name: fan(color) for name, color in outer.items()}
segment_colors["Pump"] = gradient([CYAN, VIOLET, PINK], 10)
segment_colors["Cooler"] = gradient([PINK, VIOLET], 8)

client = OpenRGBClient("127.0.0.1", 6742, "theme")
cpro = next(d for d in client.devices if d.name == "Corsair Commander Pro")
ram = next(d for d in client.devices if d.type == DeviceType.DRAM)
board = next(d for d in client.devices if d.type == DeviceType.MOTHERBOARD)

colors = [OFF] * len(cpro.leds)
for zone in cpro.zones[:2]:
    for s in zone.segments:
        start = zone.leds[0].id + s.start_idx
        colors[start:start + len(s.leds)] = segment_colors[s.name]

# ASUS board: LED 1 (nothing visible), LED 2 (ROG eye), "RGB Header 1" (WiFi logo), RGB Header 2 (nothing visible)
aura = [OFF, PINK, CYAN, OFF] + [OFF] * (len(board.leds) - 4)

for device, device_colors in ((cpro, colors), (ram, gradient([CYAN, VIOLET], 12) * 2), (board, aura)):
    device.set_mode("direct")
    device.set_colors([RGBColor(*c) for c in device_colors])

client.disconnect()
print('applied; to keep it, save it as "Synthwave" from the OpenRGB app (Profiles)')
