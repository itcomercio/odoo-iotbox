/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { logPosMessage } from "@point_of_sale/app/utils/pretty_console_log";
import { PrinterService } from "@point_of_sale/app/services/printer_service";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { buildReceiptData, buildReceiptXml } from "./receipt_serializer";

function canUseStructuredReceipt(component, props, device) {
    return (
        component === OrderReceipt &&
        Boolean(props?.order) &&
        Boolean(device?.sendAction)
    );
}

async function sendStructuredReceipt(device, order) {
    const receiptData = buildReceiptData(order);
    const receiptXml = buildReceiptXml(receiptData);

    const payload = {
        action: "print_receipt_structured",
        receipt_data: receiptData,
        receipt_xml: receiptXml,
    };

    const response = await device.sendAction(payload);
    if (!response || response.result === false) {
        throw new Error("Structured IoT print rejected");
    }

    return {
        successful: true,
    };
}

patch(PrinterService.prototype, {
    async print(component, props, options = {}) {
        if (canUseStructuredReceipt(component, props, this.device)) {
            try {
                this.state.isPrinting = true;
                return await sendStructuredReceipt(this.device, props.order);
            } catch (error) {
                logPosMessage(
                    "PrinterService",
                    "print",
                    "Structured receipt print failed, fallback to default image flow",
                    false,
                    [error]
                );
            } finally {
                this.state.isPrinting = false;
            }
        }

        return super.print(component, props, options);
    },
});

