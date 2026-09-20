#!/usr/bin/env python3
"""Show system state on the case RGB through the OpenRGB SDK server.

- Fan outer rings: a light spinning at a rate that follows the fan's RPM
- Fan inner rings: CPU package temperature
- Cooler (on the CPU block): CPU load, as a fill gauge
- Pump: a light spinning at a rate that follows the pump's RPM
- RAM sticks: memory used, as a fill gauge from the bottom (updated once a second)

Before the system sleeps every device is switched to a black hardware mode (logind delay
lock), because in S3 the USB devices stay powered and the Commander Pro would fall back
to its built-in effect once the animation stops.
"""
import glob
import math
import signal
import statistics
import threading
import time
from collections import deque

from jeepney import DBusAddress, MatchRule, new_method_call
from jeepney.bus_messages import message_bus
from jeepney.io.blocking import open_dbus_connection
from openrgb import OpenRGBClient
from openrgb.utils import DeviceType, RGBColor

# --- Layout (see OpenRGB segments on the Commander Pro) ----------------------
# Commander Pro fan tachometer channel behind each RGB fan segment (found with fan_test.py).
FAN_TACH = {"Exhaust": 5, "Middle Radiator": 3, "Top Radiator": 6, "Bottom Radiator": 4}
PUMP_TACH = 2
FAN_INNER_LEDS = 4          # each fan: 4 inner-ring LEDs, then 12 outer-ring LEDs
FAN_OUTER_LEDS = 12

# --- Look and feel -----------------------------------------------------------
FAN_STYLE = "gauge"         # "gauge" (static fill) or "spin" (rotating light). A spinner needs a
                            # high frame rate, and the LED stream then drowns out the fan-speed
                            # reads (measured: 0 of 40 batches valid), so it needs a ~70 ms pause
                            # every few seconds, which is visible as a hitch. Gauges don't move,
                            # so the pause can't be seen and the frame rate can stay low.
FPS = 15 if FAN_STYLE == "gauge" else 40
SENSOR_INTERVAL = 0.5       # seconds between CPU/memory reads (files only, no device traffic)
RPM_INTERVAL = 4.0          # seconds between fan/pump speed reads from the Commander Pro
RPM_QUIET_TIME = 0.05       # >0 pauses the LED stream before a speed read; 0 = never pause
RAM_INTERVAL = 1.0          # seconds between RAM updates (Kingston writes are slow)
FAN_REVS_PER_SEC_AT_MAX = 1.0   # visual spin speed at FAN_MAX_RPM (lower = smoother-looking)
PUMP_REVS_PER_SEC_AT_MAX = 1.0
FAN_MAX_RPM = 1650          # measured at 100 % duty
FAN_MIN_RPM = 1000          # gauge starts here, just under the idle speed (~1,080 RPM at 50 % duty),
                            # so the ramp from idle to full uses the whole bar instead of the top third
PUMP_MAX_RPM = 4850         # fixed 100 % in CoolerControl (~4810 RPM)
PUMP_MIN_RPM = 3500         # a healthy pump sits near the top; a drop is then obvious
SMOOTHING_TAU = 2.0         # seconds for displayed speed/temperature to ease to a new reading
SPIN_TAIL = 5               # LEDs in the fading tail behind the spinning head
SPIN_HEAD = (0, 212, 255)   # cyan
SPIN_BASE = (8, 0, 24)      # faint violet for the rest of the ring
PUMP_HEAD = (255, 43, 214)  # pink
SPEED_SCALE = [(0.0, (0, 212, 255)), (0.6, (80, 120, 255)), (1.0, (255, 43, 214))]   # idle -> full speed
GAUGE_OFF = (6, 0, 16)
TEMP_SCALE = [(35, (0, 60, 255)), (50, (0, 255, 80)), (65, (255, 200, 0)), (85, (255, 0, 0))]
LOAD_SCALE = [(0.0, (0, 255, 80)), (0.6, (255, 200, 0)), (1.0, (255, 0, 0))]
AURA = [(0, 0, 0), (255, 43, 214), (0, 212, 255), (0, 0, 0)]   # unused, ROG eye, WiFi logo, unused


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def scale(stops, value):
    """Colour for value on a list of (value, colour) stops."""
    if value <= stops[0][0]:
        return stops[0][1]
    for (v0, c0), (v1, c1) in zip(stops, stops[1:]):
        if value <= v1:
            return lerp(c0, c1, (value - v0) / (v1 - v0))
    return stops[-1][1]


