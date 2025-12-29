# FilamentDry+Pro

![FilamentDry+Pro Logo](logo.png)

Ein Filament-Trockenschrank, der darauf optimiert ist, **ein kleines Volumen zuverlässig auf <20% rF** zu bringen – nicht auf maximale Entfeuchtungsleistung in "l/h", sondern darauf, **auch bei sehr trockener Luft weiter sinnvoll zu entfeuchten**.

Das Projekt basiert auf einem IKEA Billy mit Vitrinentüren und einem Entfeuchter-/Kälteplatten-Konzept (Peltier + Abtau-/Pump-Zyklus), gesteuert über ESPHome (ESP32 / KC868-A16) und integriert in Home Assistant.

> Hinweis: Teile der Dokumentation (z.B. Details zur Leckflächen-Messmethode) sind bewusst als "wird noch genauer erklärt" markiert – das ist so vorgesehen.

---

## Warum <20% rF im Schrank nicht "einfach" ist

Unter 20% relativer Luftfeuchte (rF) in einem Schrank zu landen ist deutlich anspruchsvoller, als es zunächst klingt:

- **Alle Ritzen müssen dicht sein.** Ich bin nach meiner Messmethode bei einer effektiven offenen Fläche von **<100 mm²** gelandet (wie ich das genau gemessen habe, beschreibe ich noch ausführlicher).
- Der **Entfeuchter muss extrem kleine Wassermengen** handhaben können (z.B. **pro Lauf <0,5 ml** Kondensat), weil bei sehr trockener Luft schlicht nicht mehr viel Wasser pro Zyklus anfällt.
- Der **Taupunkt** rutscht schnell **unter 0°C** – d.h. der Kältebereich vereist, und man braucht eine durchdachte **Defrost-/Abtau-Strategie**.
- Ziel ist nicht "viel Wasser pro Stunde", sondern **ein kleines, sehr dichtes Volumen auch bei <20% rF weiter zu trocknen**.

---

## Mechanischer Aufbau (Schrank)

- Basis ist ein **IKEA Billy** mit passenden **Vitrinentüren**.
- Die Rückwand ist mit **XPS-Hartschaum (extrudierter Polystyrol-Hartschaum, z.B. Styrodur)** gedämmt.
- Innen ist alles mit **alu-beschichteter Dekorfolie** abgeklebt.

### Abdichtung der Türen (kritischster Punkt)

Die Türen sind mit einer **D-Dichtung** abgedichtet. Das ist die kritischste Stelle – Sorgfalt ist hier besonders wichtig:

- Jedes kleine Loch zieht unnötig viel feuchte Luft nach.
- Ich habe zusätzliche Teile gedruckt, um **zwischen den Türen** eine Dichtung anzubringen.
- Mit einer Dichtung als Anschlag auf der anderen Tür hatte ich **keinen zufriedenstellenden Erfolg**.

---

## Zusätzlich: Heizer für "alles auf einmal"

Zusätzlich ist ein **Heizer** vorgesehen, um sehr einfach **alle Filamente (ca. 60 Rollen) auf einmal zu trocknen**.
So wird billiges oder altes Filament plötzlich wieder problemlos druckbar.

---

## Dichtigkeit messen (Leckfläche)

Ich messe die Dichtigkeit über:

- einen **Durchflussmesser** (max. 35 l/min)
- den **Differenzdruck** zwischen innen und außen

Über Durchfluss und Differenzdruck kann ich auf die **äquivalente offene Fläche** schließen.

### Formel

Als Näherung (Orifice-/Düsenmodell) kann man verwenden:

$$Q = C_d \cdot A \cdot \sqrt{\frac{2\,\Delta p}{\rho}}$$

- $Q$ = Volumenstrom [$m^3/s$]
- $A$ = äquivalente Leckfläche [$m^2$]
- $\Delta p$ = Differenzdruck [Pa]
- $\rho$ = Dichte von Luft (typisch ca. $1{,}2\,kg/m^3$)
- $C_d$ = Abflussbeiwert (typisch grob $0{,}6$ als Näherung)

Umgestellt nach $A$:

$$A = \frac{Q}{C_d \cdot \sqrt{\frac{2\,\Delta p}{\rho}}}$$

### Beispielrechnung (15 l/min bei 10 Pa)

- $Q = 15\,l/min = 0{,}015\,m^3/min \approx 0{,}00025\,m^3/s$
- $\Delta p = 10\,Pa$
- $\rho \approx 1{,}2\,kg/m^3$
- $C_d \approx 0{,}6$

$$\sqrt{\frac{2\,\Delta p}{\rho}} = \sqrt{\frac{20}{1{,}2}} \approx 4{,}08$$

