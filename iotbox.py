from flask import Flask, request, jsonify, make_response
import serial
import os
import time
import json
import base64
import binascii
import datetime
import xml.etree.ElementTree as ET

app = Flask(__name__)

BAUD_RATE = 9600
CANDIDATE_PORTS = ['/dev/usb/lp0', '/dev/ttyUSB0']
CASHBOX_PULSE = b'\x1bp\x00\x19\xfa'

TEST_MODE = os.getenv('IOTBOX_TEST_MODE', '0').lower() in ('1', 'true', 'yes', 'on')
TEST_TEXT = os.getenv('IOTBOX_TEST_TEXT', 'Hello')
TEST_COOLDOWN_SECONDS = float(os.getenv('IOTBOX_TEST_COOLDOWN_SECONDS', '10'))
FORCE_TEXT_ON_IMAGE_RECEIPT = os.getenv('IOTBOX_FORCE_TEXT_ON_IMAGE_RECEIPT', '1').lower() in ('1', 'true', 'yes', 'on')
DEBUG_MODE = os.getenv('IOTBOX_DEBUG_MODE', '1').lower() in ('1', 'true', 'yes', 'on')
LAST_TEST_PRINT_TS = 0.0


def _debug(message):
    if DEBUG_MODE:
        print(message)


def _cors_response(response):
    # Keep CORS permissive for local LAN POS clients.
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
    return response


@app.after_request
def add_cors_headers(response):
    return _cors_response(response)


@app.route('/hw_proxy/<path:_subpath>', methods=['OPTIONS'])
def hw_proxy_options(_subpath):
    return _cors_response(make_response('', 200))


def detect_serial_port():
    for port in CANDIDATE_PORTS:
        if os.path.exists(port):
            print(f"Puerto serie detectado: {port}")
            return port
    print('ADVERTENCIA: No se encontro ningun puerto serie conocido.')
    return None


SERIAL_PORT = detect_serial_port()


def _refresh_serial_port(force=False):
    global SERIAL_PORT
    if force or not SERIAL_PORT or not os.path.exists(SERIAL_PORT):
        SERIAL_PORT = detect_serial_port()
    return SERIAL_PORT


def _serial_status_dict():
    port = _refresh_serial_port()
    return {
        'port': port or 'none',
        'exists': bool(port and os.path.exists(port)),
        'readable': bool(port and os.access(port, os.R_OK)),
        'writable': bool(port and os.access(port, os.W_OK)),
    }


def _write_to_serial(data):
    port = _refresh_serial_port()
    if not port:
        return False, 'No se encontro puerto serie disponible'

    try:
        if port.startswith('/dev/usb/lp'):
            with open(port, 'wb', buffering=0) as printer_dev:
                printer_dev.write(data)
            return True, None

        ser = serial.Serial(port, BAUD_RATE, timeout=1)
        ser.write(data)
        ser.close()
        return True, None
    except Exception as err:
        print(f'Error imprimiendo en {port}: {err}')
        return False, str(err)


def _send_short_test_ticket_and_open_cashbox():
    global LAST_TEST_PRINT_TS

    now = time.monotonic()
    if now - LAST_TEST_PRINT_TS < TEST_COOLDOWN_SECONDS:
        print('Modo test activo: se ignora impresion repetida por cooldown')
        return True, None

    short_ticket = b'\x1b@' + TEST_TEXT.encode('utf-8', errors='replace') + b'\n\n'
    ok, err = _write_to_serial(short_ticket)
    if not ok:
        return False, err

    ok, err = _write_to_serial(CASHBOX_PULSE)
    if ok:
        LAST_TEST_PRINT_TS = now
    return ok, err


def _jsonrpc_ok(result=True):
    return jsonify({'jsonrpc': '2.0', 'result': result})


def _jsonrpc_error(message, status_code=500):
    return jsonify({'jsonrpc': '2.0', 'error': message}), status_code


def _status_code_from_error(err):
    if not err:
        return 500
    return 503 if 'puerto serie' in err.lower() else 500


def _extract_odoo_print_job(raw_body):
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(payload, dict):
        return None

    params = payload.get('params', {})
    data = params.get('data') if isinstance(params, dict) else None
    source = data if isinstance(data, dict) else params if isinstance(params, dict) else payload
    if not isinstance(source, dict):
        source = {}

    return {
        'payload': payload,
        'params': params if isinstance(params, dict) else {},
        'data': data if isinstance(data, dict) else {},
        'source': source,
        'action': source.get('action') or (params.get('action') if isinstance(params, dict) else ''),
        'receipt': source.get('receipt') or source.get('xml_receipt') or source.get('ticket') or source.get('content'),
        'receipt_data': source.get('receipt_data'),
        'receipt_xml': source.get('receipt_xml'),
    }


