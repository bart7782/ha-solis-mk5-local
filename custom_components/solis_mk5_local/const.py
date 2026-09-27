"""Constants for the Solis MK5 Local integration."""

from homeassistant.const import Platform

DOMAIN = "solis_mk5_local"
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONF_PORT = "port"
CONF_STALE_AFTER = "stale_after_minutes"
CONF_SCAN_INTERVAL = "scan_interval_seconds"
CONF_HOST = "host"
CONF_LOGGER_SERIAL = "logger_serial"

DEFAULT_PORT = 5657
# After this many minutes without any frame (poll or push) the measurement
# sensors are marked unavailable, so stale power readings do not linger on
# dashboards all night. Kept well above the ~6 minute push interval, so the
# push can carry the sensors on its own if polling ever stops working.
DEFAULT_STALE_AFTER = 30

# Polling: the stick answers a data request on this TCP port. Measured on a
# GL17-07-261-D (firmware H4.01.51): its answer held new values on every
# request at a 10 s interval, so the stick reads the inverter at least that
# often. 0 disables polling; 1 to 4 is raised to MIN_SCAN_INTERVAL.
DEFAULT_SCAN_INTERVAL = 10
MIN_SCAN_INTERVAL = 5
POLL_PORT = 8899
# How long to wait for an answer. A healthy stick answers in ~0.3 s. For about
# 20 seconds, starting half a minute after each of its own pushes, it does
# not answer at all (one in five polls at a 10 s interval), and waiting
# longer does not change that.
POLL_TIMEOUT = 5
# The stick switches off with the inverter at night. After this many
# unanswered polls in a row, poll only every BACKOFF_INTERVAL seconds until a
# frame arrives again; the stick's first push in the morning ends the
# back-off immediately.
BACKOFF_AFTER_FAILURES = 30
BACKOFF_INTERVAL = 300

# "Live data" stays on while the newest frame is at most this many seconds
# old (or three poll intervals, whichever is longer). It has to ride out the
# stick's silent window after a push: two or three unanswered polls.
LIVE_WINDOW_MIN = 90

# Diagnostic measurements (temperature, grid and string values) are written
# at most this often, in seconds. Their values change on nearly every frame,
# so at a 10 s poll interval they would otherwise add some 40,000 database
# rows a day, at a resolution nobody needs. Power, energy and the last-update
# timestamp are never throttled.
DIAGNOSTIC_MIN_INTERVAL = 60

# Protect against a peer flooding us with garbage that never frames.
MAX_BUFFER_SIZE = 4096

# Consecutive rejected data frames before we assume the connected logger
# speaks an incompatible protocol variant and raise a repair issue about it.
INCOMPATIBLE_FRAME_THRESHOLD = 5

ISSUE_INCOMPATIBLE_LOGGER = "incompatible_logger"

# Where the stick address learned from its pushes is kept between restarts.
STORAGE_VERSION = 1
