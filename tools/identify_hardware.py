#!/usr/bin/env python3
"""Identify what this Freenove 4WD car actually is. Read-only — never moves it.

Run on the Pi:  python3 identify_hardware.py
Or from the Mac: tools/pi diag

Everything here either reads a file, reads an I2C register, or shells out to a
query command. Nothing writes to the PCA9685, so the wheels cannot turn.

The point is to replace guessing at Freenove's two version prompts
("Connect Version", "PCB Version") with evidence. See notes/version-puzzle.md.
"""
import glob
import grp
import json
import os
import subprocess
import sys

FREENOVE = os.path.expanduser("~/Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi")
CONCLUSIONS: list[tuple[str, str]] = []


def head(title: str) -> None:
    print(f"\n\033[1m== {title} {'=' * max(0, 60 - len(title))}\033[0m")


def kv(key: str, value: object) -> None:
    print(f"  {key:<28} {value}")


def conclude(topic: str, text: str) -> None:
    CONCLUSIONS.append((topic, text))


def sh(*args: str, timeout: int = 10) -> str | None:
    """Run a query command; None if it is missing or fails."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
        return None


def read(path: str) -> str | None:
    try:
        with open(path, "r", errors="replace") as f:
            return f.read()
    except OSError:
        return None


# --- 1. the board ------------------------------------------------------------

def section_board() -> int:
    head("Raspberry Pi")
    model = (read("/sys/firmware/devicetree/base/model") or "unknown").strip("\x00 \n")
    kv("model", model)

    osr = read("/etc/os-release") or ""
    pretty = next((l.split("=", 1)[1].strip('"\n')
                   for l in osr.splitlines() if l.startswith("PRETTY_NAME=")), "unknown")
    kv("os", pretty)
    kv("kernel", (read("/proc/version") or "").split(" version ")[-1].split()[0] if read("/proc/version") else "?")
    kv("python", sys.version.split()[0])
    kv("arch", os.uname().machine)

    # Freenove's Pi_Version is 2 for a Pi 5, 1 for everything older. It is the
    # one version field that is machine-detectable, and parameter.py already
    # derives it — you are never asked for it.
    pi_version = 2 if "Raspberry Pi 5" in model else 1
    kv("-> Freenove Pi_Version", pi_version)
    if pi_version == 2:
        conclude("Connect Version",
                 "MUST be 2. This is a Pi 5, and rpi-ws281x (GPIO18, Connect v1) "
                 "does not work on the RP1 chip. Freenove's led.py refuses the "
                 "v1+Pi5 combination outright.")
    return pi_version


# --- 2. buses enabled --------------------------------------------------------

def section_buses() -> None:
    head("Buses, device nodes, permissions")

    cfg_path = next((p for p in ("/boot/firmware/config.txt", "/boot/config.txt")
                     if os.path.exists(p)), None)
    kv("config.txt", cfg_path or "NOT FOUND")
    if cfg_path:
        txt = read(cfg_path) or ""
        wanted = ("dtparam=i2c_arm", "dtparam=spi", "dtparam=audio",
                  "i2c_arm_baudrate", "camera_auto_detect", "dtoverlay=")
        hits = [l.strip() for l in txt.splitlines()
                if l.strip() and not l.strip().startswith("#")
                and any(w in l for w in wanted)]
        for line in hits:
            kv("", line)
        if not any("dtparam=i2c_arm=on" in h for h in hits):
            conclude("I2C", "dtparam=i2c_arm=on is not in config.txt — every I2C "
                            "device (motors, ADC) will fail. raspi-config > Interface.")
        if not any("dtparam=spi=on" in h for h in hits):
            conclude("SPI", "dtparam=spi=on is not in config.txt — a Connect v2 "
                            "board drives the LEDs over SPI MOSI and will stay dark.")

    i2c = sorted(glob.glob("/dev/i2c-*"))
    spi = sorted(glob.glob("/dev/spidev*"))
    kv("/dev/i2c-*", " ".join(i2c) or "NONE  <- I2C is off")
    kv("/dev/spidev*", " ".join(spi) or "NONE  <- SPI is off")

    my = set()
    for gid in os.getgroups():
        try:
            my.add(grp.getgrgid(gid).gr_name)
        except KeyError:
            my.add(str(gid))
    kv("groups", " ".join(sorted(my)) or "?")
    for need, why in (("i2c", "motors and ADC"), ("spi", "LEDs"), ("gpio", "ultrasonic and line sensors")):
        if need not in my:
            conclude("permissions",
                     f"user is not in the '{need}' group ({why}). "
                     f"`sudo usermod -aG {need} $USER`, then log out and back in. "
                     f"This is why a test can pass under sudo and fail without it.")

    # Bus speed matters only for high-rate control loops, but a mismatch against
    # config.i2c_expected_hz makes the FastAPI stack log a warning at boot.
    for node in glob.glob("/sys/bus/i2c/devices/i2c-*/of_node/clock-frequency"):
        raw = open(node, "rb").read()
        kv(f"{node.split('/')[5]} clock", f"{int.from_bytes(raw[:4], 'big')} Hz")


# --- 3. what is on the I2C bus ----------------------------------------------

KNOWN = {
    0x40: "PCA9685 — 16ch PWM: the four motors (ch0-7) and pan/tilt servos (ch8-9)",
    0x48: "ADS7830 — 8ch ADC: battery on ch2, photoresistors on ch0/ch1",
    0x70: "PCA9685 all-call address (same chip as 0x40, not a second device)",
}


def section_i2c_scan() -> list[int]:
    head("I2C bus scan")
    out = sh("i2cdetect", "-y", "-r", "1", timeout=15)
    if out is None:
        kv("i2cdetect", "not available (sudo apt install i2c-tools) — probing directly")
        found = _probe_direct()
    else:
        print("".join("  " + l + "\n" for l in out.rstrip().splitlines()))
        found = []
        for line in out.splitlines()[1:]:
            base, _, rest = line.partition(":")
            if not rest:
                continue
            for i, cell in enumerate(rest.split()):
                if cell not in ("--", "UU"):
                    found.append(int(base, 16) + i)

    for addr in found:
        kv(f"0x{addr:02x}", KNOWN.get(addr, "unexpected device"))
    for addr, what in (0x40, "PCA9685"), (0x48, "ADS7830"):
        if addr not in found:
            conclude("I2C",
                     f"{what} at 0x{addr:02x} did NOT respond. Either the HAT is not "
                     f"seated, the car's power switch is off (the HAT is battery-powered, "
                     f"the Pi is not), or I2C is disabled.")
    return found


def _probe_direct() -> list[int]:
    bus = _open_bus()
    if bus is None:
        return []
    found = []
    for addr in (0x40, 0x48, 0x70):
        try:
            bus.read_byte(addr)
            found.append(addr)
        except OSError:
            pass
    bus.close()
    return found


def _open_bus():
    for mod in ("smbus2", "smbus"):
        try:
            return __import__(mod).SMBus(1)
        except Exception:
            continue
    return None


# --- 4. the battery, read both ways -----------------------------------------

ADS7830_CMD = 0x84


def _read_adc_raw(bus, channel: int) -> int | None:
    """Raw 0-255 from an ADS7830 channel, read twice for a stable value."""
    cmd = ADS7830_CMD | ((((channel << 2) | (channel >> 1)) & 0x07) << 4)
    try:
        bus.write_byte(0x48, cmd)
        for _ in range(10):
            a = bus.read_byte(0x48)
            b = bus.read_byte(0x48)
            if a == b:
                return a
        return a
    except OSError:
        return None


def section_battery(found: list[int]) -> None:
    head("Battery — the PCB-version discriminator")
    if 0x48 not in found:
        kv("skipped", "no ADS7830 on the bus")
        return
    bus = _open_bus()
    if bus is None:
        kv("skipped", "neither smbus2 nor smbus imports")
        return

    raw = _read_adc_raw(bus, 2)
    if raw is None:
        kv("read", "FAILED")
        bus.close()
        return

    # Freenove scales the raw byte differently per PCB revision:
    #   v1: raw/255 * 3.3 * 3      v2: raw/255 * 5.2 * 2
    # Full scale differs by only 5% (9.9 vs 10.4), so both readings look
    # plausible for a healthy pack. A multimeter across the pack settles it;
    # nothing here can.
    v1 = raw / 255.0 * 3.3 * 3
    v2 = raw / 255.0 * 5.2 * 2
    kv("raw ADC (ch2)", raw)
    kv("as PCB v1", f"{v1:.2f} V")
    kv("as PCB v2", f"{v2:.2f} V")
    kv("difference", f"{abs(v2 - v1):.2f} V  ({abs(v2 - v1) / max(v1, 0.01) * 100:.0f}%)")

    for label, ch in (("photoresistor L (ch0)", 0), ("photoresistor R (ch1)", 1)):
        r = _read_adc_raw(bus, ch)
        kv(label, f"raw {r}" if r is not None else "read failed")
    bus.close()

    if max(v1, v2) < 6.4:
        conclude("battery",
                 f"{max(v1, v2):.2f} V on the more generous scaling is below a 2S "
                 f"empty point. Charge before testing — a sagging pack makes motors "
                 f"and servos fail in ways that look like wiring faults.")
    conclude("PCB Version",
             f"Cannot be settled from the bus: raw {raw} reads {v1:.2f} V as v1 and "
             f"{v2:.2f} V as v2, and both are plausible for 2x 18650. Put a "
             f"multimeter across the pack and take whichever matches. Note this "
             f"affects ONLY the reported battery voltage — it changes no pin, no "
             f"driver, and cannot make a test throw.")


# --- 5. python modules -------------------------------------------------------

MODULES = [
    ("smbus2", "I2C — what the FastAPI stack uses"),
    ("smbus", "I2C — what Freenove's stock code imports"),
    ("spidev", "SPI — Connect v2 LEDs"),
    ("rpi_ws281x", "GPIO18 LEDs — Connect v1 only, broken on Pi 5"),
    ("gpiozero", "ultrasonic and line sensors"),
    ("lgpio", "gpiozero's Pi 5 backend"),
    ("RPi.GPIO", "legacy GPIO, pre-Pi-5 only"),
    ("picamera2", "camera"),
    ("fastapi", "our control stack"),
    ("uvicorn", "our control stack"),
    ("websockets", "realtime teleop — without it every WS handshake is rejected"),
]


def section_modules() -> None:
    head("Python modules")
    import importlib.util
    for name, why in MODULES:
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ValueError):
            spec = None
        mark = "ok " if spec else "-- "
        kv(f"{mark}{name}", why)
    if importlib.util.find_spec("smbus") is None and importlib.util.find_spec("smbus2") is None:
        conclude("modules", "no smbus at all — Freenove's stock code cannot even import. "
                            "`sudo apt install python3-smbus`.")


# --- 6. camera ---------------------------------------------------------------

def section_camera() -> None:
    head("Camera")
    for cmd in ("rpicam-hello", "libcamera-hello"):
        out = sh(cmd, "--list-cameras", timeout=15)
        if out is not None:
            print("".join("  " + l + "\n" for l in out.rstrip().splitlines()) or "  (no output)")
            if "No cameras available" in out:
                conclude("camera", "no camera detected — check the FPC ribbon seating "
                                   "and orientation at both ends.")
            return
    kv("", "no rpicam-hello / libcamera-hello on PATH")


# --- 7. what the software currently believes --------------------------------

def section_current_config(pi_version: int) -> None:
    head("What the software currently believes")

    params = os.path.join(FREENOVE, "Code/Server/params.json")
    if os.path.exists(params):
        try:
            p = json.loads(read(params) or "{}")
        except json.JSONDecodeError:
            p = {}
        kv("Freenove params.json", params)
        for k in ("Connect_Version", "Pcb_Version", "Pi_Version"):
            kv(f"  {k}", p.get(k, "MISSING"))
        if p.get("Pi_Version") not in (None, pi_version):
            conclude("params.json",
                     f"Pi_Version says {p.get('Pi_Version')} but this board is "
                     f"Pi_Version {pi_version}. Regenerate the file.")
        if p.get("Connect_Version") == 1 and pi_version == 2:
            conclude("params.json",
                     "Connect_Version=1 on a Pi 5 is the unsupported combination — "
                     "led.py prints 'not supported' and leaves is_support_led_function "
                     "unset, so every LED call raises AttributeError.")
    else:
        kv("Freenove params.json", "absent — the next test.py run will prompt for versions")

    unit = "/etc/yakrobot/unit.json"
    if os.path.exists(unit):
        kv("per-unit overlay", unit)
        for k, v in (json.loads(read(unit) or "{}")).items():
            kv(f"  {k}", v)
    else:
        kv("per-unit overlay", f"{unit} absent — selftest has not run on this car")

    kv("service", (sh("systemctl", "is-active", "yakrobot-freenove") or "not installed").strip())


def main() -> int:
    print("Freenove 4WD hardware identification — read-only, nothing moves.")
    pi_version = section_board()
    section_buses()
    found = section_i2c_scan()
    section_battery(found)
    section_modules()
    section_camera()
    section_current_config(pi_version)

    head("Conclusions")
    if not CONCLUSIONS:
        print("  Nothing to flag.")
    for topic, text in CONCLUSIONS:
        print(f"\n  [{topic}]")
        for line in _wrap(text, 72):
            print(f"    {line}")
    print("\n  Connect Version is settled by lighting the strip, not by reading a")
    print("  register: run `tools/pi led-probe`.\n")
    return 0


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


if __name__ == "__main__":
    sys.exit(main())
