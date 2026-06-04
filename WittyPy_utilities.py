#!/usr/bin/env python3
"""
Utility functions for Witty Pi management and system operations
Converted from utilities.sh (UUGEAR) to Python
"""

import os
import sys
from subprocess import run, CalledProcessError, CompletedProcess
import time
from logging import getLogger
from typing import Optional, Union
from datetime import datetime, timedelta

from version import __version__
from OSUtils import is_raspberry_pi

# pylint: disable=ungrouped-imports
# pylint: disable=import-error
# Impossible de grouper les imports car les imports conditionnels ne sont pas supportés
if is_raspberry_pi():
    from smbus import SMBus
else:
    import fake_rpi

    sys.modules["smbus"] = fake_rpi.smbus
    from smbus import SMBus

# Java Zoned Timestamp, with TZ=UTC
JAVA_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# I2C constants
WITTY_PI_4_L3V7_FIRMWARE_ID = 0x37  # 55 en décimal

I2C_MC_ADDRESS_WITTY_PI_3 = 0x69
I2C_MC_ADDRESS_WITTY_PI_4 = 0x08
I2C_MC_ADDRESS = 0x08
I2C_ID = 0
I2C_VOLTAGE_IN_I = 1
I2C_VOLTAGE_IN_D = 2
I2C_VOLTAGE_OUT_I = 3
I2C_VOLTAGE_OUT_D = 4
I2C_CURRENT_OUT_I = 5
I2C_CURRENT_OUT_D = 6
I2C_POWER_MODE = 7
I2C_LV_SHUTDOWN = 8
I2C_ALARM1_TRIGGERED = 9
I2C_ALARM2_TRIGGERED = 10
I2C_ACTION_REASON = 11
I2C_FW_REVISION = 12

I2C_CONF_ADDRESS = 16
I2C_CONF_DEFAULT_ON = 17
I2C_CONF_PULSE_INTERVAL = 18
I2C_CONF_LOW_VOLTAGE = 19
I2C_CONF_BLINK_LED = 20
I2C_CONF_POWER_CUT_DELAY = 21
I2C_CONF_RECOVERY_VOLTAGE = 22
I2C_CONF_DUMMY_LOAD = 23
I2C_CONF_ADJ_VIN = 24
I2C_CONF_ADJ_VOUT = 25
I2C_CONF_ADJ_IOUT = 26

I2C_CONF_SECOND_ALARM1 = 27
I2C_CONF_MINUTE_ALARM1 = 28
I2C_CONF_HOUR_ALARM1 = 29
I2C_CONF_DAY_ALARM1 = 30
I2C_CONF_WEEKDAY_ALARM1 = 31

I2C_CONF_SECOND_ALARM2 = 32
I2C_CONF_MINUTE_ALARM2 = 33
I2C_CONF_HOUR_ALARM2 = 34
I2C_CONF_DAY_ALARM2 = 35
I2C_CONF_WEEKDAY_ALARM2 = 36

I2C_CONF_RTC_OFFSET = 37
I2C_CONF_RTC_ENABLE_TC = 38
I2C_CONF_FLAG_ALARM1 = 39
I2C_CONF_FLAG_ALARM2 = 40

I2C_CONF_IGNORE_POWER_MODE = 41
I2C_CONF_IGNORE_LV_SHUTDOWN = 42

I2C_CONF_BELOW_TEMP_ACTION = 43
I2C_CONF_BELOW_TEMP_POINT = 44
I2C_CONF_OVER_TEMP_ACTION = 45
I2C_CONF_OVER_TEMP_POINT = 46
I2C_CONF_DEFAULT_ON_DELAY = 47

I2C_LM75B_TEMPERATURE = 50
I2C_LM75B_CONF = 51
I2C_LM75B_THYST = 52
I2C_LM75B_TOS = 53

I2C_RTC_CTRL1 = 54
I2C_RTC_CTRL2 = 55
I2C_RTC_OFFSET = 56
I2C_RTC_RAM_BYTE = 57
I2C_RTC_SECONDS = 58
I2C_RTC_MINUTES = 59
I2C_RTC_HOURS = 60
I2C_RTC_DAYS = 61
I2C_RTC_WEEKDAYS = 62
I2C_RTC_MONTHS = 63
I2C_RTC_YEARS = 64
I2C_RTC_SECOND_ALARM = 65
I2C_RTC_MINUTE_ALARM = 66
I2C_RTC_HOUR_ALARM = 67
I2C_RTC_DAY_ALARM = 68
I2C_RTC_WEEKDAY_ALARM = 69
I2C_RTC_TIMER_VALUE = 70
I2C_RTC_TIMER_MODE = 71

# GPIO constants
HALT_PIN = 4  # halt by GPIO-4 (BCM naming)
SYSUP_PIN = 17  # output SYS_UP signal on GPIO-17 (BCM naming)
CHRG_PIN = 5  # input to detect charging status
STDBY_PIN = 6  # input to detect standby status

# Network constants
INTERNET_SERVER = (
    "http://google.com"  # check network accessibility and get network time
)

# Reasons for startup/shutdown
REASON_ALARM1 = 0x01
REASON_ALARM2 = 0x02
REASON_CLICK = 3
REASON_LOW_VOLTAGE = 0x04
REASON_VOLTAGE_RESTORE = 0x05
REASON_OVER_TEMPERATURE = 0x06
REASON_BELOW_TEMPERATURE = 0x07
REASON_ALARM1_DELAYED = 0x08
REASON_USB_5V_CONNECTED = 0x09
REASON_POWER_CONNECTED = 0x0
REASON_REBOOT = 0x0B


#Witty Pi 5###################################################
#J'ai repris les noms de la wp4 mais par sécurité je valide 
# toutes les adresses vérifiées et testées sur programme par #OK
# Reasons for startup/shutdown - Witty Pi 5

REASON_ALARM1_WP5 = 0x01
REASON_ALARM2_WP5 = 0x02
REASON_CLICK_WP5 = 0x03
REASON_LOW_VOLTAGE_WP5 = 0x04
REASON_VOLTAGE_RESTORE_WP5 = 0x05
REASON_OVER_TEMPERATURE_WP5 = 0x06
REASON_BELOW_TEMPERATURE_WP5 = 0x07
REASON_ALARM1_DELAYED_WP5 = 0x08
REASON_USB_5V_CONNECTED_WP5 = 0x09
REASON_POWER_CONNECTED_WP5 = 0x0A  
REASON_REBOOT_WP5 = 0x0B


# Witty Pi 5 - I2C Addresses

# WP5 n'utilise plus qu'une seule adresse pour tout
I2C_MC_ADDRESS_WP5 = 0x51  # OK
I2C_ID_WP5 = 0


I2C_VOLTAGE_IN_USB_MSB_WP5 = 3
I2C_VOLTAGE_IN_USB_LSB_WP5 = 4

I2C_VOLTAGE_IN_BAT_MSB_WP5 = 5 #OK
I2C_VOLTAGE_IN_BAT_LSB_WP5 = 6 #OK

I2C_VOLTAGE_OUT_MSB_WP5 = 7 #OK
I2C_VOLTAGE_OUT_LSB_WP5 = 8 #OK

