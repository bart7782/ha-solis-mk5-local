"""Constants for the Solis Raw Capture debug integration."""

DOMAIN = "solis_raw_capture"
CONF_PORT = "port"
DEFAULT_PORT = 5657
# How long to wait for more bytes on the same connection before treating
# the current burst as "complete" and logging it. The stick may send its
# message in more than one TCP write, so we don't cut it off too early.
IDLE_TIMEOUT_SECONDS = 4.0