def span(value, low, high):
    """Where value sits between low and high, clamped to 0..1."""
    return min(max((value - low) / (high - low), 0.0), 1.0)


def gauge(n, fraction, stops):
    """n LEDs filled from index 0 up to fraction, each coloured by its position."""
    lit = fraction * n
    out = []
    for i in range(n):
        level = min(max(lit - i, 0.0), 1.0)          # partial brightness on the top LED
        out.append(lerp(GAUGE_OFF, scale(stops, (i + 1) / n), level))
    return out


def spinner(n, position, head, base):
    """A bright head at position (in LEDs, fractional) with a fading tail."""
    out = []
    for i in range(n):
        behind = (position - i) % n                  # how far LED i trails the head
        strength = max(0.0, 1.0 - behind / SPIN_TAIL) if behind < SPIN_TAIL else 0.0
        out.append(lerp(base, head, strength ** 1.5))
    return out


# --- Sensors -----------------------------------------------------------------
def hwmon(name):
    for h in glob.glob("/sys/class/hwmon/hwmon*"):
        if open(f"{h}/name").read().strip() == name:
            return h
    raise RuntimeError(f"hwmon device {name} not found")


def read_int(path, default=0):
    try:
        return int(open(path).read())
    except (OSError, ValueError):
        return default


class Sensors:
    def __init__(self):
        self.cpro = hwmon("corsaircpro")
        coretemp = hwmon("coretemp")
        self.cpu_temp_path = next(p.replace("_label", "_input") for p in glob.glob(f"{coretemp}/temp*_label")
                                  if open(p).read().startswith("Package"))
        self.prev_cpu = self._cpu_times()
        # The Commander Pro answers every request with an unlabelled reply that every program
        # holding the device sees (kernel driver, OpenRGB, CoolerControl's liquidctl), so the
        # kernel driver can take another program's reply as its own. The main loop pauses the
        # LED stream before read_rpm(), each batch is checked against the 12 V rail reading,
        # and the median of the last three good batches smooths over the rest.
        self.rpm_reads = self.rpm_good = 0
        self.history = {channel: deque(maxlen=3) for channel in [*FAN_TACH.values(), PUMP_TACH]}
        self.fan_rpm = {name: 0 for name in FAN_TACH}
        self.pump_rpm = 0
        self.cpu_temp = 0.0
        self.cpu_load = 0.0
        self.mem_used = 0.0

    @staticmethod
    def _cpu_times():
        fields = [int(x) for x in open("/proc/stat").readline().split()[1:]]
        idle = fields[3] + fields[4]                 # idle + iowait
        return sum(fields), idle

    @staticmethod
    def _plausible(channel, rpm):
        # A mispaired reply carries another channel's value (a voltage in mV, a temperature in
        # thousandths, another fan's RPM), so a range check catches almost all of them.
        return 2500 <= rpm <= 5500 if channel == PUMP_TACH else 0 <= rpm <= 2500

    def read_rpm(self):
        self.rpm_reads += 1
        batch = {channel: read_int(f"{self.cpro}/fan{channel}_input") for channel in self.history}
        if not all(self._plausible(channel, rpm) for channel, rpm in batch.items()):
            return
        self.rpm_good += 1
        for channel, history in self.history.items():
            history.append(batch[channel])
        rpm = {channel: statistics.median(history) for channel, history in self.history.items()}
        self.fan_rpm = {name: rpm[channel] for name, channel in FAN_TACH.items()}
        self.pump_rpm = rpm[PUMP_TACH]

    def read(self):
        self.cpu_temp = read_int(self.cpu_temp_path) / 1000

        total, idle = self._cpu_times()
        d_total, d_idle = total - self.prev_cpu[0], idle - self.prev_cpu[1]
        self.prev_cpu = (total, idle)
        if d_total > 0:
            self.cpu_load = 1.0 - d_idle / d_total

        mem = {}
        for line in open("/proc/meminfo"):
            key, value = line.split(":")
            mem[key] = int(value.split()[0])
        self.mem_used = 1.0 - mem["MemAvailable"] / mem["MemTotal"]