I2C_CURRENT_OUT_MSB_WP5 = 9 #OK
I2C_CURRENT_OUT_LSB_WP5 = 10 #OK


I2C_POWER_MODE_WP5 = 11 #OK
I2C_LV_SHUTDOWN_WP5 = 8 
I2C_ALARM1_TRIGGERED_WP5 = 9
I2C_ALARM2_TRIGGERED_WP5 = 10
I2C_ACTION_REASON_WP5 = 14 #OK
I2C_FW_REVISION_WP5 = 12


I2C_CONF_ADDRESS_WP5 = 16
I2C_CONF_DEFAULT_ON_WP5 = 17
I2C_CONF_PULSE_INTERVAL_WP5 = 18
I2C_CONF_LOW_VOLTAGE_WP5 = 22 #OK
I2C_CONF_BLINK_LED_WP5 = 20
I2C_CONF_POWER_CUT_DELAY_WP5 = 18
I2C_CONF_RECOVERY_VOLTAGE_WP5 = 23 #OK
I2C_CONF_DUMMY_LOAD_WP5 = 23
I2C_CONF_ADJ_VIN_WP5 = 24
I2C_CONF_ADJ_VOUT_WP5 = 25
I2C_CONF_ADJ_IOUT_WP5 = 26

# Configuration des Alarmes
I2C_CONF_SECOND_STARTUP_WP5 = 32 #OK
I2C_CONF_MINUTE_STARTUP_WP5 = 33 #OK
I2C_CONF_HOUR_STARTUP_WP5 = 34 #OK
I2C_CONF_DAY_STARTUP_WP5 =  35 #OK

I2C_CONF_SECOND_SHUTDOWN_WP5 = 36 #OK
I2C_CONF_MINUTE_SHUTDOWN_WP5 = 37 #OK
I2C_CONF_HOUR_SHUTDOWN_WP5 = 38 #OK
I2C_CONF_DAY_SHUTDOWN_WP5 = 39 #OK

I2C_CONF_RTC_OFFSET_WP5 = 37
I2C_CONF_RTC_ENABLE_TC_WP5 = 38
I2C_CONF_FLAG_ALARM1_WP5 = 39
I2C_CONF_FLAG_ALARM2_WP5 = 40

I2C_CONF_IGNORE_POWER_MODE_WP5 = 41
I2C_CONF_IGNORE_LV_SHUTDOWN_WP5 = 42

I2C_CONF_BELOW_TEMP_ACTION_WP5 = 43
I2C_CONF_BELOW_TEMP_POINT_WP5 = 44
I2C_CONF_OVER_TEMP_ACTION_WP5 = 42 #OK
I2C_CONF_OVER_TEMP_POINT_WP5 = 43 #OK
I2C_CONF_DEFAULT_ON_DELAY_WP5 = 47

# Capteur de température (Mappé sur registres virtuels 96-98)
I2C_TEMPERATURE_MSB_WP5 = 96  # MSB de la température [cite: 1648]
I2C_TEMPERATURE_LSB_WP5 = 97
I2C_TEMPERATURE_CONF_MSB_WP5 = 98         # Registre de configuration, je ne le mets pas en oeuvre ici
I2C_TEMPERATURE_CONF_LSB_WP5 = 99  

# Registres RTC (Mappés sur registres virtuels 80-95 - RX8025T)
I2C_RTC_CTRL1_WP5 = 95
I2C_RTC_CTRL2_WP5 = 95          # Registre de contrôle combiné
I2C_RTC_OFFSET_WP5 = 93         # Extension/Offset
I2C_RTC_RAM_BYTE_WP5 = 87

I2C_RTC_SECONDS_WP5 = 80#OK
I2C_RTC_MINUTES_WP5 = 81#OK
I2C_RTC_HOURS_WP5 = 82#OK
I2C_RTC_DAYS_WP5 = 84   #OK        = date dans le manual
I2C_RTC_WEEKDAYS_WP5 = 83 #OK  
I2C_RTC_MONTHS_WP5 = 85#OK
I2C_RTC_YEARS_WP5 = 86#OK

I2C_RTC_SECOND_ALARM_WP5 = 88   # Alarme Minute sur ce modèle
I2C_RTC_MINUTE_ALARM_WP5 = 88
I2C_RTC_HOUR_ALARM_WP5 = 89
I2C_RTC_DAY_ALARM_WP5 = 90
I2C_RTC_WEEKDAY_ALARM_WP5 = 90
I2C_RTC_TIMER_VALUE_WP5 = 91    # Timer Counter 0 
I2C_RTC_TIMER_MODE_WP5 = 93     # Via registre extension

#La WP5 n'utilise plus aucun GPIO hors I2C

I2C_LOG_FILE = "/home/pi/Scanorhize/Log/i2c.log"


