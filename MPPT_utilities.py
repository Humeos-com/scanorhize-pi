"""
MPPT_utilities.py
Bibliothèque de communication avec le Victron BlueSolar MPPT 75/10
via câble VE.Direct (USB-série) sur Raspberry Pi.

Protocole : VE.Direct TEXT mode, 19200 bauds, 8N1
Dépendances : stdlib uniquement (termios, os, glob, threading…)
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

# Colonnes exportées dans le CSV (dans l'ordre)
_CSV_FIELDS = [
    ("timestamp",  "Horodatage",            lambda f: time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.timestamp))),
    ("type",       "Type",                  None),   # rempli par SolarLogger
    ("V",          "Tension batterie (V)",  lambda f: f.battery_voltage),
    ("VPV",        "Tension panneau (V)",   lambda f: f.panel_voltage),
    ("PPV",        "Puissance panneau (W)", lambda f: f.panel_power),
    ("I",          "Courant batterie (A)",  lambda f: f.battery_current),
    ("IL",         "Courant charge (A)",    lambda f: f.load_current),
    ("LOAD",       "Sortie charge",         lambda f: "ON" if f.load_output_on else "OFF"),
    ("CS",         "État charge",           lambda f: f.charge_state),
    ("ERR",        "Erreur",                lambda f: f.error),
    ("MPPT",       "Mode MPPT",             lambda f: f.mppt_mode),
    ("H20",        "Production jour (kWh)", lambda f: f.yield_today),
    ("H22",        "Production hier (kWh)", lambda f: f.yield_yesterday),
    ("H19",        "Production totale (kWh)", lambda f: f.yield_total),
    ("H21",        "Puissance max jour (W)",lambda f: f.max_power_today),
]

_CSV_HEADER = [col for _, col, _ in _CSV_FIELDS]


# ---------------------------------------------------------------------------
# Logger CSV
# ---------------------------------------------------------------------------

class SolarLogger:
    """
    Enregistre les données du MPPT dans un fichier CSV lisible par tableur.

    Chaque ligne = un relevé horodaté.
    Séparateur ';' (compatible Excel FR / LibreOffice).
    Fichier unique, pas de rotation.

    Types de lignes :
      data         — relevé périodique (1 trame sur N)
      state_change — changement d'état de charge (CS)
      error        — apparition d'une erreur
      alarm        — alarme active

    Exemple :
        logger = SolarLogger()             # log 1 trame sur 10
        logger.log(frame)
        logger.log(frame, force=True)      # force l'écriture
    """

    def __init__(self, path: str = LOG_PATH, every: int = 10):
        """
        Args:
            path:  Chemin du fichier CSV.
            every: Log une trame 'data' toutes les N trames reçues (défaut 10).
        """
        self._path = path
        self._every = every
        self._frame_count: int = 0
        self._last_cs: Optional[str] = None
        self._last_err: Optional[str] = None
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self):
        """Crée le répertoire et l'en-tête CSV si le fichier n'existe pas."""
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
        Enregistre une ligne si :
        - c'est la N-ième trame reçue (type 'data'), ou
        - l'état de charge a changé (type 'state_change'), ou
        - une erreur est apparue (type 'error'), ou
        - une alarme est active (type 'alarm'), ou
        - force=True.
        """
        self._frame_count += 1
        cs  = frame.charge_state
        err = frame.error

        # Changement d'état de charge
        if cs != self._last_cs and self._last_cs is not None:
            self._write_row(frame, "state_change")
            self._last_cs = cs
            return
        self._last_cs = cs

        # Nouvelle erreur (ignore "Aucune erreur")
        if err != self._last_err and err not in (None, "Aucune erreur"):
            self._write_row(frame, "error")
            self._last_err = err
            return
        self._last_err = err

        # Alarme active
        if frame.alarm:
            self._write_row(frame, "alarm")
            return

        # Relevé périodique : 1 trame sur N
        if force or self._frame_count % self._every == 0:
            self._write_row(frame, "data")


# ---------------------------------------------------------------------------
# Couche série — stdlib uniquement (remplace pyserial)
# ---------------------------------------------------------------------------

