"""
MPPT_utilities.py
Communication library for the Victron BlueSolar MPPT 75/10
via VE.Direct cable (USB-serial) on Raspberry Pi.

Protocol : VE.Direct TEXT mode, 19200 baud, 8N1
Dependencies : stdlib only (termios, os, glob, threading…)
"""

import os
import glob
import csv
import termios
import time
import threading
from dataclasses import dataclass, field
from typing import Optional

LOG_PATH = "/home/pi/Scanorhize/Solar.log"

# CSV columns exported (in order)
_CSV_FIELDS = [
    ("timestamp",  "Timestamp",             lambda f: time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.timestamp))),
    ("type",       "Type",                  None),   # filled by SolarLogger
    ("V",          "Battery voltage (V)",   lambda f: f.battery_voltage),
    ("VPV",        "Panel voltage (V)",     lambda f: f.panel_voltage),
    ("PPV",        "Panel power (W)",       lambda f: f.panel_power),
    ("I",          "Battery current (A)",   lambda f: f.battery_current),
    ("IL",         "Load current (A)",      lambda f: f.load_current),
    ("LOAD",       "Load output",           lambda f: "ON" if f.load_output_on else "OFF"),
    ("CS",         "Charge state",          lambda f: f.charge_state),
    ("ERR",        "Error",                 lambda f: f.error),
    ("MPPT",       "MPPT mode",             lambda f: f.mppt_mode),
    ("H20",        "Yield today (kWh)",     lambda f: f.yield_today),
    ("H22",        "Yield yesterday (kWh)", lambda f: f.yield_yesterday),
    ("H19",        "Yield total (kWh)",     lambda f: f.yield_total),
    ("H21",        "Max power today (W)",   lambda f: f.max_power_today),
]

_CSV_HEADER = [col for _, col, _ in _CSV_FIELDS]


# ---------------------------------------------------------------------------
# Logger CSV
# ---------------------------------------------------------------------------

class SolarLogger:
    """
    Records MPPT data to a spreadsheet-readable CSV file.

    Each row = one timestamped reading.
    Separator ';' (compatible with Excel / LibreOffice).
    Single file, no rotation.

    Row types:
      data         — periodic reading (1 frame every N)
      state_change — charge state (CS) changed
      error        — new error appeared
      alarm        — alarm active

    Example:
        logger = SolarLogger()             # log 1 frame out of 10
        logger.log(frame)
        logger.log(frame, force=True)      # force write
    """

    def __init__(self, path: str = LOG_PATH, every: int = 10):
        """
        Args:
            path:  Path to the CSV file.
            every: Log one 'data' row every N frames received (default 10).
        """
        self._path = path
        self._every = every
        self._frame_count: int = 0
        self._last_cs: Optional[str] = None
        self._last_err: Optional[str] = None
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self):
        """Create directory and CSV header if the file does not exist."""
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        if not os.path.exists(self._path) or os.path.getsize(self._path) == 0:
            with open(self._path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f, delimiter=";").writerow(_CSV_HEADER)

    def _write_row(self, frame: "MPPTFrame", row_type: str):
        row = []
        for key, _, extractor in _CSV_FIELDS:
            if key == "type":
                row.append(row_type)
            elif extractor is not None:
                val = extractor(frame)
                row.append("" if val is None else val)
            else:
                row.append("")
        with self._lock:
            with open(self._path, "a", newline="", encoding="utf-8") as f:
                csv.writer(f, delimiter=";").writerow(row)

    def log(self, frame: "MPPTFrame", force: bool = False):
        """
        Write a row if:
        - it is the N-th frame received (type 'data'), or
        - the charge state changed (type 'state_change'), or
        - a new error appeared (type 'error'), or
        - an alarm is active (type 'alarm'), or
        - force=True.
        """
        self._frame_count += 1
        cs  = frame.charge_state
        err = frame.error

        # Charge state changed
        if cs != self._last_cs and self._last_cs is not None:
            self._write_row(frame, "state_change")
            self._last_cs = cs
            return
        self._last_cs = cs

        # New error (ignore "No error")
        if err != self._last_err and err not in (None, "No error"):
            self._write_row(frame, "error")
            self._last_err = err
            return
        self._last_err = err

        # Active alarm
        if frame.alarm:
            self._write_row(frame, "alarm")
            return

        # Periodic reading: 1 frame every N
        if force or self._frame_count % self._every == 0:
            self._write_row(frame, "data")


