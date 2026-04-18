from flask import Flask, request, jsonify, make_response
import serial
import os
import time

app = Flask(__name__)

BAUD_RATE = 9600
CANDIDATE_PORTS = ['/dev/usb/lp0', '/dev/ttyUSB0']
CASHBOX_PULSE = b'\x1bp\x00\x19\xfa'
TEST_MODE = os.getenv('IOTBOX_TEST_MODE', '0').lower() in ('1', 'true', 'yes', 'on')
TEST_TEXT = os.getenv('IOTBOX_TEST_TEXT', 'Hello')
TEST_COOLDOWN_SECONDS = float(os.getenv('IOTBOX_TEST_COOLDOWN_SECONDS', '10'))
LAST_TEST_PRINT_TS = 0.0


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
    print("ADVERTENCIA: No se encontró ningún puerto serie conocido.")
    return None

SERIAL_PORT = detect_serial_port()

@app.route('/hw_proxy/hello', methods=['GET'])
def hello():
    # Odoo uses this endpoint as connectivity ping.
    return make_response('ping', 200)

@app.route('/hw_proxy/handshake', methods=['POST'])
def handshake():
    return jsonify({"jsonrpc": "2.0", "result": True})


@app.route('/hw_proxy/status_json', methods=['GET', 'POST'])
def status_json():
    device = SERIAL_PORT if SERIAL_PORT else 'none'
    # Minimal status payload so POS can decide hardware is available.
    return jsonify({
        'jsonrpc': '2.0',
        'result': {
            'status': 'connected' if SERIAL_PORT else 'disconnected',
            'drivers': {
                'printer': {
                    'status': 'connected' if SERIAL_PORT else 'disconnected',
                    'device': device,
                }
            },
        },
    })


def _write_to_serial(data):
    if not SERIAL_PORT:
        return False, 'No se encontro puerto serie disponible'

    try:
        # usblp devices behave like plain character devices, not UART serial ports.
        if SERIAL_PORT.startswith('/dev/usb/lp'):
            with open(SERIAL_PORT, 'wb', buffering=0) as printer_dev:
                printer_dev.write(data)
            return True, None

        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        ser.write(data)
        ser.close()
        return True, None
    except Exception as err:
        print(f'Error imprimiendo en {SERIAL_PORT}: {err}')
        return False, str(err)


def _send_short_test_ticket_and_open_cashbox():
    global LAST_TEST_PRINT_TS

    now = time.monotonic()
    if now - LAST_TEST_PRINT_TS < TEST_COOLDOWN_SECONDS:
        print('Modo test activo: se ignora impresion repetida por cooldown')
        return True, None

    # Simple ESC/POS payload for a short test line.
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

@app.route('/hw_proxy/print_xml_receipt', methods=['POST'])
@app.route('/hw_proxy/print_receipt', methods=['POST'])
def print_receipt():
    # Odoo envía el ticket en formato XML o binario ESC/POS
    # Para simplificar, tomamos los datos crudos
    data = request.data

    print(f'Recibido ticket ({len(data)} bytes) desde {request.remote_addr}')

    if TEST_MODE:
        print('Modo test activo: se imprime ticket corto y se abre cajon')
        ok, err = _send_short_test_ticket_and_open_cashbox()
    else:
        ok, err = _write_to_serial(data)

    if ok:
        return _jsonrpc_ok(True)

    status_code = 503 if 'puerto serie' in err.lower() else 500
    return _jsonrpc_error(err, status_code)


@app.route('/hw_proxy/default_printer_action', methods=['POST'])
def default_printer_action():
    payload = request.get_json(silent=True) or {}
    params = payload.get('params', payload)
    action = params.get('action', '')

    # Odoo may send content in `params.data` or as raw request body.
    raw_data = params.get('data')
    if isinstance(raw_data, str):
        data = raw_data.encode('utf-8')
    elif isinstance(raw_data, bytes):
        data = raw_data
    else:
        data = request.data

    print(f"default_printer_action action='{action}' bytes={len(data)}")

    if TEST_MODE and action in ('', 'print_receipt', 'print_xml_receipt', 'print'):
        print('Modo test activo desde default_printer_action')
        ok, err = _send_short_test_ticket_and_open_cashbox()
    elif action in ('cashbox', 'open_cashbox'):
        ok, err = _write_to_serial(CASHBOX_PULSE)
    else:
        ok, err = _write_to_serial(data)

    if ok:
        return _jsonrpc_ok(True)

    status_code = 503 if 'puerto serie' in (err or '').lower() else 500
    return _jsonrpc_error(err or 'Error de impresion', status_code)


@app.route('/hw_proxy/open_cashbox', methods=['POST'])
def open_cashbox():
    # ESC/POS pulse command; may be ignored by printers without drawer port.
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
    # Odoo busca la IoT Box usualmente en el puerto 8069 o 8072
    app.run(host='0.0.0.0', port=8072)
