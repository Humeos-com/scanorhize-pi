"""
Permet de gérer l'authentification des boitiers
Utilise le pattern Singleton pour stocker le token JWT et les infos du boitier
"""

from fcntl import ioctl
from socket import socket, inet_ntoa, AF_INET, SOCK_DGRAM
from struct import pack
from os import walk
from OSUtils import is_raspberry_pi
# from Scanner import ScannerData, listConfigScanner, extract_serial

if is_raspberry_pi():
    IFACE="eth0"
else:
    IFACE="en0"

class AuthenticationData:
    """Singleton class to store authentication data"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AuthenticationData, cls).__new__(cls)
            # Initialize default values
            cls._instance._address = ""
            cls._instance._token = ""
            cls._instance._AuthenticationData__initialized = False  # Private attribute
        return cls._instance

    def __init__(self):
        # Only initialize once
        if not self.__initialized:
            self._address = ""
            self._token = ""
            self.__initialized = True

    @property
    def address(self):
        """Get the address"""
        return self._address

    @address.setter
    def address(self, value):
        """Set the address"""
        self._address = value

    @property
    def token(self):
        """Get the authentication token"""
        return self._token

    @token.setter
    def token(self, value):
        """Set the authentication token"""
        self._token = value

    @property
    def __initialized(self):
        """Get initialization status"""
        return self.__initialized

    @__initialized.setter
    def __initialized(self, value):
        """Set initialization status"""
        self.__initialized = value


def getHwAddr():
    """Renvoie l'adresse MAC de l'interface réseau eth0 pour les Raspberry Pi
    quelque soit l'interface réseau utilisée
    Cette fonction ne sert que pour authentifier le boitier

    Returns:
        str: la Mac Address du boitier
    """
    if not is_raspberry_pi():
        return "0A:0B:00C:0D:0E:0F"

    s = socket(AF_INET, SOCK_DGRAM)
    info = ioctl(s.fileno(), 0x8927, pack("256s", IFACE[:15]))
    return ":".join(f"{ord(char):02x}" for char in info[18:24])
    # return ''.join(['%02x:' % ord(char) for char in info[18:24]])[:-1]


def getIPAddr(ifname):
    if ifname == "lo":
        return "127.0.0.1"
    if not is_raspberry_pi():
        return "01.02.03.04"

    s = socket(AF_INET, SOCK_DGRAM)
    try:
        info = ioctl(s.fileno(), 0x8915, pack("256s", ifname[:15]))
    except IOError as e:
        print(f"IOError: {e}")
        return "No address assigned"
    return inet_ntoa(info[20:24])



if __name__ == "__main__":
    f = []
    path = "/sys/class/net"

    for dirpath, dirnames, filename in walk(path):
        f.extend(dirnames)
        break

    f = ["lo", IFACE]
    for iface in f:
        print("Interface:", iface)
        print("IPv4 Addr:", getIPAddr(iface))
        print("HW MAC Addr:", getHwAddr())
        print("-----------------------------")
