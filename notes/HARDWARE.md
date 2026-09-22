# This car — ground truth

One car, one file. Everything here is either **confirmed** on this unit or
marked **unknown**. Do not copy values in from `picar_freenove_fastapi/AGENTS.md`
§2: that section describes a *different, already-calibrated* car, and its own
scope note says so.

Update this file whenever a probe answers a question. Date every change.

## Kit

| | |
|---|---|
| Kit | Freenove 4WD Smart Car Kit for Raspberry Pi — docs code **FNK0043** |
| Wheels | **Mecanum** — confirmed 2026-08-27 by the operator |
| Follow which tutorial | `Tutorial(mecanum_wheels).pdf`, not the ordinary-wheels one |
| Battery | 2x 18650 Li-ion, button-top unprotected, 10 A+ discharge. Charged. |

Mecanum has two consequences worth stating up front:

- The rollers must form an **X** seen from above. Mounted wrong, a strafe comes
  out as a rotation — and a forward-only test cannot detect it.
- `wheel_type: "mecanum"` is already the FastAPI stack's default
  (`config.py:82`), so `/mecanum` will accept `vy`. Nothing to change, but it
  does mean a bad mount produces motion rather than an error.

## Raspberry Pi

| | |
|---|---|
| Model | **Raspberry Pi 4 Model B Rev 1.5** |
| OS | **Debian 13 (trixie)**, kernel 6.18.34+rpt-rpi-v8, python 3.13.5, aarch64 |
| Hostname / user | `raspberrypi.local` / `rafathebuilder` (192.168.86.137 on the home Wi-Fi) |
| Enabled as of 2026-08-22 | I²C, SPI, wayvnc on `:5900` |
| Kit repo on the Pi | `~/Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi` |
| sudo | still prompts for a password — long `apt` runs are done by the operator in a terminal, not over an agent's SSH |

The Pi model is not a detail: it decides whether Connect Version 1 is even
possible (it is not, on a Pi 5). See `version-puzzle.md`.

## Version fields

| Field | Value | Confidence |
|---|---|---|
| `Pi_Version` | **1** | derived: Pi 4B is not a Pi 5 |
| `Connect_Version` | **2** | **confirmed** — the LED test lights the strip |
| `Pcb_Version` | **2** | operator; affects only the battery number |

Set them with `tools/pi params 2 2`, then `tools/pi params-check`.

**Why Connect_Version 2 is inferred rather than known.** The operator identified
the board as "v2" from Freenove's photos, which are of the *connection board* —
and the connection board's revision is what the code calls `Connect_Version`,
not `Pcb_Version`. SPI being already enabled on this Pi points the same way; the
tutorial says to turn SPI *off* for a v1 board. But a Pi 4B accepts both values
in `led.py`, so a wrong guess produces a dark strip and no error message.
`tools/pi led-probe` is what turns this into a fact.

## Test results

| Freenove test | Result | Date |
|---|---|---|
| `Motor` | **pass** — all four wheels physically spun | 2026-08-27 |
| `Led` | **pass** | 2026-08-27 |
| `Ultrasonic` | **pass** | 2026-08-27 |
| `Infrared` | **pass** | 2026-08-27 |
| `Servo` | **pass** after re-seating the servo connectors | 2026-08-27 |
| `ADC` | **pass** as of 2026-09-18 — 0x48 answers, reads battery and both photoresistors | 2026-09-18 |
| `Buzzer` | **pass** | 2026-08-27 |
| camera | **pass** after re-seating the CSI ribbon (no `Camera` case in test.py) | 2026-08-27 |

**Bring-up complete 2026-08-27.** Every Freenove module test passes except
`ADC`, and the camera captures. The one outstanding fault is the ADS7830 (see
below) — a board fault, not a configuration problem.

## Calibration owed to this unit

None of these are known yet. The FastAPI stack's selftest derives each one and
writes it to `/etc/yakrobot/unit.json`; nothing below should be hand-edited into
`config.py`.