def _decode_receipt_base64(receipt_value):
    if not isinstance(receipt_value, str) or not receipt_value:
        return None, None
    try:
        decoded = base64.b64decode(receipt_value, validate=True)
    except (binascii.Error, ValueError):
        return None, None

    if decoded.startswith(b'\xff\xd8\xff'):
        return decoded, 'jpg'
    if decoded.startswith(b'\x89PNG\r\n\x1a\n'):
        return decoded, 'png'
    if decoded.startswith(b'GIF87a') or decoded.startswith(b'GIF89a'):
        return decoded, 'gif'
    return decoded, 'bin'


def _first_not_empty(*values):
    for value in values:
        if value not in (None, ''):
            return value
    return ''


def _render_structured_receipt_ticket(receipt_data):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    company = receipt_data.get('company') if isinstance(receipt_data, dict) else {}
    totals = receipt_data.get('totals') if isinstance(receipt_data, dict) else {}
    lines_data = receipt_data.get('lines') if isinstance(receipt_data, dict) else []
    payment_lines = receipt_data.get('payment_lines') if isinstance(receipt_data, dict) else []

    lines = [
        _first_not_empty(company.get('name'), 'POS Ticket'),
        _first_not_empty(receipt_data.get('order_name'), ''),
        _first_not_empty(receipt_data.get('date'), now),
        '-' * 32,
    ]

    for line in lines_data:
        qty = _first_not_empty(line.get('qty'), 0)
        name = _first_not_empty(line.get('product_name'), 'Producto')
        total = _first_not_empty(line.get('total_with_tax'), line.get('total_without_tax'), 0)
        lines.append(f'{qty}x {name}  {total}')

    lines.extend([
        '-' * 32,
        f"TOTAL: {_first_not_empty(totals.get('total_with_tax'), receipt_data.get('total'), '')}",
    ])

    for payment_line in payment_lines:
        method = _first_not_empty(payment_line.get('method'), 'Pago')
        amount = _first_not_empty(payment_line.get('amount'), 0)
        lines.append(f'{method}: {amount}')

    change = _first_not_empty(totals.get('change'), receipt_data.get('change'), '')
    if change not in ('', None):
        lines.append(f'Cambio: {change}')

    lines.extend(['', ''])
    return b'\x1b@' + '\n'.join(str(line) for line in lines).encode('utf-8', errors='replace') + b'\n\n'


def _parse_receipt_xml(xml_text):
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    def text(path, default=''):
        node = root.find(path)
        return node.text if node is not None and node.text is not None else default

    lines = []
    for line_node in root.findall('./lines/line'):
        lines.append({
            'product_name': _first_not_empty(
                line_node.findtext('product_name', ''),
                line_node.findtext('name', ''),
            ),
            'qty': line_node.findtext('qty', '0'),
            'total_with_tax': _first_not_empty(
                line_node.findtext('total_with_tax', ''),
                line_node.findtext('price_with_tax', ''),
                line_node.findtext('price', ''),
            ),
        })

    payment_lines = []
    for pay_node in root.findall('./payment_lines/payment_line'):
        payment_lines.append({
            'method': pay_node.findtext('method', ''),
            'amount': pay_node.findtext('amount', '0'),
        })

    return {
        'order_name': _first_not_empty(text('order_name'), text('name')),
        'date': text('date'),
        'company': {
            'name': text('./company/name'),
            'vat': text('./company/vat'),
            'phone': text('./company/phone'),
        },
        'totals': {
            'total_with_tax': _first_not_empty(text('./totals/total_with_tax'), text('total')),
            'total_without_tax': text('./totals/total_without_tax'),
            'change': _first_not_empty(text('./totals/change'), text('change')),
        },
        'lines': lines,
        'payment_lines': payment_lines,
    }


def _render_simple_fallback_ticket(reason):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = [
        '*** TICKET MODO TEXTO ***',
        now,
        '-',
        str(reason),
        '',
    ]
    return b'\x1b@' + '\n'.join(lines).encode('utf-8', errors='replace') + b'\n\n'