# ---------------------------------------------------------------------------
# Serial layer — stdlib only (replaces pyserial)
# ---------------------------------------------------------------------------

class _SerialPort:
    """
    Minimal serial port via termios/os — 8N1, configurable baud, line read.
    Linux/Raspberry Pi only.
    """

    # Baud rate → termios constant mapping
    _BAUD_MAP = {
        9600:   termios.B9600,
        19200:  termios.B19200,
        38400:  termios.B38400,
        57600:  termios.B57600,
        115200: termios.B115200,
    }

    def __init__(self, port: str, baudrate: int = 19200, timeout: float = 2.0):
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._fd: Optional[int] = None

    def open(self):
        self._fd = os.open(self._port, os.O_RDWR | os.O_NOCTTY)

        attrs = termios.tcgetattr(self._fd)
        # iflag: disable all input processing
        attrs[0] = 0
        # oflag: disable all output processing
        attrs[1] = 0
        # cflag: 8N1, receiver enabled, local mode
        baud = self._BAUD_MAP.get(self._baudrate, termios.B19200)
        attrs[2] = baud | termios.CS8 | termios.CREAD | termios.CLOCAL
        # lflag: raw mode (no echo, no signals, no canonical)
        attrs[3] = 0
        # ispeed / ospeed
        attrs[4] = baud
        attrs[5] = baud
        # cc: VMIN=0 (non-blocking), VTIME in tenths of seconds
        cc = list(attrs[6])
        cc[termios.VMIN]  = 0
        cc[termios.VTIME] = max(1, int(self._timeout * 10))  # tenths of s
        attrs[6] = cc

        termios.tcsetattr(self._fd, termios.TCSANOW, attrs)
        termios.tcflush(self._fd, termios.TCIOFLUSH)

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    @property
    def is_open(self) -> bool:
        return self._fd is not None

    def readline(self) -> bytes:
        """Lit jusqu'à '\\n' ou timeout. Retourne les octets lus."""
        buf = bytearray()
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            chunk = os.read(self._fd, 1)
            if chunk:
                buf += chunk
                if chunk == b'\n':
                    break
            else:
                time.sleep(0.005)
        return bytes(buf)


# ---------------------------------------------------------------------------
# Détection du port VE.Direct sans pyserial
# ---------------------------------------------------------------------------

def _find_vedirect_port_linux() -> Optional[str]:
    """
    Finds the USB serial port of the Victron VE.Direct cable (FTDI chip, VID=0403).
    Reads info from /sys/class/tty/.
    """
    candidates = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))

    for port in candidates:
        tty_name = os.path.basename(port)
        # Le chemin sysfs vers idVendor varie selon les niveaux USB
        # On remonte jusqu'à 5 niveaux depuis le device tty
        base = f"/sys/class/tty/{tty_name}/device"
        path = base
        for _ in range(6):
            vid_file = os.path.join(path, "idVendor")
            if os.path.exists(vid_file):
                try:
                    vid = open(vid_file).read().strip().lower()
                    if vid == "0403":   # FTDI — Victron VE.Direct cable
                        return port
                except OSError:
                    pass
            path = os.path.join(path, "..")

    # Fallback : premier ttyUSB disponible
    return candidates[0] if candidates else None


def _list_ports_linux() -> list[dict]:
    """List available USB serial ports by reading /sys/class/tty/."""
    result = []
    for port in sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")):
        tty_name = os.path.basename(port)
        base = f"/sys/class/tty/{tty_name}/device"

        def _read_sysfs(relative: str) -> str:
            # cherche le fichier en remontant jusqu'à 5 niveaux
            path = base
            for _ in range(6):
                f = os.path.join(path, relative)
                if os.path.exists(f):
                    try:
                        return open(f).read().strip()
                    except OSError:
                        break
                path = os.path.join(path, "..")
            return ""

        vid = _read_sysfs("idVendor")
        pid = _read_sysfs("idProduct")
        manufacturer = _read_sysfs("manufacturer")
        product = _read_sysfs("product")
        serial = _read_sysfs("serial")

        result.append({
            "device":       port,
            "description":  product or tty_name,
            "manufacturer": manufacturer,
            "vid":          f"0x{vid.upper()}" if vid else None,
            "pid":          f"0x{pid.upper()}" if pid else None,
            "serial":       serial,
        })
    return result


