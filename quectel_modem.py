"""
Quectel modem driver — AT command interface over serial.
Tested on EC25, EG25-G
Requires: pyserial
"""

import re
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import serial

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class SimState(Enum):
    READY       = "READY"
    PIN         = "SIM PIN"
    PUK         = "SIM PUK"
    PIN2        = "SIM PIN2"
    PUK2        = "SIM PUK2"
    NOT_PRESENT = "NOT PRESENT"
    UNKNOWN     = "UNKNOWN"


class RegStatus(Enum):
    NOT_REGISTERED    = 0
    HOME              = 1
    SEARCHING         = 2
    DENIED            = 3
    UNKNOWN           = 4
    ROAMING           = 5
    HOME_SMS_ONLY     = 6
    ROAMING_SMS_ONLY  = 7


@dataclass
class ModemInfo:
    manufacturer: Optional[str] = None
    model:        Optional[str] = None
    revision:     Optional[str] = None
    imei:         Optional[str] = None
    imsi:         Optional[str] = None
    iccid:        Optional[str] = None
    phone_number: Optional[str] = None
    sim_state:    SimState      = SimState.UNKNOWN


@dataclass
class SignalInfo:
    rssi_raw:   Optional[int]   = None   # 0-31, 99 = unknown
    rssi_dbm:   Optional[float] = None   # dBm
    ber:        Optional[int]   = None   # bit error rate 0-7
    operator:   Optional[str]   = None
    technology: Optional[str]   = None   # LTE, WCDMA, GSM…
    band:       Optional[str]   = None
    reg_status: RegStatus       = RegStatus.UNKNOWN


