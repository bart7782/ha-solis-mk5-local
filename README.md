# Solis MK5 Local

> **Note:** All code in this repository was written with AI assistance. I
> built this for my own use on my own installation, and I'm sharing it in
> case it's useful to others too. It is based on two other open-source
> repositories as a starting point (see Credits below).

Local Home Assistant integration for Solis/Ginlong inverters with a Wi-Fi
stick logger — **no cloud, no extra hardware**. Home Assistant asks the
stick for fresh data every 10 seconds, and the stick also pushes its data to
Home Assistant every ~6 minutes through a free "Remote Server" slot. The
Solis cloud and app keep working as usual through their own slot.

The protocol was reverse-engineered from raw captures of a stick with
hardware `GL17-07-261-D` and firmware `H4.01.51`; all field positions have
been validated against the logger's own web interface.

<img src="docs/images/ginlong-stick.jpg" alt="Ginlong Technologies Wi-Fi stick logger mounted under the inverter's terminal cover" width="360">

The stick this integration targets: a Ginlong Technologies Wi-Fi logger
plugged directly into the communication port under the inverter's terminal
cover, next to the DC switch. If your stick looks like this, it's very
likely the same protocol.

## Sensors

The device page in Home Assistant, showing the live sensors and diagnostics
this integration exposes:

![Solis MK5 Local device page in Home Assistant showing sensors and diagnostics](docs/images/device-page.png)

| Sensor | Unit | Note |
|---|---|---|
| Power | W | current AC power |
| Yield today | kWh | suitable for the Energy Dashboard |
| Yield total | kWh | suitable for the Energy Dashboard |
| Inverter temperature | °C | |
| Grid voltage / grid current / grid frequency | V / A / Hz | diagnostic |
| DC voltage and current string 1 and 2 | V / A | per MPPT string, diagnostic |
| Last update | timestamp | with `source` (`poll` or `push`) as attribute |
| Live data | on/off | on while the newest reading is at most 90 s old |

Power, the energy totals and "Last update" change with every reading (every
10 seconds while polling works). The diagnostic readings (temperature, grid
and string values) are written at most once a minute: they change on nearly
every reading, and at full speed they would add some 40,000 database rows a
day at a resolution nobody needs.

"Live data" is meant for automations that act on solar power, such as
switching on a load when there is a surplus: only trust the power reading
while it is on.

## How the data arrives

- **Polling (main source).** Every 10 seconds Home Assistant asks the stick
  for its current data on TCP port 8899. On the reference stick the answer
  held new values on every request, and arrived in ~0.3 s. For about 20
  seconds, starting half a minute after each of its own pushes, the stick
  does not answer; the integration simply keeps the previous reading. When
  the stick switches off with the inverter at night, polling slows down to
  once every 5 minutes until the stick is back.
- **Push (fallback, and how the stick is found).** The stick's own push
  still arrives every ~6 minutes. Every push carries the stick's serial
  number and comes from its current IP address, which is all polling needs.
  So there is nothing to configure: polling starts at the first push, and
  when the stick gets a new IP address, the next push tells the integration.
  If polling ever stops working, the push keeps the sensors going (at the
  old ~6 minute pace).

## Installation via HACS

This repository is not in the default HACS list, so add it as a custom
repository:

1. Open HACS in Home Assistant.
2. Click the three dots in the top right > "Custom repositories".
3. Enter `https://github.com/bart7782/ha-solis-mk5-local` as the Repository
   and choose "Integration" as the category.
4. Click "Add", then search for "Solis MK5 Local" in HACS and click
   "Download".
5. Restart Home Assistant.

## Installation (manual, without HACS)

1. Copy the `custom_components/solis_mk5_local` folder to the
   `custom_components` folder of your Home Assistant configuration.
2. Restart Home Assistant.

## Configuration

1. Settings > Devices & Services > Add Integration > "Solis MK5 Local".
2. Enter a free TCP port, for example 5657 (must differ from any ports
   already in use).
3. Go to your Solis logger's web interface, Advanced > Remote server, and
   set a **free** slot (for example Server C) to:
   - IP address: the IP address of your Home Assistant server
   - Port: the same port as in step 2
   - Connection: TCP
4. Save and restart the logger. Data will appear within ~6 minutes, and
   every 10 seconds from then on.

> **Running Home Assistant in Docker?** The chosen port must be published to
> the host (e.g. `-p 5657:5657`) or the stick cannot reach it. Home Assistant
> OS and Supervised installs need no extra step.

Via "Options" on the integration you can set:

- **Poll interval** in seconds (default 10, 0 switches polling off, minimum 5).
- **Staleness window**: after how many minutes without any data the
  measurement sensors are marked "unavailable" (default 30, so the push
  alone can still carry them).
- **Stick IP address and serial number**: only for a stick that does not
  push to Home Assistant. The serial is the number in the stick's own Wi-Fi
  network name (`AP_<serial>`). Leave both empty when the push is set up: a
  filled-in IP address is not followed when the stick moves to a new one.
  The form shows what the integration learned from the pushes.

Give the stick a fixed IP address (a DHCP reservation in your router) if you
can. It is not required, but it avoids a few minutes without polling after
an address change.

## Troubleshooting