- [ ] `motor_channels` — which PCA9685 channel drives which wheel, and the sign.
      **Assume nothing.** The reference car's map is globally inverted from
      Freenove's published values, which means at least one of the two is wrong
      for any given car.
- [ ] Duty floor before stall, raised and on the floor.
- [ ] Servo centre trim (pan ch8, tilt ch9).
- [ ] `led_index_clockwise` and `led_color_order`.
- [ ] `pcb_version` against a multimeter.
- [ ] Mecanum roller orientation, confirmed by a strafe and not by driving forward.

## Diagnostic run 2026-08-27 (`notes/runs/identify-20260827-075124.txt`)

Ruled **out** — do not re-investigate:

- **`sudo python` is not a different interpreter.** Both resolve to
  `/usr/bin/python3`, and `smbus`, `spidev`, `rpi_ws281x`, `gpiozero` and
  `picamera2` all import under user *and* sudo. This was the leading hypothesis
  for the non-motor failures and it is wrong.
- **Group membership is fine** — the user is in `gpio`, `i2c`, `spi`.
- **`dtoverlay=nospi10` in `config.txt` is harmless.** The name looks like it
  would disable GPIO10 and kill Connect-v2 LEDs. It does not: `dtoverlay -h`
  says "Disable the spi10 device on Pi5", and it sits inside a `[pi5]`
  conditional block that never applies on this 4B. Stock Raspberry Pi OS.
- **I²C and SPI are enabled and working** — `dtparam=i2c_arm=on`,
  `dtparam=spi=on`, `/dev/spidev0.0` present, i2c-1 at 100 kHz.

Open findings:

- **The ADS7830 is not on the bus.** A full scan of 0x03–0x77 returns only
  `0x40` and `0x70` — both the PCA9685. So the HAT is seated and I²C works, but
  the ADC does not answer at all. Working theory: the car's power switch was
  off. The PCA9685's logic runs off the Pi's 3.3 V through the header, while a
  v2 board derives the ADC's ~5.2 V reference from the battery rail — which is
  also *why* `Pcb_Version` 2 means 5.2 V. **`test.py ADC` cannot pass until
  0x48 appears in the scan**, and no params value can change that.
- **The camera is a wiring fault, not configuration.** `dtoverlay=ov5647` is
  correct for Freenove's module and the driver loads, but it cannot reach the
  sensor:
  ```
  ov5647 10-0036: ov5647_read: i2c read error, reg: 300a = -5
  ov5647 10-0036: probe with driver ov5647 failed with error -5
  ```
  EIO on the CSI I²C bus means the ribbon is unseated, in backwards, or in the
  wrong port. Editing `config.txt` will not fix it.
- `i2c-tools` is not installed, so `i2cdetect` is unavailable —
  `identify_hardware.py` falls back to probing three known addresses.
  `sudo apt install i2c-tools` when convenient.

`test.py` has no `Camera` case: the tests are `Led Motor Ultrasonic Infrared
Servo ADC Buzzer`.

## 2026-08-27 — one root cause behind both failures: no battery rail on the HAT

`test.py ADC` and `test.py Servo` both die with `OSError: [Errno 5]`, and the
evidence says they are the same fault.

| Observation | Fits "HAT has no battery power"? |
|---|---|
| ADS7830 (0x48) absent from a full 0x03–0x77 scan | yes — on a v2 board its ~5.2 V reference comes off that rail |
| PCA9685 (0x40) answers reads fine | yes — its logic VCC is 3.3 V from the Pi header, not the battery |
| 400/400 four-register writes to **unwired** channel 12 succeed | yes — bus and chip are healthy with no load |
| `PRE_SCALE=0x79` (=121, exactly 50 Hz) | `Servo.__init__` completed; the config is right |
| Servo dies on the 2nd register write of the first loop iteration | yes — `__init__` had just driven all 8 channels to 1500 µs |
| `vcgencmd get_throttled` = `0x0` | rules out the **Pi's** own supply sagging |