class _SerialPort:
    """
    Port série minimal via termios/os — 8N1, baud configurable, lecture ligne.
    Fonctionne uniquement sur Linux/Raspberry Pi.
    """

    # Correspondance baudrate → constante termios
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
        # iflag : désactiver tout traitement d'entrée
        attrs[0] = 0
        # oflag : désactiver tout traitement de sortie
        attrs[1] = 0
        # cflag : 8N1, receiver enabled, local mode
        baud = self._BAUD_MAP.get(self._baudrate, termios.B19200)
        attrs[2] = baud | termios.CS8 | termios.CREAD | termios.CLOCAL
        # lflag : mode raw (pas d'écho, pas de signaux, pas de canonique)
        attrs[3] = 0
        # ispeed / ospeed
        attrs[4] = baud
        attrs[5] = baud
        # cc : VMIN=0 (non-bloquant), VTIME en dixièmes de secondes
        cc = list(attrs[6])
        cc[termios.VMIN]  = 0
        cc[termios.VTIME] = max(1, int(self._timeout * 10))  # dixièmes de s
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
    Cherche le port USB-série du câble VE.Direct Victron (chip FTDI, VID=0403).
    Lit les infos depuis /sys/class/tty/.
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
                    if vid == "0403":   # FTDI — câble VE.Direct Victron
                        return port
                except OSError:
                    pass
            path = os.path.join(path, "..")

    # Fallback : premier ttyUSB disponible
    return candidates[0] if candidates else None


def _list_ports_linux() -> list[dict]:
    """Liste les ports série USB disponibles en lisant /sys/class/tty/."""
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
    "V":    ("Tension batterie",         "V",    lambda x: int(x) / 1000),
    "VPV":  ("Tension panneau solaire",  "V",    lambda x: int(x) / 1000),
    "PPV":  ("Puissance panneau",        "W",    lambda x: int(x)),
    "I":    ("Courant batterie",         "A",    lambda x: int(x) / 1000),
    "IL":   ("Courant charge",           "A",    lambda x: int(x) / 1000),
    "LOAD": ("État sortie charge",       "",     lambda x: x),
    "Alarm":("Alarme",                   "",     lambda x: x),
    "Relay":("État relais",              "",     lambda x: x),
    "AR":   ("Raison alarme",            "bit",  lambda x: int(x)),
    "OR":   ("Raison hors-tension",      "hex",  lambda x: x),
    "H19":  ("Production totale",        "kWh",  lambda x: int(x) * 0.01),
    "H20":  ("Production aujourd'hui",   "kWh",  lambda x: int(x) * 0.01),
    "H21":  ("Puissance max aujourd'hui","W",    lambda x: int(x)),
    "H22":  ("Production hier",          "kWh",  lambda x: int(x) * 0.01),
    "H23":  ("Puissance max hier",       "W",    lambda x: int(x)),
    "HSDS": ("Numéro jour historique",   "",     lambda x: int(x)),
    "CS":   ("État charge",              "",     lambda x: CHARGE_STATES.get(int(x), f"Inconnu ({x})")),
    "ERR":  ("Code erreur",              "",     lambda x: ERROR_CODES.get(int(x), f"Erreur {x}")),
    "MPPT": ("Mode MPPT",                "",     lambda x: MPPT_MODES.get(int(x), f"Mode {x}")),
    "FW":   ("Version firmware",         "",     lambda x: x),
    "PID":  ("Identifiant produit",      "",     lambda x: x),
    "SER#": ("Numéro de série",          "",     lambda x: x),
}

CHARGE_STATES = {
    0:   "Hors tension",
    2:   "Défaut",
    3:   "Bulk (charge rapide)",
    4:   "Absorption",
    5:   "Float (maintien)",
    7:   "Égalisation manuelle",
    245: "Démarrage",
    247: "Égalisation automatique",
    252: "Circuit externe",
}

ERROR_CODES = {
    0:   "Aucune erreur",
    2:   "Surtension batterie",
    17:  "Surchauffe chargeur",
    18:  "Surtension panneau",
    20:  "Courant de charge max dépassé",
    26:  "Surintensité borne",
    33:  "Surtension entrée",
    34:  "Entrée trop basse (< Vbatt)",
    38:  "Arrêt entrée excessive",
    39:  "Arrêt entrée excessive",
    65:  "Perte de communication",
    66:  "Périphérique incompatible",
    67:  "BMS impossible à atteindre",
    68:  "Réseau mal configuré",
    116: "Calibration perdue",
    117: "Firmware invalide",
    119: "Paramètres stockage invalides",
}