def _append_i2c_log(address: int, register: int, value: int, purpose: str, success: bool, retry: int = 0):
    """Append one line to the I2C write log file. Only writes when /run/config exists (config mode)."""
    if not os.path.exists("/run/config"):
        return
    status = "OK" if success else "FAIL"
    retry_str = f" retry={retry}" if retry > 0 else ""
    line = (
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | WRITE"
        f" | addr=0x{address:02X} | reg={register} (0x{register:02X})"
        f" | val={value} (0x{value:02X}) | {purpose}{retry_str} | {status}\n"
    )
    try:
        os.makedirs(os.path.dirname(I2C_LOG_FILE), exist_ok=True)
        with open(I2C_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass  # never crash because of logging


class WittyPi:
    """Classe pour la carte Witty Pi qui permet de gérer les paramètres de la carte"""

    _instance = None  # Class variable to store the single instance

    def __new__(cls):
        """Ensure only one instance is created (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super(WittyPi, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the instance if not already initialized."""
        if not hasattr(self, "initialized"):  # Prevent re-initialization
            try:
                self.i2c_bus = SMBus(1)
            except FileNotFoundError:
                getLogger().error("ERROR: I2C bus not available")
                self.i2c_bus = None
                self.initialized = True
                return

            self.i2c_address = I2C_MC_ADDRESS_WITTY_PI_3
            self.firmware_id = 0
            self.reason_click = 0
            # For lazy initialisation
            self.boot_config_file = None

            # On commence par récupérer le type Witty Pi
            self.get_firmware_id()
            if self.firmware_id is None:
                self.initialized = True
                return

            self.get_reason_click()
            self.initialized = True

    def get_firmware_id(self):
        # on teste d'abord la carte Witty Pi 3
        self.i2c_address = I2C_MC_ADDRESS_WITTY_PI_3
        self.firmware_id = self.i2c_read_byte(0x00, 1)
        if self.firmware_id is not None:
            getLogger().warning("Witty Pi 3 board found.")
            return self.firmware_id
        
        getLogger().warning("No Witty Pi 3 board found, trying Witty Pi 4.")
        self.i2c_address = I2C_MC_ADDRESS_WITTY_PI_4
        self.firmware_id = self.i2c_read_byte(0x00, 1)
        if self.firmware_id is not None:
            getLogger().warning("Witty Pi 4 board found.")
            return self.firmware_id
        
        getLogger().warning("No Witty Pi 4 board found, trying Witty Pi 5.")
        self.i2c_address = I2C_MC_ADDRESS_WP5
        self.firmware_id = self.i2c_read_byte(0x00,1)
        if self.firmware_id is not None:
            getLogger().warning("Witty Pi 5 board found.")
            return self.firmware_id

        getLogger().error("ERROR: No Witty Pi board found.")
        return None

    def get_reason_click(self) -> int:
        if self.i2c_bus is None or self.firmware_id is None:
            return 0
        if self.is_WittyPi_5():
            self.reason_click = self.i2c_read_byte(I2C_ACTION_REASON_WP5)>>4
        else :
            self.reason_click = self.i2c_read_byte(I2C_ACTION_REASON)
        return self.reason_click

    def get_boot_config_file(self):
        """Get the appropriate boot config file path based on OS."""
        if self.boot_config_file is None:
            try:
                result = run(
                    ["lsb_release", "-si"], capture_output=True, text=True, check=True
                )
                if result.stdout.strip() == "Ubuntu":
                    self.boot_config_file = "/boot/firmware/usercfg.txt"
                else:
                    self.boot_config_file = "/boot/config.txt"
            except (CalledProcessError, FileNotFoundError):
                self.boot_config_file = "/boot/config.txt"
        return self.boot_config_file

    def is_WittyPi_3(self) -> bool:
        return self.i2c_address == I2C_MC_ADDRESS_WITTY_PI_3

    def is_WittyPi_4(self) -> bool:
        return self.i2c_address == I2C_MC_ADDRESS_WITTY_PI_4

    def is_WittyPi_4_L3V7(self) -> bool:
        return self.firmware_id == WITTY_PI_4_L3V7_FIRMWARE_ID
    
    def is_WittyPi_5(self) -> bool:
        return self.firmware_id == I2C_MC_ADDRESS_WP5

    def is_reason_click(self) -> bool:
        getLogger().info(f"self.reason_click = {self.reason_click}")
        return self.reason_click == REASON_CLICK

    def i2c_read_byte(self, register: int, retry: int = 3) -> Optional[int]:
        """Read a single byte from I2C register using SMBus."""
        if not self.i2c_bus:
            return None
        try:
            data = self.i2c_bus.read_byte_data(self.i2c_address, register)
            return data
        except (OSError, IOError) as e:
            if retry > 1:
                time.sleep(1)
                message = f"I2C read {self.i2c_address:02X}:{register:02X} failed, retrying {retry + 1}..."
                getLogger().info(message)
                return self.i2c_read_byte(register, retry - 1)

            message = f"I2C read {self.i2c_address:02X}:{register:02X} failed after {retry} retries: {e}"
            getLogger().error(message)
            return None

    def i2c_read_word(self, register: int, retry: int = 100) -> Optional[int]:
        """Read a word (16-bit) from I2C register using SMBus."""
        if not self.i2c_bus:
            return None

        try:
            data = self.i2c_bus.read_word_data(self.i2c_address, register)
            return data
        except (OSError, IOError) as e:
            if retry > 1:
                time.sleep(1)
                message = f"I2C read word {self.i2c_address:02X}:{register:02X} failed, retrying {retry + 1}..."
                getLogger().info(message)
                return self.i2c_read_word(register, retry - 1)

            message = f"I2C read word {self.i2c_address:02X}:{register:02X} failed after {retry} retries: {e}"
            getLogger().error(message)
            return None

    def i2c_write_byte(self, register: int, value: int, retry: int = 0, purpose: str = "") -> bool:
        """Write a single byte to I2C register using SMBus."""
        if not self.i2c_bus:
            return False

        try:
            self.i2c_bus.write_byte_data(self.i2c_address, register, value)
            time.sleep(0.02)
            try:
                result = self.i2c_bus.read_byte_data(self.i2c_address, register)
                success = (result == value)
                if not success:
                    #Retry up to 100 times!
                    if retry < 100:
                        time.sleep(0.05)
                        getLogger().info(
                            "I2C verify mismatch addr=0x%02X reg=%d: wrote 0x%02X read 0x%02X, retrying %d...",
                            self.i2c_address, register, value, result, retry + 1,
                        )
                        return self.i2c_write_byte(register, value, retry + 1, purpose)
                    getLogger().error(
                        "I2C verify mismatch addr=0x%02X reg=%d: wrote 0x%02X read 0x%02X after %d retries",
                        self.i2c_address, register, value, result, retry,
                    )
            except (OSError, IOError):
                # Read-back failed but the write raised no exception — treat as OK
                success = True
                getLogger().warning(
                    "I2C verify-read failed addr=0x%02X reg=%d; write probably OK",
                    self.i2c_address, register,
                )
            _append_i2c_log(self.i2c_address, register, value, purpose, success, retry)
            return success
        except (OSError, IOError) as e:
            if retry < 3:
                time.sleep(1)
                message = f"I2C write {self.i2c_address:02X}:{register:02X} {value:02X} failed, retrying {retry + 1}..."
                getLogger().info(message)
                return self.i2c_write_byte(register, value, retry + 1, purpose)

            _append_i2c_log(self.i2c_address, register, value, purpose, False, retry)
            message = f"I2C write {self.i2c_address:02X}:{register:02X} {value:02X} failed after {retry} retries: {e}"
            getLogger().error(message)
            return False


def get_fw_revision() -> Optional[str]:
    """Return firmware version. WittyPi 5: registers 1 (major) + 2 (minor) → '1.4'.
    Other models: register 12 → raw integer string."""
    wp = WittyPi()
    if wp.is_WittyPi_5():
        major = wp.i2c_read_byte(1)
        minor_raw = wp.i2c_read_byte(2)
        if major is None or minor_raw is None:
            return None
        return f"{major}.{minor_raw}"
    val = wp.i2c_read_byte(I2C_FW_REVISION)
    return str(val) if val is not None else None


def get_power_cut_delay() -> Optional[int]:
    """Return power cut delay in seconds. WittyPi 5: register 18. Other models: register 21."""
    wp = WittyPi()
    if wp.is_WittyPi_5():
        return wp.i2c_read_byte(I2C_CONF_POWER_CUT_DELAY_WP5)
    return wp.i2c_read_byte(I2C_CONF_POWER_CUT_DELAY)


def set_power_cut_delay(value: int) -> bool:
    """Write the power cut delay register. Returns True if confirmed by readback."""
    wp = WittyPi()
    reg = I2C_CONF_POWER_CUT_DELAY_WP5 if wp.is_WittyPi_5() else I2C_CONF_POWER_CUT_DELAY
    wp.i2c_write_byte(reg, value)
    readback = wp.i2c_read_byte(reg)
    return readback == value


def get_power_mode() -> int:
    """Get current power mode using direct I2C access."""
    if is_WittyPi_5() :
        result = WittyPi().i2c_read_byte(I2C_POWER_MODE_WP5)
    else:
        result = WittyPi().i2c_read_byte(I2C_POWER_MODE)
    return result if result is not None else 0


def get_usb_voltage() -> float:
    """Get USB 5V input voltage (WittyPi 5 only). Returns 0.0 on WP3/WP4."""
    if not is_WittyPi_5():
        return 0.0
    lsb = WittyPi().i2c_read_byte(I2C_VOLTAGE_IN_USB_LSB_WP5)
    msb = WittyPi().i2c_read_byte(I2C_VOLTAGE_IN_USB_MSB_WP5)
    if lsb is not None and msb is not None:
        return (msb * 256 + lsb) / 1000
    return 0.0


def get_input_voltage() -> float:
    """Get input voltage using direct I2C access."""
    
    if not is_WittyPi_5():
        if get_power_mode() != 0:
            i = WittyPi().i2c_read_byte(I2C_VOLTAGE_IN_I)
            d = WittyPi().i2c_read_byte(I2C_VOLTAGE_IN_D)
            if i is not None and d is not None:
                return float(i) + float(d) / 100
    #sur wp5, on peut lire vin sans problème meme en s'alimentant sur USB
    #ici je choisis de lire toujours vin... on pourrait lire vusb si besoin
    else :
            lsb = WittyPi().i2c_read_byte(I2C_VOLTAGE_IN_BAT_LSB_WP5)
            msb = WittyPi().i2c_read_byte(I2C_VOLTAGE_IN_BAT_MSB_WP5)
            if lsb is not None and msb is not None:
                return (msb * 256 + lsb) / 1000 
    return 0.0


def get_output_voltage() -> float:
    """Get output voltage using direct I2C access."""
    if not is_WittyPi_5():
        i = WittyPi().i2c_read_byte(I2C_VOLTAGE_OUT_I)
        d = WittyPi().i2c_read_byte(I2C_VOLTAGE_OUT_D)
        if i is not None and d is not None:
            return float(i) + float(d) / 100
    else :
        lsb = WittyPi().i2c_read_byte(I2C_VOLTAGE_OUT_LSB_WP5)
        msb = WittyPi().i2c_read_byte(I2C_VOLTAGE_OUT_MSB_WP5)
        if lsb is not None and msb is not None:
            return (msb * 256 + lsb) / 1000 
    return 0.0


def get_output_current() -> float:
    """Get output current using direct I2C access."""
    if not is_WittyPi_5():
        i = WittyPi().i2c_read_byte(I2C_CURRENT_OUT_I)
        d = WittyPi().i2c_read_byte(I2C_CURRENT_OUT_D)
        if i is not None and d is not None:
            return float(i) + float(d) / 100
    else:
        lsb = WittyPi().i2c_read_byte(I2C_CURRENT_OUT_LSB_WP5)
        msb = WittyPi().i2c_read_byte(I2C_CURRENT_OUT_MSB_WP5)
        if lsb is not None and msb is not None:
            return (msb * 256 + lsb) / 1000 
    return 0.0


def is_WittyPi_3() -> bool:
    return WittyPi().is_WittyPi_3()


def is_WittyPi_4() -> bool:
    return WittyPi().is_WittyPi_4()


def is_WittyPi_4_L3V7() -> bool:
    return WittyPi().is_WittyPi_4_L3V7()

def is_WittyPi_5() -> bool:
    return WittyPi().is_WittyPi_5()


def is_reason_click() -> bool:
    return WittyPi().is_reason_click()


def init_i2c_bus() -> bool:
    return WittyPi().i2c_bus is not None


def close_i2c_bus():
    """Close I2C bus connection."""
    if WittyPi().i2c_bus is not None:
        try:
            WittyPi().i2c_bus.close()
            WittyPi().i2c_bus = None
            getLogger().info("I2C bus closed")
        except (OSError, IOError) as e:
            getLogger().error("Error closing I2C bus: %s", e)


# Determine boot config file based on OS
def get_boot_config_file() -> str:
    return WittyPi().get_boot_config_file()


def run_command(cmd: list, capture_output: bool = True) -> CompletedProcess:
    """Run a shell command and return the result."""
    try:
        return run(cmd, capture_output=capture_output, text=True, check=False)
    except CalledProcessError as e:
        getLogger().error("Command failed: %s - %s", " ".join(cmd), e)
        return CompletedProcess(cmd, returncode=1, stdout="", stderr=str(e))


def one_wire_confliction() -> bool:
    """Check if there's a one-wire conflict with the halt pin."""
    if HALT_PIN == 4:
        if (
            run_command(
                ["grep", "-qe", r"^\s*dtoverlay=w1-gpio\s*$", get_boot_config_file()]
            ).returncode
            == 0
        ):
            return True
        if (
            run_command(
                [
                    "grep",
                    "-qe",
                    r"^\s*dtoverlay=w1-gpio-pullup\s*$",
                    get_boot_config_file(),
                ]
            ).returncode
            == 0
        ):
            return True

    patterns = [
        rf"^\s*dtoverlay=w1-gpio,gpiopin={HALT_PIN}\s*$",
        rf"^\s*dtoverlay=w1-gpio-pullup,gpiopin={HALT_PIN}\s*$",
    ]

    for pattern in patterns:
        if (
            run_command(["grep", "-qe", pattern, get_boot_config_file()]).returncode
            == 0
        ):
            return True

    return False


def has_internet() -> bool:
    """Check if internet connection is available."""
    try:
        result = run_command(["curl", "-s", "--head", INTERNET_SERVER])
        return len(result.stdout) > 0
    except (OSError, IOError, CalledProcessError) as e:
        getLogger().error("Error checking internet connection: %s", e)
        return False


# pylint: disable=too-many-nested-blocks
def get_network_timestamp() -> int:
    """Get network timestamp from internet server."""
    if has_internet():
        try:
            result = run_command(["curl", "-s", "--head", INTERNET_SERVER])
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.startswith("Date: "):
                        date_str = line[6:]  # Remove 'Date: ' prefix
                        timestamp = run_command(["date", "-d", date_str, "+%s"])
                        if timestamp.returncode == 0:
                            return int(timestamp.stdout.strip())
        except (OSError, IOError, ValueError, IndexError, CalledProcessError) as e:
            getLogger().error("Error getting network timestamp: %s", e)
    return -1


def is_mc_connected() -> bool:
    """Check if the microcontroller is connected via I2C."""
    return WittyPi().firmware_id is not None


def get_pi_model() -> str:
    """Get Raspberry Pi model information."""
    try:
        with open("/proc/device-tree/model", "r", encoding="utf-8") as f:
            return f.read().strip()
    except (OSError, IOError, ValueError, IndexError) as e:
        getLogger().error("Error reading Pi model: %s", e)
        return "Unknown"


def get_os() -> str:
    """Get operating system information."""
    try:
        result = run_command(["hostnamectl"])
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "Operating System:" in line:
                    return line.split("Operating System: ")[1].strip()
    except (OSError, IOError, CalledProcessError) as e:
        getLogger().error("Error getting OS info: %s", e)
    return "Unknown"


def get_kernel() -> str:
    """Get kernel version information."""
    try:
        result = run_command(["uname", "-sr"])
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, IOError, CalledProcessError) as e:
        getLogger().error("Error getting kernel info: %s", e)
    return "Unknown"