Mechanism: with V+ dead, `Servo.__init__` sets all eight channels active and the
two fitted servos get phantom-powered through their signal pins into an
unpowered rail. That parasitic load drags the PCA9685 around until the bus
errors. Repeatedly signalling unpowered servos is also bad for them — do not
rerun `test.py Servo` until the car is switched on.

**"The Motor test passed" is not counter-evidence.** `test_Motor` writes to the
motor driver's *logic inputs* (PCA9685 ch0–7), which are 3.3 V logic, and prints
"The car is moving forward" unconditionally — it never checks that anything
moved. With the battery off it completes cleanly on a motionless car. Whether
the wheels actually turned is the open question.

### Correction, same day: the battery rail IS live

Operator confirmed all four wheels physically spun during `test.py Motor`, and
the HAT's power LED is lit. The "no battery power" reading above is **wrong** —
keep it only as a record of what the bus evidence looked like.

What survives from it: 0x48 is still absent on a full rescan with the car
powered, the bus is healthy unloaded (400/400 writes to unwired ch12), and the
Pi's own supply is clean (`get_throttled=0x0`). So motors work off the raw
battery while the ADC does not answer at all and the servo channels crash the
bus. Two hypotheses remain:

1. **The HAT's 5 V peripheral regulator is dead.** Motors run from raw battery
   through the driver, so they are unaffected; the ADS7830, the servo header and
   the WS2812 strip would all hang off the 5 V rail and all fail together.
2. **Ground bounce between two supplies.** If the Pi is on its own USB adapter
   rather than fed from the car board, servo current has to return through the
   GPIO header's ground pins. That shifts the HAT's ground against the Pi's and
   corrupts SDA/SCL — which would explain the servo EIO but *not* the ADC being
   absent when idle.

**The LED test discriminates them**, because the strip is on the same 5 V rail
and needs no I²C at all: strip lights ⇒ rail alive ⇒ hypothesis 1 is dead.

### 2026-08-27 close-out: two faults left, both hardware

Passing: `Motor` (wheels genuinely turned), `Led`, `Ultrasonic`, `Infrared`.
That clears the I²C bus, the 5 V rail, GPIO, the params file and
`Connect_Version 2`.

**The ADS7830 is absent from every I²C bus on the Pi** — `i2c-0`, `1`, `10`,
`20`, `21`, `22` scanned 0x03–0x77; only `0x40` (PCA9685) answers anywhere. With
the 5 V rail proven alive by the LED strip, this is a chip- or trace-level fault
on the board, not anything software can reach. Cost: battery voltage and the two
photoresistors. Motors, servos, ultrasonic, line sensors and LEDs are all
independent of it — so `/drive`, `/look`, `/distance`, `/line` and `/led` are
unaffected and only `/battery` will error. **Keep a multimeter on the pack**;
there is no low-voltage warning.

**Servo is a current/sag problem, not a bus problem.** `__init__`'s ~32 writes
all succeed, `PRE_SCALE` lands at exactly 50 Hz, and the failure comes on the
*first loop write* — i.e. once the two servos are actually slewing. Unloaded
writes to ch12 ran 400/400. The LED strip proves the 5 V rail exists but only
draws ~100 mA; two slewing servos want an amp. Candidates, in order:
a stalled servo (listen for buzzing), a sagging pack under load, a marginal 5 V
regulator, or ground bounce if the Pi runs off its own USB adapter instead of
the car board.

Isolating test: **unplug both servos, rerun `test.py Servo`.** If it runs clean,
the load is the cause — then plug them back one at a time.

### 2026-08-27 — the servo fault was a connector, not the board

Unplugging both servos made `test.py Servo` run clean; **re-seating them and
plugging back in made it pass with the servos attached.** So the EIO was a
partially-seated servo lead: intermittent contact on the 5 V/ground pins let the
slew current arc rather than flow, sagging the rail enough to corrupt I²C. The
board, the PCA9685 and the bus were never at fault.

