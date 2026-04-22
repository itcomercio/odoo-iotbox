/** @odoo-module **/

function asNumber(value, fallback = 0) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
}

function firstAvailable(...values) {
    for (const value of values) {
        if (value !== undefined && value !== null && value !== "") {
            return value;
        }
    }
    return "";
}

function xmlEscape(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&apos;");
}

function getLineQty(line) {
    if (line?.getQuantity) {
        return asNumber(line.getQuantity(), 0);
    }
    return asNumber(firstAvailable(line?.qty), 0);
}

function getLineTotalWithTax(line) {
    return asNumber(
        firstAvailable(
            line?.priceIncl,
            line?.prices?.total_included,
            line?.prices?.total_included_currency,
            line?.price_subtotal_incl,
            line?.displayPrice,
            line?.displayPriceNoDiscount
        ),
        0
    );
}

function getLineTotalWithoutTax(line) {
    return asNumber(
        firstAvailable(
            line?.priceExcl,
            line?.prices?.total_excluded,
            line?.prices?.total_excluded_currency,
            line?.price_subtotal,
            line?.displayPriceUnit
        ),
        0
    );
}

function getOrderTotalWithTax(order) {
    return asNumber(
        firstAvailable(
            order?.priceIncl,
            order?.totalDue,
            order?.amount_total,
            order?.prices?.taxDetails?.total_amount_no_rounding,
            order?.prices?.taxDetails?.total_amount,
            order?.prices?.taxDetails?.total_amount_currency
        ),
        0
    );
}

function getOrderTotalWithoutTax(order) {
    return asNumber(
        firstAvailable(
            order?.priceExcl,
            order?.prices?.taxDetails?.base_amount,
            order?.prices?.taxDetails?.base_amount_currency
        ),
        0
    );
}

export function buildReceiptData(order) {
    const lines = (order?.lines || []).map((line) => ({
        product_name: firstAvailable(line?.full_product_name, line?.product_id?.display_name, line?.product_id?.name),
        qty: getLineQty(line),
        unit_price: asNumber(firstAvailable(line?.price_unit, line?.displayPriceUnit), 0),
        discount: asNumber(firstAvailable(line?.discount, line?.getDiscount?.()), 0),
        total_with_tax: getLineTotalWithTax(line),
        total_without_tax: getLineTotalWithoutTax(line),
        customer_note: firstAvailable(line?.customerNote),
    }));

    const payment_lines = (order?.payment_ids || [])
        .filter((payment) => !payment.is_change)
        .map((payment) => ({
            method: firstAvailable(payment?.payment_method_id?.name),
            amount: asNumber(payment?.getAmount ? payment.getAmount() : payment?.amount, 0),
        }));

    const totalWithTax = getOrderTotalWithTax(order);
    const totalWithoutTax = getOrderTotalWithoutTax(order);

    return {
        order_name: firstAvailable(order?.name),
        date: order?.date_order?.toISO ? order.date_order.toISO() : firstAvailable(order?.date_order),
        cashier: order?.getCashierName ? order.getCashierName() : "",
        company: {
            name: firstAvailable(order?.company?.name),
            vat: firstAvailable(order?.company?.vat),
            phone: firstAvailable(order?.company?.phone),
            email: firstAvailable(order?.company?.email),
            website: firstAvailable(order?.company?.website),
            address: [order?.company?.street, order?.company?.city, order?.company?.zip]
                .filter(Boolean)
                .join(", "),
        },
        totals: {
            total_with_tax: totalWithTax,
            total_without_tax: totalWithoutTax,
            total_tax: asNumber(firstAvailable(order?.amountTaxes, totalWithTax - totalWithoutTax), 0),
            change: asNumber(order?.change, 0),
            show_change: Boolean(order?.showChange),
            total_discount: asNumber(order?.getTotalDiscount ? order.getTotalDiscount() : 0, 0),
        },
        lines,
        payment_lines,
    };
}

export function buildReceiptXml(receiptData) {
    const linesXml = (receiptData.lines || [])
        .map(
            (line) =>
                `<line><product_name>${xmlEscape(line.product_name)}</product_name><qty>${xmlEscape(line.qty)}</qty><unit_price>${xmlEscape(line.unit_price)}</unit_price><total_with_tax>${xmlEscape(line.total_with_tax)}</total_with_tax><total_without_tax>${xmlEscape(line.total_without_tax)}</total_without_tax><discount>${xmlEscape(line.discount)}</discount><customer_note>${xmlEscape(line.customer_note)}</customer_note></line>`
        )
        .join("");

    const paymentXml = (receiptData.payment_lines || [])
        .map(
            (line) =>
                `<payment_line><method>${xmlEscape(line.method)}</method><amount>${xmlEscape(line.amount)}</amount></payment_line>`
        )
        .join("");

    return [
        "<receipt>",
        `<order_name>${xmlEscape(receiptData.order_name)}</order_name>`,
        `<date>${xmlEscape(receiptData.date)}</date>`,
        `<cashier>${xmlEscape(receiptData.cashier)}</cashier>`,
        "<company>",
        `<name>${xmlEscape(receiptData.company?.name)}</name>`,
        `<vat>${xmlEscape(receiptData.company?.vat)}</vat>`,
        `<phone>${xmlEscape(receiptData.company?.phone)}</phone>`,
        `<email>${xmlEscape(receiptData.company?.email)}</email>`,
        `<website>${xmlEscape(receiptData.company?.website)}</website>`,
        `<address>${xmlEscape(receiptData.company?.address)}</address>`,
        "</company>",
        "<totals>",
        `<total_with_tax>${xmlEscape(receiptData.totals?.total_with_tax)}</total_with_tax>`,
        `<total_without_tax>${xmlEscape(receiptData.totals?.total_without_tax)}</total_without_tax>`,
        `<total_tax>${xmlEscape(receiptData.totals?.total_tax)}</total_tax>`,
        `<change>${xmlEscape(receiptData.totals?.change)}</change>`,
        `<total_discount>${xmlEscape(receiptData.totals?.total_discount)}</total_discount>`,
        "</totals>",
        `<lines>${linesXml}</lines>`,
        `<payment_lines>${paymentXml}</payment_lines>`,
        "</receipt>",
    ].join("");
}
