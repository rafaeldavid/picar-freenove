# picar-freenove

Working bench for one Freenove 4WD Smart Car (FNK0043, mecanum wheels) with a
Raspberry Pi on top. Mac side lives here; the car is `raspberrypi.local`.

## First run

```bash
tools/pi host        # is it awake? which Pi is it?
tools/pi diag        # read-only hardware report, saved to notes/runs/
tools/pi led-probe   # lights the strip on each bus — settles Connect Version
```

Nothing above can move the car.

## What is here

| Path | What |
|---|---|
| `picar_freenove_fastapi/` | the control stack we deploy — a clone of [pi-drg/picar_freenove_fastapi](https://github.com/pi-drg/picar_freenove_fastapi), its own git repo |
| `reference/` | Freenove's own code and docs, read-only (`tools/fetch-reference.sh`) |
| `tools/` | operator tools, all driven through `tools/pi` |
| `notes/HARDWARE.md` | what is actually true of **this** car |
| `notes/version-puzzle.md` | what Freenove's version prompts really control |
| `CLAUDE.md` | safety rules and working rules for an agent |

`picar_freenove_fastapi/` and `reference/` are gitignored — each belongs to
someone else's repository. What this repo tracks is the notes and the tools.

## The two trees

`reference/freenove-upstream/` is Freenove's stock code: a TCP server on port
5000 speaking `CMD_X#...`, plus `test.py` for per-module bring-up. Useful for
first-light checks and as documentation of the board's wiring.

`picar_freenove_fastapi/` replaces it — a FastAPI server with its own drivers,
per-unit calibration, an auto-stop deadman on every motion command, and realtime
teleop over WebSockets. It shares no code with Freenove's repo; the board
constants were ported into one `config.py` with attribution.

Deploying it: read its `AGENTS.md` first, then `tools/pi push`.

## Where things stand

Bring-up. Freenove's `Motor` test passes; the other module tests error, and the
tracebacks are not captured yet. See `notes/HARDWARE.md` for the current state
and `notes/version-puzzle.md` for why the PCB-version mix-up is not the cause.