Worth remembering as a class: **on this kit an EIO on a healthy bus means look
at a connector before suspecting a chip.** Freenove's `test.py Servo` is a poor
isolator for it — its `__init__` drives all eight channels at once and then
sweeps into potential end stops. `tools/pi servo-probe <ch>` drives one channel
to one pulse and watches the bus instead.

Still failing after the re-seat, rescanned 2026-08-27:

- **ADS7830** — bus `i2c-1` still shows only `0x40`. Unchanged by the re-seat,
  and the chip is soldered to the board with no connector in its path. Board fault.
- **OV5647 camera** — `i2c-10` scans completely empty (the sensor should answer
  at `0x36`), `rpicam-hello --list-cameras` says "No cameras available!". Same
  connector class as the servo fault, so the ribbon is the first thing to redo.
  **The CSI bus is only probed at boot — reboot after re-seating or the scan
  will look unchanged.**

### 2026-08-27 — camera fixed; one fault left

Re-seating the CSI ribbon fixed it. The sensor now enumerates as
`ov5647 [2592x1944 10-bit GBRG]` on `/base/soc/i2c0mux/i2c@1/ov5647@36`, and
`tools/pi camera-test` captured a real full-resolution frame
(`notes/runs/camera-test.jpg`) — recognisable subject, correct colour, optics
fine. **Two of the three faults were the same thing: a connector not fully
home.** Nothing was wrong with the board except the ADC.

`sudo python camera.py` still aborts over SSH, and that is not a camera fault:
`start_image()` opens a Qt preview window, so it needs a display.
`qt.qpa.xcb: could not connect to display` is the whole of it. Capture headlessly
with `tools/pi camera-test`, or run it from the Pi's desktop over wayvnc (`:5900`)
— and note wayvnc is Wayland, so the `xcb` plugin will still fail; Qt needs
`QT_QPA_PLATFORM=wayland` there.

**Remaining: the ADS7830 only.** Absent from all six I²C buses across three
scans, including after both re-seats and a reboot. Soldered down, no connector
in its path. Board fault — Freenove ticket, with the bus scan as evidence.
Everything else on this car now works.

### The board has TWO power switches and THREE indicators

Tutorial p.66 (mecanum PDF p.70): **S1 = power main switch, S2 = motor and servo
power switch** — two blue push switches side by side. "Both S1 and S2 need to be
pressed. Then 5V, 3.3V, battery power indicators will be turned on." Three
indicator LEDs, not one.

This matters for the missing ADC. Everything that currently works can be fed
from the Pi through the GPIO header (PCA9685 logic, WS2812s, ultrasonic, line
sensors) or from S2 (motors, servos). The ADS7830 is the one device with no
path except the board's own S1-switched rail. **S1 off reproduces the exact
observed pattern**, including the earlier "yes, a power LED is lit" — there are
three, and one being lit says nothing about the other two.

Argues against it: Freenove say motors need both switches. Still the first thing
to check, because it costs seconds and the alternative is an RMA.

Also from the same page: **the ADC may be a PCF8591, not an ADS7830** — Freenove
say "the smart car board has two chips, PCF8591 and PCA9685... 0X48 and 0X40",
while `adc.py` sends ADS7830 command bytes. Both datasheets ship in the kit.
Irrelevant to this fault: an I²C address ACK happens before any command byte, so
a wrong chip type would still show at 0x48. Nothing shows.

Their healthy-board screenshot shows `i2cdetect -y 1` reporting **both 40 and
48**. That is the target.

### Deploy state, end of 2026-08-27

`tools/pi push` + `deploy/install.sh` both ran clean on the Pi — apt deps in,
venv built with `--system-site-packages`, all imports OK, `/etc/yakrobot/env`
written with a fresh `ROBOT_TOKEN`, `/etc/yakrobot/unit.json` created as `{}`.

The service was deliberately **not** started: the packaged `motor_channels` is
the inverse of what this car needs (see CLAUDE.md), so starting it before
`selftest motors` would give a car that drives backwards.

