# odoo-iotbox

Proxy IoT Box minimal para Odoo POS con impresion por puerto serie USB.

## Objetivo

Este proyecto permite que Odoo POS imprima contra un servicio Flask compatible con `/hw_proxy/*`.

Soporta dos flujos:

1. Flujo legacy de Odoo (`print_receipt` con imagen base64).
2. Flujo estructurado (`print_receipt_structured`) con `receipt_data` (JSON) y `receipt_xml`.

## Requisitos

```bash
pip install -r requirements.txt
```

## Ejecutar

```bash
python iotbox.py
```

## Variables de entorno

- `IOTBOX_TEST_MODE=1`: modo test, imprime texto corto y abre cajon.
- `IOTBOX_TEST_TEXT="Hello"`: texto de prueba.
- `IOTBOX_TEST_COOLDOWN_SECONDS=10`: evita bucles de impresion en test.
- `IOTBOX_FORCE_TEXT_ON_IMAGE_RECEIPT=1`: ignora imagen base64 y saca ticket texto fallback.
- `IOTBOX_DEBUG_MODE=1`: logs de depuracion.

## Hook Odoo 19 (JSON/XML)

Se ha creado un addon en tu repo local de Odoo:

- `/home/javiroman/HACK/dev/odoo/addons/pos_iot_json_proxy`

Ese addon parchea `PrinterService` para que intente primero enviar ticket estructurado a:

- `POST /hw_proxy/default_printer_action`
- `action = print_receipt_structured`
- `receipt_data` (JSON)
- `receipt_xml` (XML)

Si falla, hace fallback automatico al flujo original de Odoo (imagen JPG base64).

### Instalar addon en Odoo

```bash
cd /home/javiroman/HACK/dev/odoo
./odoo-bin -d TU_BD -u pos_iot_json_proxy --dev=assets
```

Recarga POS con assets limpios (Ctrl+F5).

## Payload esperado por `iotbox.py`

Ejemplo simplificado del JSON-RPC que envia el addon:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "data": {
      "action": "print_receipt_structured",
      "receipt_data": {
        "order_name": "POS/00123",
        "company": {"name": "Mi tienda"},
        "totals": {"total_with_tax": 12.5},
        "lines": [{"product_name": "Cafe", "qty": 1, "total_with_tax": 12.5}],
        "payment_lines": [{"method": "Efectivo", "amount": 12.5}]
      },
      "receipt_xml": "<receipt>...</receipt>"
    }
  }
}
```