class SetupError(Exception):
    """The OpenRGB server is up but hasn't applied the saved zone sizes and segments."""


class SensorThread(threading.Thread):
    """Reads sensors off the animation loop.

    Reading the CPU package temperature makes the kernel interrupt a specific core, which can
    take a few hundred ms when every core is busy; doing that inline stalled the animation
    during CPU load peaks. Speed reads additionally need the LED stream to go quiet, so this
    thread asks the main loop to pause via `quiet` and waits for it to acknowledge."""

    def __init__(self, sensors):
        super().__init__(daemon=True)
        self.sensors = sensors
        self.quiet = threading.Event()      # set while the main loop must not send frames
        self.paused = threading.Event()     # set by the main loop once it has stopped sending
        self.pauses = []                    # LED silence durations, reported once a minute

    def run(self):
        next_rpm = 0.0
        while True:
            self.sensors.read()
            now = time.monotonic()
            if now >= next_rpm:
                started = time.monotonic()
                if RPM_QUIET_TIME > 0:
                    self.quiet.set()
                    self.paused.wait(timeout=0.5)
                    time.sleep(RPM_QUIET_TIME)   # let OpenRGB's LED traffic drain
                self.sensors.read_rpm()
                self.quiet.clear()
                self.pauses.append(time.monotonic() - started)
                next_rpm = time.monotonic() + RPM_INTERVAL
            time.sleep(SENSOR_INTERVAL)


# --- Sleep -------------------------------------------------------------------
LOGIND = DBusAddress("/org/freedesktop/login1", bus_name="org.freedesktop.login1",
                     interface="org.freedesktop.login1.Manager")


class SleepWatcher(threading.Thread):
    """Holds a logind delay lock and tells the main loop when the system is about to sleep.

    logind waits (up to InhibitDelayMaxSec, 5 s by default) until the lock is released,
    which gives the main loop time to switch the LEDs off."""

    def __init__(self):
        super().__init__(daemon=True)
        self.sleeping = threading.Event()    # set from PrepareForSleep(true) until wake-up
        self.lights_off = threading.Event()  # set by the main loop once the LEDs are off

    def _inhibit(self, conn):
        reply = conn.send_and_get_reply(new_method_call(
            LOGIND, "Inhibit", "ssss",
            ("sleep", "rgb-monitor", "Switching the case LEDs off", "delay")))
        return reply.body[0]                 # the lock is held while this fd is open

    def run(self):
        try:
            conn = open_dbus_connection(bus="SYSTEM", enable_fds=True)
            rule = MatchRule(type="signal", interface=LOGIND.interface,
                             member="PrepareForSleep", path=LOGIND.object_path)
            conn.send_and_get_reply(message_bus.AddMatch(rule))
            lock = self._inhibit(conn)
            with conn.filter(rule) as queue:
                while True:
                    going_to_sleep = conn.recv_until_filtered(queue).body[0]
                    if going_to_sleep:
                        self.lights_off.clear()
                        self.sleeping.set()
                        self.lights_off.wait(timeout=4)
                        lock.close()
                    else:
                        lock = self._inhibit(conn)
                        self.sleeping.clear()
        except Exception as err:             # keep the LEDs running even without sleep handling
            print(f"sleep handling disabled: {err!r}", flush=True)


# --- Output ------------------------------------------------------------------
def to_rgb(colors):
    return [RGBColor(*c) for c in colors]


