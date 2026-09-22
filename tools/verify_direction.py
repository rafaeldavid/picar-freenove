#!/usr/bin/env python3
"""Check that each wheel turns the way the software thinks it does.

    tools/pi verify-direction            # from the Mac
    cd ~/source && .venv/bin/python ~/diagnostics/verify_direction.py   # on the Pi

THIS MOVES THE CAR. It refuses to start until you confirm the wheels are off
the ground, and it will not accept that confirmation silently -- you have to
type the word.

WHAT IT TESTS, IN ORDER

  1. Each wheel alone, forward then back. Tests DIRECTION and IDENTITY at once:
     if "left front" spins the right rear, the map is wrong in a way that
     driving forward can never reveal.
  2. All four forward, then all four back.
  3. A strafe, on mecanum wheels only. This is the one test that catches two
     wheels swapped between ports -- forward motion looks perfectly correct
     with a swapped pair, and only a lateral command exposes it.

Every burst is short, preceded by a countdown, and followed by a hard stop.
The stop is in a `finally`, so Ctrl-C stops the motors too.
"""

import argparse
import sys
import time

DEFAULT_DUTY = 900      # raised wheels; unit.json's duty_floor_unloaded is 600
DEFAULT_MS = 1200
LEAD_S = 2.0            # your eyes are on the keyboard when you press Enter


def countdown(label: str, lead: float = LEAD_S) -> None:
    print(f"\n  {label}")
    for n in range(int(lead), 0, -1):
        print(f"    {n}...", end="", flush=True)
        time.sleep(1.0)
    print(" GO", flush=True)


def ask(prompt: str) -> str:
    try:
        return input(f"    {prompt} ").strip().lower()
    except EOFError:
        print("\n  no terminal — run this via `tools/pi verify-direction`")
        sys.exit(2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duty", type=int, default=DEFAULT_DUTY)
    ap.add_argument("--ms", type=int, default=DEFAULT_MS)
    ap.add_argument("--skip-strafe", action="store_true",
                    help="skip the floor test; wheel identity then stays unverified")
    a = ap.parse_args()

    if not sys.stdin.isatty():
        print("This asks questions and needs a terminal. Use `tools/pi verify-direction`.")
        return 2
    if a.duty > 1400:
        print(f"refusing duty {a.duty}: this is a bring-up check, not a speed run")
        return 2

    from picar_freenove_fastapi.config import BoardConfig
    from picar_freenove_fastapi.drivers import PCA9685, Motors

    cfg = BoardConfig.load()
    print(__doc__.split("WHAT IT TESTS")[0].strip())
    print(f"\n  map in use: " + ", ".join(f"{k}={tuple(v)}" for k, v in cfg.motor_channels.items()))
    print(f"  wheels: {cfg.wheel_type}   duty: {a.duty}   burst: {a.ms} ms")

    print("\n  SAFETY CHECK")
    print("  The next steps spin the wheels. They must be OFF THE GROUND --")
    print("  car on a box, a book, anything that lifts all four clear.")
    if ask("Type 'raised' to continue:") != "raised":
        print("  stopping. Nothing was moved.")
        return 1

    pca = PCA9685(cfg.pca9685_address, busnum=cfg.i2c_busnum,
                  expected_hz=cfg.i2c_expected_hz)
    pca.set_pwm_freq(cfg.pwm_freq_hz)
    motors = Motors(pca, cfg)

    results = {}
    try:
        # --- 1. one wheel at a time -----------------------------------------
        print("\n" + "=" * 62)
        print("  PART 1 - each wheel alone. Watch which wheel moves, and which way.")
        print("=" * 62)
        for wheel in Motors.ORDER:
            pretty = wheel.replace("_", " ")
            for sign, word in ((1, "FORWARD"), (-1, "BACKWARD")):
                countdown(f"{pretty}  ->  should spin {word}")
                motors._set_wheel(wheel, sign * a.duty)
                time.sleep(a.ms / 1000.0)
                motors.stop()
                time.sleep(0.4)
            ans = ask(f"Did the {pretty.upper()} wheel spin, forward then back? [y/n/other]")
            results[wheel] = ans
            if ans.startswith("n"):
                print(f"      noted: {pretty} did not behave. Continuing.")
            elif ans.startswith("o"):
                which = ask("Which wheel moved instead?")
                results[wheel] = f"wrong wheel: {which}"

        # --- 2. all four together -------------------------------------------
        print("\n" + "=" * 62)
        print("  PART 2 - all four together.")
        print("=" * 62)
        for sign, word in ((1, "FORWARD"), (-1, "BACKWARD")):
            countdown(f"all four  ->  should drive {word}")
            motors.set(*(sign * a.duty,) * 4)
            time.sleep(a.ms / 1000.0)
            motors.stop()
            time.sleep(0.5)
        results["all_four"] = ask("Did all four spin the right way, forward then back? [y/n]")

        # --- 3. strafe, on the floor ----------------------------------------
        if cfg.wheel_type == "mecanum" and not a.skip_strafe:
            print("\n" + "=" * 62)
            print("  PART 3 - strafe. THIS ONE NEEDS THE CAR ON THE FLOOR.")
            print("=" * 62)
            print("  Forward motion looks correct even with two wheels swapped")
            print("  between ports. A strafe is the only cheap way to catch that:")
            print("  the car must slide SIDEWAYS without rotating.")
            print("\n  Put the car on the floor with a clear metre around it.")
            if ask("Type 'floor' when it is down and clear:") != "floor":
                print("  skipping the strafe. Wheel identity stays UNVERIFIED.")
            else:
                for vy, word in ((1200, "LEFT"), (-1200, "RIGHT")):
                    countdown(f"strafe  ->  should slide {word}, not turn")
                    motors.mecanum(0, vy, 0)
                    time.sleep(a.ms / 1000.0)
                    motors.stop()
                    time.sleep(0.8)
                results["strafe"] = ask("Did it slide sideways both ways without spinning? [y/n]")
    except KeyboardInterrupt:
        print("\n  interrupted")
    finally:
        # The only line here that really matters.
        try:
            motors.stop()
            pca.close()
        except Exception:
            pass
        print("\n  motors stopped.")

    # --- verdict -------------------------------------------------------------
    print("\n" + "=" * 62)
    print("  RESULT")
    print("=" * 62)
    for k, v in results.items():
        print(f"    {k:<14} {v}")

    bad = [k for k, v in results.items() if not str(v).startswith("y")]
    if not bad:
        print("\n  Everything behaved. The map in unit.json is correct for this car.")
    else:
        print(f"\n  Problems with: {', '.join(bad)}")
        print("  Do NOT hand-edit motor_channels to chase this. Run the real")
        print("  derivation, which energises one channel at a time and builds")
        print("  the map from what you saw:")
        print("    cd ~/source && picar_freenove_fastapi/.venv/bin/python \\")
        print("        -m picar_freenove_fastapi.selftest motors")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
