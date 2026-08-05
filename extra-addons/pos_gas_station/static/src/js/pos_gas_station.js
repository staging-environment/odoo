/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class PumpGridWidget extends Component {
    static template = "pos_gas_station.PumpGridWidget";

    setup() {
        this.pos = usePos();
        this.state = useState({
            pumps: [
                { id: 1, name: "Surtidor 1", fuel: "Gasolina 95", amount: 42.50, liters: 28.3, status: "dispensing", statusText: "SUMINISTRANDO" },
                { id: 2, name: "Surtidor 2", fuel: "Diesel A", amount: 50.00, liters: 36.2, status: "ready", statusText: "PENDIENTE DE COBRO" },
                { id: 3, name: "Surtidor 3", fuel: "Gasolina 98", amount: 0.00, liters: 0.0, status: "idle", statusText: "LIBRE" },
                { id: 4, name: "Surtidor 4", fuel: "Diesel Premium", amount: 15.00, liters: 10.8, status: "ready", statusText: "PENDIENTE DE COBRO" },
                { id: 5, name: "Surtidor 5", fuel: "Gasolina 95", amount: 0.00, liters: 0.0, status: "idle", statusText: "LIBRE" },
                { id: 6, name: "Surtidor 6", fuel: "Diesel A", amount: 0.00, liters: 0.0, status: "locked", statusText: "BLOQUEADO" }
            ]
        });
    }

    async onPumpClick(pump) {
        if (pump.status === 'ready' && pump.amount > 0) {
            const currentOrder = this.pos.get_order();
            if (currentOrder) {
                const products = Object.values(this.pos.db.product_by_id || {});
                const product = products[0];
                if (product) {
                    await currentOrder.add_product(product, {
                        price: pump.amount,
                        quantity: 1,
                        extras: {
                            price_manually_set: true
                        }
                    });
                }
            }
        }
    }
}

patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);
    }
});

ProductScreen.components = {
    ...ProductScreen.components,
    PumpGridWidget,
};