**No data after ~10 minutes?** Work through this list:

1. **Right IP and port?** In the logger's web interface, double-check the
   Remote Server slot points at your Home Assistant IP and the exact port you
   entered when adding the integration.
2. **Free slot used?** Use a slot that isn't already taken by the Solis cloud
   (typically Server A). Overwriting the cloud slot breaks the app; use a free
   one (e.g. Server C) instead.
3. **Same network / reachable?** The stick must be able to open a TCP
   connection to Home Assistant. Check firewalls and, for Docker, that the
   port is published (see the note above).
4. **Logger restarted?** Some loggers only apply Remote Server changes after a
   reboot. Restart it (or power-cycle the inverter) and wait ~6 minutes.
5. **Only every ~6 minutes, not every 10 seconds?** Then polling does not
   work. Download the diagnostics (Settings > Devices & services > Solis MK5
   Local > three dots > Download diagnostics) and look at `poll_target` and
   `poll_stats`. `poll_target` empty: no push has arrived yet since the
   integration started, and no IP address and serial are set in the options.
   Many unanswered polls: check that TCP port 8899 of the stick is reachable
   from Home Assistant.
6. **Still nothing?** Enable debug logging (below) and look for
   "Connection opened from ..." lines. If you see connections but no parsed
   data, the logger likely speaks a different protocol variant — please open
   an issue using the "Unsupported logger" template.

## Reporting an unsupported logger

If a Repairs entry appears (Settings > System > Repairs) saying the logger
sends an unrecognised protocol, or connections arrive but no sensors fill in,
your stick is probably a different generation than the one this was built for.
That's fixable with a few captured frames:

1. Enable debug logging (see below).
2. Wait for a couple of pushes so a few frames are logged.
3. Open an issue with the
   [Unsupported logger template](https://github.com/bart7782/ha-solis-mk5-local/issues/new?template=unsupported_logger.yml)
   and paste the hex lines, plus the readings from the logger's own web page
   at that moment so the byte positions can be checked.

## Good to know

- **At night** the inverter powers off and the stick stops sending. The
  measurement sensors (power, voltages, currents) then become
  "unavailable" after the staleness window; the energy sensors keep their
  last value and also survive a Home Assistant restart. "Live data" goes
  off 90 seconds after the last reading.
- **Energy Dashboard**: use "Yield today" or "Yield total" as your solar
  production source.
- **Example dashboard**: [`examples/solar-dashboard.yaml`](examples/solar-dashboard.yaml)
  contains a complete solar dashboard (power gauge, yield per day, history,
  MPPT strings and grid diagnostics) that you can paste in via the Raw
  configuration editor. Make sure to replace the entity IDs with those of
  your own installation first — see the notes at the top of the file.
- **Frames with a different layout** (different firmware/hardware) are not
  silently parsed incorrectly: every frame is validated on checksum,
  length and plausibility. Rejected frames appear with a full hex dump in
  the log. If several frames in a row get rejected, the integration raises
  a Repairs entry (Settings > System > Repairs) so it's clear the connected
  logger is speaking a variant this integration doesn't recognise, instead
  of silently doing nothing.
- Enable debug logging with:

  ```yaml
  logger:
    logs:
      custom_components.solis_mk5_local: debug
  ```

## Protocol documentation

<img src="docs/images/solis-inverter-manual.png" alt="Cover of the Solis Single Phase Inverter installation and operation manual" width="280">

Developed and tested against a Solis single-phase grid-tie inverter (the
manual pictured above), paired with the Ginlong stick shown earlier — this
is the exact hardware combination the byte map below was reverse-engineered
from.

For those who want to hack on this themselves: the stick opens a connection
roughly every 6 minutes and sends one burst with two frames (`0x68 ... 0x16`,
checksum = sum of all bytes after the start byte modulo 256):

- a **data frame** of 103 bytes (control code `51 b0`) with the telemetry;
- an **info frame** of 55 bytes (control code `51 b1`) with the firmware
  versions and the hardware model as ASCII.

It also answers a 16-byte request on TCP port 8899,
`68 02 40 30 <serial x2> 01 00 <checksum> 16`, with the same data frame and a
short acknowledgement frame (`51 f0`, "DATA SEND IS OK"). The serial is the
logger's serial number as a 32-bit little-endian number, the same one that
sits at bytes 4-11 of every frame it sends.

The full byte map is documented in
[`protocol.py`](custom_components/solis_mk5_local/protocol.py), and
[`tests/test_protocol.py`](tests/test_protocol.py) contains real captures
with their expected values; [`tests/test_poller.py`](tests/test_poller.py)
runs the poller against a fake stick. Tests run without Home Assistant:

```
python tests/test_protocol.py
python tests/test_poller.py
```

## Credits

Inspired by the reverse-engineering work of
[planetmarshall/solis-service](https://github.com/planetmarshall/solis-service)
and [Rapsssito/local-solis-ginglong-inverter](https://github.com/Rapsssito/local-solis-ginglong-inverter),
with additional reference from
[avlemos/ha_solis_server](https://github.com/avlemos/ha_solis_server).
This stick generation (MK5, `GL17-...`) speaks an older protocol than those
integrations support; hence this separate implementation.
