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
REASON_ALARM1 = "0x01"
REASON_ALARM2 = "0x02"
REASON_CLICK = "0x03"
REASON_LOW_VOLTAGE = "0x04"
REASON_VOLTAGE_RESTORE = "0x05"
REASON_OVER_TEMPERATURE = "0x06"
REASON_BELOW_TEMPERATURE = "0x07"
REASON_ALARM1_DELAYED = "0x08"
REASON_USB_5V_CONNECTED = "0x09"
REASON_POWER_CONNECTED = "0x0a"
REASON_REBOOT = "0x0b"


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
            # For lazy initialisation
            self.boot_config_file = None

            # On commence par récupérer le type Witty Pi
            self.get_firmware_id()
            if self.firmware_id is None:
                self.initialized = True
                return

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

        getLogger().error("ERROR: No Witty Pi board found.")
        return None

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

    def is_WittyPi_4_L3V7(self):
        return self.firmware_id == WITTY_PI_4_L3V7_FIRMWARE_ID

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
                getLogger().warning(message)
                return self.i2c_read_byte(register, retry - 1)

            message = f"I2C read {self.i2c_address:02X}:{register:02X} failed after {retry} retries: {e}"
            getLogger().error(message)
            return None

    def i2c_read_word(self, register: int, retry: int = 3) -> Optional[int]:
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
                getLogger().warning(message)
                return self.i2c_read_word(register, retry - 1)

            message = f"I2C read word {self.i2c_address:02X}:{register:02X} failed after {retry} retries: {e}"
            getLogger().error(message)
            return None

    def i2c_write_byte(self, register: int, value: int, retry: int = 0) -> bool:
        """Write a single byte to I2C register using SMBus."""
        if not self.i2c_bus:
            return False

        try:
            self.i2c_bus.write_byte_data(self.i2c_address, register, value)
            # Verify write
            result = self.i2c_read_byte(register)
            if result == value:
                return True
            return False
        except (OSError, IOError) as e:
            if retry < 3:
                time.sleep(1)
                message = f"I2C write {self.i2c_address:02X}:{register:02X} {value:02X} failed, retrying {retry + 1}..."
                getLogger().warning(message)
                return self.i2c_write_byte(register, value, retry + 1)

            message = f"I2C write {self.i2c_address:02X}:{register:02X} {value:02X} failed after {retry} retries: {e}"
            getLogger().error(message)
            return False


def get_power_mode() -> int:
    """Get current power mode using direct I2C access."""
    result = WittyPi().i2c_read_byte(I2C_POWER_MODE)
    return result if result is not None else 0


def get_input_voltage() -> float:
    """Get input voltage using direct I2C access."""
    if get_power_mode() != 0:
        i = WittyPi().i2c_read_byte(I2C_VOLTAGE_IN_I)
        d = WittyPi().i2c_read_byte(I2C_VOLTAGE_IN_D)
        if i is not None and d is not None:
            return float(i) + float(d) / 100
    return 0.0


def get_output_voltage() -> float:
    """Get output voltage using direct I2C access."""
    i = WittyPi().i2c_read_byte(I2C_VOLTAGE_OUT_I)
    d = WittyPi().i2c_read_byte(I2C_VOLTAGE_OUT_D)
    if i is not None and d is not None:
        return float(i) + float(d) / 100
    return 0.0


def get_output_current() -> float:
    """Get output current using direct I2C access."""
    i = WittyPi().i2c_read_byte(I2C_CURRENT_OUT_I)
    d = WittyPi().i2c_read_byte(I2C_CURRENT_OUT_D)
    if i is not None and d is not None:
        return float(i) + float(d) / 100
    return 0.0


def init_i2c_bus():
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
    """Get temperature from LM75B sensor using direct I2C access."""
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

    return 0.0


def clear_alarm_flags(ctrl2_value: Optional[int] = None):
    """Clear alarm flags using direct I2C access."""
    if ctrl2_value is None:
        ctrl2_value = WittyPi().i2c_read_byte(I2C_RTC_CTRL2)

    if ctrl2_value is not None:
        ctrl2_value &= 0xBF  # Clear bit 6
        WittyPi().i2c_write_byte(I2C_RTC_CTRL2, ctrl2_value)

    WittyPi().i2c_write_byte(I2C_CONF_FLAG_ALARM1, 0)
    WittyPi().i2c_write_byte(I2C_CONF_FLAG_ALARM2, 0)


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
        run_command(["shutdown", "-h", "now"])
    else:
        os.remove("/boot/wittypi.lock")


def get_low_voltage_threshold() -> float:
    """Get low voltage threshold using direct I2C access."""
    low_volt = WittyPi().i2c_read_byte(I2C_CONF_LOW_VOLTAGE)
    if low_volt == 255:
        return 0.0
    return low_volt / 10.0


