> **RESOLVED 2026-09-18 — Freenove replaced the board.** They accepted this
> ticket and shipped a new connection board; the operator fitted it and 0x48 now
> answers and reads correctly (battery 6.89 V, both photoresistors responding).
>
> The August diagnosis held up: the ADS7830 was dead at chip level, which is
> what the bus evidence said and why the ticket was worth sending. Kept as a
> record of a diagnosis that was correct and an RMA that worked.

# Freenove support — draft email

To: support@freenove.com
Subject: FNK0043 — no I2C device at 0x48 (ADC); everything else on the board works

---

Hello,

I have the 4WD Smart Car Kit for Raspberry Pi (FNK0043, mecanum wheels,
connection board V2) on a Raspberry Pi 4B running Raspberry Pi OS (Debian 13).

The ADC never appears on the I2C bus. Your tutorial (p.66) says the board
carries chips at 0x48 and 0x40 and shows i2cdetect reporting both. Mine reports
only 0x40:

     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
40: 40 -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: 70 -- -- -- -- -- --

So `sudo python test.py ADC` fails at the first write:
`OSError: [Errno 5] Input/output error`.

**Every other test passes.** test.py Motor, Led, Ultrasonic, Infrared, Servo and
Buzzer all work, and the camera captures at full 2592x1944. Only the ADC fails,
which costs me the battery voltage and both photoresistors. I have attached a
video showing the working tests and the failing one.

I have ruled out the obvious causes. The PCA9685 at 0x40 responds to reads and
writes on the same SDA/SCL lines without a single error, so the bus and wiring
are good. I scanned 0x03-0x77 on every I2C bus the Pi exposes and 0x48 appears
on none of them. The result is identical across several power cycles, a reboot,
and re-seating the connectors. I2C is enabled, my user is in the i2c group, and
params.json is correct. Both S1 and S2 are pressed, and the servos draw about an
amp from the board's 5V rail and work fine, so that rail is live.

Is this a known fault, and can the board be replaced under warranty? I can send
photographs of the board if that would help.

Thanks,
Rafael
