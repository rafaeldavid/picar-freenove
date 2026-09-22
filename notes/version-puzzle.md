# The Freenove version prompts, and what they actually control

*Written 2026-08-27, from reading `Code/Server/*.py` in Freenove's kit repo and
the mecanum tutorial. Confirm the hypotheses at the bottom against real output
before acting on them.*

Freenove's `test.py` asks two questions on first run and stores the answers in
`params.json`. The prompts are vague, the tutorial explains one of them and not
the other, and a wrong answer fails in a way that does not point back at the
prompt. This is what each one really does.

## The three fields

`params.json` holds three keys. Only two are ever asked for.

| Key | Asked? | Read by | Controls |
|---|---|---|---|
| `Pi_Version` | **no** — auto-detected | `led.py` | 2 if `/sys/firmware/devicetree/base/model` says "Raspberry Pi 5", else 1 |
| `Connect_Version` | yes | `led.py` **only** | which pin drives the LED strip |
| `Pcb_Version` | yes | `adc.py` **only** | how the battery ADC byte is scaled |

That is the whole blast radius. Grep confirms it:

```console
$ grep -rn "Pcb_Version\|Connect_Version" Code/Server/*.py | grep -v parameter.py
adc.py:11:  self.pcb_version = self.parameter_manager.get_pcb_version()
led.py:13:  self.connect_version = self.param.get_connect_version()
```

## Connect Version — the one that can actually break a test

The connection board (the small adapter between the Pi and the car shield) ships
in two revisions. Per the tutorial (p.5), **the only difference is the LED pin**:

- **v1** drives the eight WS2812s from **GPIO18** via `rpi_ws281x`.
- **v2** drives them from **GPIO10 / SPI0 MOSI** via `spidev`.

v2 exists because `rpi-ws281x-python` cannot reach GPIO18 through the Pi 5's RP1
chip. Freenove call v2 an interim measure and say v1 was still the one on sale.

`led.py` branches on the pair `(connect_version, pi_version)`:

On a **Pi 4B** both values are accepted, so the software will not tell you when
you have guessed wrong — the strip simply stays dark. Only the Pi 5 row below is
self-announcing.

| Connect | Pi | Result |
|---|---|---|
| 2 | any | SPI driver. **Needs `dtparam=spi=on` and the user in the `spi` group.** |
| 1 | <5 | `rpi_ws281x` on GPIO18. Needs root. |
| 1 | 5 | prints "not supported", sets `is_support_led_function = False` — every LED call becomes a no-op |
| missing/None | any | **no branch matches**: `self.strip` and `self.is_support_led_function` are never assigned, so the first LED call raises `AttributeError` |

Two traps follow from that table:

- **On a Pi 5 the answer is forced.** Connect v1 has no working LED path there.
  If the board really is v1, Freenove's own fix (tutorial p.5) is a female-female
  jumper from **GPIO10 to GPIO18**, after which you answer 2.
- **v2 with SPI disabled looks identical to broken hardware** — the driver opens,
  writes succeed, and the strip stays dark.

**How to settle it:** `tools/pi led-probe`. It drives both buses in turn and asks
what lit. No register reports this; only the strip does.

## PCB Version — cosmetic, and *cannot* be your error

`adc.py` uses it for one thing:

```python
self.adc_voltage_coefficient = 3.3 if self.pcb_version == 1 else 5.2
...
power = adc.read_adc(2) * (3 if adc.pcb_version == 1 else 2)
```

So the battery reading is `raw/255 × 3.3 × 3` (v1) or `raw/255 × 5.2 × 2` (v2).
Full scale: **9.9 V vs 10.4 V — 5% apart.**

Two consequences:

1. **Answering 1 instead of 2 changes no pin, loads no different driver, and
   cannot make any test throw.** Whatever went wrong in the non-motor tests, this
   was not the cause. It only made the battery read ~5% low.
2. **The reading cannot tell you which revision you have.** Both scalings put a
   healthy 2S pack in a believable range. `tools/pi diag` prints the raw byte and
   both interpretations; a multimeter across the pack picks the winner. If you
   never plan to trust the number to better than half a volt, either answer works.