class Monitor:
    def __init__(self, client):
        self.client = client
        self.cpro = next(d for d in client.devices if d.name == "Corsair Commander Pro")
        self.ram = next(d for d in client.devices if d.type == DeviceType.DRAM)
        self.board = next((d for d in client.devices if d.type == DeviceType.MOTHERBOARD), None)

        # absolute LED index of each segment on the Commander Pro (an LED's id is its device index)
        self.segments = {s.name: (zone.leds[0].id + s.start_idx, len(s.leds))
                         for zone in self.cpro.zones[:2] if zone.leds for s in (zone.segments or [])}
        missing = [name for name in [*FAN_TACH, "Pump", "Cooler"] if name not in self.segments]
        if missing:
            # OpenRGB matches saved settings by name, serial and firmware version; if the
            # Commander Pro reported a wrong version at startup, its zones come up empty.
            raise SetupError(f"Commander Pro segments missing ({', '.join(missing)}); OpenRGB didn't apply "
                             f"~/.config/OpenRGB/Configuration.json - try: systemctl --user restart openrgb")

        self.fan_pos = {name: 0.0 for name in FAN_TACH}
        self.pump_pos = 0.0
        # Readings arrive in steps (speeds every RPM_INTERVAL seconds, temperature twice a second).
        # Easing the displayed values keeps the spin rate and colours from jumping when the fans
        # ramp up during a CPU temperature peak.
        self.shown = {}

        for device in (self.cpro, self.ram, self.board):
            if device is not None:
                self._set_direct(device)
        if self.board is not None:
            self.board.set_colors(to_rgb(AURA))

    @staticmethod
    def _set_direct(device):
        """Switch to Direct and wait until the server reports it: the server applies mode changes
        asynchronously, and set_colors() picks its code path from the mode the client last saw
        (after wake-up the devices are still in the black Static mode from all_off())."""
        direct = next(m for m in device.modes if m.name.lower() == "direct")
        for _ in range(20):
            if device.active_mode == direct.id:
                return
            device.set_mode(direct)
            time.sleep(0.1)
            device.update()
        raise ConnectionError(f"{device.name} did not switch to Direct mode")

    def _ease(self, key, target, dt):
        """Exponential approach, framerate independent."""
        current = self.shown.get(key)
        if current is None:
            self.shown[key] = target
        else:
            self.shown[key] = current + (target - current) * (1.0 - math.exp(-dt / SMOOTHING_TAU))
        return self.shown[key]

    def frame(self, sensors, dt):
        colors = [(0, 0, 0)] * len(self.cpro.leds)
        inner = [scale(TEMP_SCALE, self._ease("temp", sensors.cpu_temp, dt))] * FAN_INNER_LEDS

        for name in FAN_TACH:
            rpm = self._ease(name, min(sensors.fan_rpm[name], FAN_MAX_RPM), dt)
            if FAN_STYLE == "gauge":
                outer = gauge(FAN_OUTER_LEDS, span(rpm, FAN_MIN_RPM, FAN_MAX_RPM), SPEED_SCALE)
            else:
                self.fan_pos[name] += FAN_OUTER_LEDS * FAN_REVS_PER_SEC_AT_MAX * rpm / FAN_MAX_RPM * dt
                outer = spinner(FAN_OUTER_LEDS, self.fan_pos[name], SPIN_HEAD, SPIN_BASE)
            start, count = self.segments[name]
            colors[start:start + count] = inner + outer

        start, count = self.segments["Pump"]
        rpm = self._ease("pump", min(sensors.pump_rpm, PUMP_MAX_RPM), dt)
        if FAN_STYLE == "gauge":
            colors[start:start + count] = gauge(count, span(rpm, PUMP_MIN_RPM, PUMP_MAX_RPM), SPEED_SCALE)
        else:
            self.pump_pos += count * PUMP_REVS_PER_SEC_AT_MAX * rpm / PUMP_MAX_RPM * dt
            colors[start:start + count] = spinner(count, self.pump_pos, PUMP_HEAD, SPIN_BASE)

        start, count = self.segments["Cooler"]
        colors[start:start + count] = gauge(count, self._ease("load", sensors.cpu_load, dt), LOAD_SCALE)

        self.cpro.set_colors(to_rgb(colors), fast=True)

    def all_off(self):
        """Black hardware modes, which the devices keep without further updates."""
        for device in (self.cpro, self.ram, self.board):
            if device is None:
                continue
            modes = {m.name.lower(): m for m in device.modes}
            if "off" in modes:
                device.set_mode(modes["off"])
            else:
                static = modes["static"]
                static.colors = [RGBColor(0, 0, 0)]
                device.set_mode(static)

    def ram_frame(self, sensors):
        stick = gauge(len(self.ram.zones[0].leds), sensors.mem_used, LOAD_SCALE)
        self.ram.set_colors(to_rgb(stick * len(self.ram.zones)), fast=True)


