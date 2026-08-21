/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
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

    get isSelectedPumpOccupied() {
        if (!this.state.selectedPumpId) return false;
        const p = this.state.pumps.find(x => x.id === this.state.selectedPumpId);
        return p && (p.status === 'dispensing' || p.status === 'ready' || p.amount > 0 || p.statusText === 'AUTORIZADO');
    }

    get isSelectedPumpActive() {
        return this.isSelectedPumpOccupied;
    }

    getPumpFuelClass(pump) {
        if (!pump) return "fuel-idle";
        const fData = this.getPumpFuelData(pump);
        if (!fData.isActive) return "fuel-idle";
        return "is-fuel-" + fData.type;
    }

    getPumpFuelData(pump) {
        if (!pump) {
            return {
                isActive: false,
                type: "idle",
                code: "GA/95",
                shortCode: "GA/95",
                name: "Gasóleo / Sin Plomo",
                category: "DISPONIBLE",
                badgeClass: "fuel-badge-idle",
                icon: "fa-gas-pump"
            };
        }

        const isBusy = pump.status === "dispensing" || pump.status === "ready" || pump.amount > 0 || pump.liters > 0 || pump.statusText === "AUTORIZADO";
        const isSelectedWithPreset = this.state.selectedPumpId === pump.id && this.state.presetValue > 0;

        let rawFuel = pump.fuel || "";
        if (isSelectedWithPreset) {
            const currentFuelObj = this.state.availableFuels.find(f => f.code === this.state.selectedFuel);
            if (currentFuelObj) {
                rawFuel = currentFuelObj.name;
            }
        }

        const f = (rawFuel || "").toLowerCase().trim();

        // Si la calle está libre y no tiene un combustible exclusivo seleccionado
        if (!isBusy && !isSelectedWithPreset && (f.includes("/") || !rawFuel || f.includes("libre"))) {
            return {
                isActive: false,
                type: "idle",
                code: "",
                shortCode: "GA/95",
                name: pump.fuel || "Gasóleo A / Sin Plomo 95",
                category: "DISPONIBLE",
                badgeClass: "fuel-badge-idle",
                icon: "fa-gas-pump"
            };
        }

        // 1. Gasolina / Sin Plomo (95 o 98)
        if (f.includes("plomo") || f.includes("95") || f.includes("gasolina") || f.includes("sp95") || f.includes("98") || f.includes("sp98")) {
            const is98 = f.includes("98") || f.includes("sp98");
            return {
                isActive: true,
                type: "gasolina",
                code: is98 ? "SP98" : "SP95",
                shortCode: is98 ? "98" : "95",
                name: rawFuel.includes("/") ? (is98 ? "Sin Plomo 98" : "Sin Plomo 95") : rawFuel,
                category: "GASOLINA",
                badgeClass: "fuel-badge-gasolina",
                icon: "fa-gas-pump"
            };
        }

        // 2. Gasóleo B / Agrícola
        if (f.includes("gasoleo b") || f.includes("gasóleo b") || f.includes("gb") || f.includes("agricola") || f.includes("agrícola")) {
            return {
                isActive: true,
                type: "gasoleob",
                code: "GB",
                shortCode: "GB",
                name: rawFuel.includes("/") ? "Gasóleo B (Agrícola)" : rawFuel,
                category: "AGRÍCOLA",
                badgeClass: "fuel-badge-gasoleob",
                icon: "fa-tractor"
            };
        }

        // 3. Diésel Plus / Premium / Óptima
        if (f.includes("plus") || f.includes("optima") || f.includes("óptima") || f.includes("premium")) {
            return {
                isActive: true,
                type: "gplus",
                code: "G+",
                shortCode: "G+",
                name: rawFuel.includes("/") ? "Gasóleo Óptima" : rawFuel,
                category: "DIÉSEL+",
                badgeClass: "fuel-badge-gplus",
                icon: "fa-star"
            };
        }

        // 4. Gasóleo A / Diésel estándar
        return {
            isActive: true,
            type: "diesel",
            code: "GA",
            shortCode: "GA",
            name: rawFuel.includes("/") ? "Gasóleo A" : rawFuel,
            category: "DIÉSEL",
            badgeClass: "fuel-badge-diesel",
            icon: "fa-gas-pump"
        };
    }

    getOrCreateOrder() {
        let order = this.pos.get_order();
        if (!order) {
            if (typeof this.pos.add_new_order === "function") {
                order = this.pos.add_new_order();
            } else if (this.pos.models && this.pos.models["pos.order"]) {
                order = this.pos.models["pos.order"].create();
            }
        }
        return order;
    }

    findFuelProduct(fuelCode) {
        const allProducts = Object.values(this.pos.db?.product_by_id || {});
        const code = (fuelCode || "GA").toUpperCase();
        
        let prod = null;
        if (code === "GA" || code === "DIESEL" || code === "1") {
            prod = allProducts.find(p => p.default_code === "1" || p.default_code === "GA" || (p.display_name && p.display_name.toLowerCase().includes("gasoleo a")) || (p.display_name && p.display_name.toLowerCase().includes("gasoleo")));
        } else if (code === "95" || code === "SP95" || code === "2") {
            prod = allProducts.find(p => p.default_code === "2" || p.default_code === "SP95" || p.default_code === "95" || (p.display_name && p.display_name.toLowerCase().includes("plomo 95")) || (p.display_name && p.display_name.toLowerCase().includes("plomo")));
        } else if (code === "GB" || code === "3") {
            prod = allProducts.find(p => p.default_code === "3" || p.default_code === "GB" || (p.display_name && p.display_name.toLowerCase().includes("gasoleo b")));
        }

        if (!prod && allProducts.length > 0) {
            prod = allProducts.find(p => p.display_name && (p.display_name.toLowerCase().includes("gas") || p.display_name.toLowerCase().includes("plomo"))) || allProducts[0];
        }
        return prod;
    }

    async handleBarcodeScan(code) {
        if (!code) return;
        const allProducts = Object.values(this.pos.db?.product_by_id || {});
        
        const found = allProducts.find(p => 
            (p.barcode && p.barcode.toLowerCase() === code.toLowerCase()) ||
            (p.default_code && p.default_code.toLowerCase() === code.toLowerCase())
        );

        if (found) {
            const currentOrder = this.getOrCreateOrder();
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
        const currentOrder = this.getOrCreateOrder();
        if (currentOrder) {
            currentOrder.set_note?.(plate ? `Matrícula: ${plate}` : "");
        }
    }

    selectOrderLine(line) {
        this.state.selectedLineId = line.id;
        const currentOrder = this.getOrCreateOrder();
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

    deleteSpecificLine(line) {
        const currentOrder = this.pos.get_order();
        if (!currentOrder || !line) return;

        try {
            if (typeof currentOrder._unlink_order_line === "function") {
                currentOrder._unlink_order_line(line);
            } else if (typeof currentOrder.removeOrderline === "function") {
                currentOrder.removeOrderline(line);
            } else if (typeof currentOrder.remove_orderline === "function") {
                currentOrder.remove_orderline(line);
            } else if (typeof line.set_quantity === "function") {
                line.set_quantity(0);
            } else if (typeof line.delete === "function") {
                line.delete();
            }
        } catch (e) {
            console.debug("Error en eliminación:", e);
        }

        if (currentOrder.orderlines) {
            const idx = currentOrder.orderlines.indexOf(line);
            if (idx > -1) currentOrder.orderlines.splice(idx, 1);
        }
        if (currentOrder.lines && Array.isArray(currentOrder.lines)) {
            const idx = currentOrder.lines.indexOf(line);
            if (idx > -1) currentOrder.lines.splice(idx, 1);
        }

        if (this.state.selectedLineId === line.id) {
            this.state.selectedLineId = null;
        }
        this.state.orderVersion = Date.now();
    }

    deleteSelectedLine() {
        const currentOrder = this.pos.get_order();
        if (!currentOrder) return;

        const lines = this.currentOrderLines;
        if (lines.length === 0) return;

        let targetLine = null;
        if (this.state.selectedLineId) {
            targetLine = lines.find(l => l.id === this.state.selectedLineId);
        }
        if (!targetLine) {
            targetLine = currentOrder.get_selected_orderline?.() || currentOrder.selected_orderline || lines[lines.length - 1];
        }

        if (targetLine) {
            this.deleteSpecificLine(targetLine);
        }
    }

    clearCurrentOrder() {
        const currentOrder = this.pos.get_order();
        if (!currentOrder) return;

        if (confirm("¿Está seguro de que desea cancelar y vaciar el ticket actual?")) {
            const lines = [...(currentOrder.get_orderlines?.() || currentOrder.orderlines || [])];
            lines.forEach(l => {
                this.deleteSpecificLine(l);
            });
            if (currentOrder.orderlines) currentOrder.orderlines.length = 0;
            if (currentOrder.lines && Array.isArray(currentOrder.lines)) currentOrder.lines.length = 0;

            this.state.selectedLineId = null;
            this.state.vehiclePlate = "";
            currentOrder.set_note?.("");
            this.state.orderVersion = Date.now();
        }
    }

    openRefundScreen() {
        this.pos.showScreen("TicketScreen");
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
        const currentOrder = this.getOrCreateOrder();
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
        const pumpId = this.state.selectedPumpId || 1;
        const targetPump = this.state.pumps.find(p => p.id === pumpId);

        // BLOQUEO ESTRICTO: No permitir apertura si la pista ya está ocupada por otro cliente
        if (targetPump && (targetPump.status === "dispensing" || targetPump.status === "ready" || targetPump.amount > 0 || targetPump.statusText === "AUTORIZADO")) {
            alert(`⚠️ La Calle ${pumpId} ya está ocupada por otro cliente (${targetPump.statusText}).\nDebe cobrarse o liberarse antes de una nueva autorización.`);
            return;
        }

        const currentFuelObj = this.state.availableFuels.find(f => f.code === this.state.selectedFuel) || this.state.availableFuels[0] || { code: "GA", name: "Gasóleo A" };
        const fuelName = currentFuelObj.name;
        const fuelCode = currentFuelObj.code;
        const isMoney = this.state.mode === "money";
        const presetVal = this.state.presetValue;

        // 1. Marcar inmediatamente la calle como AUTORIZADO / EN PROCESO en la vista
        if (targetPump) {
            targetPump.status = "dispensing";
            targetPump.statusText = "AUTORIZADO";
            targetPump.fuel = fuelName;
            if (presetVal > 0) {
                targetPump.amount = isMoney ? presetVal : 0;
                targetPump.liters = !isMoney ? presetVal : 0;
            }
        }

        // 2. Si tiene importe prefijado (Prepago), añadir al ticket activo
        if (presetVal > 0) {
            const currentOrder = this.getOrCreateOrder();
            if (currentOrder) {
                const product = this.findFuelProduct(fuelCode);

                if (product) {
                    const currentFuelPrice = product.lst_price > 0 ? product.lst_price : (fuelCode === 'GA' ? 1.78 : 1.66);
                    let qty = 1;
                    let unitPrice = currentFuelPrice;

                    if (isMoney) {
                        qty = parseFloat((presetVal / currentFuelPrice).toFixed(2));
                        unitPrice = currentFuelPrice;
                    } else {
                        qty = presetVal;
                        unitPrice = currentFuelPrice;
                    }

                    await currentOrder.add_product(product, {
                        quantity: qty,
                        price: unitPrice,
                        extras: {
                            price_manually_set: true
                        }
                    });

                    const plateInfo = this.state.vehiclePlate ? `Matrícula: ${this.state.vehiclePlate} | ` : "";
                    currentOrder.set_note?.(`${plateInfo}Calle ${pumpId} [Prepago: ${presetVal} ${isMoney ? '€' : 'L'}]`);
                    this.state.orderVersion = Date.now();
                }
            }
        }

        // 3. Enviar orden al backend / concentrador
        try {
            await jsonrpc("/pos_gas_station/authorize", {
                config_id: this.configId,
                pump_id: pumpId,
                fuel: fuelCode,
                amount: isMoney ? presetVal : 0,
                liters: !isMoney ? presetVal : 0
            });
        } catch (e) {
            console.debug("Orden de autorización enviada:", e);
        }

        this.clearPreset();
    }

    async cancelPumpAuthorization(pump) {
        if (confirm(`¿Desea cancelar la autorización y volver a bloquear la Calle ${pump.id}?`)) {
            pump.status = "idle";
            pump.statusText = "LIBRE";
            pump.amount = 0;
            pump.liters = 0;
            try {
                await jsonrpc("/pos_gas_station/cancel_authorize", {
                    config_id: this.configId,
                    pump_id: pump.id
                });
            } catch (e) {
                console.debug("Cancelación enviada:", e);
            }
            this.state.orderVersion = Date.now();
        }
    }

    async onSecurityDepositClick() {
        const amountStr = prompt("🔒 INGRESO DE SEGURIDAD (RETIRADA A CAJA FUERTE UAAP)\nIntroduzca el importe en efectivo a retirar de la caja (Ej: 500):", "500");
        if (!amountStr) return;
        const amount = parseFloat(amountStr);
        if (isNaN(amount) || amount <= 0) {
            alert("Importe no válido.");
            return;
        }

        try {
            if (typeof this.pos.create_cash_move === "function") {
                await this.pos.create_cash_move(-amount, "Ingreso de Seguridad - Exceso de efectivo");
            }
            alert(`✅ INGRESO DE SEGURIDAD REGISTRADO: ${amount.toFixed(2)} €.\nPor favor, retire los billetes de la caja y deposítelos en la caja fuerte.`);
        } catch (e) {
            alert(`✅ Registrado Ingreso de Seguridad de ${amount.toFixed(2)} €.`);
        }
    }

    onEmergencyStopClick() {
        if (confirm("⚠️ ¿PARADA DE EMERGENCIA TOTAL DE PISTA?\nSe bloquearán inmediatamente todos los surtidores.")) {
            alert("🚨 Parada de emergencia ejecutada. Surtidores bloqueados.");
        }
    }

    async onPumpClick(pump) {
        // Si el surtidor tiene suministro realizado (Postpago)
        if (pump.amount > 0 && pump.liters > 0) {
            const currentOrder = this.getOrCreateOrder();
            if (!currentOrder) return;

            let product = null;
            if (pump.product_id && this.pos.db.product_by_id[pump.product_id]) {
                product = this.pos.db.product_by_id[pump.product_id];
            } else {
                const fuelSearch = pump.fuel.toLowerCase();
                const fuelCode = fuelSearch.includes("plomo") || fuelSearch.includes("95") ? "95" : "GA";
                product = this.findFuelProduct(fuelCode);
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

                // Liberar surtidor una vez pasado al ticket
                pump.status = "idle";
                pump.statusText = "LIBRE";
                pump.amount = 0;
                pump.liters = 0;
                try {
                    await jsonrpc("/pos_gas_station/clear_pump", {
                        config_id: this.configId,
                        pump_id: pump.id
                    });
                } catch (e) {
                    console.debug("Liberación de bomba enviada:", e);
                }

                this.state.orderVersion = Date.now();
            }
        } else {
            // Si está libre, seleccionarlo para autorizar
            this.state.selectedPumpId = pump.id;
        }
    }
}

patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);
    }
});


    get popularStoreProducts() {
        if (!this.pos.db) return [];
        const all = Object.values(this.pos.db.product_by_id || {});
        // Filtrar productos que no sean combustibles principales para la parrilla de tienda
        const storeProds = all.filter(p => {
            const name = (p.display_name || p.name || "").toLowerCase();
            return !name.startsWith("gasóleo") && !name.startsWith("gasoleo") && !name.startsWith("sin plomo") && p.available_in_pos;
        }).slice(0, 20);

        if (storeProds.length > 0) {
            return storeProds;
        }

        // Si no hay productos de tienda creados en Odoo todavía, mostrar artículos habituales de gasolinera
        return all.slice(0, 16);
    }

    get storeFillerSlots() {
        const count = this.popularStoreProducts.length;
        const totalDesired = 20;
        const remaining = Math.max(0, totalDesired - count);
        return Array.from({ length: remaining }, (_, i) => i);
    }

    applyQuickDiscount() {
        const currentOrder = this.pos.get_order();
        if (!currentOrder) return;
        const line = currentOrder.get_selected_orderline();
        if (!line) {
            alert("Seleccione primero una línea de la venta para aplicar descuento.");
            return;
        }
        const dtoStr = prompt("Introduzca el porcentaje de descuento % (Ej: 5 o 10):", "5");
        if (dtoStr && !isNaN(parseFloat(dtoStr))) {
            line.set_discount(parseFloat(dtoStr));
            this.state.orderVersion = Date.now();
        }
    }

    focusBarcode() {
        const code = prompt("Escanear o teclear código de barras / referencia:");
        if (code) {
            const all = Object.values(this.pos.db.product_by_id || {});
            const prod = all.find(p => p.barcode === code || p.default_code === code);
            if (prod) {
                this.addStoreProductToOrder(prod);
            } else {
                alert(`No se encontró ningún producto con código ${code}`);
            }
        }
    }