# ---------------------------------------------------------------------------
# Table de correspondance des champs VE.Direct du MPPT 75/10
# ---------------------------------------------------------------------------
VEDIRECT_LABELS = {
    "V":    ("Battery voltage",          "V",    lambda x: int(x) / 1000),
    "VPV":  ("Panel voltage",            "V",    lambda x: int(x) / 1000),
    "PPV":  ("Panel power",              "W",    lambda x: int(x)),
    "I":    ("Battery current",          "A",    lambda x: int(x) / 1000),
    "IL":   ("Load current",             "A",    lambda x: int(x) / 1000),
    "LOAD": ("Load output state",        "",     lambda x: x),
    "Alarm":("Alarm",                    "",     lambda x: x),
    "Relay":("Relay state",              "",     lambda x: x),
    "AR":   ("Alarm reason",             "bit",  lambda x: int(x)),
    "OR":   ("Off reason",               "hex",  lambda x: x),
    "H19":  ("Yield total",              "kWh",  lambda x: int(x) * 0.01),
    "H20":  ("Yield today",              "kWh",  lambda x: int(x) * 0.01),
    "H21":  ("Max power today",          "W",    lambda x: int(x)),
    "H22":  ("Yield yesterday",          "kWh",  lambda x: int(x) * 0.01),
    "H23":  ("Max power yesterday",      "W",    lambda x: int(x)),
    "HSDS": ("Day sequence number",      "",     lambda x: int(x)),
    "CS":   ("Charge state",             "",     lambda x: CHARGE_STATES.get(int(x), f"Unknown ({x})")),
    "ERR":  ("Error code",               "",     lambda x: ERROR_CODES.get(int(x), f"Error {x}")),
    "MPPT": ("MPPT mode",                "",     lambda x: MPPT_MODES.get(int(x), f"Mode {x}")),
    "FW":   ("Firmware version",         "",     lambda x: x),
    "PID":  ("Product ID",               "",     lambda x: x),
    "SER#": ("Serial number",            "",     lambda x: x),
}

CHARGE_STATES = {
    0:   "Off",
    2:   "Fault",
    3:   "Bulk",
    4:   "Absorption",
    5:   "Float",
    7:   "Equalize (manual)",
    245: "Starting up",
    247: "Auto equalize",
    252: "External control",
}

ERROR_CODES = {
    0:   "No error",
    2:   "Battery voltage too high",
    17:  "Charger temperature too high",
    18:  "Charger over current",
    20:  "Bulk time limit exceeded",
    26:  "Terminals overheated",
    33:  "Input voltage too high (solar panel)",
    34:  "Input current too high (solar panel)",
    38:  "Input shutdown (excessive battery voltage)",
    39:  "Input shutdown (current flow while off)",
    65:  "Lost communication",
    66:  "Incompatible device",
    67:  "BMS connection lost",
    68:  "Network misconfigured",
    116: "Factory calibration data lost",
    117: "Invalid/incompatible firmware",
    119: "User settings invalid",
}

MPPT_MODES = {
    0: "Off",
    1: "Voltage or current limited",
    2: "MPP tracker active",
}


# ---------------------------------------------------------------------------
# VE.Direct HEX protocol — configuration register reading
# ---------------------------------------------------------------------------

_HEX_REGISTERS: dict = {
    "absorption_voltage": (0xEDF7, "uint16", 0.01),   # cV → V  (scale 0.01 per Victron spec)
    "float_voltage":      (0xEDF6, "uint16", 0.01),   # cV → V
    "max_charge_current": (0xEDF0, "uint16", 0.1),    # 100mA → A
    "battery_type":       (0xEDF1, "uint8",  1),      # enum (source: BlueSolar-HEX-protocol.pdf)
    "system_voltage":     (0xEDEF, "uint8",  1),      # V: 0=auto, 12=12V, 24=24V (BlueSolar-HEX-protocol.pdf)
}

# MPPT 75/10 (no rotary switch) has only two types:
#   1   = GEL Victron Deep discharge
#   255 = User defined  ← correct setting for LiFePO4 (set voltages manually)
_HEX_BATTERY_TYPES: dict = {
    1:   "GEL Victron Deep discharge",
    255: "User defined",
}

_HEX_LIFEPO4_TYPES = {255}  # on MPPT 75/10, User defined is the only valid LiFePO4 setting


def _hex_checksum(data: bytes) -> int:
    """Checksum byte such that (sum(data) + checksum) & 0xFF == 0x55."""
    return (0x55 - sum(data)) & 0xFF


