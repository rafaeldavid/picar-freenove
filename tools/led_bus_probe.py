#!/usr/bin/env python3
"""Settle Freenove's "Connect Version" by lighting the strip, not by guessing.

Run on the Pi:   python3 led_bus_probe.py        (needs a tty — it asks questions)
Or from the Mac: tools/pi led-probe

The connection board comes in two revisions whose ONLY difference is the pin
that drives the eight WS2812s:

    Connect v1  ->  GPIO18, driven by rpi_ws281x   (needs sudo; dead on a Pi 5)
    Connect v2  ->  GPIO10 / SPI0 MOSI, via spidev (needs dtparam=spi=on)

No register identifies which board you have. The strip lighting up on one bus
and not the other does. This drives each bus in turn and asks what you saw.

Safe: touches only the LED pin. It never opens the PCA9685, so nothing moves.
"""
import os
import sys
import time

FREENOVE_SERVER = os.path.expanduser(
    "~/Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi/Code/Server")
COUNT = 8
BRIGHT = 40          # these are painfully bright at 255; 40 is plenty indoors
HOLD_S = 3.0


def say(msg: str = "") -> None:
    print(msg, flush=True)


def ask_yes(prompt: str) -> bool:
    while True:
        a = input(f"{prompt} [y/n] ").strip().lower()
        if a in ("y", "yes"):
            return True
        if a in ("n", "no"):
            return False


def _import_freenove(module: str):
    if FREENOVE_SERVER not in sys.path:
        sys.path.insert(0, FREENOVE_SERVER)
    return __import__(module)


def try_spi() -> tuple[bool, str]:
    """Connect v2 path: WS2812 bit-banged out of SPI MOSI."""
    if not os.path.exists("/dev/spidev0.0"):
        return False, "/dev/spidev0.0 does not exist — SPI is off (dtparam=spi=on)"
    try:
        mod = _import_freenove("spi_ledpixel")
        strip = mod.Freenove_SPI_LedPixel(COUNT, BRIGHT, "GRB")
    except Exception as e:                                  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"
    try:
        # check_spi_state() is Freenove's own guard; 0 means the bus opened.
        if hasattr(strip, "check_spi_state") and strip.check_spi_state() != 0:
            return False, "spidev opened but check_spi_state() reports not ready"
        strip.set_all_led_color(0, 0, 0)
        strip.show()
        for i in range(COUNT):
            strip.set_led_color(i, 0, 0, 255)               # blue = SPI
            strip.show()
            time.sleep(0.12)
        time.sleep(HOLD_S)
        strip.set_all_led_color(0, 0, 0)
        strip.show()
        return True, "drove /dev/spidev0.0 without error"
    except Exception as e:                                  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"
    finally:
        try:
            strip.led_close()
        except Exception:                                   # noqa: BLE001
            pass


def try_gpio18() -> tuple[bool, str]:
    """Connect v1 path: rpi_ws281x on GPIO18. Root only, and dead on a Pi 5."""
    model = ""
    try:
        with open("/sys/firmware/devicetree/base/model") as f:
            model = f.read()
    except OSError:
        pass
    if "Raspberry Pi 5" in model:
        return False, ("skipped — this is a Pi 5. rpi_ws281x cannot drive GPIO18 "
                       "through the RP1 chip, so a v1 board simply has no working "
                       "LED path here. Jumper GPIO10 to GPIO18 to make it behave "
                       "as v2 (Freenove's own workaround).")
    if os.geteuid() != 0:
        return False, "skipped — rpi_ws281x needs root. Re-run with sudo."
    try:
        mod = _import_freenove("rpi_ledpixel")
        strip = mod.Freenove_RPI_WS281X(COUNT, BRIGHT, "RGB")
    except Exception as e:                                  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"
    try:
        strip.set_all_led_color(0, 0, 0)
        strip.show()
        for i in range(COUNT):
            strip.set_led_color(i, 0, 255, 0)               # green = GPIO18
            strip.show()
            time.sleep(0.12)
        time.sleep(HOLD_S)
        strip.set_all_led_color(0, 0, 0)
        strip.show()
        return True, "drove GPIO18 without error"
    except Exception as e:                                  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"
    finally:
        try:
            strip.led_close()
        except Exception:                                   # noqa: BLE001
            pass


def main() -> int:
    if not os.path.isdir(FREENOVE_SERVER):
        say(f"Freenove reference code not found at {FREENOVE_SERVER}.")
        say("This probe borrows its two WS2812 encoders. Clone the kit repo first.")
        return 1
    if not sys.stdin.isatty():
        say("This probe needs a terminal — run it via `tools/pi led-probe`.")
        return 1

    say(__doc__.strip())
    say()
    say("Make sure the car's power switch is ON (the HAT is battery-powered) and")
    say("that you can see the eight LEDs on top of the car.")
    input("Press Enter when you are watching the strip... ")

    results = {}

    say("\n--- Connect v2 path: SPI0 MOSI / GPIO10. Expect BLUE, one LED at a time.")
    ok, detail = try_spi()
    say(f"    driver: {'no error' if ok else 'FAILED'} — {detail}")
    results["spi"] = ok and ask_yes("    Did the LEDs light BLUE?")

    say("\n--- Connect v1 path: GPIO18 / rpi_ws281x. Expect GREEN, one LED at a time.")
    ok, detail = try_gpio18()
    say(f"    driver: {'no error' if ok else 'FAILED'} — {detail}")
    results["gpio18"] = ok and ask_yes("    Did the LEDs light GREEN?")

    say("\n" + "=" * 68)
    if results["spi"] and not results["gpio18"]:
        say("VERDICT: Connect Version 2  (LEDs on SPI MOSI / GPIO10).")
        say("  Freenove: answer 2 at the 'Enter Connect Version' prompt.")
        say("  FastAPI stack: this is what it assumes — nothing to change.")
    elif results["gpio18"] and not results["spi"]:
        say("VERDICT: Connect Version 1  (LEDs on GPIO18).")
        say("  Freenove: answer 1 at the 'Enter Connect Version' prompt.")
        say("  FastAPI stack: its Leds driver is SPI-ONLY and will NOT drive this")
        say("  board. Either jumper GPIO10 -> GPIO18 (Freenove's own suggestion,")
        say("  tutorial p.5) or the /led endpoint stays dark. Flag this before")
        say("  deploying — nothing else in the stack is affected.")
    elif results["spi"] and results["gpio18"]:
        say("VERDICT: both buses lit the strip — a GPIO10-to-GPIO18 jumper is")
        say("  almost certainly fitted. Use Connect Version 2; it is the path")
        say("  that works on any Pi.")
    else:
        say("VERDICT: neither bus lit the strip. This is a wiring or enablement")
        say("  problem, not a version question. In order:")
        say("    1. Car power switch on? The Pi runs off USB; the LEDs do not.")
        say("    2. `ls /dev/spidev*` — empty means dtparam=spi=on is missing.")
        say("    3. Is your user in the `spi` group? (log out and back in after)")
        say("    4. Re-seat the 5-pin XH-2.54 LED lead at the board end.")
        say("    5. On a Pi older than 4B, Freenove requires blacklisting the")
        say("       audio module or GPIO18 LEDs misbehave (tutorial p.46).")
    say("=" * 68)
    say("\nRecord the answer in notes/HARDWARE.md.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say("\ninterrupted")
        sys.exit(130)
