
import smbus
from Miscellious import *
bus = smbus.SMBus(1)    # 0 = /dev/i2c-0 (port I2C0), 1 = /dev/i2c-1 (port I2C1)

DEVICE_ADDRESS = 0x55      #7 bit address (will be left shifted to add the read write bit)


def ReadBatVoltCap():
    try:
        res=bus.read_i2c_block_data(DEVICE_ADDRESS,0x04,2)
        Volt=(res[1]*256+res[0])/1000
        Cap=round((Volt-2.7)/1.49*100,2)    
        
    except :
        Volt=0
        Cap=0
    WriteBatterieFile(Volt,Cap)
    return(Volt,Cap)

def ReadBatSOC():
    try:
        res=bus.read_i2c_block_data(DEVICE_ADDRESS,0x1C,2)
        SOC=(res[1]*256+res[0])
        print(SOC)
    except :
        SOC=0
    return(SOC)


def ReadBatCAP():
    try:
        res=bus.read_i2c_block_data(DEVICE_ADDRESS,0x0A,2)
        CAP=(res[1]*256+res[0])
        print(CAP)
    except :
        CAP=0  
    return(CAP)
