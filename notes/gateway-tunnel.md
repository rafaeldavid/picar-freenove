# Gateway + Cloudflare tunnel

Set up 2026-09-21. Gateway runs on the **Mac**, not the Pi — it reaches the car
over the LAN and publishes a public URL.

    browser / agent  ->  trycloudflare URL  ->  cloudflared (Mac)
                     ->  gateway :8090 (Mac)  ->  car :8080 (Pi)

## Running it

    # 1. robot control server, on the Pi
    ssh rafathebuilder@raspberrypi.local
    cd ~/source && set -a && . /etc/yakrobot/env && set +a
    picar_freenove_fastapi/.venv/bin/python -m uvicorn \
        picar_freenove_fastapi.server:app --host 0.0.0.0 --port 8080

    # 2. gateway, on the Mac
    cd ~/robots/yakrobot-gateway
    uv run yakrobot-py serve --robots picar_freenove --port 8090

    # 3. tunnel, on the Mac -- see the config-bleed note below
    cloudflared --config /tmp/cfd-quick/empty.yml --no-autoupdate \
        tunnel --url http://127.0.0.1:8090

## Three traps, all hit on the first attempt

**1. `--tunnel cloudflare` inherits `/etc/cloudflared/config.yml`.** This machine
already runs a named tunnel (`berlin-tumbller-01`, pid 785), and cloudflared
reads that config by default even for a quick tunnel -- picking up its
`credentials-file`. The symptom is the worst kind: the tunnel reports
`Registered tunnel connection`, looks entirely healthy, and every request gets
**HTTP 404 from `server: cloudflare`** with the request never reaching the
gateway at all. Pass `--config` pointing at an empty YAML to isolate it.

**2. `tunnel.py` hardcodes `--url http://localhost:{port}`.** On macOS
`localhost` resolves to IPv6 `::1` first, and uvicorn binds IPv4 only, so
cloudflared dials a dead address. Use `127.0.0.1` explicitly. Worth fixing
upstream in `src/core/tunnel.py`.

**3. The CLI's tunnel URL is print()ed, so it is block-buffered** when stdout is
redirected. uvicorn's logging (stderr) appears while the URL sits invisible in
the buffer -- it looks like the tunnel silently failed. `PYTHONUNBUFFERED=1`.

Also: port 8000 is taken on this Mac by an unrelated app (SPEC-IT), so the
gateway needs `--port 8090`.

## Auth -- verified, not assumed

Two independent tokens:

- `MCP_TOKENS=operator=...` guards the GATEWAY. In `.env` (0600, gitignored).
- `PICAR_FREENOVE_TOKEN` is the CAR's own `ROBOT_TOKEN`, used gateway->car. The
  gateway injects it upstream so a browser never sees it.

Verified against the **public** URL with a real WebSocket client, because a curl
upgrade probe is misleading here -- `_refuse()` deliberately calls `accept()`
then `close(1008)`, so curl reports HTTP 101 on a socket that is about to be
shut. Actual results:

    no token    -> CLOSED 1008 "reservation required"
    bad token   -> CLOSED 1008 "invalid lease"
    real token  -> OPEN, hello{deadman_ms:700, max_duty:1400}
    POST /mcp with no token -> 401

`/` and `/ui` are readable unauthenticated -- the HTML shell and the fleet
listing. Nothing that moves the car is.

## Safety posture

- **700 ms deadman** on the drive socket: silence stops the car. This is the
  real protection on a transatlantic link, not the token.
- `max_duty` 1400.
- One driver at a time (reservation), 5-minute free lease.
- Quick-tunnel URLs are ephemeral and die with the cloudflared process. **They
  are not secret in any cryptographic sense** -- the token is what protects the
  robot.
