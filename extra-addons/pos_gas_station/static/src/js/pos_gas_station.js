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
        
        // Obtener config_id de forma robusta desde la URL o el objeto pos
        const urlParams = new URLSearchParams(window.location.search);
        this.configId = parseInt(urlParams.get("config_id")) || (this.pos.config ? this.pos.config.id : 2);
        
        this.state = useState({
            stationName: (this.pos.config && this.pos.config.name) ? `CONTROL DE PISTA - ${this.pos.config.name.toUpperCase()}` : "CONTROL DE PISTA",
            pumps: []
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
            const data = await jsonrpc("/pos_gas_station/status", {
                config_id: this.configId
            });
            if (data) {
                if (data.station_name) {
                    this.state.stationName = data.station_name;
                }
                if (data.pumps && Array.isArray(data.pumps)) {
                    this.state.pumps = data.pumps;
                }
            }
        } catch (err) {
            console.debug("Error al consultar estado de surtidores:", err);
        }
    }

    async onPumpClick(pump) {
        if (pump.amount > 0 && pump.liters > 0) {
            const currentOrder = this.pos.get_order();
            if (!currentOrder) return;

            let product = null;
            if (pump.product_id && this.pos.db.product_by_id[pump.product_id]) {
                product = this.pos.db.product_by_id[pump.product_id];
            } else {
                const allProducts = Object.values(this.pos.db.product_by_id || {});
                const fuelSearch = pump.fuel.toLowerCase().split('/')[0].trim();
                product = allProducts.find(p => p.display_name.toLowerCase().includes(fuelSearch)) || allProducts[0];
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
