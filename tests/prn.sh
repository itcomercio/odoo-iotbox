#lpadmin -p POS -E -v "usb://Printer/USB%20Thermal%20Printer?serial=0.0" -m drv:///cupsfilters.drv/textonly.ppd
#lpadmin -p POS -E -v "usb://Printer/USB%20Thermal%20Printer?serial=0.0" -m drv:///sample.drv/epson9.ppd
lpadmin -p POS -E -v "usb://Printer/USB%20Thermal%20Printer?serial=0.0" -m drv:///sample.drv/generictxt.pp

# Definir tamaño de papel (58mm de ancho por longitud genérica/continua)
lpadmin -p POS -o PageSize=RP58x210 -o MediaSource=Continuous

# Eliminar márgenes físicos (vital para que el ticket no salga desplazado)
lpadmin -p POS -o margins-desktop=0 -o margins-top=0 -o margins-bottom=0 -o margins-left=0 -o margins-right=0

# Evitar que la impresora espere un "Fin de página" (Form Feed)
lpadmin -p POS -o Protocol=None