- Kill switch: stop the robot server on the Pi, or `pkill -f cloudflared`
  (safe on the Mac; NEVER use `pkill -f` over SSH -- it matches the remote
  shell's own argv and kills the connection).


## /ui2 — the trace console (added 2026-09-21)

A camera-less console, because this car's CSI ribbon passes I2C but not image
data. Same socket, same auth, no video. **A fork, not a replacement**: `/ui`,
`console.html` and the MCP surface are untouched — the only edit to an existing
file is a new route in `src/core/console.py`.

    <tunnel>/picar_freenove/ui2?token=<MCP_TOKENS value>

New files: `src/core/static/console_trace.html`, `run-gateway.sh`.

### What it shows

- **Dead-reckoned path.** Integrated from the velocities we SEND — this car has
  no wheel encoders, so slip, ramp-up and battery sag all make it drift. The
  page says so in a banner rather than implying odometry it does not have.
  Two sliders (mm/s and °/s per 1000 duty) exist because nothing calibrates
  that conversion; they are guesses until someone measures a known distance.
- **Ultrasonic** as a cone ahead, plus a fading dot dropped in world frame at
  each reading. Real measurements, dead-reckoned positions.
- **IR line array** — three pads in the panel, and three dots on the car
  sprite so direction reads at a glance. A red mark is dropped where dark was
  seen.
- **Photoresistors** as two bars with a left-vs-right verdict.
- **Pi vitals** — SoC temperature, and the firmware throttle flags.

### Robot-side additions

`telemetry` gained `line`, `light` and `host` (AGENTS.md sec. 7 permits
additions; existing clients ignore unknown keys, and the stock `/ui` was
verified still working afterwards). `Robot.photoresistors()` and
`Robot.host_stats()` are new. `host_stats` does NOT take the I2C lock — nothing
in it touches the bus.

**`host.throttled` is the one that earns its place.** This car has browned out
twice on a tired pack, and both times it presented as a dead SD card or a broken
network. Bit 0 = happening now; bit 16 = happened since boot and never clears.
The console currently shows "ok (brownout earlier)" from the flat-battery boot,
which is correct and exactly the signal that was missing in September.

### Two more traps

**The editable install does not survive `uv run`.** uv writes
`_editable_impl_yakrobot_gateway.pth` pointing at `./src`, and on this machine
(Python 3.14, uv 0.10.6) `site.addpackage` silently declines to add it — the
file content and the target directory are both valid, and a trailing newline
does not fix it. `yakrobot_cli` imports only immediately after
`--reinstall-package` and breaks on the next `uv run`. Cause unresolved;
`run-gateway.sh` sets PYTHONPATH explicitly and sidesteps it. **Use that script
rather than `uv run`.**

**`pkill -f` / `pgrep -f` over SSH kills the connection.** Documented in
AGENTS.md sec. 6 and hit twice anyway. Kill the robot server by PORT:

    PID=$(ss -ltnp | grep ":8080" | grep -oE "pid=[0-9]+" | head -1 | cut -d= -f2)


### The rover sprite and its animations (2026-09-21)

The arrow became an actual top-down rover, drawn **to scale from the FNK0043
CAD** so it sits correctly against the 100 mm grid: 151 mm across the wheels,
211 mm long, wheel centres at +/-70 mm fore/aft and +/-62 mm either side, 53 mm
wheels. Every number in `CAR` is a millimetre off the datasheet, not a pixel
guess. Below ~0.25 px/mm it stops scaling and floors at a legible size —
a readable icon beats an accurate smudge.

The mecanum rollers are hatched at 45 deg and **mirrored across the diagonal**,
which is the real X pattern. Drawing it truthfully means the sprite shows at a
glance whether someone has mounted a wheel the wrong way round.

Animations, all driven by real state rather than decoration:

- **Wheels** hatch-scroll at a rate set by commanded duty.
- **Eyes** are the two ultrasonic transducers, because on this car they really
  are the face. Pupils lead the direction of travel; they blink on a random
  2.6-6.8 s timer; inside 25 cm they widen, go red and a bobbing "!" appears.
  That last one is cute AND the fastest way to notice an imminent collision.
- **Sonar** emits an expanding ring per reading, so the 3 s telemetry cadence
  is visible — a static cone cannot tell you whether the sensor is alive.
- **IR** pads pulse when they see dark, and drop a red mark on the map.
- **Dust puffs** behind the driving wheels above ~300 duty; motion whiskers
  above ~400; a curved arrow when spinning in place.

### Lights

Nine presets (off / red / green / blue / white / amber / party / chase /
breathe) plus a brightness slider defaulting to 55, which is Freenove's own cap
— these LEDs are bright.

**This needed a robot-side protocol addition.** A browser can reach the robot
only through the WS proxy or MCP, and MCP needs a session handshake that is
absurd for a colour button. So `/ws/control` gained an `led` message type
mirroring the existing `POST /led`, gated on `is_controller` alongside
drive/look/stop — a view-only second connection must not be able to strobe the
lights at whoever is driving. Verified end to end: all 8 pixels respond to
solid colours and to rainbow.


### /ui2 reskin — "the scope" (2026-09-21)

Brief was Candy Crush x air-traffic control, mobile first. The ATC half is not
decoration: **this car has no camera, so the operator really is flying on
instruments**, and "dead reckoning" is genuine aviation vocabulary — which is
why the honesty disclaimer became a `DR` badge that belongs on the instrument
rather than an apology bolted above it.

Tokens: deep scope indigo `#14103a` (never pure black), grape `#7b3ff2` for
structure, bubblegum `#ff5fa2` as the single accent carrying both the rover and
the sweep, lime/tangerine/cherry for go/caution/alert. **Fredoka** (rounded,
chunky) for chrome against **Space Mono** for every number — the split is the
brief: candy for the furniture, instruments for the data.

Signature: the scope is a **circle**, not a rectangle. Range rings labelled in
metres, bearing ticks every 30 deg with cardinals emphasised, and a conic-
gradient sweep. North-up like a real controller's display: track-up would be
easier to drive but would make the traced path meaningless, and the path is the
whole point of this console.

**The functional part of the reskin is the thumbpad.** A phone has no keyboard,
so WASD made the old page unusable on mobile regardless of how it looked. The
pad uses pointer events (one path for mouse, touch and stylus) with
`setPointerCapture`, so a thumb sliding off the pad still ends the drag here
instead of leaving the car driving. 14% dead zone, because a thumb is never
exactly centred. Rotation is two round buttons either side.

Verified: fonts load, the media query flips to single-column at 420 px,
`touch-action:none` on the pad, and every control clears the 44 px touch floor
(pad 151, spin 58, LED 48, STOP deliberately largest). `prefers-reduced-motion`
disables the animation. `/ui` remains byte-for-byte unmodified.


## Persistent tunnel (2026-09-22)

The quick tunnel's `*.trycloudflare.com` URL changed on every run, so it could
never be shared in advance or bookmarked. Replaced with a **named** tunnel:

    https://picar-freenove-01.yakrover.online/picar_freenove/ui2

    tools/tunnel start | stop | status | url     (in yakrobot-gateway)

Tunnel `picar-freenove-01`, id `6e8b594b-3139-4a11-a903-21295d7076a3`, config at
`~/.cloudflared/picar-freenove-01.yml`. The name follows the convention already
in use on this account (`berlin-tumbller-01.yakrover.online`). No login was
needed — `~/.cloudflared/cert.pem` was already valid.

**The ingress points at `http://127.0.0.1:8090`, deliberately not `localhost`.**
See the IPv6 note above; the config carries the same warning inline, because
"tidying" it to localhost silently breaks the whole thing with a 404 that never
reaches the gateway.

### Cloudflare's bot rules block plain scripted clients

`urllib` with its default `Python-urllib/3.14` User-Agent gets **403** on POST
through this zone, while the identical request from curl or a browser gets 200.
Browsers are unaffected, so the console is fine — but any agent or script
dialling the gateway over the tunnel must send a browser-like User-Agent or it
will look broken in a way that has nothing to do with this code.

### The robot server must be a service

The public URL is worthless if the car's server is not running, and the Pi
rebooted on its own during this session — taking the manually-`nohup`ed server
with it. A corrected unit is staged at `~/yakrobot-freenove.service` on the Pi
(the shipped one hardcodes the reference car's `drg` user and paths, which do
not exist here). Install it with:

    ssh -t rafathebuilder@raspberrypi.local '
      sudo cp ~/yakrobot-freenove.service /etc/systemd/system/ &&
      sudo systemctl daemon-reload &&
      sudo systemctl enable --now yakrobot-freenove &&
      systemctl is-active yakrobot-freenove'

`Restart=always`, not `on-failure`: a clean exit should still come back.

**Still not automatic:** the gateway and the tunnel both run on the Mac from
`nohup`, so a Mac restart takes the public URL down. launchd agents would fix
that; not done yet.


### Occupancy mapping and "Look around" (2026-09-22)

The console now builds a map instead of scattering dots. **A range reading is
not one data point, it is a statement about a whole ray**: something returned an
echo at the far end, and everything between is empty. Counting both is what
turns scattered returns into rooms.

60 mm cells, each keeping a hit/miss tally, rendered as lilac gumdrop blocks
(obstacle) over mint (known-clear floor).

**Hits and misses are NOT symmetric, and treating them as such was a real bug.**
The first version decremented `hit` on every miss, so rays travelling PARALLEL
to a wall crossed its cells and reported them free — eroding the wall faster
than perpendicular rays could build it. A synthetic 1.2 m room produced exactly
one wall out of four. Fixed with log-odds weights: a hit is a positive
detection (1.0), a miss is an inference (0.32) and is wrong whenever the ~30 deg
beam clips an edge. Same synthetic room now yields all four walls.

`Look around` sweeps the head 30-150 deg in 15 deg steps and feeds every bearing
into the grid — one sweep fills an arc that driving forward never would. Needed
a `scan` message on `/ws/control` (an addition, like `led`), which stops the
wheels first: sweeping while driving smears every bearing against a pose that is
changing underneath it.

**Bearing convention, easy to mirror:** pan 90 is straight ahead and HIGHER pan
is to the RIGHT, while the world frame is anticlockwise-positive, so a sample at
pan p sits at `heading + (90 - p)` degrees. Verified offline: pan 30 -> +60 deg
(left), pan 150 -> -60 deg (right).

The whole sweep shares ONE pose snapshot, taken at the start. Reading the pose
per sample would let drift during the sweep fan the returns out.

Both limits stay honest and are on the DR badge: positions come from dead
reckoning so the map smears, and the beam is wide so a return is credited to the
centre cell when it could be anywhere across the arc. It is a sketch of the
room, not a survey.

Test hooks `__probe` / `__feed` / `__place` / `__mapStats` are display-only by
construction — none touches `cmd` or the socket, so none can command the robot.


### The 501 that blocked registration (2026-09-22)

`register.yakrobot.com` reported *"Could not fetch descriptor: gateway returned
HTTP 501"*. The route's own message said `descriptor export is not installed —
run uv sync --extra export`, which was misleading: the extra WAS installed, and
`yakrobot_descriptor` was visibly present in the venv.

**Same root cause as the `yakrobot_cli` failure.** Both packages are editable
installs, both write a `.pth` into site-packages, and on this machine (Python
3.14, uv 0.10.6) `site` silently declines to process them — the file content and
the target directory are both valid, `sys.path` just never gets them. The route
catches `ImportError` and reports it as "not installed", which is true from its
point of view and useless from the operator's.

`run-gateway.sh` now **reads the venv's .pth files itself** and prepends every
absolute directory to PYTHONPATH, rather than hardcoding one path. That fixes
the class rather than the instance — a third editable dependency would have
failed the same way.

    + /Users/rafa/Documents/robots/yakrobot-descriptor/src
    + /Users/rafa/Documents/robots/yakrobot-gateway/src

Also set `CLOUDFLARE_DOMAIN=picar-freenove-01.yakrover.online` in `.env`. The
descriptor's endpoint URLs come from `NGROK_DOMAIN`, then `CLOUDFLARE_DOMAIN`,
then the request's Host header; pinning it means the exported JSON never depends
on which Host header happens to arrive.

Verified from the public edge: descriptor 200 with both endpoints pointing at
the named tunnel, `Access-Control-Allow-Origin: *`, and the CORS preflight
answering 204 — that OPTIONS handler is what a cross-origin registration page
needs before it will issue the GET.


## Registered on Base Sepolia — 2026-09-22

    name        PiCar-Berlin-01
    agent ID    9320
    tx          0xabc5cd0fef2df8cc6d83f8ed2bca3a6995de7b4e1879caaa428a6e6ef18713ce
    registrar   register.yakrobot.com
    endpoints   https://picar-freenove-01.yakrover.online/picar_freenove/mcp
                https://picar-freenove-01.yakrover.online/fleet/mcp

Renamed from the plugin's hardcoded `PiCar-Finland-01` (the reference car) via
the new `PICAR_FREENOVE_NAME` env var — see the upstream branch
`fix/tunnel-ipv6-and-descriptor-error`, not yet pushed.

### What being on-chain changes operationally

The registered endpoints are now a public promise, and **three separate things
have to be running for that promise to hold**:

1. the robot server on the Pi (port 8080),
2. the gateway on the Mac (port 8090),
3. cloudflared on the Mac.

Only the tunnel has a restart story. The other two are `nohup`/`setsid` jobs
that die with a reboot, and the Pi has already rebooted on its own once during
this work. **A registered agent that resolves to nothing is worse than an
unregistered one** — it advertises a capability it cannot honour.

Outstanding, in the order that matters:

- **Install the systemd unit on the Pi.** Staged at
  `~/yakrobot-freenove.service`; needs the operator's sudo. Without it every
  Pi reboot silently takes the agent offline.
- **launchd agents on the Mac** for the gateway and the tunnel. Not written
  yet. A Mac restart — or just a sleep — currently takes the endpoint down.
- The Mac sleeping is the likeliest cause of a mystery outage; `caffeinate`
  or Energy Saver settings are worth a look before debugging anything else.


## The Mac side now restarts itself — and why the repos moved (2026-09-22)

`launchd` agents run the gateway and the tunnel, both `KeepAlive`, both
verified by killing them and watching them come back:

    com.yakrobot.gateway   ~/Library/LaunchAgents/com.yakrobot.gateway.plist
    com.yakrobot.tunnel    ~/Library/LaunchAgents/com.yakrobot.tunnel.plist
    logs                   ~/robots/yakrobot-gateway/logs/

**The gateway and descriptor repos moved out of `~/Documents`:**

    ~/Documents/robots/yakrobot-gateway     ->  ~/robots/yakrobot-gateway
    ~/Documents/robots/yakrobot-descriptor  ->  ~/robots/yakrobot-descriptor

Not a preference — macOS TCC protects `~/Documents`, `~/Desktop` and
`~/Downloads`, and a launchd agent does not inherit the access Terminal has.
The agent failed with exit 126 and

    getcwd: cannot access parent directories: Operation not permitted
    bash: .../run-gateway.sh: Operation not permitted

Confirmed with a throwaway agent: it could list `~/.cloudflared` fine and got
`Operation not permitted` on `~/Documents/robots`. The alternative was granting
Full Disk Access to `/bin/bash`, which would hand every shell script on the
machine access to every protected folder — a bad trade for a convenience
feature. TCC keys on the real path, so a symlink does not help.

**The venv is path-bound** (absolute shebangs in `.venv/bin/*`), so it was
rebuilt rather than moved. Both editable installs now resolve to the new paths.

`picar-freenove/` deliberately stayed in `~/Documents` — nothing in it runs
unattended.

### What survives what, now

| | Pi reboot | Mac reboot | process killed |
|---|---|---|---|
| robot server (systemd) | yes | n/a | yes |
| gateway (launchd) | n/a | yes | yes |
| tunnel (launchd) | n/a | yes | yes |

Remaining gap: **Mac sleep** still suspends the gateway and tunnel. launchd
restarts crashed processes, not sleeping ones. If the endpoint is meant to stay
reachable unattended, the Mac needs to not sleep (`caffeinate -s`, or Energy
Saver), or the gateway needs to move to the Pi.