MPPT_MODES = {
    0: "Inactif",
    1: "Puissance max (voltage sweep)",
    2: "Puissance max (ombrage)",
}


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
    # Propriétés nommées — mesures électriques
    # ------------------------------------------------------------------

    @property
    def battery_voltage(self) -> Optional[float]:
        """Tension batterie en Volts."""
        return self.parsed.get("V")

    @property
    def panel_voltage(self) -> Optional[float]:
        """Tension panneau solaire en Volts."""
        return self.parsed.get("VPV")

    @property
    def panel_power(self) -> Optional[int]:
        """Puissance panneau solaire en Watts."""
        return self.parsed.get("PPV")

    @property
    def battery_current(self) -> Optional[float]:
        """Courant batterie en Ampères, positif = charge."""
        return self.parsed.get("I")

    @property
    def load_current(self) -> Optional[float]:
        """Courant de la sortie charge en Ampères."""
        return self.parsed.get("IL")

    @property
    def load_output_on(self) -> Optional[bool]:
        """True si la sortie charge est activée."""
        v = self.parsed.get("LOAD")
        if v is None:
            return None
        return str(v).upper() == "ON"

    # ------------------------------------------------------------------
    # Propriétés nommées — état et mode
    # ------------------------------------------------------------------

    @property
    def charge_state(self) -> Optional[str]:
        """État du chargeur (ex: 'Bulk (charge rapide)', 'Float (maintien)')."""
        return self.parsed.get("CS")

    @property
    def error(self) -> Optional[str]:
        """Description de l'erreur active (ex: 'Aucune erreur')."""
        return self.parsed.get("ERR")

    @property
    def mppt_mode(self) -> Optional[str]:
        """Mode de l'algorithme MPPT."""
        return self.parsed.get("MPPT")

    @property
    def alarm(self) -> Optional[bool]:
        """True si une alarme est active."""
        v = self.parsed.get("Alarm")
        if v is None:
            return None
        return str(v).upper() == "ALARM"

    @property
    def relay(self) -> Optional[bool]:
        """True si le relais est fermé."""
        v = self.parsed.get("Relay")
        if v is None:
            return None
        return str(v).upper() == "ON"

    # ------------------------------------------------------------------
    # Propriétés nommées — historique / énergie
    # ------------------------------------------------------------------

    @property
    def yield_today(self) -> Optional[float]:
        """Production solaire du jour en kWh."""
        return self.parsed.get("H20")

    @property
    def yield_yesterday(self) -> Optional[float]:
        """Production solaire d'hier en kWh."""
        return self.parsed.get("H22")

    @property
    def yield_total(self) -> Optional[float]:
        """Production totale depuis la mise en service en kWh."""
        return self.parsed.get("H19")

    @property
    def max_power_today(self) -> Optional[int]:
        """Puissance maximale atteinte aujourd'hui en Watts."""
        return self.parsed.get("H21")

    @property
    def max_power_yesterday(self) -> Optional[int]:
        """Puissance maximale atteinte hier en Watts."""
        return self.parsed.get("H23")

    @property
    def day_number(self) -> Optional[int]:
        """Numéro du jour dans l'historique interne."""
        return self.parsed.get("HSDS")

    # ------------------------------------------------------------------
    # Propriétés nommées — identification
    # ------------------------------------------------------------------

    @property
    def firmware_version(self) -> Optional[str]:
        """Version du firmware."""
        return self.parsed.get("FW")

    @property
    def product_id(self) -> Optional[str]:
        """Identifiant produit Victron (ex: '0xA042' pour MPPT 75/10)."""
        return self.parsed.get("PID")

    @property
    def serial_number(self) -> Optional[str]:
        """Numéro de série de l'appareil."""
        return self.parsed.get("SER#")

    def summary(self) -> str:
        """Résumé lisible de la frame."""
        lines = [f"=== Relevé MPPT — {time.strftime('%H:%M:%S', time.localtime(self.timestamp))} ==="]
        for label, info in VEDIRECT_LABELS.items():
            if label in self.parsed:
                desc, unit, _ = info
                val = self.parsed[label]
                unit_str = f" {unit}" if unit else ""
                lines.append(f"  {desc:<35} {val}{unit_str}")
        if not self.checksum_ok:
            lines.append("  [ATTENTION] Checksum invalide")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parser VE.Direct TEXT