`Robot.battery()` guard verified on this Pi, three ways: a stub that raises
returns `None` and logs exactly once per process; a stub that works returns
7.92; the real chip on this car returns `None`. So `/info` and the WebSocket
handshake will both survive the dead ADC.

**Next session starts here:** raise the wheels, then
`cd ~/source && python -m picar_freenove_fastapi.selftest --all`, skipping
`battery`. `motors` and `mecanum` are the two that matter.

## 2026-09-18 — the ADC is BACK, and the batteries were the real fault

**Reverse the August conclusion. 0x48 now answers.** A full bus scan returns
`0x40, 0x48, 0x70`, and the chip reads properly:

    battery ch2 raw=169  ->  6.89 V as PCB v2
    photoresistor L raw 137, R raw 113   (differing = responding to light)
    Robot.battery() -> 6.82 V through our own stack

**Because the board was replaced.** Freenove accepted the ticket in
`freenove-ticket.md` and shipped a new connection board, which the operator
fitted on 2026-09-18. So the August diagnosis was right: the ADS7830 was dead at
chip level, exactly as the bus evidence said, and no amount of reseating would
ever have fixed it. The ticket is **closed successfully**, not void.

**6.89 V is a nearly flat 2S pack** (8.4 full, 7.4 nominal, ~6.4 empty), and
that is the whole of the "Pi won't boot" problem:

- Pi on battery: PWR LED solid red, ACT LED dark, never read the SD card.
- Pi on a wall charger: boots in ~5 s, `vcgencmd get_throttled` = 0x0.
- The SD card was pulled and inspected on the Mac: boot partition perfectly
  intact, every firmware file present, `config.txt` identical to August. The
  card was never the problem.

A marginal pack can hold enough voltage to light the HAT's LEDs and still fail
the Pi's boot-current draw. **With no low-voltage warning, this will keep
happening — charge the cells, and check the pack before each session.** The
`/battery` endpoint now works again, so that guard is available.

Filesystem survived intact after the unclean power cycles: no ext4 or mmc errors
in dmesg, root mounted rw, 7.0 G used of 53 G.

### The selftest ran on 2026-08-27, but only partly

`/etc/yakrobot/unit.json` exists and is dated 2026-08-27T14:12:42Z:

    duty_floor_unloaded: 700
    led_index_clockwise: false        <- this car's strip runs COUNTER-clockwise
    line_active_high_on_dark: true
    wheel_type: mecanum

**`motor_channels` is absent**, so the `motors` step never completed and the
packaged default is still in force. That default is the exact inverse of
Freenove's published map, which is the map this car actually needs (its stock
`test.py Motor` drives the right way round). **Expect the stack to drive this car
backwards until `selftest motors` is run.** Also absent: `pcb_version`, because
the battery step could not read the then-dead ADC — worth re-running now that it
works, to confirm v2 against a multimeter.

## THIS IS A DIFFERENT BOARD — re-verify what is board-dependent

Fitted 2026-09-18. Every board-level value in this file was measured on the OLD
board and is now an assumption. Three things need re-establishing, and the first
two are cheap:

1. **`Pcb_Version`** — sets the ADC scaling, 3.3x3 for v1 versus 5.2x2 for v2.
   The replacement is not guaranteed to be the same revision as the original.
   Right now raw 169 reads 6.56 V as v1 and 6.89 V as v2, and both are plausible
   for a tired 2S pack, so the bus cannot settle it. **Multimeter across the
   terminals, then set it.** The FastAPI `selftest battery` step asks exactly
   this question and writes the answer to unit.json.

2. **`Connect_Version`** — picks the LED driver, GPIO18 via rpi_ws281x for v1
   versus GPIO10/SPI MOSI for v2. `tools/pi led-probe` settles it by lighting
   the strip on each bus in turn. On a Pi 4B both values are accepted, so a
   wrong guess is silent: the strip simply stays dark.

3. **`motor_channels`** — swapping the board means every motor lead was
   unplugged and replugged, so which channel drives which wheel is now unknown
   independently of the map question. This was already the outstanding item;
   the board swap makes it mandatory rather than merely advisable.