def _build_hex_get(register_id: int) -> bytes:
    """Build a VE.Direct HEX GET request for the given register address."""
    lo    = register_id & 0xFF
    hi    = (register_id >> 8) & 0xFF
    flags = 0x00
    cs    = _hex_checksum(bytes([0x07, lo, hi, flags]))
    return f":7{lo:02X}{hi:02X}{flags:02X}{cs:02X}\n".encode("ascii")


def _parse_hex_response(line: str) -> Optional[tuple[int, int, bytes]]:
    """
    Parse a VE.Direct HEX response line.
    Returns (register_id, flags, value_bytes) or None if malformed/bad checksum.
    """
    line = line.strip()
    if not (line.startswith(":") and len(line) >= 10):
        return None

    cmd_char = line[1]
    rest     = line[2:]
    if len(rest) % 2 != 0:
        return None

    try:
        data_bytes = bytes(int(rest[i:i+2], 16) for i in range(0, len(rest), 2))
    except ValueError:
        return None

    if len(data_bytes) < 4:
        return None

    if (int(cmd_char, 16) + sum(data_bytes)) & 0xFF != 0x55:
        return None  # bad checksum

    reg_id      = data_bytes[0] | (data_bytes[1] << 8)
    resp_flags  = data_bytes[2]
    value_bytes = data_bytes[3:-1]   # strip trailing checksum byte
    return reg_id, resp_flags, value_bytes


@dataclass
class MPPTConfig:
    """MPPT configuration registers read via the VE.Direct HEX protocol."""
    absorption_voltage: Optional[float] = None   # V
    float_voltage:      Optional[float] = None   # V
    max_charge_current: Optional[float] = None   # A
    battery_type:       Optional[int]   = None   # raw enum value
    system_voltage:     Optional[int]   = None   # V: 12, 24, etc.


    def battery_type_str(self) -> str:
        if self.battery_type is None:
            return "N/A"
        return _HEX_BATTERY_TYPES.get(self.battery_type, f"Unknown ({self.battery_type})")

    def check_lifepo4_12v(self, capacity_ah: float = 6.0) -> list[tuple[str, str, str]]:
        """
        Validate settings for a LiFePO4 12.8V (4S) battery.
        Returns list of (status, label, detail), status in {'ok','warn','fail'}.
        """
        results = []

        if self.absorption_voltage is not None:
            v = self.absorption_voltage
            if 14.0 <= v <= 14.6:
                results.append(("ok",   "Absorption voltage", f"{v:.2f}V (14.0–14.6V ✔)"))
            elif v < 14.0:
                results.append(("warn", "Absorption voltage", f"{v:.2f}V ⚠ below 14.0V — may undercharge"))
            else:
                results.append(("fail", "Absorption voltage", f"{v:.2f}V ✘ above 14.6V — risk of overcharge"))
        else:
            results.append(("fail", "Absorption voltage", "N/A — register did not respond"))

        if self.float_voltage is not None:
            v = self.float_voltage
            if 13.50 <= v <= 13.55:
                results.append(("ok",   "Float voltage", f"{v:.2f}V (ideal: 13.50V)"))
            elif v < 13.50:
                results.append(("warn", "Float voltage", f"{v:.2f}V ⚠ below 13.50V — battery may not stay topped up"))
            elif v <= 13.8:
                results.append(("warn", "Float voltage", f"{v:.2f}V ⚠ higher than 13.55V recommended — reduces LiFePO4 longevity"))
            else:
                results.append(("fail", "Float voltage", f"{v:.2f}V ✘ above 13.8V — too high for LiFePO4"))
        else:
            results.append(("fail", "Float voltage", "N/A — register did not respond"))

        if self.max_charge_current is not None:
            c      = self.max_charge_current
            c_rate = c / capacity_ah if capacity_ah > 0 else 0
            detail = f"{c:.1f}A ({c_rate:.2f}C for {capacity_ah:.0f}Ah)"
            if c_rate < 0.9:
                results.append(("ok",   "Max charge current", detail))
            else:
                results.append(("fail", "Max charge current", detail + " ✘ too high for this battery"))
        else:
            results.append(("fail", "Max charge current", "N/A — register did not respond"))

        if self.system_voltage is not None:
            sv = self.system_voltage
            if sv == 12:
                results.append(("ok",   "Battery voltage", f"{sv}V"))
            elif sv == 0:
                results.append(("warn", "Battery voltage", "Auto-detect ⚠ — risky if panel connected before battery"))
            else:
                results.append(("fail", "Battery voltage", f"{sv}V ✘ wrong for this 12V battery"))
        else:
            results.append(("fail", "Battery voltage", "N/A — register did not respond"))

        if self.battery_type is not None:
            bt_str = self.battery_type_str()
            if self.battery_type in _HEX_LIFEPO4_TYPES:
                results.append(("ok",   "Battery type", f"{bt_str} (correct for LiFePO4 battery — check configuration values above)"))
            else:
                results.append(("fail", "Battery type", f"{bt_str} ✘ should be User defined for LiFePO4"))
        else:
            results.append(("fail", "Battery type", "N/A — register did not respond"))

        return results