def _handle_print(raw_body, forced_action=''):
    if TEST_MODE:
        print('Modo test activo: se imprime ticket corto y se abre cajon')
        return _send_short_test_ticket_and_open_cashbox()

    job = _extract_odoo_print_job(raw_body)
    action = forced_action
    if job and not action:
        action = job.get('action') or ''

    if job:
        _debug(f"[PRINT] action={action!r} params.keys={list(job.get('params', {}).keys())}")

        receipt_data = job.get('receipt_data')
        if isinstance(receipt_data, dict):
            _debug('[PRINT] Recibo estructurado JSON detectado')
            return _write_to_serial(_render_structured_receipt_ticket(receipt_data))

        receipt_xml = job.get('receipt_xml')
        if isinstance(receipt_xml, str) and receipt_xml.strip().startswith('<'):
            _debug('[PRINT] Recibo XML estructurado detectado')
            parsed = _parse_receipt_xml(receipt_xml)
            if parsed:
                return _write_to_serial(_render_structured_receipt_ticket(parsed))

        receipt = job.get('receipt')
        if isinstance(receipt, str) and receipt:
            if receipt.lstrip().startswith('<'):
                parsed = _parse_receipt_xml(receipt)
                if parsed:
                    return _write_to_serial(_render_structured_receipt_ticket(parsed))

            image_bytes, image_ext = _decode_receipt_base64(receipt)
            if image_bytes is not None:
                if FORCE_TEXT_ON_IMAGE_RECEIPT:
                    _debug('[PRINT] Imagen base64 ignorada; imprimiendo fallback de texto')
                    fallback = _render_simple_fallback_ticket(
                        f'Recibo imagen ignorado ({image_ext}, {len(image_bytes)} bytes)'
                    )
                    return _write_to_serial(fallback)
                return False, f'Recibo en imagen base64 ({image_ext}) no soportado en modo actual'

    if raw_body.lstrip()[:1] == b'<':
        parsed = _parse_receipt_xml(raw_body.decode('utf-8', errors='replace'))
        if parsed:
            return _write_to_serial(_render_structured_receipt_ticket(parsed))

    return _write_to_serial(raw_body)


@app.route('/hw_proxy/hello', methods=['GET'])
def hello():
    return make_response('ping', 200)


@app.route('/hw_proxy/handshake', methods=['POST'])
def handshake():
    return jsonify({'jsonrpc': '2.0', 'result': True})


@app.route('/hw_proxy/status_json', methods=['GET', 'POST'])
def status_json():
    serial_status = _serial_status_dict()
    return jsonify({
        'jsonrpc': '2.0',
        'result': {
            'status': 'connected' if serial_status['port'] != 'none' else 'disconnected',
            'drivers': {
                'printer': {
                    'status': 'connected' if serial_status['port'] != 'none' else 'disconnected',
                    'device': serial_status['port'],
                }
            },
        },
    })


@app.route('/hw_proxy/print_xml_receipt', methods=['POST'])
@app.route('/hw_proxy/print_receipt', methods=['POST'])
def print_receipt():
    print(f'Recibido ticket ({len(request.data)} bytes) desde {request.remote_addr}')
    ok, err = _handle_print(request.data)
    if ok:
        return _jsonrpc_ok(True)
    return _jsonrpc_error(err, _status_code_from_error(err))


@app.route('/hw_proxy/default_printer_action', methods=['POST'])
def default_printer_action():
    raw_body = request.get_data(cache=True)
    job = _extract_odoo_print_job(raw_body)
    action = ''
    if job:
        action = job.get('action') or ''
        _debug(f"[PRINTER_ACTION] action={action!r} keys={list(job['payload'].keys())}")

    if action in ('cashbox', 'open_cashbox'):
        ok, err = _write_to_serial(CASHBOX_PULSE)
    elif TEST_MODE and action in ('', 'print_receipt', 'print_xml_receipt', 'print', 'print_receipt_structured'):
        ok, err = _send_short_test_ticket_and_open_cashbox()
    else:
        ok, err = _handle_print(raw_body, action)

    if ok:
        return _jsonrpc_ok(True)
    return _jsonrpc_error(err or 'Error de impresion', _status_code_from_error(err))


@app.route('/hw_proxy/open_cashbox', methods=['POST'])
def open_cashbox():
    ok, err = _write_to_serial(CASHBOX_PULSE)
    if ok:
        return _jsonrpc_ok(True)
    return _jsonrpc_error(err, 500)


@app.route('/hw_proxy/log', methods=['POST'])
def hw_proxy_log():
    payload = request.get_json(silent=True) or {}
    print(f'POS log: {payload}')
    return _jsonrpc_ok(True)


if __name__ == '__main__':
    if DEBUG_MODE:
        print('[DEBUG] Modo debug activo')
    if FORCE_TEXT_ON_IMAGE_RECEIPT:
        print('[DEBUG] Receipts en imagen se sustituyen por ticket de texto simple')
    if TEST_MODE:
        print(f'[TEST] Modo test activo. Texto: "{TEST_TEXT}" Cooldown: {TEST_COOLDOWN_SECONDS}s')
    app.run(host='0.0.0.0', port=8072)