def main():
    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    sensors = Sensors()
    reader = SensorThread(sensors)
    reader.start()
    watcher = SleepWatcher()
    watcher.start()
    while running:
        try:
            client = OpenRGBClient("127.0.0.1", 6742, "rgb-monitor")
        except (ConnectionError, OSError, TimeoutError):
            time.sleep(5)                            # server not up yet
            continue
        try:
            monitor = Monitor(client)
            last = next_ram = next_report = time.monotonic()
            frame_gaps = []
            slow_frames = {}
            last_action = "none"
            while running:
                if watcher.sleeping.is_set():
                    monitor.all_off()
                    time.sleep(1.0)                  # let OpenRGB write it out (RAM is slow)
                    watcher.lights_off.set()
                    print("system going to sleep: LEDs off", flush=True)
                    while running and watcher.sleeping.is_set():
                        time.sleep(0.2)
                    print("woke up: reconnecting", flush=True)
                    time.sleep(3)                    # give USB devices time to come back
                    break                            # reconnect: devices may have been reset
                now = time.monotonic()
                if reader.quiet.is_set():            # speed read in progress: stop sending
                    reader.paused.set()
                    time.sleep(0.01)
                    last = now
                    continue
                reader.paused.clear()
                if now >= next_report:
                    if sensors.rpm_reads:
                        gaps = sorted(frame_gaps)
                        jitter = (f"frame gap median={statistics.median(gaps) * 1000:.0f} "
                                  f"p95={gaps[int(len(gaps) * 0.95)] * 1000:.0f} "
                                  f"max={gaps[-1] * 1000:.0f} ms over {len(gaps)} frames") if gaps else ""
                        pauses = sorted(reader.pauses)
                        silence = (f"LED silence median={statistics.median(pauses) * 1000:.0f} "
                                   f"max={pauses[-1] * 1000:.0f} ms x{len(pauses)}; ") if pauses else ""
                        reader.pauses.clear()
                        print(f"speed reads: {sensors.rpm_good}/{sensors.rpm_reads} good; {silence}{jitter}; "
                              f"slow frames {slow_frames or '-'}; "
                              f"fans {sensors.fan_rpm} pump {sensors.pump_rpm}", flush=True)
                    frame_gaps.clear()
                    slow_frames.clear()
                    next_report = now + 60
                gap = now - last
                frame_gaps.append(gap)
                if gap > 0.12:                       # note what ran in the previous iteration
                    slow_frames[last_action] = slow_frames.get(last_action, 0) + 1
                monitor.frame(sensors, gap)
                last_action = "none"
                if now >= next_ram:
                    monitor.ram_frame(sensors)
                    next_ram = now + RAM_INTERVAL
                    last_action = "ram"
                last = now
                time.sleep(max(0.0, 1 / FPS - (time.monotonic() - now)))
        except SetupError as err:
            print(err, flush=True)
            time.sleep(30)
        except (ConnectionError, OSError, TimeoutError, StopIteration) as err:
            print(f"lost OpenRGB connection ({err!r}), reconnecting", flush=True)
            time.sleep(2)
        finally:
            if not running:
                try:
                    client.load_profile("Synthwave")
                except Exception:
                    pass
            try:
                client.disconnect()
            except Exception:
                pass


if __name__ == "__main__":
    main()
