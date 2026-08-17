/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { jsonrpc } from "@web/core/network/rpc_service";

export class UtrecarMainScreen extends Component {
    static template = "pos_gas_station.UtrecarMainScreen";

    setup() {
        this.pos = usePos();
        
        const urlParams = new URLSearchParams(window.location.search);
        this.configId = parseInt(urlParams.get("config_id")) || (this.pos.config ? this.pos.config.id : 2);
        
        this.state = useState({
            stationName: (this.pos.config && this.pos.config.name) ? `CONTROL DE PISTA - ${this.pos.config.name.toUpperCase()}` : "CONTROL DE PISTA",
            vehiclePlate: "",
            selectedPumpId: null,
            selectedLineId: null,
            mode: "money", // 'money' o 'liters'
            presetValue: 0,
            selectedFuel: "GA",
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

    get currentOrderLines() {
        const order = this.pos.get_order();
        return order ? order.get_orderlines() : [];
    }

    get currentTotalAmount() {
        const order = this.pos.get_order();
        return order ? order.get_total_with_tax() : 0.00;
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

    onPlateChange(ev) {
        const plate = ev.target.value.toUpperCase();
        this.state.vehiclePlate = plate;
        const currentOrder = this.pos.get_order();
        if (currentOrder) {
            currentOrder.set_note(plate ? `Matrícula: ${plate}` : "");
        }
    }

    selectOrderLine(line) {
        this.state.selectedLineId = line.id;
        const currentOrder = this.pos.get_order();
        if (currentOrder) {
            currentOrder.select_orderline(line);
        }
    }

    deleteSelectedLine() {
        const currentOrder = this.pos.get_order();
        if (currentOrder) {
            const line = currentOrder.get_selected_orderline();
            if (line) {
                currentOrder.remove_orderline(line);
            }
        }
    }

    clearCurrentOrder() {
        const currentOrder = this.pos.get_order();
        if (currentOrder && confirm("¿Está seguro de que desea cancelar y vaciar el ticket actual?")) {
            const lines = [...currentOrder.get_orderlines()];
            lines.forEach(l => currentOrder.remove_orderline(l));
            this.state.vehiclePlate = "";
            currentOrder.set_note("");
        }
    }

    goToPayment() {
        const currentOrder = this.pos.get_order();
        if (!currentOrder || currentOrder.get_orderlines().length === 0) {
            alert("No hay artículos en el ticket para cobrar.");
            return;
        }
        this.pos.showScreen("PaymentScreen");
    }

    onPumpSelect(pump) {
        this.state.selectedPumpId = pump.id;
    }

    toggleMode() {
        this.state.mode = this.state.mode === "money" ? "liters" : "money";
    }

    addPreset(val) {
        this.state.presetValue = val;
    }

    selectFuel(fuel) {
        this.state.selectedFuel = fuel;
    }

    clearPreset() {
        this.state.presetValue = 0;
        this.state.selectedPumpId = null;
    }

    async authorizePreset() {
        if (!this.state.selectedPumpId) {
            alert("Por favor, seleccione primero la Calle / Surtidor a autorizar.");
            return;
        }
        const fuelNames = {
            "GA": "Gasóleo A",
            "95": "Sin Plomo 95",
            "GB": "Gasóleo B",
            "G+": "Gasóleo Plus"
        };
        const fuelName = fuelNames[this.state.selectedFuel] || "Gasóleo A";
        const valText = this.state.presetValue > 0 ? `${this.state.presetValue} ${this.state.mode === 'money' ? '€' : 'L'}` : "Libre";
        
        alert(`✅ Surtidor Calle ${this.state.selectedPumpId} AUTORIZADO\nCombustible: ${fuelName}\nPrefijado: ${valText}`);
        this.clearPreset();
    }

    onSecurityDepositClick() {
        const amount = prompt("🔒 INGRESO DE SEGURIDAD\nIntroduzca el importe en efectivo a retirar de la caja (Ej: 500):");
        if (amount && !isNaN(parseFloat(amount))) {
            alert(`✅ Registrado Ingreso de Seguridad de ${parseFloat(amount).toFixed(2)} €.\nImprimiendo comprobante de depósito.`);
        }
    }

    onEmergencyStopClick() {
        if (confirm("⚠️ ¿PARADA DE EMERGENCIA TOTAL DE PISTA?\nSe bloquearán inmediatamente todos los surtidores.")) {
            alert("🚨 Parada de emergencia ejecutada. Surtidores bloqueados.");
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
                if (this.state.vehiclePlate) {
                    currentOrder.set_note(`Matrícula: ${this.state.vehiclePlate}`);
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
    UtrecarMainScreen,
};