def get_recovery_voltage_threshold() -> float:
    """Get recovery voltage threshold using direct I2C access."""
    # Pour les cartes WittyPi 4 L3V7, on a:
    # 0 => pas d'action sur l'alimentation
    # 1 => on démarre sur l'alimentation
    # Pour les cartes WittyPi 4, on a:
    # 0 si aucune valeur n'est définie
    # ou un voltage en float si une valeur est définie
    rec_volt = WittyPi().i2c_read_byte(I2C_CONF_RECOVERY_VOLTAGE)
    if WittyPi().is_WittyPi_4_L3V7():
        if rec_volt > 0:
            return 1.0
        return 0.0
    if rec_volt == 255:
        return 0.0
    return rec_volt / 10.0


def set_low_voltage_threshold(value: int):
    """Set low voltage threshold using direct I2C access."""
    WittyPi().i2c_write_byte(I2C_CONF_LOW_VOLTAGE, value)


def set_recovery_voltage_threshold(value: int):
    """Set recovery voltage threshold using direct I2C access."""
    if WittyPi().is_WittyPi_4_L3V7():
        if value > 0:
            value = 1
        else:
            value = 0
    else:
        if value == 0:
            value = 255
        else:
            value = int(value * 10)
    WittyPi().i2c_write_byte(I2C_CONF_RECOVERY_VOLTAGE, value)


def clear_low_voltage_threshold():
    """Clear low voltage threshold using direct I2C access."""
    WittyPi().i2c_write_byte(I2C_CONF_LOW_VOLTAGE, 0xFF)


def clear_recovery_voltage_threshold():
    """Clear recovery voltage threshold using direct I2C access."""
    WittyPi().i2c_write_byte(I2C_CONF_RECOVERY_VOLTAGE, 0xFF)


def get_over_temperature_action() -> int:
    """Get over temperature action using direct I2C access."""
    result = WittyPi().i2c_read_byte(I2C_CONF_OVER_TEMP_ACTION)
    return hex2dec(result) if result is not None else 0


def get_over_temperature_point() -> int:
    """Get over temperature point using direct I2C access."""
    temp = WittyPi().i2c_read_byte(I2C_LM75B_TOS)
    if temp is not None:
        if temp > 127:
            temp = temp - 256
        return temp
    return 0


def get_below_temperature_action() -> int:
    """Get below temperature action using direct I2C access."""
    result = WittyPi().i2c_read_byte(I2C_CONF_BELOW_TEMP_ACTION)
    return hex2dec(result) if result is not None else 0


def get_below_temperature_point() -> int:
    """Get below temperature point using direct I2C access."""
    temp = WittyPi().i2c_read_byte(I2C_LM75B_THYST)
    if temp is not None:
        if temp > 127:
            temp = temp - 256
        return temp
    return 0


def over_temperature_action(
    action: Optional[int] = None, point: Optional[int] = None
) -> str:
    """Get or display over temperature action."""
    if action is None:
        action = get_over_temperature_action()
        point = get_over_temperature_point()

    action_map = {1: "Shutdown", 2: "Startup"}
    action_name = action_map.get(action, "None")

    if action_name != "None":
        return f"T>{point}°C → {action_name}"
    return ""


def below_temperature_action(
    action: Optional[int] = None, point: Optional[int] = None
) -> str:
    """Get or display below temperature action."""
    if action is None:
        action = get_below_temperature_action()
        point = get_below_temperature_point()

    action_map = {1: "Shutdown", 2: "Startup"}
    action_name = action_map.get(action, "None")

    if action_name != "None":
        return f"T<{point}°C → {action_name}"
    return ""


def set_over_temperature_action(action: int, temperature: int):
    """Set over temperature action and point using direct I2C access."""
    WittyPi().i2c_write_byte(I2C_CONF_OVER_TEMP_ACTION, action)

    # Handle negative temperatures
    temp_value = temperature
    if temperature < 0:
        temp_value = temperature + 256

    WittyPi().i2c_write_byte(I2C_LM75B_TOS, temp_value)
    WittyPi().i2c_write_byte(I2C_CONF_OVER_TEMP_POINT, temp_value)


def set_below_temperature_action(action: int, temperature: int):
    """Set below temperature action and point using direct I2C access."""
    WittyPi().i2c_write_byte(I2C_CONF_BELOW_TEMP_ACTION, action)

    # Handle negative temperatures
    temp_value = temperature
    if temperature < 0:
        temp_value = temperature + 256

    WittyPi().i2c_write_byte(I2C_LM75B_THYST, temp_value)
    WittyPi().i2c_write_byte(I2C_CONF_BELOW_TEMP_POINT, temp_value)


def clear_over_temperature_action():
    """Clear over temperature action using direct I2C access."""
    WittyPi().i2c_write_byte(I2C_CONF_OVER_TEMP_ACTION, 0x00)


def clear_below_temperature_action():
    """Clear below temperature action using direct I2C access."""
    WittyPi().i2c_write_byte(I2C_CONF_BELOW_TEMP_ACTION, 0x00)


def get_rtc_timestamp() -> int:
    """Get RTC timestamp using direct I2C access."""
    try:
        sec = bcd2dec(WittyPi().i2c_read_byte(I2C_RTC_SECONDS) or 0)
        minutes = bcd2dec(WittyPi().i2c_read_byte(I2C_RTC_MINUTES) or 0)
        hour = bcd2dec(WittyPi().i2c_read_byte(I2C_RTC_HOURS) or 0)
        date = bcd2dec(WittyPi().i2c_read_byte(I2C_RTC_DAYS) or 0)
        month = bcd2dec(WittyPi().i2c_read_byte(I2C_RTC_MONTHS) or 0)
        year = bcd2dec(WittyPi().i2c_read_byte(I2C_RTC_YEARS) or 0)

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


