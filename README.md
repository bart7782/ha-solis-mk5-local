# Solis Raw Packet Capture (debug tool)

Doel: exact vastleggen wat jouw Solis/Ginlong stick daadwerkelijk over de
lijn stuurt, zonder enige aanname over headerformaat of paketlengte. Dit
is een tijdelijk hulpmiddel om data te verzamelen voor het bouwen van een
op maat gemaakte parser, geen permanente oplossing.

## Installatie via HACS

Deze repository staat niet in de standaard HACS-lijst, dus voeg 'm toe als
custom repository:

1. Open HACS in Home Assistant.
2. Klik rechtsboven op de drie puntjes > "Custom repositories".
3. Vul bij Repository `https://github.com/bart7782/ha-solis-mk5-local` in
   en kies als categorie "Integration".
4. Klik "Add" en zoek daarna naar "Solis Raw Packet Capture" in HACS,
   en klik "Download".
5. Herstart Home Assistant.
6. Ga verder bij "Instellingen > Apparaten en Diensten" hieronder.

## Installatie (handmatig, zonder HACS)

1. Kopieer de map `custom_components/solis_raw_capture` naar de
   `custom_components` map van je Home Assistant configuratie.
2. Herstart Home Assistant.

## Instellingen > Apparaten en Diensten

1. Instellingen > Apparaten en Diensten > Integratie toevoegen >
   "Solis Raw Packet Capture".
2. Vul een vrije poort in, bijvoorbeeld 5658 (moet anders zijn dan de
   poorten die je al gebruikt voor Server A/B).

## De logger erop wijzen

Ga naar de webinterface van je Solis logger, Advanced > Remote server,
en zet in een vrij slot (bijvoorbeeld Server C):

- IP address: het IP adres van je Home Assistant server
- Port: dezelfde poort die je in stap 4 hebt ingevuld
- Connection: TCP

Sla op en herstart de logger.

## Data verzamelen

Elke keer dat er een pakket binnenkomt, verschijnt in de Home Assistant
log (zet desnoods debug logging aan voor
`custom_components.solis_raw_capture`) een regel met de volledige hex
dump en het aantal bytes. Er verschijnt ook een sensor entiteit
`sensor.solis_raw_capture_last_packet` met de laatste hex dump als
attribuut, te bekijken via Developer Tools > States.

Noteer bij een paar opeenvolgende pakketten ook de waarden die op dat
moment op de "Connected Inverter" pagina van de logger's eigen
webinterface staan (vermogen, spanning, temperatuur). Die bekende
waarden zijn het ijkpunt om straks de juiste byte posities in de hex
dump terug te vinden.

## Daarna

Zodra je een paar hex dumps hebt, samen met de bijbehorende bekende
waarden, kan daarmee een exacte parser gebouwd worden die precies bij
deze stick/firmware past, in plaats van te gokken op basis van
andermans hardware.

## Onderhoud (voor HACS)

HACS leest updates uit GitHub releases. Verhoog bij een wijziging de
`version` in `custom_components/solis_raw_capture/manifest.json` en
maak een bijpassende git tag + GitHub release aan (bijvoorbeeld `v0.1.0`),
anders ziet HACS geen nieuwe versie.
