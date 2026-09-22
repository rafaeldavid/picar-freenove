# CLAUDE.md — picar-freenove workspace

Bench for one physical robot: a Freenove 4WD Smart Car (FNK0043, **mecanum
wheels**) with a Raspberry Pi on top. This directory is the Mac-side working
copy; the car is at `rafathebuilder@raspberrypi.local`.

## Safety — read before issuing anything that can move it

1. **Confirm the wheels are elevated before any drive command.** Ask the
   operator every time. Do not infer it from earlier in the conversation, and do
   not carry it over from a previous test.
2. **Kill switch:** `tools/pi stop` (`sudo systemctl stop yakrobot-freenove`).
   Say it out loud before a floor test.
3. **Cap `duration_ms` at ~1000 during bring-up.** The server auto-stops, but a
   typo'd `8000` is eight seconds of unattended car.
4. **Servo buzzing = stop immediately.** It is stalling against an end stop.
5. **Never benchmark with a non-zero duty on PCA9685 channels 0–7.** Use
   channels 10–15; nothing is wired to them.
6. If you are unsure whether something moves the car, it moves the car.

The two diagnostic tools in `tools/` are safe by construction:
`identify_hardware.py` only reads, and `led_bus_probe.py` touches the LED pin and
never opens the PCA9685.

## Layout

```
picar_freenove_fastapi/   the control stack we deploy — a clone of
                          github.com/pi-drg/picar_freenove_fastapi, its OWN git
                          repo, gitignored here. Read its AGENTS.md before
                          changing anything in it.
reference/                Freenove's code and docs, read-only, gitignored.
                          tools/fetch-reference.sh repopulates it.
tools/                    Mac-side operator tools (below).
cover/                    the printable top cover: build_cover.py (parametric,
                          CadQuery), test_cover.py (16 fit + printability
                          tests), and the STL/STEP to print. Read its README
                          before changing a constant.
viewer/                   local three.js site: the car from Freenove's STEP,
                          plus four candidate shells. `tools/viewer` serves it.
                          car.glb and cad_design/ are gitignored — regenerate
                          with tools/step2glb.py. See viewer/README.md.
notes/                    what we know about THIS car.
  HARDWARE.md             per-unit ground truth. Unknowns are marked; fill them
                          in as probes answer them.
  version-puzzle.md       what Freenove's two version prompts actually control.
  gateway-tunnel.md       running the yakrobot-gateway + a Cloudflare quick
                          tunnel, and the three traps that cost an hour.
  runs/                   captured diagnostic output, gitignored.
```

Two trees, two purposes: `reference/` is what Freenove ships and we only read;
`picar_freenove_fastapi/` is what we run and may change. **They share no code** —
the FastAPI stack deliberately depends on nothing from Freenove's repo.

## Tools

```
tools/pi host                  which address answers, plus the Pi's model
tools/pi diag                  full read-only hardware report -> notes/runs/
tools/pi camera-test           probe CSI, capture a still, copy it back
tools/pi led-probe             settle Connect Version by lighting the strip
tools/pi servo-probe <ch>      drive ONE servo channel and watch the bus
tools/pi params [c] [p]        write Freenove's params.json (sudo + chown)
tools/pi params-check          find every params.json on the Pi
tools/pi freenove-test Led     run Freenove's stock test for one module
tools/pi push                  rsync the control stack to ~/source on the Pi
tools/pi logs [n]              journal for the control service
tools/pi stop                  kill switch

tools/viewer                   serve the cover viewer on :8000
tools/setup-cad-env.sh         build the OpenCASCADE python env (~600 MB)
tools/analyse*.py              measure the STEP; provenance for every constant
tools/step2glb.py IN OUT [mm]  tessellate a STEP into glTF (needs cadquery-ocp)
```

`tools/pi` falls back from `raspberrypi.local` to the last known IP, because
mDNS fails while the Pi is booting and the resulting hang looks like a dead Pi.

## Where things stand

**Start with `notes/HANDOFF.md`** — current state, open items, and the
traps. This section is the bring-up history. (2026-08-27)

**Bring-up is complete.** Every Freenove module test passes except `ADC`, and
the camera captures at full resolution. Full history in `notes/HARDWARE.md`;
the short version:

- Passing: Motor, Led, Ultrasonic, Infrared, Servo, Buzzer, camera.
- **Failing: the ADS7830 at I2C 0x48 is absent from every bus.** Board fault —
  Freenove ticket sent 2026-08-27 (`notes/freenove-ticket.md`). Costs battery
  voltage and both photoresistors; nothing else. Do not re-diagnose this: six
  buses scanned, three times, across re-seats, reboots and power cycles.
- Two faults during bring-up turned out to be **connectors not fully seated**
  (a servo lead, the CSI ribbon), presenting as `OSError [Errno 5]` and
  `IndexError`. On this kit, suspect a connector before a chip.
- Params settled: `Connect_Version 2` (confirmed by lighting the strip),
  `Pcb_Version 2`, `Pi_Version 1`. Pi 4B, Debian 13 trixie.

### Local change to picar_freenove_fastapi — UNCOMMITTED

`Robot.battery()` now returns `None` instead of raising when the ADC does not
answer, and `/info`, `/battery`, `/ws/control`'s hello frame and the telemetry
loop all express "no reading" as `battery_v: null`. Without it, a dead ADC gave
a 500 on `/info` and a WebSocket handshake that never completed — no teleop at
all on a car that is otherwise fine. Verified on hardware against both a stub
and the real dead chip. `/info` also reports `hardware: "ok, no ADC"`.

This lives in the cloned repo, which is gitignored here — **commit it upstream
or it will be lost on the next clone.**

### Deployed, but not yet calibrated

`tools/pi push` and `deploy/install.sh` have both run; the venv imports cleanly
and `/etc/yakrobot/unit.json` exists but is `{}`. The service is **not** started
yet, deliberately.

**The selftest has NOT been run, and the packaged motor map is probably wrong
for this car.** Freenove's stock `test.py Motor` drives it in the correct
direction, which means this car's wiring matches Freenove's published values —
and `config.py`'s map is the exact inverse of those, every pair swapped:

| Wheel | Freenove (works here) | config.py default |
|---|---|---|
| left_front | `(1, 0)` | `(0, 1)` |
| left_rear | `(2, 3)` | `(3, 2)` |
| right_front | `(7, 6)` | `(6, 7)` |
| right_rear | `(5, 4)` | `(4, 5)` |

So the stack will likely drive this car **backwards** until `selftest motors`
derives the real map. Do not hand-edit `config.py` — the selftest writes the
overlay. Skip the `battery` step; it reads the dead ADC.

## Working rules

- **`notes/HARDWARE.md` outranks `picar_freenove_fastapi/AGENTS.md` §2.** That
  section documents a different, already-calibrated car and says so itself. Its
  motor map, duty floors and servo trims are a starting guess here, not facts.
- **Derive per-car values, do not hand-edit `config.py`.** The selftest writes
  them to `/etc/yakrobot/unit.json`, which `BoardConfig.load()` layers over the
  packaged defaults.
- **Do not change the HTTP endpoint contract.** An external gateway adapter
  dials those exact paths and shapes. Additions are fine.
- **Capture output, do not paraphrase it.** `tools/pi diag` tees to
  `notes/runs/`. A remembered error message is not evidence.
- **Editing on both sides is how this project drifts.** After `tools/pi push`,
  the running process still holds what it imported at last start —
  `sudo systemctl restart yakrobot-freenove`.
- `pkill -f <pattern>` over SSH matches the remote shell's own argv and kills
  your connection. Check `ss -ltn | grep :8080` instead.