# ---------------------------------------------------------------------------
class VEDirectParser:
    """Parse le flux série VE.Direct et reconstruit les frames complètes."""

    def __init__(self):
        self._buffer: dict[str, str] = {}

    def feed(self, line: str) -> Optional[MPPTFrame]:
        """
        Fournit une ligne du port série.
        Retourne une MPPTFrame complète à la réception du checksum, sinon None.
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
    # Détection et liste des ports
    # ------------------------------------------------------------------
    @staticmethod
    def find_vedirect_port() -> Optional[str]:
        """Retourne le port USB-série du câble VE.Direct (FTDI), ou None."""
        return _find_vedirect_port_linux()

    @staticmethod
    def list_ports() -> list[dict]:
        """Liste tous les ports USB-série disponibles avec leurs infos."""
        return _list_ports_linux()

    # ------------------------------------------------------------------
    # Ouverture / fermeture
    # ------------------------------------------------------------------
    def open(self) -> str:
        """Ouvre la connexion série. Retourne le nom du port utilisé."""
        if self._port_name is None and self._auto_detect:
            self._port_name = _find_vedirect_port_linux()
        if self._port_name is None:
            raise RuntimeError(
                "Aucun port VE.Direct trouvé. "
                "Passez le port explicitement : MPPTReader(port='/dev/ttyUSB0')"
            )
        self._serial = _SerialPort(self._port_name, baudrate=self.BAUD_RATE, timeout=2.0)
        self._serial.open()
        return self._port_name

    def close(self):
        """Ferme la connexion série."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    # ------------------------------------------------------------------
    # Lecture bloquante (one-shot)
    # ------------------------------------------------------------------
    def read_one(self, timeout: float = 10.0) -> MPPTFrame:
        """
        Attend une frame complète et la retourne.

        Raises:
            TimeoutError: si aucune frame dans le délai imparti.
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

        raise TimeoutError(f"Aucune frame VE.Direct reçue en {timeout}s sur {self._port_name}")

    # ------------------------------------------------------------------
    # Lecture continue (thread d'arrière-plan)
    # ------------------------------------------------------------------
    def start(self):
        """Démarre la lecture continue en arrière-plan."""
        if self._running:
            return
        self.open()
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True, name="mppt-reader")
        self._thread.start()

    def stop(self):
        """Arrête la lecture continue."""
        self.close()

    def latest(self) -> Optional[MPPTFrame]:
        """Retourne la dernière frame reçue (None si aucune encore)."""
        with self._frame_lock:
            return self._latest_frame

    def wait_for_frame(self, timeout: float = 10.0) -> MPPTFrame:
        """Attend la prochaine frame complète (mode continu)."""
        deadline = time.time() + timeout
        prev = self._latest_frame
        while time.time() < deadline:
            with self._frame_lock:
                if self._latest_frame is not None and self._latest_frame is not prev:
                    return self._latest_frame
            time.sleep(0.05)
        raise TimeoutError("Aucune nouvelle frame reçue dans le délai imparti.")

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
                print(f"[MPPTReader] Erreur série : {e}")
                break
            except Exception as e:
                print(f"[MPPTReader] Erreur inattendue : {e}")

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()


# ---------------------------------------------------------------------------
# Fonctions standalone
# ---------------------------------------------------------------------------
def read_mppt(port: Optional[str] = None, timeout: float = 10.0) -> MPPTFrame:
    """
    Retourne une frame complète du MPPT (connexion one-shot).

    Exemple:
        frame = read_mppt()
        print(frame.battery_voltage, 'V')
        print(frame.charge_state)
    """
    return MPPTReader(port=port).read_one(timeout=timeout)


def monitor_mppt(
    port: Optional[str] = None,
    interval: float = 5.0,
    count: int = 0,
    log_path: Optional[str] = LOG_PATH,
    log_every: int = 10,
):
    """
    Affiche les relevés du MPPT en continu et les enregistre dans Solar.log.

    Args:
        port:      Port série (None = détection auto).
        interval:  Secondes entre chaque affichage terminal.
        count:     Nombre de relevés affichés (0 = infini).
        log_path:  Chemin du fichier CSV (None = pas de log).
        log_every: Log une trame 'data' toutes les N trames (défaut 10).
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
        print("\nArrêt.")
    finally:
        reader.stop()


# ---------------------------------------------------------------------------
# Test rapide si exécuté directement
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    print("Ports USB-série disponibles :")
    ports = MPPTReader.list_ports()
    if ports:
        for p in ports:
            print(f"  {p['device']:15} — {p['description']}  (VID:{p['vid']} PID:{p['pid']})")
    else:
        print("  (aucun)")

    detected = MPPTReader.find_vedirect_port()
    if detected:
        print(f"\nPort VE.Direct détecté : {detected}")
    else:
        print("\nAucun port VE.Direct détecté automatiquement.")
        sys.exit(1)

    print(f"\nLecture d'une frame sur {detected}...\n")
    try:
        frame = read_mppt(port=detected)
        print(frame.summary())

        logger = SolarLogger()
        logger.log(frame, force=True)
        print(f"\nDonnées enregistrées dans {LOG_PATH}")

        print("\n--- Propriétés nommées ---")
        print(f"  Tension batterie : {frame.battery_voltage} V")
        print(f"  Tension panneau  : {frame.panel_voltage} V")
        print(f"  Puissance        : {frame.panel_power} W")
        print(f"  Courant          : {frame.battery_current} A")
        print(f"  Sortie charge    : {'ON' if frame.load_output_on else 'OFF'}")
        print(f"  État de charge   : {frame.charge_state}")
        print(f"  Mode MPPT        : {frame.mppt_mode}")
        print(f"  Erreur           : {frame.error}")
        print(f"  Production/jour  : {frame.yield_today} kWh")
        print(f"  Production totale: {frame.yield_total} kWh")
        print(f"  Puissance max/j  : {frame.max_power_today} W")
        print(f"  Firmware         : {frame.firmware_version}")
        print(f"  N° de série      : {frame.serial_number}")
    except TimeoutError as e:
        print(f"Erreur : {e}")
    except RuntimeError as e:
        print(f"Erreur : {e}")