The FastAPI stack defaults to `pcb_version: 2` (`config.py:147`) and its
`battery` selftest step resolves it the same way — show both, ask which matches.

## The naming collision — "PCB version" means two different things

This is the trap, and it is Freenove's, not yours.

**Both tutorials use "PCB_V1.0 / PCB_V2.0" exclusively for the connection
board.** The photos are captioned "Connection board (PCB_V1.0)" and "Connection
board (PCB_V2.0)", and the LED chapter says the prompt is asking for "the PCB
version of the connection board... Please enter 1 or 2 according to the version
number of your connection board."

But in the *code*, the connection board's revision is `Connect_Version`.
`Pcb_Version` is a second field the tutorials never mention at all — it appears
nowhere in either PDF except inside a printed code listing.

So if you identified your board as "v2" from Freenove's photos, you identified
the **connection board**, and the field that should be 2 is `Connect_Version`.
What `Pcb_Version` actually refers to is undocumented; from the ADS7830
datasheet and Freenove's command byte `0x84` (PD1:PD0 = 01, internal reference
**off**), it is a property of the main car shield — which rail feeds the ADC's
VREF pin and what the battery divider ratio is. Nothing on the connection board
could change either.

Practically: set both to 2 and move on. `Pcb_Version` is worth 5% on one
displayed number, and the FastAPI stack defaults it to 2 anyway.

## Fixing a wrong answer

`params.json` is written to the **current working directory** — `PARAM_FILE` is a
bare relative filename. Run `sudo python test.py` from `Code/Server` and it lands
in `Code/Server/params.json` owned by root; run something from elsewhere and you
silently get a second file with different answers.

```bash
cd ~/Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi/Code/Server
sudo python parameter.py        # answer "yes" to re-enter both values
# or, to start clean:
sudo rm params.json             # the next test.py run re-prompts
```

Then check there is exactly one: `find ~ -name params.json`.

**It will be root-owned.** `sudo python test.py` creates it as root, so opening
it in a normal-user `nano` gets you `[ Error writing params.json: Permission
denied ]` only *after* you have typed the edit. Hand it back once and the
problem goes away for good — root can still write a user-owned file, so the
sudo tests are unaffected:

```bash
sudo chown $USER:$USER ~/Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi/Code/Server/params.json
```

`tools/pi params` does this for you.

## Why the other tests failed — hypotheses, ranked

Motor passing already rules a lot out: I²C is enabled, the PCA9685 answers, the
HAT is seated, and the pack has usable charge. `sudo python test.py Motor` never
touches `params.json`, which is consistent with it being the one that worked.

Ranked by how well each fits "motor passes, others error", most likely first:

1. **`sudo python` is a different interpreter from `python`.** Freenove's
   `setup.py` pip-installs into the user's site-packages; `sudo` does not see
   them. `smbus` comes from apt and is system-wide — which is exactly why the
   motor test survives and `gpiozero`/`picamera2` ones do not. Symptom:
   `ModuleNotFoundError` under sudo for a module that imports fine without it.
2. **gpiozero has no usable pin factory.** `ultrasonic.py`, `infrared.py` and
   `buzzer.py` all import gpiozero, and it needs `lgpio` on Bookworm/Pi 5.
   Symptom: `PinFactoryFallback` warnings then `BadPinFactory`, or
   "Cannot determine SOC peripheral base address".
3. **Group membership.** Not being in `spi`/`gpio`/`i2c` fails without sudo and
   passes with it — the reverse of hypothesis 1, and the two together produce a
   maddening "works one way, not the other".
4. **`Connect_Version` wrong or absent** — the LED test only. See the table above.
5. **Camera ribbon or `camera_auto_detect`** — the camera test only.

`tools/pi diag` reports the evidence for all five without moving the car. Run it
first, then paste the actual traceback for whichever test still fails; the point
of the list is to stop the guessing, not to replace the output.