def get_arch() -> str:
    """Get system architecture."""
    try:
        result = run_command(["dpkg", "--print-architecture"])
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, IOError, CalledProcessError) as e:
        getLogger().error("Error getting architecture: %s", e)
    return "Unknown"


def get_sys_time() -> str:
    """Get current system time as formatted string."""
    return time.strftime("%Y-%m-%d %H:%M:%S %Z")


def get_sys_timestamp() -> int:
    """Get current system timestamp."""
    return int(time.time())


def bcd2dec(bcd_value: int) -> int:
    """Convert BCD value to decimal."""
    return (bcd_value // 16) * 10 + (bcd_value & 0xF)


def dec2bcd(dec_value: int) -> int:
    """Convert decimal value to BCD."""
    return (dec_value // 10) * 16 + (dec_value % 10)


def dec2hex(dec_value: int) -> str:
    """Convert decimal value to hexadecimal string."""
    return f"0x{dec_value:02x}"


def hex2dec(hex_value: Union[str, int]) -> int:
    """Convert hexadecimal value to decimal."""
    if isinstance(hex_value, str):
        return int(hex_value, 16)
    return int(hex_value)


def trim(text: str) -> str:
    """Remove leading and trailing whitespace."""
    return text.strip()


def get_temperature() -> float:
    """Get temperature from LM75B or TMP112 sensor using direct I2C access."""
    if not is_WittyPi_5() :
        try:
            data = WittyPi().i2c_read_word(I2C_LM75B_TEMPERATURE)
            if data is not None:
                # Swap bytes and shift right by 5
                data = (((data & 0xFF) << 8) | ((data & 0xFF00) >> 8)) >> 5

                # Handle negative temperatures
                if data >= 0x400:
                    data = (data & 0x3FF) - 1024

                celsius = data * 0.125

                return float(celsius)
        except (OSError, IOError, ValueError, IndexError) as e:
            getLogger().error("Error reading temperature: %s", e)
    else :
        lsb = WittyPi().i2c_read_byte(I2C_TEMPERATURE_LSB_WP5)
        msb = WittyPi().i2c_read_byte(I2C_TEMPERATURE_MSB_WP5)
        if lsb is not None and msb is not None:
            raw = (msb << 4) | (lsb >> 4)
            if raw > 2047: #handling negative temp
                raw -= 4096
            return raw  * 0.0625
    return 0.0


def clear_alarm_flags(ctrl2_value: Optional[int] = None):
    """Clear alarm flags using direct I2C access."""

    if not is_WittyPi_5() : #no need to clear registers on wp5
        if ctrl2_value is None:
            ctrl2_value = WittyPi().i2c_read_byte(I2C_RTC_CTRL2)

        if ctrl2_value is not None:
            ctrl2_value &= 0xBF  # Clear bit 6 of CTRL2 - PCF85063 (wp4)
            WittyPi().i2c_write_byte(I2C_RTC_CTRL2, ctrl2_value, purpose="clear alarm flag bit in RTC CTRL2 (PCF85063)")

        WittyPi().i2c_write_byte(I2C_CONF_FLAG_ALARM1, 0, purpose="clear startup alarm flag")
        WittyPi().i2c_write_byte(I2C_CONF_FLAG_ALARM2, 0, purpose="clear shutdown alarm flag")

    


def do_shutdown(halt_pin: int, has_mc: bool):
    """Perform system shutdown."""
    # Restore halt pin
    run_command(["gpio", "-g", "mode", str(halt_pin), "in"])
    run_command(["gpio", "-g", "mode", str(halt_pin), "up"])

    # Clear alarm flags if microcontroller is present
    if has_mc:
        clear_alarm_flags()

    getLogger().warning("Halting all processes and then shutdown Raspberry Pi...")

    # Check for lock file
    if not os.path.exists("/boot/wittypi.lock"):
        run_command(["sudo", "shutdown", "-h", "now"])
    else:
        os.remove("/boot/wittypi.lock")


def doShutdown():
    return do_shutdown(HALT_PIN, is_mc_connected())


def get_default_on() -> bool:
    """Return True if WittyPi is configured to turn on automatically when powered."""
    if is_WittyPi_5():
        value = WittyPi().i2c_read_byte(I2C_CONF_DEFAULT_ON_WP5)
    else:
        value = WittyPi().i2c_read_byte(I2C_CONF_DEFAULT_ON)
    return value


def set_default_on(value: int) -> bool:
    """Write the default-on delay register (0=immediately, 255=stay off, N=delay in seconds).
    Returns True if the write was confirmed by readback."""
    reg = I2C_CONF_DEFAULT_ON_WP5 if is_WittyPi_5() else I2C_CONF_DEFAULT_ON
    WittyPi().i2c_write_byte(reg, value)
    readback = WittyPi().i2c_read_byte(reg)
    return readback == value


def get_low_voltage_threshold() -> float:
    """Get low voltage threshold using direct I2C access."""
    # Pour WittyPi 5 : 0 => disabled ; entier = vseuil x10
    # Pour wp4 : 255 => disabled ; entier = vseuil x10 
    if not is_WittyPi_5():
        low_volt = WittyPi().i2c_read_byte(I2C_CONF_LOW_VOLTAGE)
        if low_volt == 255:
            return 0.0
    else :
        low_volt = WittyPi().i2c_read_byte(I2C_CONF_LOW_VOLTAGE_WP5)
    return low_volt / 10.0


def get_recovery_voltage_threshold() -> float:
    """Get recovery voltage threshold using direct I2C access."""
    #Recovery voltage = valeur minimale Vin pour que la wpi accepte de démarrer
    # Pour les cartes WittyPi 4 L3V7, on a:
    # 255 = disabled ; int = vseuil x10
    # Pour les cartes WittyPi 4, on a:
    # 0 si aucune valeur n'est définie
    # ou un voltage en float si une valeur est définie
    # sur wp5 : 0 = désactivé ; int = vseuilx10 
   
    if WittyPi().is_WittyPi_4_L3V7():
        rec_volt = WittyPi().i2c_read_byte(I2C_CONF_RECOVERY_VOLTAGE)
        if rec_volt == 255:
            return 0.0
            
    elif WittyPi().is_WittyPi_5():
        rec_volt = WittyPi().i2c_read_byte(I2C_CONF_RECOVERY_VOLTAGE_WP5)

    return rec_volt / 10.0


def set_low_voltage_threshold(value: int):
    """Set low voltage threshold using direct I2C access."""
    if not is_WittyPi_5():
        WittyPi().i2c_write_byte(I2C_CONF_LOW_VOLTAGE, value, purpose="set low voltage shutdown threshold")
    else:
        WittyPi().i2c_write_byte(I2C_CONF_LOW_VOLTAGE_WP5, value, purpose="set low voltage shutdown threshold (WP5)")


def set_recovery_voltage_threshold(value: int):
    """Set recovery voltage threshold using direct I2C access."""
    if WittyPi().is_WittyPi_4_L3V7():
        if value > 0:
            value = 1
        else:
            value = 0
    else:
        if value == 0 and not is_WittyPi_5():
            value = 255
        else:
            value = int(value)
    if not is_WittyPi_5():
        WittyPi().i2c_write_byte(I2C_CONF_RECOVERY_VOLTAGE, value, purpose="set minimum Vin to allow startup (recovery voltage)")
    else:
        WittyPi().i2c_write_byte(I2C_CONF_RECOVERY_VOLTAGE_WP5, value, purpose="set minimum Vin to allow startup (recovery voltage, WP5)")



def set_over_temperature_action(action: int, temperature: int):
    """Set over temperature action and point using direct I2C access."""
    if (
        WittyPi().firmware_id is None
        or WittyPi().firmware_id != WITTY_PI_4_L3V7_FIRMWARE_ID
        or WittyPi().firmware_id != I2C_MC_ADDRESS_WP5
    ):
        return
    if not is_WittyPi_5():
        WittyPi().i2c_write_byte(I2C_CONF_OVER_TEMP_ACTION, action, purpose="set action when over-temp threshold crossed")
    else:
        WittyPi().i2c_write_byte(I2C_CONF_OVER_TEMP_ACTION_WP5, action, purpose="set action when over-temp threshold crossed (WP5)")

    # Handle negative temperatures
    temp_value = temperature
    if temperature < 0:
        temp_value = temperature + 256

    if not is_WittyPi_5() :
        WittyPi().i2c_write_byte(I2C_LM75B_TOS, temp_value, purpose="set LM75B over-temp trip point (TOS register)")
        WittyPi().i2c_write_byte(I2C_CONF_OVER_TEMP_POINT, temp_value, purpose="set over-temperature threshold point")
    else:
        WittyPi().i2c_write_byte(I2C_CONF_OVER_TEMP_POINT_WP5, temp_value, purpose="set over-temperature threshold point (WP5)")


def get_rtc_timestamp() -> int:
    """Get RTC timestamp using direct I2C access."""
    try:
        if not is_WittyPi_5():
            sec = bcd2dec(WittyPi().i2c_read_byte(I2C_RTC_SECONDS) or 0)
            minutes = bcd2dec(WittyPi().i2c_read_byte(I2C_RTC_MINUTES) or 0)
            hour = bcd2dec(WittyPi().i2c_read_byte(I2C_RTC_HOURS) or 0)
            date = bcd2dec(WittyPi().i2c_read_byte(I2C_RTC_DAYS) or 0)
            month = bcd2dec(WittyPi().i2c_read_byte(I2C_RTC_MONTHS) or 0)
            year = bcd2dec(WittyPi().i2c_read_byte(I2C_RTC_YEARS) or 0)
        
        else : #voir manuel du rx8025T section 8.2 registers (c'est du BCD aussi)
            sec =  bcd2dec(WittyPi().i2c_read_byte(I2C_RTC_SECONDS_WP5) or 0)
            minutes =  bcd2dec(WittyPi().i2c_read_byte(I2C_RTC_MINUTES_WP5)or 0)
            hour =  bcd2dec(WittyPi().i2c_read_byte(I2C_RTC_HOURS_WP5)or 0)
            date =  bcd2dec(WittyPi().i2c_read_byte(I2C_RTC_DAYS_WP5)or 0)
            month =  bcd2dec(WittyPi().i2c_read_byte(I2C_RTC_MONTHS_WP5)or 0)
            year = bcd2dec( WittyPi().i2c_read_byte(I2C_RTC_YEARS_WP5)or 0)



        if year == 0:  # Invalid year
            return -1

        # Create datetime string and convert to timestamp
        dt_str = (
            f"{2000 + year}-{month:02d}-{date:02d} {hour:02d}:{minutes:02d}:{sec:02d}"
        )
        timestamp = run_command(["date", "-d", dt_str, "+%s"])
        if timestamp.returncode == 0:
            return int(timestamp.stdout.strip())
    except (OSError, IOError, ValueError, IndexError) as e:
        getLogger().error("Error reading RTC timestamp: %s", e)

    return -1

def parse_wittypi_time(value):
    """
    Converts Witty Pi format:
        '28 08:02:12'
    into a datetime using current month/year.
    """
    from datetime import datetime
    now = datetime.now()

    parts = value.strip().split(" ")
    day = int(parts[0])

    t = datetime.strptime(parts[1], "%H:%M:%S")

    dt = datetime(
        year=now.year,
        month=now.month,
        day=day,
        hour=t.hour,
        minute=t.minute,
        second=t.second,
    )

    # Handle next month rollover
    if dt < now:
        if now.month == 12:
            dt = dt.replace(year=now.year + 1, month=1)
        else:
            dt = dt.replace(month=now.month + 1)

    return dt
    

def get_startup_time() -> str:
    """Get startup time using direct I2C access."""
    try:
        if not is_WittyPi_5():
            sec = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_SECOND_ALARM1) or 0)
            minutes = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_MINUTE_ALARM1) or 0)
            hour = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_HOUR_ALARM1) or 0)
            date = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_DAY_ALARM1) or 0)
        else:
            sec = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_SECOND_STARTUP_WP5) or 0)
            minutes = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_MINUTE_STARTUP_WP5) or 0)
            hour = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_HOUR_STARTUP_WP5) or 0)
            date = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_DAY_STARTUP_WP5) or 0)
        return f"{date:02d} {hour:02d}:{minutes:02d}:{sec:02d}"
    except (OSError, IOError, ValueError, IndexError) as e:
        getLogger().error("Error reading startup time: %s", e)
        return "00 00:00:00"


