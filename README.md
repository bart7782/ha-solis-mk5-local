# Solis MK5 Local

Lokale Home Assistant-integratie voor Solis/Ginlong omvormers met een
Wi-Fi stick logger. De stick stuurt zijn data rechtstreeks (via TCP) naar
Home Assistant — **zonder cloud, zonder polling, zonder extra hardware**.
Je gebruikt hiervoor een vrij "Remote Server"-slot van de stick, dus de
Solis-cloud en app blijven gewoon werken via het bestaande slot.

Het protocol is reverse-engineered op basis van raw captures van een stick
met hardware `GL17-07-261-D` en firmware `H4.01.51`; alle veldposities zijn
gevalideerd tegen de eigen webinterface van de logger.

## Sensoren

| Sensor | Eenheid | Opmerking |
|---|---|---|
| Vermogen | W | actueel AC-vermogen |
| Opbrengst vandaag | kWh | geschikt voor het Energy Dashboard |
| Opbrengst totaal | kWh | geschikt voor het Energy Dashboard |
| Omvormertemperatuur | °C | |
| Netspanning / netstroom / netfrequentie | V / A / Hz | diagnostisch |
| DC-spanning en -stroom string 1 en 2 | V / A | per MPPT-string, diagnostisch |
| Laatste update | timestamp | met de raw hex van het laatste frame als attribuut |

De data wordt door de stick gepusht, ongeveer elke 6 minuten.

## Installatie via HACS

Deze repository staat niet in de standaard HACS-lijst, dus voeg 'm toe als
custom repository:

1. Open HACS in Home Assistant.
2. Klik rechtsboven op de drie puntjes > "Custom repositories".
3. Vul bij Repository `https://github.com/bart7782/ha-solis-mk5-local` in
   en kies als categorie "Integration".
4. Klik "Add", zoek daarna naar "Solis MK5 Local" in HACS en klik "Download".
5. Herstart Home Assistant.

## Installatie (handmatig, zonder HACS)

1. Kopieer de map `custom_components/solis_mk5_local` naar de
   `custom_components` map van je Home Assistant configuratie.
2. Herstart Home Assistant.

## Configuratie

1. Instellingen > Apparaten en Diensten > Integratie toevoegen >
   "Solis MK5 Local".
2. Vul een vrije TCP-poort in, bijvoorbeeld 5657 (moet anders zijn dan de
   poorten die al in gebruik zijn).
3. Ga naar de webinterface van je Solis logger, Advanced > Remote server,
   en zet in een **vrij** slot (bijvoorbeeld Server C):
   - IP address: het IP-adres van je Home Assistant server
   - Port: dezelfde poort als in stap 2
   - Connection: TCP
4. Sla op en herstart de logger. Binnen ~6 minuten verschijnt de data.

Via "Opties" op de integratie stel je in na hoeveel minuten stilte de
meetsensoren als "niet beschikbaar" worden gemarkeerd (standaard 30).

## Goed om te weten

- **'s Nachts** gaat de omvormer uit en stopt de stick met sturen. De
  meetsensoren (vermogen, spanningen, stromen) worden dan "niet
  beschikbaar"; de energiesensoren houden hun laatste waarde vast en
  overleven ook een herstart van Home Assistant.
- **Energy Dashboard**: gebruik "Opbrengst vandaag" of "Opbrengst totaal"
  als zonneproductie-bron.
- **Voorbeeld-dashboard**: in
  [`examples/solar-dashboard.yaml`](examples/solar-dashboard.yaml) staat een
  compleet zonne-dashboard (vermogensmeter, opbrengst per dag, verloop,
  MPPT-strings en netdiagnostiek) dat je via de Raw configuratie-editor kunt
  plakken. Vervang wel eerst de entity-ID's door die van jouw installatie —
  zie de toelichting bovenin het bestand.
- **Frames met een afwijkende indeling** (andere firmware/hardware) worden
  niet stilletjes verkeerd geparsed: elk frame wordt gevalideerd op
  checksum, lengte en plausibiliteit. Afgekeurde frames verschijnen met
  volledige hex dump in het log — maak daarmee gerust een issue aan.
- Debug logging aanzetten kan met:

  ```yaml
  logger:
    logs:
      custom_components.solis_mk5_local: debug
  ```

## Kom je van "Solis Raw Packet Capture"?

Versie 1.0.0 vervangt de tijdelijke raw-capture-debugtool uit deze repo.
Na het updaten via HACS:

1. Verwijder de oude "Solis Raw Packet Capture"-integratie bij
   Instellingen > Apparaten en Diensten.
2. Herstart Home Assistant.
3. Voeg "Solis MK5 Local" toe (zelfde poort hergebruiken kan gewoon).

## Protocoldocumentatie

Voor wie zelf wil hacken: de stick opent elke ~6 minuten een verbinding en
stuurt één burst met twee frames (`0x68 ... 0x16`, checksum = som van alle
bytes na de startbyte modulo 256):

- een **dataframe** van 103 bytes (controlecode `51 b0`) met de telemetrie;
- een **infoframe** van 55 bytes (controlecode `51 b1`) met de
  firmwareversies en het hardwaremodel als ASCII.

De volledige byte-map staat gedocumenteerd in
[`protocol.py`](custom_components/solis_mk5_local/protocol.py), en
[`tests/test_protocol.py`](tests/test_protocol.py) bevat echte captures met
de bijbehorende verwachte waarden. Tests draaien zonder Home Assistant:

```
python tests/test_protocol.py
```

## Credits

Geïnspireerd door het reverse-engineering-werk van
[planetmarshall/solis-service](https://github.com/planetmarshall/solis-service),
[Rapsssito/local-solis-ginglong-inverter](https://github.com/Rapsssito/local-solis-ginglong-inverter)
en [avlemos/ha_solis_server](https://github.com/avlemos/ha_solis_server).
Deze stick-generatie (MK5, `GL17-...`) spreekt een ouder protocol dan die
integraties ondersteunen; vandaar deze aparte implementatie.
