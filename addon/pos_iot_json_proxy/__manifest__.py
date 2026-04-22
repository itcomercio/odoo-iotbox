{
    "name": "POS IoT JSON Receipt Proxy",
    "version": "19.0.1.0.0",
    "summary": "Send structured POS receipt payloads to IoT proxy before image fallback",
    "depends": ["point_of_sale"],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_iot_json_proxy/static/src/js/receipt_serializer.js",
            "pos_iot_json_proxy/static/src/js/printer_service_patch.js"
        ]
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}