def get_shutdown_time() -> str:
    """Get shutdown time using direct I2C access."""
    try:
        if not is_WittyPi_5():
            sec = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_SECOND_ALARM2) or 0)
            minutes = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_MINUTE_ALARM2) or 0)
            hour = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_HOUR_ALARM2) or 0)
            date = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_DAY_ALARM2) or 0)
        else:
            sec = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_SECOND_SHUTDOWN_WP5) or 0)
            minutes = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_MINUTE_SHUTDOWN_WP5) or 0)
            hour = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_HOUR_SHUTDOWN_WP5) or 0)
            date = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_DAY_SHUTDOWN_WP5) or 0)
        return f"{date:02d} {hour:02d}:{minutes:02d}:{sec:02d}"
    except (OSError, IOError, ValueError, IndexError) as e:
        getLogger().error("Error reading shutdown time: %s", e)
        return "00 00:00:00"


def set_startup_time(date: int, hour: int, minute: int, second: int):
    """Set startup time using direct I2C access."""
    try:
        if not is_WittyPi_5():
            WittyPi().i2c_write_byte(I2C_CONF_SECOND_ALARM1, dec2bcd(second), purpose="set startup alarm seconds")
            WittyPi().i2c_write_byte(I2C_CONF_MINUTE_ALARM1, dec2bcd(minute), purpose="set startup alarm minutes")
            WittyPi().i2c_write_byte(I2C_CONF_HOUR_ALARM1, dec2bcd(hour), purpose="set startup alarm hours")
            WittyPi().i2c_write_byte(I2C_CONF_DAY_ALARM1, dec2bcd(date), purpose="set startup alarm day")
        else:
            WittyPi().i2c_write_byte(I2C_CONF_SECOND_STARTUP_WP5, dec2bcd(second), purpose="set startup seconds (WP5)")
            WittyPi().i2c_write_byte(I2C_CONF_MINUTE_STARTUP_WP5, dec2bcd(minute), purpose="set startup minutes (WP5)")
            WittyPi().i2c_write_byte(I2C_CONF_HOUR_STARTUP_WP5, dec2bcd(hour), purpose="set startup hours (WP5)")
            WittyPi().i2c_write_byte(I2C_CONF_DAY_STARTUP_WP5, dec2bcd(date), purpose="set startup day (WP5)")

    except (OSError, IOError) as e:
        getLogger().error("Error setting startup time: %s", e)


