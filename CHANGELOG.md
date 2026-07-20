# Changelog

All notable changes to this project are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.0.0]: https://github.com/bart7782/ha-solis-mk5-local/releases/tag/v1.0.0