def get_startup_time() -> str:
    """Get startup time using direct I2C access."""
    try:
        sec = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_SECOND_ALARM1) or 0)
        minutes = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_MINUTE_ALARM1) or 0)
        hour = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_HOUR_ALARM1) or 0)
        date = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_DAY_ALARM1) or 0)
        return f"{date:02d} {hour:02d}:{minutes:02d}:{sec:02d}"
    except (OSError, IOError, ValueError, IndexError) as e:
        getLogger().error("Error reading startup time: %s", e)
        return "00 00:00:00"


def get_shutdown_time() -> str:
    """Get shutdown time using direct I2C access."""
    try:
        sec = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_SECOND_ALARM2) or 0)
        minutes = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_MINUTE_ALARM2) or 0)
        hour = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_HOUR_ALARM2) or 0)
        date = bcd2dec(WittyPi().i2c_read_byte(I2C_CONF_DAY_ALARM2) or 0)
        return f"{date:02d} {hour:02d}:{minutes:02d}:{sec:02d}"
    except (OSError, IOError, ValueError, IndexError) as e:
        getLogger().error("Error reading shutdown time: %s", e)
        return "00 00:00:00"


def set_startup_time(date: int, hour: int, minute: int, second: int):
    """Set startup time using direct I2C access."""
    try:
        WittyPi().i2c_write_byte(I2C_CONF_SECOND_ALARM1, dec2bcd(second))
        WittyPi().i2c_write_byte(I2C_CONF_MINUTE_ALARM1, dec2bcd(minute))
        WittyPi().i2c_write_byte(I2C_CONF_HOUR_ALARM1, dec2bcd(hour))
        WittyPi().i2c_write_byte(I2C_CONF_DAY_ALARM1, dec2bcd(date))
    except (OSError, IOError) as e:
        getLogger().error("Error setting startup time: %s", e)


def set_shutdown_time(date: int, hour: int, minute: int, second: int):
    """Set shutdown time using direct I2C access."""
    try:
        WittyPi().i2c_read_byte(I2C_CONF_SECOND_ALARM2, dec2bcd(second))
        WittyPi().i2c_write_byte(I2C_CONF_MINUTE_ALARM2, dec2bcd(minute))
        WittyPi().i2c_write_byte(I2C_CONF_HOUR_ALARM2, dec2bcd(hour))
        WittyPi().i2c_write_byte(I2C_CONF_DAY_ALARM2, dec2bcd(date))
    except (OSError, IOError) as e:
        getLogger().error("Error setting shutdown time: %s", e)


def clear_startup_time():
    """Clear startup time using direct I2C access."""
    try:
        WittyPi().i2c_write_byte(I2C_CONF_SECOND_ALARM1, 0x00)
        WittyPi().i2c_write_byte(I2C_CONF_MINUTE_ALARM1, 0x00)
        WittyPi().i2c_write_byte(I2C_CONF_HOUR_ALARM1, 0x00)
        WittyPi().i2c_write_byte(I2C_CONF_DAY_ALARM1, 0x00)
    except (OSError, IOError) as e:
        getLogger().error("Error clearing startup time: %s", e)


def clear_shutdown_time():
    """Clear shutdown time using direct I2C access."""
    try:
        WittyPi().i2c_write_byte(I2C_CONF_SECOND_ALARM2, 0x00)
        WittyPi().i2c_write_byte(I2C_CONF_MINUTE_ALARM2, 0x00)
        WittyPi().i2c_write_byte(I2C_CONF_HOUR_ALARM2, 0x00)
        WittyPi().i2c_write_byte(I2C_CONF_DAY_ALARM2, 0x00)
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
    except (OSError, IOError) as e:
        getLogger().error("Error checking time synchronization: %s", e)


def net_to_system():
    """Apply network time to system."""
    net_ts = get_network_timestamp()
    if net_ts != -1:
        getLogger().warning("  Applying network time to system...")
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
        WittyPi().i2c_write_byte(I2C_RTC_SECONDS, dec2bcd(time_struct.tm_sec))
        WittyPi().i2c_write_byte(I2C_RTC_MINUTES, dec2bcd(time_struct.tm_min))
        WittyPi().i2c_write_byte(I2C_RTC_HOURS, dec2bcd(time_struct.tm_hour))
        WittyPi().i2c_write_byte(I2C_RTC_DAYS, dec2bcd(time_struct.tm_mday))
        WittyPi().i2c_write_byte(I2C_RTC_WEEKDAYS, dec2bcd(time_struct.tm_wday))
        WittyPi().i2c_write_byte(I2C_RTC_MONTHS, dec2bcd(time_struct.tm_mon))
        WittyPi().i2c_write_byte(I2C_RTC_YEARS, dec2bcd(time_struct.tm_year % 100))

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