$$A \approx \frac{0{,}00025}{0{,}6 \cdot 4{,}08} \approx 1{,}02\cdot10^{-4}\,m^2 \approx 102\,mm^2$$

### Zusammenhang (Intuition)

- Bei gleicher Leckgeometrie gilt grob: $Q \propto A \cdot \sqrt{\Delta p}$.
- Heißt: doppelte Leckfläche → ungefähr doppelter Durchfluss; vierfacher Druck → ungefähr doppelter Durchfluss.
- In der Praxis ist $C_d$ nicht exakt bekannt und die Strömung kann komplex sein – als Vergleichs-/Debug-Tool funktioniert es aber sehr gut.

### Was ich damit herausgefunden habe

- **Glasscheiben in den Rahmen sind undicht** → unbedingt mit **Silikon** abdichten.
- **Tape außen am Schrank** hilft quasi nicht → besser **innen abkleben** oder **silikonisieren**.

---

## Elektronik & Steuerung (ESPHome / Home Assistant)

Die Steuerung läuft auf einem **ESP32** (Board: `esp32dev`) und ist als **ESPHome-Node** in Home Assistant eingebunden (API mit Encryption).

### Sensorik

- **SHT3x** am I²C (Temp + rF)
- **Absolute Feuchte** als berechneter Sensor
- **DS18B20** am 1‑Wire Bus (u.a. Kaltplatte + Heißseite)
- **LD2412 Radar** über UART (Präsenz, Telemetrie)
- **Türkontakt** über PCF8574 Input

### Aktoren

- Peltier-Leistungsstufe (Enable/slow PWM)
- Lüfter Kaltseite (slow PWM)
- Lüfter Heißseite (GPIO/PCF8574)
- Peristaltikpumpe (GPIO/PCF8574)
- Innenlicht (GPIO/PCF8574)
- Zusatzlüfter (GPIO/PCF8574)

### Logik: State Machine

Die Entfeuchtung läuft als State Machine mit den Zuständen:

- `IDLE`
- `COOLING`
- `DEFROST`
- `PUMP`

Wichtige Punkte:

- Start/Stop über relative Feuchte (`rh_start` / `rh_stop`)
- Solltemperatur der Kaltplatte (`t_cold_soll`) mit einfacher Regelung
- Defrost-Ende über Kaltplatten-Temperatur (`t_defrost_end`) und zusätzlich:
  - Max. Cooling-Dauer (`t_cool_max`)
  - Eis-Heuristik über Temperaturabweichung (`delta_t_ice`, `t_ice_min`)
- Pumpdauer im Pump-State (`t_pump`)
- Übertemperatur-Schutz Heißseite (`t_hot_max`) → Fault (gelatcht)
- Türlogik: State Machine läuft weiter, aber bei offener Tür wird **nur** der Zusatzlüfter sofort aus gemacht
- Auto-Licht: Radar/Tür + Hold-Timer (`t_light_hold`)

### Home Assistant Entities

ESPHome erzeugt die Entities automatisch; die Entity-IDs sind dabei in der Regel nach dem Muster:

- `domain.<node>_<name>`

Also z.B. (bei `devicename: filament-dryer`):

- `switch.filament_dryer_peltier_enable`
- `number.filament_dryer_t_pump`
- `sensor.filament_dryer_rh`

Wenn du stattdessen unbedingt `number.t_pump_<devicename>` (Gerätename hinten) willst, ist das in ESPHome nicht sauber erzwingbar – das macht man am zuverlässigsten über die **Entity Registry** in Home Assistant.

---

## Konfiguration / Inbetriebnahme

- ESPHome (z.B. als Home-Assistant Add-on) installieren
- `filamentdrypro.yaml` als Node-Konfiguration verwenden
- `secrets.yaml` anlegen (wird per `.gitignore` ausgeschlossen)

Beispiel-Struktur (Platzhalter):

```yaml
wifi_ssid: "..."
wifi_password: "..."
esp_password: "..."
api_key: "..."  # ESPHome API encryption key
ota_password: "..."
```

Wichtige Stellen in der YAML:

- `substitutions.devicename` / `friendly_name`
- DS18B20 `address` (Kalt/Heißseite) an deine Sensoren anpassen
- Pin-/I²C-/PCF8574-Addresses entsprechen dem KC868-A16 Setup

---

## Danksagung / Meta

Ein Teil der YAML-Aufräumarbeiten (Entity-Definitionen, IDs, Validierung) und das Rundschleifen dieser README wurde von **GitHub Copilot (GPT-5.2)** unterstützt.

---

## Sicherheit

Achtung: Je nach Netzteil/Heizer/Peripherie sind hier Ströme/Spannungen im Spiel, die gefährlich sein können. Elektrik nur fachgerecht ausführen und absichern.