`led_index_clockwise: false` and `line_active_high_on_dark: true` in unit.json
describe the strip and the line sensors, not the board, so they should survive —
but the LED strip plugs into the board, so treat the first as unconfirmed too.

## 2026-09-21 — card reflashed, Pi rebuilt from scratch

The Wi-Fi changed (old SSID `Love`, new `o2-WLAN85`, and the whole LAN moved
from 192.168.86.0/24 to 192.168.1.0/24). Editing `network-config` on the card
plus bumping cloud-init's `instance-id` did not bring it back, so the operator
**reflashed with Raspberry Pi Imager** and set the Wi-Fi there. That worked
first time.

Everything on the Pi was lost and rebuilt: `~/source`, the venv,
`/etc/yakrobot/*`, the Freenove kit repo, and the August calibration.

Current state, verified 2026-09-21:

- **Debian 13 trixie, kernel 6.18.50**+rpt-rpi-v8 (was 6.18.34 in August).
- `raspberrypi.local` -> **192.168.1.16**. NOTE the Pi's MAC is `98:fe:54:22:8f:ab`,
  which is NOT in the classic Raspberry Pi OUI list — `tools/pi`'s MAC sweep
  missed it until `98:fe:54` was added. mDNS found it; the sweep did not.
- I2C and SPI were **off** on the fresh image; `deploy/install.sh` enabled them,
  and a reboot was required before `/dev/i2c-1` appeared.
- Bus scan: **0x40, 0x48, 0x70** — the replacement board's ADC is present.
- `Robot.battery()` -> **7.92 V**. Healthy 2S pack; the operator replaced the
  cells that had been sitting at 5.47 V.
- Camera enumerates: `ov5647 [2592x1944]`.
- Package and every dependency import from `~/source` (the package's PARENT —
  importing from `~` fails with ModuleNotFoundError and that is expected).
- `sudo` needs a password on this image, so `deploy/install.sh` must be run by
  the operator from a real terminal. Claude Code's `!` prefix does NOT allocate
  a TTY, so sudo fails there with "a terminal is required to read the password".

**`/etc/yakrobot/unit.json` is `{}` — this car is now completely uncalibrated.**
The August values are recorded above but were never restored, and two of them
are suspect anyway because the connection board was replaced on 2026-09-18.
`motor_channels` is at the packaged default, which is the inverse of what this
car needs.

### 2026-09-21 rebuild — where it ended up

Freenove's own suite is restored to the Pi from `reference/freenove-upstream/`
(the Server dir only, 160 KB, not the 195 MB repo), with `params.json` written
as Connect 2 / Pcb 2 / Pi 1. `tools/pi freenove-test <name>` works again.

**`test.py Motor` passes on the rebuilt system** — hardware, wiring and the
battery are all good. Note what that does and does not show: it drives all four
wheels together through FREENOVE's driver, so it proves the hardware works but
says nothing about our `motor_channels` map, and it cannot detect two wheels
swapped between ports.

`/etc/yakrobot/unit.json` now holds:

    duty_floor_unloaded: 600          (was 700 in August)
    led_index_clockwise: true         (was false — the strip now plugs into the
                                       REPLACEMENT board, so a flip is expected)
    line_active_high_on_dark: true
    wheel_type: mecanum
    motor_channels: LF(1,0) LR(2,3) RF(7,6) RR(5,4)

`motor_channels` is **derived, not measured** — parsed out of Freenove's
`motor.py` on the grounds that their stock test drives this car correctly, and
verified by a fake-bus dry run (forward puts duty on ch1/2/5/7). Every motor
lead was unplugged during the 2026-09-18 board swap, so wheel IDENTITY remains
unconfirmed. `tools/pi verify-direction` drives one wheel at a time through OUR
driver and finishes with a strafe, which is the only cheap test for a swapped
pair; `selftest motors` is what replaces the inference with a measurement.