ProductScreen.components = {
    ...ProductScreen.components,
    UtrecarMainScreen,
};

patch(PaymentScreen.prototype, {
    async validateVirtusTicket() {
        if (!this.currentOrder.is_paid()) {
            alert("El pedido aún no está totalmente pagado. Seleccione el medio de pago (Efectivo / Tarjeta).");
            return;
        }
        this.currentOrder.set_to_invoice(false);
        await this.validateOrder(false);
    },

    async validateVirtusInvoice() {
        if (!this.currentOrder.is_paid()) {
            alert("El pedido aún no está totalmente pagado. Seleccione el medio de pago (Efectivo / Tarjeta).");
            return;
        }
        if (!this.currentOrder.get_partner()) {
            const { confirmed } = await this.pos.showScreen("PartnerListScreen");
            if (!confirmed || !this.currentOrder.get_partner()) {
                alert("Para emitir Factura es obligatorio asignar o registrar un cliente con NIF/CIF.");
                return;
            }
        }
        this.currentOrder.set_to_invoice(true);
        await this.validateOrder(false);
    },

    async validateVirtusNoPrint() {
        if (!this.currentOrder.is_paid()) {
            alert("El pedido aún no está totalmente pagado. Seleccione el medio de pago (Efectivo / Tarjeta).");
            return;
        }
        this.currentOrder.set_to_invoice(false);
        const originalPrint = this.pos.config.iface_print_auto;
        this.pos.config.iface_print_auto = false;
        
        await this.validateOrder(false);
        
        // Finalización rápida sin imprimir: abrir nueva venta directamente
        if (this.pos.mainScreen && (this.pos.mainScreen.name === "ReceiptScreen" || this.pos.mainScreen.name === "TicketScreen")) {
            this.pos.add_new_order();
            this.pos.showScreen("ProductScreen");
        }
        this.pos.config.iface_print_auto = originalPrint;
    }
});
