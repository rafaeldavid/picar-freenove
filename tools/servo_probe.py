#!/usr/bin/env python3
"""Drive ONE servo channel, gently, and report whether the I2C bus survived.

    sudo python3 servo_probe.py 8            # centre channel 8, hold, report
    sudo python3 servo_probe.py 8 --pulse 1300 --hold 3

Freenove's `test.py Servo` is a blunt instrument for isolation: its __init__
drives all eight channels to centre at once, then sweeps 50->110 deg. That both
loads the rail with every servo simultaneously and drives a mis-fitted horn into
its end stop. This writes one channel, one pulse, and watches the bus.

Channel map (Freenove servo.py): '0' -> ch8 (pan), '1' -> ch9 (tilt).
Channels 10-15 are unwired on this kit and are the safe target for a control run.

STOP IMMEDIATELY IF THE SERVO BUZZES. That is a stall against an end stop, and
it is what draws the current that corrupts the bus.
"""
import argparse
import sys
import time

ADDR = 0x40
MODE1, PRESCALE, LED0_ON_L = 0x00, 0xFE, 0x06


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("channel", type=int, help="PCA9685 channel (8=pan, 9=tilt)")
    ap.add_argument("--pulse", type=int, default=1500,
                    help="microseconds, 1500 = centre (default: %(default)s)")
    ap.add_argument("--hold", type=float, default=2.0, help="seconds to hold")
    a = ap.parse_args()

    if not 0 <= a.channel <= 15:
        print("channel must be 0-15"); return 2
    if a.channel <= 7:
        print(f"channel {a.channel} is a MOTOR channel on this kit — refusing.")
        print("Servos are 8 (pan) and 9 (tilt); 10-15 are unwired.")
        return 2
    if not 500 <= a.pulse <= 2500:
        print(f"{a.pulse}us is outside the 500-2500us servo range — refusing.")
        return 2

    try:
        import smbus2
    except ImportError:
        print("smbus2 not available"); return 1
    bus = smbus2.SMBus(1)

    def w(reg, val):
        bus.write_byte_data(ADDR, reg, val)

    try:
        # 50 Hz, the servo frame rate. prescale = round(25MHz/(4096*50)) - 1.
        old = bus.read_byte_data(ADDR, MODE1)
        print(f"MODE1 before = 0x{old:02x}")
        w(MODE1, (old & 0x7F) | 0x10)          # sleep to change prescale
        w(PRESCALE, 121)
        w(MODE1, old)
        time.sleep(0.005)
        w(MODE1, old | 0x80)                    # restart
        print(f"PRE_SCALE    = {bus.read_byte_data(ADDR, PRESCALE)} (121 = 50 Hz)")
    except OSError as e:
        print(f"FAILED before touching the servo: {e}")
        print("The bus is broken independently of any servo load.")
        bus.close(); return 1

    off = int(a.pulse * 4096 / 20000)
    base = LED0_ON_L + 4 * a.channel
    print(f"\nchannel {a.channel} -> {a.pulse}us (off count {off}), holding {a.hold}s")
    print("LISTEN. Buzzing = stalled servo. Ctrl+C now if you hear it.\n")

    try:
        for reg, val in ((base, 0), (base + 1, 0), (base + 2, off & 0xFF), (base + 3, off >> 8)):
            w(reg, val)
    except OSError as e:
        print(f"WRITE FAILED while commanding the servo: {e}")
        print(f"-> channel {a.channel}'s load is what corrupts the bus.")
        bus.close(); return 1

    # The interesting part is not the command but whether the bus survives the
    # slew that follows it, so keep reading while the servo actually moves.
    bad = 0
    t0 = time.time()
    while time.time() - t0 < a.hold:
        try:
            bus.read_byte_data(ADDR, MODE1)
        except OSError as e:
            bad += 1
            if bad == 1:
                print(f"bus error {time.time() - t0:.2f}s after the command: {e}")
        time.sleep(0.02)

    if bad:
        print(f"\n{bad} bus errors during the hold.")
        print(f"-> channel {a.channel}'s servo sags the rail as it moves.")
        rc = 1
    else:
        print(f"\nbus clean for {a.hold}s.")
        print(f"-> channel {a.channel} is not the problem at {a.pulse}us.")
        rc = 0

    try:                                        # release the channel
        w(base + 2, 0); w(base + 3, 0)
        print("channel released (0 duty).")
    except OSError:
        print("could not release the channel — power the car off.")
    bus.close()
    return rc


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted — power the car off if a servo is still buzzing")
        sys.exit(130)
