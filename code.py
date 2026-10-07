# Pico W – 60 LED NeoPixel Clock
# Seconds = 1 LED, Minutes = 1 LED, Hours = 3 LEDs
# LED data line on GP0.

import os
import time
import board
import neopixel
import rtc
import socketpool
import wifi
import microcontroller
import adafruit_ntp

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
NUM_PIXELS = 60
PIXEL_PIN = board.GP0
PIXEL_ORDER = neopixel.GRB      # use neopixel.RGB for some strips
BRIGHTNESS = 0.15               # 0.0-1.0 (60 LEDs at full white can draw 3.6 A!)

COLOR_HOUR = (255, 0, 0)        # red
COLOR_MIN = (0, 255, 0)         # green
COLOR_SEC = (0, 0, 255)         # blue
OFF = (0, 0, 0)

SMOOTH_HOURS = True             # hour hand creeps forward with the minutes
RESYNC_SECONDS = 6 * 60 * 60    # re-sync NTP every 6 hours

TZ_OFFSET = float(os.getenv("TZ_OFFSET", "0"))      # hours from UTC (standard time)
DST_RULE = str(os.getenv("DST_RULE", "none")).lower()  # "us", "eu", "none"

# ----------------------------------------------------------------------
# Hardware
# ----------------------------------------------------------------------
pixels = neopixel.NeoPixel(
    PIXEL_PIN, NUM_PIXELS,
    brightness=BRIGHTNESS,
    auto_write=False,
    pixel_order=PIXEL_ORDER,
)

# ----------------------------------------------------------------------
# Drawing helpers
# ----------------------------------------------------------------------
def show_buffer(buf):
    for i in range(NUM_PIXELS):
        pixels[i] = buf[i]
    pixels.show()

def add_led(buf, idx, color):
    """Additively blend a color into the frame buffer (wraps around)."""
    idx %= NUM_PIXELS
    r, g, b = buf[idx]
    buf[idx] = (
        min(255, r + color[0]),
        min(255, g + color[1]),
        min(255, b + color[2]),
    )

def render(hour_center, minute_pos, second_pos):
    """Draw the three hands: 3 LEDs hour, 2 LEDs minute, 1 LED second."""
    buf = [OFF] * NUM_PIXELS
    for off in (-1, 0, 1):
        add_led(buf, hour_center + off, COLOR_HOUR)
#    for off in (0, 1): # these two lines are for a 2 LED minute hand
#        add_led(buf, minute_pos + off, COLOR_MIN)
    add_led(buf, minute_pos, COLOR_MIN)
    add_led(buf, second_pos, COLOR_SEC)
    show_buffer(buf)

def hour_center_for(hour, minute):
    pos = (hour % 12) * 5
    if SMOOTH_HOURS:
        pos += minute // 12          # 0-4 extra steps within the hour
    return pos % NUM_PIXELS

