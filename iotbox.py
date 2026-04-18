from flask import Flask, request, jsonify
import serial

app = Flask(__name__)

# Configura aquí tu puerto detectado anteriormente
SERIAL_PORT = '/dev/ttyUSB0'
BAUD_RATE = 9600

@app.route('/hw_proxy/hello', methods=['GET'])
def hello():
    # Odoo usa esto para el "check" de conexión
    return "OK", 200

@app.route('/hw_proxy/handshake', methods=['POST'])
def handshake():
    return jsonify({"result": True})

@app.route('/hw_proxy/print_xml_receipt', methods=['POST'])
def print_receipt():
    # Odoo envía el ticket en formato XML o binario ESC/POS
    # Para simplificar, tomamos los datos crudos
    data = request.data

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        ser.write(data)
        ser.close()
        return jsonify({"jsonrpc": "2.0", "result": True})
    except Exception as e:
        print(f"Error imprimiendo: {e}")
        return jsonify({"jsonrpc": "2.0", "error": str(e)}), 500

if __name__ == '__main__':
    # Odoo busca la IoT Box usualmente en el puerto 8069 o 8072
    app.run(host='0.0.0.0', port=8072)