# ---------------------------------------------------------------------------
# Dataclass résultat
# ---------------------------------------------------------------------------
@dataclass
class MPPTFrame:
    """Une trame VE.Direct complète."""
    raw: dict = field(default_factory=dict)
    parsed: dict = field(default_factory=dict)
    descriptions: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    checksum_ok: bool = True

    def get(self, label: str, default=None):
        """Retourne la valeur convertie d'un champ (ex: 'V', 'CS', 'PPV')."""
        return self.parsed.get(label, default)

    # ------------------------------------------------------------------
    # Named properties — electrical measurements
    # ------------------------------------------------------------------

    @property
    def battery_voltage(self) -> Optional[float]:
        """Battery voltage in Volts."""
        return self.parsed.get("V")

    @property
    def panel_voltage(self) -> Optional[float]:
        """Solar panel voltage in Volts."""
        return self.parsed.get("VPV")

    @property
    def panel_power(self) -> Optional[int]:
        """Solar panel power in Watts."""
        return self.parsed.get("PPV")

    @property
    def battery_current(self) -> Optional[float]:
        """Battery current in Amperes, positive = charging."""
        return self.parsed.get("I")

    @property
    def load_current(self) -> Optional[float]:
        """Load output current in Amperes."""
        return self.parsed.get("IL")

    @property
    def load_output_on(self) -> Optional[bool]:
        """True if the load output is active."""
        v = self.parsed.get("LOAD")
        if v is None:
            return None
        return str(v).upper() == "ON"

    # ------------------------------------------------------------------
    # Named properties — state and mode
    # ------------------------------------------------------------------

    @property
    def charge_state(self) -> Optional[str]:
        """Charger state (e.g. 'Bulk', 'Float', 'Off')."""
        return self.parsed.get("CS")

    @property
    def error(self) -> Optional[str]:
        """Active error description (e.g. 'No error')."""
        return self.parsed.get("ERR")

    @property
    def mppt_mode(self) -> Optional[str]:
        """MPPT algorithm mode."""
        return self.parsed.get("MPPT")

    @property
    def alarm(self) -> Optional[bool]:
        """True if an alarm is active."""
        v = self.parsed.get("Alarm")
        if v is None:
            return None
        return str(v).upper() == "ALARM"

    @property
    def relay(self) -> Optional[bool]:
        """True if the relay is closed."""
        v = self.parsed.get("Relay")
        if v is None:
            return None
        return str(v).upper() == "ON"

    # ------------------------------------------------------------------
    # Named properties — history / energy
    # ------------------------------------------------------------------

    @property
    def yield_today(self) -> Optional[float]:
        """Solar yield today in kWh."""
        return self.parsed.get("H20")

    @property
    def yield_yesterday(self) -> Optional[float]:
        """Solar yield yesterday in kWh."""
        return self.parsed.get("H22")

    @property
    def yield_total(self) -> Optional[float]:
        """Total yield since commissioning in kWh."""
        return self.parsed.get("H19")

    @property
    def max_power_today(self) -> Optional[int]:
        """Maximum power reached today in Watts."""
        return self.parsed.get("H21")

    @property
    def max_power_yesterday(self) -> Optional[int]:
        """Maximum power reached yesterday in Watts."""
        return self.parsed.get("H23")

    @property
    def day_number(self) -> Optional[int]:
        """Day sequence number in the internal history."""
        return self.parsed.get("HSDS")

    # ------------------------------------------------------------------
    # Named properties — identification
    # ------------------------------------------------------------------

    @property
    def firmware_version(self) -> Optional[str]:
        """Firmware version."""
        return self.parsed.get("FW")

    @property
    def product_id(self) -> Optional[str]:
        """Victron product ID (e.g. '0xA042' for MPPT 75/10)."""
        return self.parsed.get("PID")

    @property
    def serial_number(self) -> Optional[str]:
        """Device serial number."""
        return self.parsed.get("SER#")

    def summary(self) -> str:
        """Human-readable frame summary."""
        lines = [f"=== MPPT reading — {time.strftime('%H:%M:%S', time.localtime(self.timestamp))} ==="]
        for label, info in VEDIRECT_LABELS.items():
            if label in self.parsed:
                desc, unit, _ = info
                val = self.parsed[label]
                unit_str = f" {unit}" if unit else ""
                lines.append(f"  {desc:<35} {val}{unit_str}")
        if not self.checksum_ok:
            lines.append("  [WARNING] Invalid checksum")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parser VE.Direct TEXT
