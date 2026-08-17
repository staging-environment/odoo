/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { jsonrpc } from "@web/core/network/rpc_service";

export class PumpGridWidget extends Component {
    static template = "pos_gas_station.PumpGridWidget";

    setup() {
        this.pos = usePos();
        this.state = useState({
            pumps: [
                { id: 1, name: "Calle 1", fuel: "Gasóleo A", amount: 0.00, liters: 0.0, status: "idle", statusText: "LIBRE", product_id: 51, price: 1.769 },
                { id: 2, name: "Calle 2", fuel: "Gasóleo A", amount: 0.00, liters: 0.0, status: "idle", statusText: "LIBRE", product_id: 51, price: 1.769 },
                { id: 3, name: "Calle 3", fuel: "Sin Plomo 95", amount: 0.00, liters: 0.0, status: "idle", statusText: "LIBRE", product_id: 52, price: 1.655 },
                { id: 4, name: "Calle 4", fuel: "Gasóleo A", amount: 0.00, liters: 0.0, status: "idle", statusText: "LIBRE", product_id: 51, price: 1.769 }
            ]
        });

        this.pollInterval = null;

        onMounted(() => {
            this.fetchPumpsStatus();
            this.pollInterval = setInterval(() => {
                this.fetchPumpsStatus();
            }, 1500);
        });

        onWillUnmount(() => {
            if (this.pollInterval) {
                clearInterval(this.pollInterval);
            }
        });
    }

    async fetchPumpsStatus() {
        try {
            const data = await jsonrpc("/pos_gas_station/status", {});
            if (data && data.pumps && Array.isArray(data.pumps) && data.pumps.length > 0) {
                this.state.pumps = data.pumps;
            }
        } catch (err) {
            console.debug("Error al consultar estado de surtidores:", err);
        }
    }

    async onPumpClick(pump) {
        if (pump.amount > 0 && pump.liters > 0) {
            const currentOrder = this.pos.get_order();
            if (!currentOrder) return;

            // Buscar el producto en la BD del POS por ID o por nombre
            let product = null;
            if (pump.product_id && this.pos.db.product_by_id[pump.product_id]) {
                product = this.pos.db.product_by_id[pump.product_id];
            } else {
                const allProducts = Object.values(this.pos.db.product_by_id || {});
                product = allProducts.find(p => p.display_name.toLowerCase().includes(pump.fuel.toLowerCase())) || allProducts[0];
            }

            if (product) {
                await currentOrder.add_product(product, {
                    quantity: pump.liters,
                    price: pump.price || (pump.amount / pump.liters),
                    extras: {
                        price_manually_set: true
                    }
                });
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
