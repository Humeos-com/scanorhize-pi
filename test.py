
import sys
import usb.core

# 2109:2817
# 2109:2817 VIA Labs, Inc. USB2.0 Hub, USB 2.10, 4 ports, ppps
dev = usb.core.find(idVendor=0x2109, idProduct=0x2817)
if dev is None:
    raise ValueError('Our device is not connected')
else:
    # set the active configuration. With no arguments, the first
    # configuration will be the active one
    # dev.set_configuration()
    print(dev)

    for cfg in dev:
        sys.stdout.write(str(cfg.bConfigurationValue) + '\n')
        for intf in cfg:
            sys.stdout.write('\t' + \
                         str(intf.bInterfaceNumber) + \
                         ',' + \
                         str(intf.bAlternateSetting) + \
                         '\n')
            for ep in intf:
                sys.stdout.write('\t\t' + \
                             str(ep.bEndpointAddress) + \
                             '\n')
    # get an endpoint instance
    # cfg = dev.get_active_configuration()
    # intf = cfg[(0,0)]