def SetNextStartDate(date):  # date en UTC!!
    """Set the next startup time for the WittyPi.
    If the parsing of the date fails, the next day is used as default.
    Args:
        date (str): Date string in format "YYYY-MM-DDTHH:mm:ssZ"
    Returns:
        int: Result of set_startup_time call, or 0 if not on Raspberry Pi
    """

    if not is_raspberry_pi():
        return 0
    # Get current date plus one day for defaults
    tomorrow = datetime.utcnow() + timedelta(days=1)
    defaults = {
        "year": tomorrow.year,
        "month": tomorrow.month,
        "day": tomorrow.day,
        "hour": tomorrow.hour,
        "mins": tomorrow.minute,
        "secs": tomorrow.second,
    }

    # Parse date components with error handling
    try:
        # Extract components using string slicing
        components = {
            "year": int(date[0:4]),
            "month": int(date[5:7]),
            "day": int(date[8:10]),
            "hour": int(date[11:13]),
            "mins": int(date[14:16]),
            "secs": int(date[17:19]),
        }
    except (ValueError, IndexError) as e:
        # Use tomorrow's date if parsing fails
        components = defaults
        getLogger().error("Error parsing date: %s", e)

    return set_startup_time(
        components["day"], components["hour"], components["mins"], components["secs"]
    )


