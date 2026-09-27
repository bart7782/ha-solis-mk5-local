# Changelog

All notable changes to this project are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-09-27

Home Assistant now asks the stick for its data every 10 seconds, instead of
waiting for the push every ~6 minutes. Nothing to configure: existing
installs keep their entities, entity ids and history.

### Added
- **Polling** on TCP port 8899, every 10 seconds by default (0 = off). The
  stick's IP address and serial are learned from its pushes and remembered
  across restarts, so polling starts at the first push and follows the stick
  to a new IP address. For a stick that does not push, both can be set in the
  options.
- **"Live data" binary sensor**: on while the newest reading is at most 90
  seconds old. Meant for automations that act on solar power.
- **Diagnostics download** with the poll target, poll statistics and the last
  raw frame.
- Polling slows down to once every 5 minutes after 30 unanswered polls (the
  stick is off at night) and speeds up again at the first frame.

### Changed
- Diagnostic readings (temperature, grid and string values) are written at
  most once a minute, to keep the database small at the new pace.
- "Last update" carries `source` (`poll` or `push`) as its attribute instead
  of the raw frame hex, which moved to the diagnostics download: with a new
  frame every 10 seconds, that attribute cost a database row each time.
- `iot_class` is now `local_polling`.

## [1.0.0] - 2026-07-20

First public release. Local, push-based Home Assistant integration for
Solis/Ginlong inverters with an MK5 (`GL17-...`) Wi-Fi stick logger — no
cloud, no polling, no extra hardware.

### Added
- **Local push over TCP.** The stick sends data straight to Home Assistant
  via a free "Remote Server" slot, so the Solis cloud and app keep working
  through their existing slot.
- **Sensors:** AC power, yield today, yield total (both Energy Dashboard
  ready), inverter temperature, grid voltage/current/frequency, per-string
  DC voltage and current, and a "Last update" timestamp that carries the raw
  frame hex as an attribute.
- **Robust frame validation.** Every frame is checked on start/end markers,
  checksum, length and value plausibility, so a different protocol variant is
  never silently parsed into wrong readings.
- **Repairs entry for incompatible loggers.** After several rejected frames
  in a row, a Repairs issue points out that the connected logger speaks an
  unrecognised protocol, instead of just failing quietly.
- **Survives nights and restarts.** Energy totals keep their value while the
  inverter is off overnight and are restored after a Home Assistant restart;
  live measurements go unavailable after a configurable staleness window.
- **Config & options flow.** Pick the listening port (with in-use detection)
  and tune the staleness window from the UI.
- **HACS support** and an example solar dashboard
  ([`examples/solar-dashboard.yaml`](examples/solar-dashboard.yaml)).
- English and Dutch translations.

### Notes
- Reverse-engineered and validated against a stick with hardware
  `GL17-07-261-D` and firmware `H4.01.51`. Different logger generations may
  use a different frame layout — if yours does, the Repairs entry and the
  "Unsupported logger" issue template explain how to report it.

[1.1.0]: https://github.com/bart7782/ha-solis-mk5-local/releases/tag/v1.1.0
[1.0.0]: https://github.com/bart7782/ha-solis-mk5-local/releases/tag/v1.0.0
