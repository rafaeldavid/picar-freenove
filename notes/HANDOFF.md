# Where things stand — 2026-09-22

Read this first. `HARDWARE.md` is the forensic detail; this is the state.

## It is running, and it restarts itself

    PiCar-Berlin-01, agent 9320 on Base Sepolia
    https://picar-freenove-01.yakrover.online/picar_freenove/ui2

Three processes keep that link alive, and all three now come back on their own:

| | where | managed by |
|---|---|---|
| robot server | Pi, port 8080 | systemd `yakrobot-freenove` (enabled) |
| gateway | Mac, port 8090 | launchd `com.yakrobot.gateway` |
| tunnel | Mac | launchd `com.yakrobot.tunnel` |

**The one gap: a sleeping Mac takes the endpoint down.** launchd restarts
crashed processes, not sleeping ones. If the robot is meant to be reachable
unattended, either stop the Mac sleeping or move the gateway onto the Pi.

## Where the code lives

    ~/Documents/robots/picar-freenove   this workspace (committed)
    ~/robots/yakrobot-gateway           gateway + console (committed, 2 branches)
    ~/robots/yakrobot-descriptor        contract package

The gateway is **not** under `~/Documents`: macOS TCC blocks launchd agents from
that folder, which is what forced the move. Do not move it back.

## Open items, in the order that matters

1. **`motor_channels` is derived, not measured.** Parsed out of Freenove's
    source on the grounds that their stock test drives this car correctly, and
    dry-run verified — but every motor lead was unplugged during the board swap,
    so which channel drives which wheel is unconfirmed. `tools/pi
    verify-direction` (wheels raised) settles direction and identity;
    `selftest motors` replaces the inference with a measurement. **Until then a
    strafe may come out as a rotation.**
2. **The camera is dead at the ribbon.** The sensor enumerates and reports valid
    modes, but the CSI data lanes deliver nothing — `frontend has timed out`.
    Survived two reseats. Next step is a replacement 15-pin FPC, a couple of
    euros. Everything else on the car works.
3. **Two branches on the gateway, neither pushed.**
    `fix/tunnel-ipv6-and-descriptor-error` — three upstream bug fixes, PR-ready,
    Discord message already drafted for Anuraj.
    `feature/trace-console-no-camera` — the /ui2 console, plus a second commit
    of local-only scripts that should NOT go upstream.
4. **launchd for the Mac is done; sleep is not.** See above.

## Things that will waste your time if you forget them

- **`pkill -f` / `pgrep -f` over SSH kills the connection** — the pattern
  matches the remote shell's own argv. Kill the robot server by port instead.
- **`sudo` on the Pi needs a password**, and Claude Code's `!` prefix gives no
  TTY, so sudo fails there with "a terminal is required". Run those from a real
  terminal.
- **Editable installs are invisible in the gateway venv** on this machine.
  `run-gateway.sh` works around it. If a package is "not installed" but
  demonstrably present, that is this.
- **Check the battery before blaming anything else.** A flat pack has already
  masqueraded as a dead SD card and as a dead network. There is a `/battery`
  reading again now that the ADC works.
- **Connectors before chips.** Two of three hardware faults were seating.