def set_shutdown_time(date: int, hour: int, minute: int, second: int):
    """Set shutdown time using direct I2C access."""
    try:
        if not is_WittyPi_5():
            WittyPi().i2c_write_byte(I2C_CONF_SECOND_ALARM2, dec2bcd(second), purpose="set shutdown alarm seconds")
            WittyPi().i2c_write_byte(I2C_CONF_MINUTE_ALARM2, dec2bcd(minute), purpose="set shutdown alarm minutes")
            WittyPi().i2c_write_byte(I2C_CONF_HOUR_ALARM2, dec2bcd(hour), purpose="set shutdown alarm hours")
            WittyPi().i2c_write_byte(I2C_CONF_DAY_ALARM2, dec2bcd(date), purpose="set shutdown alarm day")
        else:
            WittyPi().i2c_write_byte(I2C_CONF_SECOND_SHUTDOWN_WP5, dec2bcd(second), purpose="set shutdown seconds (WP5)")
            WittyPi().i2c_write_byte(I2C_CONF_MINUTE_SHUTDOWN_WP5, dec2bcd(minute), purpose="set shutdown minutes (WP5)")
            WittyPi().i2c_write_byte(I2C_CONF_HOUR_SHUTDOWN_WP5, dec2bcd(hour), purpose="set shutdown hours (WP5)")
            WittyPi().i2c_write_byte(I2C_CONF_DAY_SHUTDOWN_WP5, dec2bcd(date), purpose="set shutdown day (WP5)")

    except (OSError, IOError) as e:
        getLogger().error("Error setting shutdown time: %s", e)


# pylint: disable=duplicate-code
def setNextShutdownDate(date: str):
    """_summary_
    Args:
        date (str): Date in JAVA format
    Returns:
        result: Date in WittyPi format "DD HH MM SS"
    """
    if not is_raspberry_pi():
        return 0
    try:
        date_obj = datetime.strptime(date, JAVA_FORMAT)
        date = date_obj.strftime("%d %H %M %S")
    except ValueError:
        date = "01 06 25 00"
    datew = date.split(" ")
    return set_shutdown_time(int(datew[0]), int(datew[1]), int(datew[2]), int(datew[3]))


def clear_startup_time():
    """Clear startup time using direct I2C access."""
    try:
        if not is_WittyPi_5():
            WittyPi().i2c_write_byte(I2C_CONF_SECOND_ALARM1, 0x00, purpose="clear startup alarm seconds")
            WittyPi().i2c_write_byte(I2C_CONF_MINUTE_ALARM1, 0x00, purpose="clear startup alarm minutes")
            WittyPi().i2c_write_byte(I2C_CONF_HOUR_ALARM1, 0x00, purpose="clear startup alarm hours")
            WittyPi().i2c_write_byte(I2C_CONF_DAY_ALARM1, 0x00, purpose="clear startup alarm day")
        else:
            WittyPi().i2c_write_byte(I2C_CONF_SECOND_STARTUP_WP5, 0x00, purpose="clear startup seconds (WP5)")
            WittyPi().i2c_write_byte(I2C_CONF_MINUTE_STARTUP_WP5, 0x00, purpose="clear startup minutes (WP5)")
            WittyPi().i2c_write_byte(I2C_CONF_HOUR_STARTUP_WP5, 0x00, purpose="clear startup hours (WP5)")
            WittyPi().i2c_write_byte(I2C_CONF_DAY_STARTUP_WP5, 0x00, purpose="clear startup day (WP5)")
    except (OSError, IOError) as e:
        getLogger().error("Error clearing startup time: %s", e)


def clear_shutdown_time():
    """Clear shutdown time using direct I2C access."""
    try:
        if not is_WittyPi_5():
            WittyPi().i2c_write_byte(I2C_CONF_SECOND_ALARM2, 0x00, purpose="clear shutdown alarm seconds")
            WittyPi().i2c_write_byte(I2C_CONF_MINUTE_ALARM2, 0x00, purpose="clear shutdown alarm minutes")
            WittyPi().i2c_write_byte(I2C_CONF_HOUR_ALARM2, 0x00, purpose="clear shutdown alarm hours")
            WittyPi().i2c_write_byte(I2C_CONF_DAY_ALARM2, 0x00, purpose="clear shutdown alarm day")
        else:
            WittyPi().i2c_write_byte(I2C_CONF_SECOND_SHUTDOWN_WP5, 0x00, purpose="clear shutdown seconds (WP5)")
            WittyPi().i2c_write_byte(I2C_CONF_MINUTE_SHUTDOWN_WP5, 0x00, purpose="clear shutdown minutes (WP5)")
            WittyPi().i2c_write_byte(I2C_CONF_HOUR_SHUTDOWN_WP5, 0x00, purpose="clear shutdown hours (WP5)")
            WittyPi().i2c_write_byte(I2C_CONF_DAY_SHUTDOWN_WP5, 0x00, purpose="clear shutdown day (WP5)")
    except (OSError, IOError) as e:
        getLogger().error("Error clearing shutdown time: %s", e)