def status(color, count=3):
    """Show a small status marker at the top of the dial."""
    pixels.fill(OFF)
    for i in range(count):
        pixels[(i - count // 2) % NUM_PIXELS] = color
    pixels.show()

def wheel(pos):
    pos &= 255
    if pos < 85:
        return (255 - pos * 3, pos * 3, 0)
    if pos < 170:
        pos -= 85
        return (0, 255 - pos * 3, pos * 3)
    pos -= 170
    return (pos * 3, 0, 255 - pos * 3)

# ----------------------------------------------------------------------
# Time zone / DST handling (RTC holds UTC; local time is computed)
# ----------------------------------------------------------------------
def _weekday(y, m, d):
    return time.localtime(time.mktime((y, m, d, 12, 0, 0, 0, 0, -1))).tm_wday

def _nth_sunday(y, m, n):
    first = 1 + (6 - _weekday(y, m, 1)) % 7
    return first + 7 * (n - 1)

def _last_sunday(y, m, days_in_month=31):
    return days_in_month - (_weekday(y, m, days_in_month) + 1) % 7

def dst_active(utc):
    if DST_RULE not in ("us", "eu"):
        return False
    std = int(TZ_OFFSET * 3600)
    year = time.localtime(utc).tm_year
    if DST_RULE == "us":
        # 2nd Sunday March 02:00 local std -> 1st Sunday Nov 02:00 local DST
        d1 = _nth_sunday(year, 3, 2)
        d2 = _nth_sunday(year, 11, 1)
        start = time.mktime((year, 3, d1, 2, 0, 0, 0, 0, -1)) - std
        end = time.mktime((year, 11, d2, 2, 0, 0, 0, 0, -1)) - (std + 3600)
    else:
        # last Sunday March 01:00 UTC -> last Sunday October 01:00 UTC
        d1 = _last_sunday(year, 3)
        d2 = _last_sunday(year, 10)
        start = time.mktime((year, 3, d1, 1, 0, 0, 0, 0, -1))
        end = time.mktime((year, 10, d2, 1, 0, 0, 0, 0, -1))
    return start <= utc < end

def local_now():
    utc = time.time()
    offset = int(TZ_OFFSET * 3600) + (3600 if dst_active(utc) else 0)
    return time.localtime(utc + offset)

# ----------------------------------------------------------------------
# Networking setup
# ----------------------------------------------------------------------
def connect_wifi():
    """Block until Wi-Fi is connected. Amber = trying, red = failed."""
    ssid = os.getenv("CIRCUITPY_WIFI_SSID")
    password = os.getenv("CIRCUITPY_WIFI_PASSWORD")
    if not ssid:
        raise RuntimeError("CIRCUITPY_WIFI_SSID missing in settings.toml")

    while not wifi.radio.connected:
        status((255, 140, 0))
        try:
            wifi.radio.connect(ssid, password)
        except Exception as e:  # noqa: BLE001
            print("Wi-Fi connect failed:", e)
            status((255, 0, 0))
            time.sleep(3)

def sync_time(attempts=5):
    """Fetch UTC from NTP and set the RTC. Returns True on success."""
    for attempt in range(attempts):
        try:
            if not wifi.radio.connected:
                connect_wifi()
            status((0, 80, 255))  # blue-ish = fetching time
            pool = socketpool.SocketPool(wifi.radio)
            ntp = adafruit_ntp.NTP(pool, tz_offset=0)   # keep RTC in UTC
            rtc.RTC().datetime = ntp.datetime
            print("Time synced (UTC):", time.localtime())
            return True
        except Exception as e:  # noqa: BLE001
            print("NTP attempt", attempt + 1, "failed:", e)
            status((255, 0, 0))
            time.sleep(2)
    return False

# ----------------------------------------------------------------------
# Startup animations
# ----------------------------------------------------------------------
def color_wipe(color, delay=0.01):
    for i in range(NUM_PIXELS):
        pixels[i] = color
        pixels.show()
        time.sleep(delay)

def wipe_off(delay=0.005):
    for i in range(NUM_PIXELS):
        pixels[i] = OFF
        pixels.show()
        time.sleep(delay)

def comet(color, tail=12, laps=3):
    """A comet that accelerates around the dial."""
    total = NUM_PIXELS * laps
    for step in range(total):
        progress = step / total
        delay = 0.03 - 0.027 * progress          # speeds up
        pixels.fill(OFF)
        for t in range(tail):
            fade = (1 - t / tail) ** 2
            c = (int(color[0] * fade), int(color[1] * fade), int(color[2] * fade))
            pixels[(step - t) % NUM_PIXELS] = c
        pixels.show()
        time.sleep(delay)

def rainbow(duration=3.0):
    end = time.monotonic() + duration
    offset = 0
    while time.monotonic() < end:
        for i in range(NUM_PIXELS):
            pixels[i] = wheel(int(i * 256 / NUM_PIXELS) + offset)
        pixels.show()
        offset = (offset + 6) & 255
        time.sleep(0.01)

def settle_on_time(frames=120, frame_delay=0.02):
    """
    The three hands spin in and decelerate onto the *live* time.
    Targets are re-read every frame so the final frame is exactly correct.
    """
    for f in range(frames + 1):
        t = f / frames
        remaining = (1 - t) ** 3                 # ease-out cubic
        now = local_now()
        h_target = hour_center_for(now.tm_hour, now.tm_min)
        s_pos = (now.tm_sec - int(120 * remaining)) % NUM_PIXELS   # 2 laps
        m_pos = (now.tm_min - int(60 * remaining)) % NUM_PIXELS    # 1 lap
        h_pos = (h_target - int(45 * remaining)) % NUM_PIXELS
        render(h_pos, m_pos, s_pos)
        time.sleep(frame_delay)

def startup_animation():
    pixels.fill(OFF)
    pixels.show()
    color_wipe(COLOR_HOUR)
    color_wipe(COLOR_MIN)
    color_wipe(COLOR_SEC)
    wipe_off()
    comet((255, 255, 255))
    rainbow(3.0)
    wipe_off(0.003)
    settle_on_time()

# ----------------------------------------------------------------------
# Main program
# ----------------------------------------------------------------------
def main():
    pixels.fill(OFF)
    pixels.show()

    # 1. Network + time. Keep trying until we have a valid time.
    connect_wifi()
    while not sync_time():
        time.sleep(5)
    last_sync = time.monotonic()

    # 2. Show off.
    startup_animation()

    # 3. Run the clock.
    last_sec = -1
    while True:
        now = local_now()
        if now.tm_sec != last_sec:
            last_sec = now.tm_sec
            render(
                hour_center_for(now.tm_hour, now.tm_min),
                now.tm_min,
                now.tm_sec,
            )

        # Periodic re-sync (RP2040 RTC drifts slightly). Failure is non-fatal.
        if time.monotonic() - last_sync > RESYNC_SECONDS:
            if sync_time(attempts=2):
                last_sync = time.monotonic()
            else:
                last_sync = time.monotonic() - RESYNC_SECONDS + 300  # retry in 5 min
            last_sec = -1  # force redraw

        time.sleep(0.02)

try:
    main()
except Exception as e:  # noqa: BLE001
    # Last-resort recovery: flash red, then reboot.
    print("Fatal error:", repr(e))
    try:
        for _ in range(5):
            pixels.fill((255, 0, 0))
            pixels.show()
            time.sleep(0.3)
            pixels.fill(OFF)
            pixels.show()
            time.sleep(0.3)
    finally:
        time.sleep(5)
        microcontroller.reset()