# ---------------------------------------------------------------------------
class VEDirectParser:
    """Parse the VE.Direct serial stream and reconstruct complete frames."""

    def __init__(self):
        self._buffer: dict[str, str] = {}

    def feed(self, line: str) -> Optional[MPPTFrame]:
        """
        Feed one line from the serial port.
        Returns a complete MPPTFrame when the checksum line is received, otherwise None.
        """
        line = line.strip()
        if not line:
            return None

        if line.startswith("Checksum"):
            frame = self._build_frame()
            self._buffer.clear()
            return frame

        if "\t" in line:
            label, _, value = line.partition("\t")
            self._buffer[label] = value

        return None

    def _build_frame(self) -> MPPTFrame:
        raw = dict(self._buffer)
        parsed = {}
        descriptions = {}

        for label, value in raw.items():
            if label in VEDIRECT_LABELS:
                desc, _, converter = VEDIRECT_LABELS[label]
                try:
                    parsed[label] = converter(value)
                except (ValueError, TypeError):
                    parsed[label] = value
                descriptions[label] = desc
            else:
                parsed[label] = value

        return MPPTFrame(raw=raw, parsed=parsed, descriptions=descriptions)


# ---------------------------------------------------------------------------
# Classe principale
# ---------------------------------------------------------------------------
class MPPTReader:
    """
    Interface haut niveau pour lire les données du Victron MPPT 75/10.

    Usage minimal :
        reader = MPPTReader()
        reader.start()
        frame = reader.latest()
        print(frame.summary())
        reader.stop()

    Ou en one-shot :
        frame = MPPTReader().read_one()
        print(frame.battery_voltage, 'V')
    """

    BAUD_RATE = 19200

    def __init__(
        self,
        port: Optional[str] = None,
        auto_detect: bool = True,
        logger: Optional["SolarLogger"] = None,
    ):
        """
        Args:
            port:       Port série explicite ou None pour détection auto.
            auto_detect: Détection automatique du câble VE.Direct.
            logger:     SolarLogger pour enregistrer les données dans Solar.log.
                        Exemple : MPPTReader(logger=SolarLogger())
        """
        self._port_name = port
        self._auto_detect = auto_detect
        self._solar_logger = logger
        self._serial: Optional[_SerialPort] = None
        self._parser = VEDirectParser()
        self._latest_frame: Optional[MPPTFrame] = None
        self._frame_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False

    # ------------------------------------------------------------------
    # Port detection and listing
    # ------------------------------------------------------------------
    @staticmethod
    def find_vedirect_port() -> Optional[str]:
        """Return the USB serial port of the VE.Direct cable (FTDI), or None."""
        return _find_vedirect_port_linux()

    @staticmethod
    def list_ports() -> list[dict]:
        """List all available USB serial ports with their info."""
        return _list_ports_linux()

    # ------------------------------------------------------------------
    # Open / close
    # ------------------------------------------------------------------
    def open(self) -> str:
        """Open the serial connection. Returns the port name used."""
        if self._port_name is None and self._auto_detect:
            self._port_name = _find_vedirect_port_linux()
        if self._port_name is None:
            raise RuntimeError(
                "No VE.Direct port found. "
                "Pass the port explicitly: MPPTReader(port='/dev/ttyUSB0')"
            )
        self._serial = _SerialPort(self._port_name, baudrate=self.BAUD_RATE, timeout=2.0)
        self._serial.open()
        return self._port_name

    def close(self):
        """Close the serial connection."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    # ------------------------------------------------------------------
    # Blocking read (one-shot)
    # ------------------------------------------------------------------
    def read_one(self, timeout: float = 10.0) -> MPPTFrame:
        """
        Wait for a complete frame and return it.

        Raises:
            TimeoutError: if no frame is received within the timeout.
        """
        was_open = self._serial and self._serial.is_open
        if not was_open:
            self.open()

        deadline = time.time() + timeout
        try:
            while time.time() < deadline:
                raw = self._serial.readline()
                line = raw.decode("ascii", errors="replace")
                frame = self._parser.feed(line)
                if frame:
                    return frame
        finally:
            if not was_open:
                self.close()

        raise TimeoutError(f"No VE.Direct frame received in {timeout}s on {self._port_name}")

    # ------------------------------------------------------------------
    # Continuous reading (background thread)
    # ------------------------------------------------------------------
    def start(self):
        """Start continuous background reading."""
        if self._running:
            return
        self.open()
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True, name="mppt-reader")
        self._thread.start()

    def stop(self):
        """Stop continuous reading."""
        self.close()

    def latest(self) -> Optional[MPPTFrame]:
        """Return the last received frame (None if none yet)."""
        with self._frame_lock:
            return self._latest_frame

    def wait_for_frame(self, timeout: float = 10.0) -> MPPTFrame:
        """Wait for the next complete frame (continuous mode)."""
        deadline = time.time() + timeout
        prev = self._latest_frame
        while time.time() < deadline:
            with self._frame_lock:
                if self._latest_frame is not None and self._latest_frame is not prev:
                    return self._latest_frame
            time.sleep(0.05)
        raise TimeoutError("No new frame received within the timeout.")

    def _read_loop(self):
        while self._running:
            try:
                if not self._serial or not self._serial.is_open:
                    break
                raw = self._serial.readline()
                line = raw.decode("ascii", errors="replace")
                frame = self._parser.feed(line)
                if frame:
                    with self._frame_lock:
                        self._latest_frame = frame
                    if self._solar_logger:
                        self._solar_logger.log(frame)
            except OSError as e:
                print(f"[MPPTReader] Serial error: {e}")
                break
            except Exception as e:
                print(f"[MPPTReader] Unexpected error: {e}")

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()


# ---------------------------------------------------------------------------
# Standalone functions
# ---------------------------------------------------------------------------
def read_mppt(port: Optional[str] = None, timeout: float = 10.0) -> MPPTFrame:
    """
    Return one complete frame from the MPPT (one-shot connection).

    Example:
        frame = read_mppt()
        print(frame.battery_voltage, 'V')
        print(frame.charge_state)
    """
    return MPPTReader(port=port).read_one(timeout=timeout)


def read_config(port: Optional[str] = None, timeout: float = 15.0) -> "MPPTConfig":
    """
    Read MPPT configuration registers via VE.Direct HEX protocol.
    Opens a fresh serial connection independently of read_mppt().

    Strategy: send all GET requests at once, then listen for the full timeout
    collecting every HEX line (GET responses AND async push).  This handles the
    case where the MPPT pushes registers spontaneously (command 'A') rather than
    replying with an explicit GET response (command '7').

    Args:
        port:    Serial port path (None = auto-detect).
        timeout: Total listening timeout in seconds (default 15).

    Returns:
        MPPTConfig with None fields for registers that could not be read.
    """
    if port is None:
        port = _find_vedirect_port_linux()
    if port is None:
        raise RuntimeError("No VE.Direct port found.")

    # Build a reverse map: register address → (attr, reg_type, scale)
    reg_map = {reg_id: (attr, reg_type, scale)
               for attr, (reg_id, reg_type, scale) in _HEX_REGISTERS.items()}

    serial = _SerialPort(port, baudrate=19200, timeout=1.0)
    serial.open()
    config = MPPTConfig()
    hex_lines_seen: list[str] = []

    try:
        termios.tcflush(serial._fd, termios.TCIOFLUSH)

        # Listen and retry: resend GETs every RETRY_INTERVAL seconds for missing registers.
        # The MPPT 75/10 processes HEX commands at ~1Hz (TEXT frame rate), so a burst may
        # get partially dropped. Each register is sent twice per burst for redundancy.
        RETRY_INTERVAL = 1.0
        deadline = time.monotonic() + timeout
        remaining = set(reg_map.keys())
        last_send_time = 0.0  # force send on first iteration

        while remaining and time.monotonic() < deadline:
            if time.monotonic() - last_send_time >= RETRY_INTERVAL:
                for reg_id in remaining:
                    os.write(serial._fd, _build_hex_get(reg_id))
                    time.sleep(0.05)
                    os.write(serial._fd, _build_hex_get(reg_id))  # duplicate for reliability
                    time.sleep(0.05)
                termios.tcdrain(serial._fd)
                last_send_time = time.monotonic()

            raw  = serial.readline()
            line = raw.decode("ascii", errors="replace").strip()
            if not line.startswith(":"):
                continue
            hex_lines_seen.append(line)
            result = _parse_hex_response(line)
            if result is None:
                continue
            resp_reg, flags, value_bytes = result
            if resp_reg not in reg_map:
                continue

            # Got a response for this register — stop retrying regardless of flags
            remaining.discard(resp_reg)

            if flags != 0x00:
                # Register responded with error (0x01=unknown, 0x02=not supported, 0x04=param error)
                hex_lines_seen.append(f"[reg {resp_reg:#06x} error flags={flags:#04x}]")
                continue

            attr, reg_type, scale = reg_map[resp_reg]
            if reg_type == "uint8" and value_bytes:
                raw_val = value_bytes[0]
                setattr(config, attr, raw_val if scale == 1 else round(raw_val * scale, 3))
            elif reg_type == "uint16" and len(value_bytes) >= 2:
                raw_val = value_bytes[0] | (value_bytes[1] << 8)
                setattr(config, attr, round(raw_val * scale, 3))
    finally:
        serial.close()

    all_none = all(getattr(config, f) is None
                   for f in ("absorption_voltage", "float_voltage", "max_charge_current", "battery_type", "system_voltage"))
    if all_none:
        sample = hex_lines_seen[:6] if hex_lines_seen else ["(none — MPPT sent no HEX lines)"]
        raise RuntimeError(f"No registers responded. HEX lines received: {sample}")

    return config


def monitor_mppt(
    port: Optional[str] = None,
    interval: float = 5.0,
    count: int = 0,
    log_path: Optional[str] = LOG_PATH,
    log_every: int = 10,
):
    """
    Display MPPT readings continuously and log them to Solar.log.

    Args:
        port:      Serial port (None = auto-detect).
        interval:  Seconds between terminal displays.
        count:     Number of readings to display (0 = infinite).
        log_path:  CSV file path (None = no log).
        log_every: Log one 'data' row every N frames (default 10).
    """
    logger = SolarLogger(path=log_path, every=log_every) if log_path else None
    reader = MPPTReader(port=port, logger=logger)
    reader.start()
    n = 0
    try:
        while count == 0 or n < count:
            time.sleep(interval)
            frame = reader.latest()
            if frame:
                print(frame.summary())
                print()
                n += 1
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        reader.stop()


# ---------------------------------------------------------------------------
# Quick test when run directly
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    print("Available USB serial ports:")
    ports = MPPTReader.list_ports()
    if ports:
        for p in ports:
            print(f"  {p['device']:15} — {p['description']}  (VID:{p['vid']} PID:{p['pid']})")
    else:
        print("  (none)")

    detected = MPPTReader.find_vedirect_port()
    if detected:
        print(f"\nVE.Direct port detected: {detected}")
    else:
        print("\nNo VE.Direct port detected automatically.")
        sys.exit(1)

    print(f"\nReading one frame on {detected}...\n")
    try:
        frame = read_mppt(port=detected)
        print(frame.summary())

        logger = SolarLogger()
        logger.log(frame, force=True)
        print(f"\nData logged to {LOG_PATH}")

        print("\n--- Named properties ---")
        print(f"  Battery voltage : {frame.battery_voltage} V")
        print(f"  Panel voltage   : {frame.panel_voltage} V")
        print(f"  Panel power     : {frame.panel_power} W")
        print(f"  Battery current : {frame.battery_current} A")
        print(f"  Load output     : {'ON' if frame.load_output_on else 'OFF'}")
        print(f"  Charge state    : {frame.charge_state}")
        print(f"  MPPT mode       : {frame.mppt_mode}")
        print(f"  Error           : {frame.error}")
        print(f"  Yield today     : {frame.yield_today} kWh")
        print(f"  Yield total     : {frame.yield_total} kWh")
        print(f"  Max power today : {frame.max_power_today} W")
        print(f"  Firmware        : {frame.firmware_version}")
        print(f"  Serial number   : {frame.serial_number}")
    except TimeoutError as e:
        print(f"Error: {e}")
    except RuntimeError as e:
        print(f"Error: {e}")