def check_sys_and_rtc_time():
    """Check if system and RTC time are synchronized."""
    try:
        rtc_ts = get_rtc_timestamp()
        if rtc_ts == -1:
            print("[Warning] RTC time is invalid or not available.")
            return

        sys_ts = get_sys_timestamp()
        delta = abs(rtc_ts - sys_ts)

        if delta > 10:
            rtc_time = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(rtc_ts))
            sys_time = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(sys_ts))

            print(
                f"[Warning] System and RTC time seem not synchronized, difference is {delta}s."
            )
            print(f'System time is "{sys_time}", while RTC time is "{rtc_time}".')
            print("Please synchronize the time first.")
        else :
            print(f"[Warning] OK : System and RTC time are synchronized, difference is {delta}s.")
    except (OSError, IOError) as e:
        getLogger().error("Error checking time synchronization: %s", e)


def net_to_system():
    """Apply network time to system."""
    net_ts = get_network_timestamp()
    if net_ts != -1:
        getLogger().info("  Applying network time to system...")
        try:
            run_command(["sudo", "date", "-u", "-s", f"@{net_ts}"])
            getLogger().info("  Done :-)")
        except (OSError, IOError) as e:
            getLogger().error("  Error setting system time: %s", e)
    else:
        getLogger().warning("  Cannot get legitimate network time.")


def system_to_rtc():
    """Write system time to RTC using direct I2C access."""
    getLogger().warning("  Writing system time to RTC...")
    try:
        sys_ts = get_sys_timestamp()
        time_struct = time.localtime(sys_ts)

        # Write to RTC registers using direct I2C access

        if not is_WittyPi_5:
            WittyPi().i2c_write_byte(I2C_RTC_SECONDS, dec2bcd(time_struct.tm_sec), purpose="sync system seconds to RTC")
            WittyPi().i2c_write_byte(I2C_RTC_MINUTES, dec2bcd(time_struct.tm_min), purpose="sync system minutes to RTC")
            WittyPi().i2c_write_byte(I2C_RTC_HOURS, dec2bcd(time_struct.tm_hour), purpose="sync system hours to RTC")
            WittyPi().i2c_write_byte(I2C_RTC_DAYS, dec2bcd(time_struct.tm_mday), purpose="sync system day to RTC")
            WittyPi().i2c_write_byte(I2C_RTC_WEEKDAYS, dec2bcd(time_struct.tm_wday), purpose="sync system weekday to RTC")
            WittyPi().i2c_write_byte(I2C_RTC_MONTHS, dec2bcd(time_struct.tm_mon), purpose="sync system month to RTC")
            WittyPi().i2c_write_byte(I2C_RTC_YEARS, dec2bcd(time_struct.tm_year % 100), purpose="sync system year to RTC")
        else:
            WittyPi().i2c_write_byte(I2C_RTC_SECONDS_WP5, dec2bcd(time_struct.tm_sec), purpose="sync system seconds to RTC (WP5)")
            WittyPi().i2c_write_byte(I2C_RTC_MINUTES_WP5, dec2bcd(time_struct.tm_min), purpose="sync system minutes to RTC (WP5)")
            WittyPi().i2c_write_byte(I2C_RTC_HOURS_WP5, dec2bcd(time_struct.tm_hour), purpose="sync system hours to RTC (WP5)")
            WittyPi().i2c_write_byte(I2C_RTC_DAYS_WP5, dec2bcd(time_struct.tm_mday), purpose="sync system day to RTC (WP5)")
            WittyPi().i2c_write_byte(I2C_RTC_WEEKDAYS_WP5, dec2bcd(time_struct.tm_wday), purpose="sync system weekday to RTC (WP5)")
            WittyPi().i2c_write_byte(I2C_RTC_MONTHS_WP5, dec2bcd(time_struct.tm_mon), purpose="sync system month to RTC (WP5)")
            WittyPi().i2c_write_byte(I2C_RTC_YEARS_WP5, dec2bcd(time_struct.tm_year % 100), purpose="sync system year to RTC (WP5)")

        getLogger().info("  Done :-)")
    except (OSError, IOError) as e:
        getLogger().error("  Error writing to RTC: %s", e)


def rtc_to_system():
    """Write RTC time to system."""
    getLogger().warning("  Writing RTC time to system...")
    try:
        rtc_ts = get_rtc_timestamp()
        if rtc_ts != -1:
            run_command(["sudo", "timedatectl", "set-ntp", "0"])
            run_command(["sudo", "date", "-s", f"@{rtc_ts}"])

            getLogger().info("  Done :-)")
        else:
            getLogger().warning("  RTC time is invalid, cannot set system time")
    except (OSError, IOError) as e:
        getLogger().error("  Error setting system time from RTC: %s", e)


def current_timestamp() -> int:
    """Get current timestamp from RTC or system."""
    try:
        rtc_ts = get_rtc_timestamp()
        if rtc_ts > 0:
            return rtc_ts
    except (OSError, IOError):
        pass
    return int(time.time())


def schedule_script_interrupted() -> bool:
    """Check if scheduled script was interrupted."""
    startup_time = get_startup_time()
    shutdown_time = get_shutdown_time()

    if startup_time != "00 00:00:00" and shutdown_time != "00 00:00:00":
        try:
            # Parse times and check if we're in the shutdown period
            # This is a simplified version - would need proper time parsing
            return False
        except (OSError, IOError):
            return False
    return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        prog="utilities.py",
        usage="%(prog)s [--version] [--check]",
        epilog="Utility functions for Witty Pi management and system operations",
    )
    parser.add_argument(
        "-v", "--version", action="store_true", help="Display program version"
    )
    parser.add_argument(
        "-c", "--check", action="store_true", help="Check system status"
    )

    args = parser.parse_args()

    if args.version:
        print(f"utilities.py version: {__version__}")
        sys.exit(0)

    if args.check:
        print(f"Pi Model: {get_pi_model()}")
        print(f"OS: {get_os()}")
        print(f"Kernel: {get_kernel()}")
        print(f"Architecture: {get_arch()}")
        print(f"System Time: {get_sys_time()}")
        print(f"I2C Available: {init_i2c_bus()}")
        print(f"MC Connected: {is_mc_connected()}")
        print(f"Internet Available: {has_internet()}")
        print(f"One Wire Conflict: {one_wire_confliction()}")

        if is_mc_connected():
            print(f"Input Voltage: {get_input_voltage():.3f}V")
            print(f"Output Voltage: {get_output_voltage():.3f}V")
            print(f"Output Current: {get_output_current():.3f}A")
            print(f"Power Mode: {get_power_mode()}")
            print(f"Temperature: {get_temperature()}")
            print(f"Low Voltage Threshold: {get_low_voltage_threshold()}")
            print(f"Recovery Voltage Threshold: {get_recovery_voltage_threshold()}")
            print(f"Startup Time: {get_startup_time()}")
            print(f"Shutdown Time: {get_shutdown_time()}")
            print(f"RTC Timestamp: {get_rtc_timestamp()}")
    else:
        print("Use -h for help or -c to check system status")

    # Clean up I2C bus when done
    close_i2c_bus()
