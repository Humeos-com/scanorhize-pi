#!/usr/bin/env python3
"""
GPIO utility functions for the Raspberry Pi
"""

import sys
from subprocess import run, SubprocessError, CalledProcessError
from time import sleep

from OSUtils import is_raspberry_pi, has_MEGA4
from ConfigApp import getLogger, getUhubctl
from pin_config import get_ch_pin, CONFIG_PIN

# pylint: disable=ungrouped-imports
# pylint: disable=import-error
# Impossible de grouper les imports car les imports conditionnels ne sont pas supportés
if is_raspberry_pi():
    from RPi import GPIO
else:
    import fake_rpi

    sys.modules["RPi"] = fake_rpi.RPi  # Mock RPi module
    sys.modules["RPi.GPIO"] = fake_rpi.RPi.GPIO
    sys.modules["smbus"] = fake_rpi.smbus
    from RPi import GPIO


def init_gpio():
    """Initialize GPIO pins"""
    if not is_raspberry_pi():
        return 0
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        if not has_MEGA4():
            # Turn off scanners
            for i_pin in range(0, 3):
                print(f"Initializing GPIO: {get_ch_pin(i_pin)}")
                GPIO.setup(get_ch_pin(i_pin), GPIO.OUT)
                GPIO.output(get_ch_pin(i_pin), GPIO.LOW)
    except IOError as e:
        getLogger().error("IOError: %s", e)
        return 1
    return 0


def end_gpio():
    """Clean up GPIO"""
    if not is_raspberry_pi():
        return
    GPIO.cleanup()


def enable_4g():
    """Enable 4G USB port"""
    if not is_raspberry_pi():
        return 1
    try:
        if not has_MEGA4():
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(get_ch_pin(3), GPIO.OUT)
            GPIO.output(get_ch_pin(3), GPIO.HIGH)
    except IOError as e:
        getLogger().error("IOError: %s", e)
        return 0
    return 1


def disable_4g():
    """Disable 4G USB port"""
    if not is_raspberry_pi():
        return 1
    try:
        if not has_MEGA4():
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.output(get_ch_pin(3), GPIO.LOW)
            GPIO.cleanup(get_ch_pin(3))
    except IOError as e:
        getLogger().error("IOError: %s", e)
        return 0
    return 1


def turn_usb_on(i_scan: int, time: int):
    """Turn on USB port for scanner"""
    if has_MEGA4():
        # Use Hub 1-1
        # USB ports are numbered starting from 1 with uhubctl
        cmd = f"{getUhubctl()} -l 1-1 -p {i_scan + 1} -a on"
        try:
            run(
                cmd,
                capture_output=True,
                universal_newlines=True,
                shell=True,
                check=True,
            )
            sleep(time)
            return 0
        except (SubprocessError, CalledProcessError) as e:
            getLogger().error("turn_usb_on: %s", e)
            return 1
    else:
        try:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(get_ch_pin(i_scan), GPIO.OUT)
            GPIO.output(get_ch_pin(i_scan), GPIO.HIGH)
            sleep(time)
            return 0
        except IOError as e:
            getLogger().error("turn_usb_on: %s", e)
            return 1


def turn_usb_off(i_scan: int, delay: int = 0):
    """Turn off USB port for scanner"""
    if delay > 0:
        sleep(delay)
    if has_MEGA4():
        cmd = f"{getUhubctl()} -l 1-1 -p {i_scan + 1} -a off"
        try:
            run(
                cmd,
                capture_output=True,
                universal_newlines=True,
                shell=True,
                check=True,
            )
            return 0
        except (SubprocessError, CalledProcessError) as e:
            getLogger().error("turn_usb_off: %s", e)
            return 1
    else:
        try:
            GPIO.output(get_ch_pin(i_scan), GPIO.LOW)
            GPIO.cleanup(get_ch_pin(i_scan))
            return 0
        except IOError as e:
            getLogger().error("turn_usb_off: %s", e)
            return 1


def read_gpio_input(pin: int):
    """Read the GPIO input"""
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        state_ = GPIO.input(pin)
    except IOError as e:
        getLogger().error("IOError: %s", e)
        state_ = 1

    return state_


def read_gpio_config():
    return read_gpio_input(CONFIG_PIN)


def read_gpio_output(pin: int):
    """Read the state of a GPIO output pin

    Args:
        pin (int): The GPIO pin number to read

    Returns:
        int: 1 if the pin is HIGH, 0 if the pin is LOW
    """
    if not is_raspberry_pi():
        return 0
    try:
        state = GPIO.input(pin)
        getLogger().log("GPIO output state pin %d: %d", pin, state)
        return state
    except IOError as e:
        getLogger().error("read_gpio_output IOError: %s", e)
        return 0
