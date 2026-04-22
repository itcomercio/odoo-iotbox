# POS IoT JSON Proxy (Odoo 19)

Addon para POS que intenta imprimir con payload estructurado (JSON/XML) antes del flujo estandar por imagen.

## Como funciona

1. Parchea `PrinterService.print`.
2. Si el componente es `OrderReceipt` y hay `HWPrinter`, envia:
   - `action: print_receipt_structured`
   - `receipt_data` (JSON)
   - `receipt_xml` (XML)
3. Si falla la llamada, hace fallback al flujo original de Odoo (JPG base64).

## Archivos

- `static/src/js/receipt_serializer.js`: crea `receipt_data` y `receipt_xml`.
- `static/src/js/printer_service_patch.js`: hook de impresion + fallback.

## Instalacion

```bash
cd /home/javiroman/HACK/dev/odoo
./odoo-bin -d TU_BD -u pos_iot_json_proxy --dev=assets
```

Luego recarga el POS con cache limpia.

