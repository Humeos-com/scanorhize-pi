#!/usr/bin/env python3
"""
Write a set of registers to WittyPi 5 and report how many retries were needed.
Usage: sudo python3 test_i2c_retries.py
"""

import time
from smbus import SMBus

# --- Ensure I2C baudrate is set in /boot/firmware/config.txt ---
CONFIG_FILE  = "/boot/firmware/config.txt"
BAUDRATE_LINE = "dtparam=i2c_arm_baudrate=50000"

with open(CONFIG_FILE, "r") as f:
    config = f.read()

if BAUDRATE_LINE in config:
    print(f"[config] {BAUDRATE_LINE} already set.")
else:
    with open(CONFIG_FILE, "a") as f:
        f.write(f"\n{BAUDRATE_LINE}\n")
    print(f"[config] Added: {BAUDRATE_LINE}")
    print("[config] Reboot required for baudrate change to take effect.")

WP5_ADDR  = 0x51
WP5_BUS   = 1
DELAY_S   = 0.02   # settling delay between write and readback
MAX_RETRY = 5

# Registers to write: (register, value, description)
REGISTERS = [
    (32, 0x00, "startup  second"),
    (33, 0x30, "startup  minute  (30)"),
    (34, 0x14, "startup  hour    (20)"),
    (35, 0x01, "startup  day     (1)"),
    (36, 0x00, "shutdown second"),
    (37, 0x25, "shutdown minute  (25)"),
    (38, 0x14, "shutdown hour    (20)"),
    (39, 0x01, "shutdown day     (1)"),
]

LOOPS = 10

bus = SMBus(WP5_BUS)

grand_writes   = 0
grand_retries  = 0
grand_failures = 0

for loop in range(1, LOOPS + 1):
    print(f"\n--- Loop {loop}/{LOOPS} ---")
    print(f"{'REG':>4}  {'VAL':>4}  {'RETRIES':>7}  {'RESULT':<8}  DESCRIPTION")
    print("-" * 60)

    loop_retries  = 0
    loop_failures = 0

    for reg, val, desc in REGISTERS:
        retries = 0
        success = False

        for attempt in range(MAX_RETRY + 1):
            try:
                bus.write_byte_data(WP5_ADDR, reg, val)
                time.sleep(DELAY_S)
                readback = bus.read_byte_data(WP5_ADDR, reg)
                if readback == val:
                    success = True
                    break
                else:
                    retries += 1
                    time.sleep(0.05)
            except (OSError, IOError):
                retries += 1
                time.sleep(0.05)

        loop_retries  += retries
        if not success:
            loop_failures += 1

        status = "OK" if success else "FAIL"
        print(f"  {reg:02d}    0x{val:02X}  {retries:>7}  {status:<8}  {desc}")

    grand_writes   += len(REGISTERS)
    grand_retries  += loop_retries
    grand_failures += loop_failures
    print(f"  → loop retries: {loop_retries}  failures: {loop_failures}")

bus.close()

print("\n" + "=" * 60)
print(f"  TOTAL: {grand_writes} writes — {grand_retries} retries — {grand_failures} failures")
if grand_retries == 0:
    print("  → No retries at all: I2C is reliable at this speed.")
elif grand_failures == 0:
    print(f"  → All writes succeeded eventually ({grand_retries} retries over {LOOPS} loops).")
else:
    print(f"  → {grand_failures} write(s) failed even after {MAX_RETRY} retries — consider lowering baudrate.")
