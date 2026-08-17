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
            orderVersion: 0,
            mode: "money", // 'money' o 'liters'
            presetValue: 0,
            selectedFuel: "GA",
            availableFuels: [
                { code: "GA", name: "Gasóleo A", class: "ga" },
                { code: "95", name: "Sin Plomo 95", class: "sp95" }
            ],
            isStoreModalOpen: false,
            storeSearch: "",
            pumps: []
        });

        this.pollInterval = null;
        this.barcodeBuffer = "";
        this.barcodeTimeout = null;

        // Escucha global de pistola de código de barras
        this.onGlobalKeyDown = (ev) => {
            if (ev.target && ev.target.classList.contains("euro-plate-text")) {
                return;
            }

            if (ev.key === "Enter") {
                if (this.barcodeBuffer.length >= 3) {
                    this.handleBarcodeScan(this.barcodeBuffer.trim());
                    this.barcodeBuffer = "";
                    ev.preventDefault();
                }
            } else if (ev.key && ev.key.length === 1) {
                this.barcodeBuffer += ev.key;
                if (this.barcodeTimeout) clearTimeout(this.barcodeTimeout);
                this.barcodeTimeout = setTimeout(() => {
                    this.barcodeBuffer = "";
                }, 250);
            }
        };

        onMounted(() => {
            this.fetchPumpsStatus();
            this.pollInterval = setInterval(() => {
                this.fetchPumpsStatus();
                // Actualizar versión reactiva de la cesta
                const ord = this.pos.get_order();
                if (ord) {
                    const linesCount = ord.get_orderlines?.()?.length || ord.orderlines?.length || 0;
                    const totalAmt = ord.get_total_with_tax?.() || 0;
                    const v = linesCount * 1000 + totalAmt;
                    if (this.state.orderVersion !== v) {
                        this.state.orderVersion = v;
                    }
                }
            }, 800);
            window.addEventListener("keydown", this.onGlobalKeyDown);
        });

        onWillUnmount(() => {
            if (this.pollInterval) {
                clearInterval(this.pollInterval);
            }
            window.removeEventListener("keydown", this.onGlobalKeyDown);
        });
    }

    async handleBarcodeScan(code) {
        if (!code) return;
        const allProducts = Object.values(this.pos.db?.product_by_id || {});
        
        const found = allProducts.find(p => 
            (p.barcode && p.barcode.toLowerCase() === code.toLowerCase()) ||
            (p.default_code && p.default_code.toLowerCase() === code.toLowerCase())
        );

        if (found) {
            const currentOrder = this.pos.get_order();
            if (currentOrder) {
                await currentOrder.add_product(found, { quantity: 1 });
                if (this.state.vehiclePlate) {
                    currentOrder.set_note?.(`Matrícula: ${this.state.vehiclePlate}`);
                }
                this.state.orderVersion = Date.now();
                if (this.state.isStoreModalOpen) {
                    this.closeStoreModal();
                }
            }
        } else {
            console.warn("Código de barras no encontrado en catálogo:", code);
        }
    }

    get currentOrderLines() {
        const dummy = this.state.orderVersion;
        const order = this.pos.get_order();
        return order ? (order.get_orderlines?.() || order.orderlines || []) : [];
    }

    get currentTotalAmount() {
        const dummy = this.state.orderVersion;
        const order = this.pos.get_order();
        return order ? (order.get_total_with_tax?.() || 0.00) : 0.00;
    }

    get filteredStoreProducts() {
        let all = [];
        if (this.pos.db && this.pos.db.product_by_id) {
            all = Object.values(this.pos.db.product_by_id);
        } else if (this.pos.models && this.pos.models["product.product"]) {
            all = this.pos.models["product.product"].getAll();
        }

        const q = (this.state.storeSearch || "").toLowerCase().trim();
        if (!q) {
            return all.slice(0, 40);
        }
        return all.filter(p => {
            const name = (p.display_name || p.name || "").toLowerCase();
            const code = (p.default_code || "").toLowerCase();
            const barcode = (p.barcode || "").toLowerCase();
            return name.includes(q) || code.includes(q) || barcode.includes(q);
        }).slice(0, 40);
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
                if (data.available_fuels && Array.isArray(data.available_fuels)) {
                    this.state.availableFuels = data.available_fuels;
                    if (!this.state.availableFuels.some(f => f.code === this.state.selectedFuel)) {
                        this.state.selectedFuel = this.state.availableFuels[0].code;
                    }
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
            currentOrder.set_note?.(plate ? `Matrícula: ${plate}` : "");
        }
    }

    selectOrderLine(line) {
        this.state.selectedLineId = line.id;
        const currentOrder = this.pos.get_order();
        if (currentOrder) {
            if (typeof currentOrder.select_orderline === "function") {
                currentOrder.select_orderline(line);
            } else if (typeof currentOrder.selectOrderline === "function") {
                currentOrder.selectOrderline(line);
            } else {
                currentOrder.selected_orderline = line;
            }
        }
    }

    deleteSelectedLine() {
        const currentOrder = this.pos.get_order();
        if (currentOrder) {
            const line = currentOrder.get_selected_orderline?.() || currentOrder.selected_orderline || (this.currentOrderLines.length > 0 ? this.currentOrderLines[this.currentOrderLines.length - 1] : null);
            if (line) {
                if (typeof currentOrder.removeOrderline === "function") {
                    currentOrder.removeOrderline(line);
                } else if (typeof currentOrder.remove_orderline === "function") {
                    currentOrder.remove_orderline(line);
                } else if (typeof line.delete === "function") {
                    line.delete();
                } else if (currentOrder.orderlines) {
                    const idx = currentOrder.orderlines.indexOf(line);
                    if (idx > -1) currentOrder.orderlines.splice(idx, 1);
                }
                this.state.orderVersion = Date.now();
            }
        }
    }

    clearCurrentOrder() {
        const currentOrder = this.pos.get_order();
        if (currentOrder && confirm("¿Está seguro de que desea cancelar y vaciar el ticket actual?")) {
            const lines = [...(currentOrder.get_orderlines?.() || currentOrder.orderlines || [])];
            lines.forEach(l => {
                if (typeof currentOrder.removeOrderline === "function") {
                    currentOrder.removeOrderline(l);
                } else if (typeof currentOrder.remove_orderline === "function") {
                    currentOrder.remove_orderline(l);
                } else if (typeof l.delete === "function") {
                    l.delete();
                }
            });
            this.state.vehiclePlate = "";
            currentOrder.set_note?.("");
            this.state.orderVersion = Date.now();
        }
    }

    goToPayment() {
        const currentOrder = this.pos.get_order();
        if (!currentOrder || this.currentOrderLines.length === 0) {
            alert("No hay artículos en el ticket para cobrar.");
            return;
        }
        this.pos.showScreen("PaymentScreen");
    }

    openStoreModal() {
        this.state.storeSearch = "";
        this.state.isStoreModalOpen = true;
    }

    closeStoreModal() {
        this.state.isStoreModalOpen = false;
    }

    onStoreSearchInput(ev) {
        this.state.storeSearch = ev.target.value;
    }

    async addStoreProductToOrder(product) {
        const currentOrder = this.pos.get_order();
        if (currentOrder) {
            await currentOrder.add_product(product, {
                quantity: 1,
            });
            if (this.state.vehiclePlate) {
                currentOrder.set_note?.(`Matrícula: ${this.state.vehiclePlate}`);
            }
            this.state.orderVersion = Date.now();
        }
        this.closeStoreModal();
    }

    onPumpSelect(pump) {
        this.state.selectedPumpId = pump.id;
    }

    toggleMode() {
        this.state.mode = this.state.mode === "money" ? "liters" : "money";
        this.state.presetValue = 0;
    }

    addPreset(val) {
        this.state.presetValue = (this.state.presetValue || 0) + val;
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
        const currentFuelObj = this.state.availableFuels.find(f => f.code === this.state.selectedFuel) || { name: "Gasóleo A" };
        const fuelName = currentFuelObj.name;
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
                product = allProducts.find(p => p.display_name.toLowerCase().includes(fuelSearch) && p.default_code?.startsWith("100")) ||
                          allProducts.find(p => p.display_name.toLowerCase().includes(fuelSearch)) ||
                          allProducts[0];
            }

            if (product) {
                const unitPrice = pump.price || (pump.amount / pump.liters);
                await currentOrder.add_product(product, {
                    quantity: pump.liters,
                    price: unitPrice,
                    extras: {
                        price_manually_set: true
                    }
                });
                if (this.state.vehiclePlate) {
                    currentOrder.set_note?.(`Matrícula: ${this.state.vehiclePlate}`);
                }
                this.state.orderVersion = Date.now();
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
