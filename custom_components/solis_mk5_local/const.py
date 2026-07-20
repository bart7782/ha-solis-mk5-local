"""Constants for the Solis MK5 Local integration."""

from homeassistant.const import Platform

DOMAIN = "solis_mk5_local"
PLATFORMS = [Platform.SENSOR]

CONF_PORT = "port"
CONF_STALE_AFTER = "stale_after_minutes"

DEFAULT_PORT = 5657
# The stick pushes a data burst roughly every 6 minutes. After this many
# minutes of silence the measurement sensors are marked unavailable so
# stale power readings do not linger on dashboards all night.
DEFAULT_STALE_AFTER = 30

# Protect against a peer flooding us with garbage that never frames.
MAX_BUFFER_SIZE = 4096

# Consecutive rejected data frames before we assume the connected logger
# speaks an incompatible protocol variant and raise a repair issue about it.
INCOMPATIBLE_FRAME_THRESHOLD = 5

ISSUE_INCOMPATIBLE_LOGGER = "incompatible_logger"