@dataclass
class NetworkInfo:
    apn:        Optional[str] = None
    ip_address: Optional[str] = None
    connected:  bool          = False


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class QuectelModem:
    """
    Serial AT-command interface for Quectel modems.

    Usage:
        with QuectelModem("/dev/ttyUSB2") as modem:
            info = modem.get_modem_info()
            print(info.imei)
    """

    _RSSI_TABLE = {0: -113, 1: -111, **{n: -109 + (n - 2) * 2 for n in range(2, 31)}, 31: -51}

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 3.0):
        self.port     = port
        self.baudrate = baudrate
        self.timeout  = timeout
        self._serial: Optional[serial.Serial] = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.close()

    def open(self):
        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            write_timeout=self.timeout,
        )
        # Flush any stale data
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()
        logger.debug("Serial port %s opened", self.port)

    def close(self):
        if self._serial and self._serial.is_open:
            self._serial.close()
            logger.debug("Serial port %s closed", self.port)

    # ------------------------------------------------------------------
    # Low-level AT transport
    # ------------------------------------------------------------------

    def send_at(self, command: str, wait: float = 1.0) -> list[str]:
        """
        Send an AT command and return response lines (stripped, non-empty).
        Raises RuntimeError if the modem replies ERROR.
        """
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("Serial port is not open")

        self._serial.reset_input_buffer()
        raw = (command.rstrip() + "\r\n").encode()
        self._serial.write(raw)
        logger.debug(">> %s", command)

        time.sleep(wait)

        response = self._serial.read(self._serial.in_waiting or 1024).decode(errors="replace")
        lines = [l.strip() for l in response.splitlines() if l.strip()]
        logger.debug("<< %s", lines)

        if "ERROR" in lines:
            raise RuntimeError(f"AT error for command '{command}': {lines}")

        # Remove echo
        lines = [l for l in lines if l != command.strip()]
        return lines

    def _first_match(self, lines: list[str], pattern: str) -> Optional[re.Match]:
        for line in lines:
            m = re.search(pattern, line)
            if m:
                return m
        return None

    def _value_after_colon(self, lines: list[str], prefix: str) -> Optional[str]:
        for line in lines:
            if line.startswith(prefix + ":"):
                return line.split(":", 1)[1].strip()
        return None

    # ------------------------------------------------------------------
    # Identification
    # ------------------------------------------------------------------

    def get_manufacturer(self) -> Optional[str]:
        lines = self.send_at("AT+CGMI")
        return lines[0] if lines else None

    def get_model(self) -> Optional[str]:
        lines = self.send_at("AT+CGMM")
        return lines[0] if lines else None

    def get_revision(self) -> Optional[str]:
        """Firmware revision string."""
        lines = self.send_at("AT+QGMR")
        return lines[0] if lines else None

    def get_imei(self) -> Optional[str]:
        lines = self.send_at("AT+CGSN")
        for line in lines:
            if re.fullmatch(r"\d{15}", line):
                return line
        return None

    # ------------------------------------------------------------------
    # SIM
    # ------------------------------------------------------------------

    def get_sim_state(self) -> SimState:
        try:
            lines = self.send_at("AT+CPIN?")
        except RuntimeError:
            return SimState.NOT_PRESENT

        raw = self._value_after_colon(lines, "+CPIN") or ""
        try:
            return SimState(raw)
        except ValueError:
            return SimState.UNKNOWN

    def get_imsi(self) -> Optional[str]:
        """International Mobile Subscriber Identity (15 digits)."""
        try:
            lines = self.send_at("AT+CIMI")
        except RuntimeError:
            return None
        for line in lines:
            if re.fullmatch(r"\d{14,15}", line):
                return line
        return None

    def get_iccid(self) -> Optional[str]:
        """SIM card serial number (ICCID)."""
        try:
            lines = self.send_at("AT+QCCID")
        except RuntimeError:
            return None
        raw = self._value_after_colon(lines, "+QCCID")
        if raw:
            return raw.strip("F").strip()
        return None

    def get_phone_number(self) -> Optional[str]:
        """Subscriber number stored on the SIM (not always provisioned)."""
        try:
            lines = self.send_at("AT+CNUM", wait=2.0)
        except RuntimeError:
            return None
        # +CNUM: "label","number",type
        m = self._first_match(lines, r'\+CNUM:\s*"[^"]*","([^"]+)"')
        return m.group(1) if m else None

    def unlock_sim(self, pin: str) -> bool:
        """Send SIM PIN. Returns True on success."""
        try:
            self.send_at(f'AT+CPIN="{pin}"')
            return True
        except RuntimeError:
            return False

    # ------------------------------------------------------------------
    # Network & signal
    # ------------------------------------------------------------------

    def get_signal(self) -> SignalInfo:
        info = SignalInfo()
        try:
            lines = self.send_at("AT+CSQ")
            raw = self._value_after_colon(lines, "+CSQ")
            if raw:
                parts = raw.split(",")
                rssi_raw = int(parts[0])
                info.rssi_raw = rssi_raw
                info.rssi_dbm = self._RSSI_TABLE.get(rssi_raw)
                info.ber = int(parts[1]) if len(parts) > 1 else None
        except (RuntimeError, ValueError):
            pass
        return info

    def get_registration(self) -> RegStatus:
        """EPS (4G) registration; falls back to CS registration."""
        for cmd, prefix in [("AT+CEREG?", "+CEREG"), ("AT+CREG?", "+CREG")]:
            try:
                lines = self.send_at(cmd)
                raw = self._value_after_colon(lines, prefix)
                if raw:
                    # format: n,stat  or just stat
                    stat = int(raw.split(",")[-1])
                    return RegStatus(stat)
            except (RuntimeError, ValueError):
                continue
        return RegStatus.UNKNOWN

    def get_operator(self) -> Optional[str]:
        try:
            lines = self.send_at("AT+COPS?")
        except RuntimeError:
            return None
        raw = self._value_after_colon(lines, "+COPS")
        if not raw:
            return None
        # +COPS: mode,format,"operator",act
        m = re.search(r'"([^"]+)"', raw)
        return m.group(1) if m else None

    def get_network_info(self) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Returns (technology, band, channel). EC25/EG25 specific."""
        try:
            lines = self.send_at("AT+QNWINFO")
        except RuntimeError:
            return None, None, None
        raw = self._value_after_colon(lines, "+QNWINFO")
        if not raw:
            return None, None, None
        parts = [p.strip().strip('"') for p in raw.split(",")]
        technology = parts[0] if len(parts) > 0 else None
        operator   = parts[1] if len(parts) > 1 else None
        band       = parts[2] if len(parts) > 2 else None
        return technology, band, operator

    # ------------------------------------------------------------------
    # Data / PDP
    # ------------------------------------------------------------------

    def get_apn(self) -> Optional[str]:
        try:
            lines = self.send_at("AT+CGDCONT?")
        except RuntimeError:
            return None
        for line in lines:
            # +CGDCONT: 1,"IP","apn.name",...
            m = re.search(r'\+CGDCONT:\s*1,"[^"]*","([^"]*)"', line)
            if m:
                return m.group(1)
        return None

    def get_pdp_address(self) -> Optional[str]:
        """IP address assigned to PDP context 1."""
        try:
            lines = self.send_at("AT+CGPADDR=1")
        except RuntimeError:
            return None
        for line in lines:
            m = re.search(r'\+CGPADDR:\s*1,(.+)', line)
            if m:
                addr = m.group(1).strip().strip('"')
                return addr if addr else None
        return None

    # ------------------------------------------------------------------
    # Hardware
    # ------------------------------------------------------------------

    def get_temperature(self) -> Optional[dict[str, int]]:
        """CPU / PA / board temperatures (Quectel extension AT+QTEMP)."""
        try:
            lines = self.send_at("AT+QTEMP")
        except RuntimeError:
            return None
        raw = self._value_after_colon(lines, "+QTEMP")
        if not raw:
            return None
        # +QTEMP: cpu,pa,board  (values in °C)
        parts = raw.split(",")
        keys = ["cpu", "pa", "board"]
        try:
            return {k: int(v) for k, v in zip(keys, parts)}
        except ValueError:
            return None

    def reset(self, wait_reboot: float = 30.0):
        """Hardware reset via AT+CFUN=1,1. Waits for the modem to come back."""
        try:
            self.send_at("AT+CFUN=1,1", wait=1.0)
        except RuntimeError:
            pass
        self.close()
        logger.info("Modem reset — waiting %.0f s", wait_reboot)
        time.sleep(wait_reboot)
        self.open()

    # ------------------------------------------------------------------
    # Convenience: full snapshot
    # ------------------------------------------------------------------

    def get_modem_info(self) -> ModemInfo:
        """Collect all identification fields in one call."""
        info = ModemInfo()
        info.manufacturer = self.get_manufacturer()
        info.model        = self.get_model()
        info.revision     = self.get_revision()
        info.imei         = self.get_imei()
        info.sim_state    = self.get_sim_state()
        if info.sim_state == SimState.READY:
            info.imsi         = self.get_imsi()
            info.iccid        = self.get_iccid()
            info.phone_number = self.get_phone_number()
        return info

    def get_full_status(self) -> dict:
        """Return a dict with all available data (useful for logging/JSON)."""
        modem   = self.get_modem_info()
        signal  = self.get_signal()
        tech, band, _ = self.get_network_info()

        return {
            "manufacturer": modem.manufacturer,
            "model":        modem.model,
            "revision":     modem.revision,
            "imei":         modem.imei,
            "sim_state":    modem.sim_state.value,
            "imsi":         modem.imsi,
            "iccid":        modem.iccid,
            "phone_number": modem.phone_number,
            "operator":     self.get_operator(),
            "technology":   tech,
            "band":         band,
            "rssi_dbm":     signal.rssi_dbm,
            "reg_status":   self.get_registration().name,
            "apn":          self.get_apn(),
            "ip_address":   self.get_pdp_address(),
            "temperature":  self.get_temperature(),
        }


# ---------------------------------------------------------------------------
# Quick CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser(description="Quectel modem diagnostic")
    parser.add_argument("port", nargs="?", default="/dev/ttyUSB2", help="Serial port")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--at", metavar="CMD", help="Send a raw AT command")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    with QuectelModem(args.port, args.baud) as modem:
        if args.at:
            print("\n".join(modem.send_at(args.at)))
        else:
            status = modem.get_full_status()
            print(json.dumps(status, indent=2, ensure_ascii=False))
