# DigilogClock
Digital clock displayed in an analog format

60-LED Ring/Strip Clock for Pico W

Written in CircuitPython

What it does:

Connects to Wi-Fi and gets the time from NTP, retrying until it succeeds.

Plays a startup sequence: color wipes, an accelerating comet, a rainbow, and finally the three "hands" spinning in and settling on the live time.

Runs the clock:

Seconds: 1 LED, blue

Minutes: 1 LED, green      #I have commented out code for 2 LEDs, but I didn't use it as it looked strange

Hours: 3 LEDs, red, centered on the hour position (12-hour dial, 5 LEDs per hour, creeping forward with the minutes)

Overlapping LEDs blend additively, so every hand stays visible.

Re-syncs with NTP every 6 hours and recovers from errors by resetting.

Required libraries:

Copy these from the CircuitPython library bundle into CIRCUITPY/lib:

neopixel.mpy

adafruit_ntp.mpy

adafruit_ticks.mpy (a dependency of newer adafruit_ntp versions)

Notes:

Power: Power the strip from a proper 5 V supply and connect its ground to the Pico's ground.

Ideally add a level shifter (3.3 V → 5 V) on the data line and a 300–500 Ω resistor in series.

The default brightness of 0.15 keeps current draw modest.

Colors look wrong? Change PIXEL_ORDER to neopixel.RGB.

Hour hand: With SMOOTH_HOURS = True the 3-LED hour marker shifts one LED every 12 minutes. Set it to False to make it jump in 5-LED steps.

Startup colors: During boot, amber means connecting to Wi-Fi, blue means fetching time, and red means a failure that is being retried.

Time storage:

The RTC stores UTC, and local time plus DST is computed on the fly. DST changes are therefore handled automatically without re-syncing.
