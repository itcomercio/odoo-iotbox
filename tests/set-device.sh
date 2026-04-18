# usb-devices
# T:  Bus=03 Lev=01 Prnt=01 Port=01 Cnt=01 Dev#=  3 Spd=12   MxCh= 0
# D:  Ver= 1.10 Cls=00(>ifc ) Sub=00 Prot=00 MxPS=16 #Cfgs=  1
# P:  Vendor=0416 ProdID=5011 Rev=00.00
# S:  Manufacturer=Printer
# S:  Product=USB Thermal Printer
# C:  #Ifs= 1 Cfg#= 1 Atr=80 MxPwr=100mA
# I:  If#= 0 Alt= 1 #EPs= 2 Cls=07(print) Sub=01 Prot=02 Driver=usblp
# E:  Ad=01(O) Atr=02(Bulk) MxPS=  64 Ivl=0ms
# E:  Ad=82(I) Atr=02(Bulk) MxPS=  64 Ivl=0ms

# En el caso de Fedora usa el driver /dev/usb/lp0
# Veamos si trabaja la apertura:
# echo -e -n "\x1b\x70\x00\x19\xfa" > /dev/usb/lp0
# FUNCIONA!!



# Registra los IDs de tu impresora en el driver serial simple
# echo "0416 5011" > /sys/bus/usb-serial/drivers/generic/new_id
