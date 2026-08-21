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

        this.barcodeBuffer = "";
        this.barcodeTimeout = null;

        this.onGlobalKeyDown = (ev) => {
            if (ev.target && (ev.target.tagName === 'INPUT' || ev.target.tagName === 'TEXTAREA')) {
                return;
            }
            if (ev.key === 'Enter') {
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

                    get popularStoreProducts() {
        // Matriz completa de 20 casillas de VirtusTPV (5x4) con todas las imágenes de la base de datos
        const virtusGridItems = [
            // Fila 1
            { id: "v_hielo", display_name: "HIELO EN BOLSA", lst_price: 1.90, bg_image: "/pos_gas_station/static/src/img/products/prod_341005.png", default_code: "341005" },
            { id: "v_chupa", display_name: "CHUPA CHUPS", lst_price: 0.40, bg_image: "/pos_gas_station/static/src/img/products/prod_312006.png", default_code: "312006" },
            { id: "v_kinder", display_name: "KINDER BUENO", lst_price: 1.50, bg_image: "/pos_gas_station/static/src/img/products/prod_311001.png", default_code: "311001" },
            { id: "v_mechero", display_name: "MECHERO CLIPPER", lst_price: 1.00, bg_image: "/pos_gas_station/static/src/img/products/prod_323003.png", default_code: "323003" },

            // Fila 2
            { id: "v_butano", display_name: "BOMBONA BUTANO", lst_price: 23.00, bg_image: "/pos_gas_station/static/src/img/products/prod_360014.png", default_code: "360014" },
            { id: "v_dulces", display_name: "DULCES DULCESOL", lst_price: 1.00, bg_image: "/pos_gas_station/static/src/img/products/prod_315006.png", default_code: "315006" },
            { id: "v_coca", display_name: "LATA COCA-COLA", lst_price: 1.50, bg_image: "/pos_gas_station/static/src/img/products/prod_342001.png", default_code: "342001" },
            { id: "v_cocazero", display_name: "COCA-COLA ZERO", lst_price: 1.50, bg_image: "/pos_gas_station/static/src/img/products/prod_342003.png", default_code: "342003" },

            // Fila 3
            { id: "v_aceite2t", display_name: "ACEITE 2T NIPOMIX", lst_price: 1.40, bg_image: "/pos_gas_station/static/src/img/products/prod_331002.png", default_code: "331002" },
            { id: "v_castrol", display_name: "ACEITE 2T CASTROL", lst_price: 2.00, bg_image: "/pos_gas_station/static/src/img/products/prod_331001.png", default_code: "331001" },
            { id: "v_vaper", display_name: "VAPER SABORES", lst_price: 6.50, bg_image: "/pos_gas_station/static/src/img/products/prod_323006.png", default_code: "323006" },
            { id: "v_papel", display_name: "PAPEL DE LIAR", lst_price: 1.00, bg_image: "/pos_gas_station/static/src/img/products/prod_323001.png", default_code: "323001" },

            // Fila 4
            { id: "v_cafe", display_name: "CAFE", lst_price: 1.00, bg_image: "/pos_gas_station/static/src/img/products/prod_382001.png", default_code: "382001" },
            { id: "v_zumo", display_name: "ZUMO DE BOTE", lst_price: 1.30, bg_image: "/pos_gas_station/static/src/img/products/prod_382006.png", default_code: "382006" },
            { id: "v_bifrutas", display_name: "BI FRUTAS", lst_price: 1.20, bg_image: "/pos_gas_station/static/src/img/products/prod_382008.png", default_code: "382008" },
            { id: "v_cubata", display_name: "CUBATAS", lst_price: 4.00, bg_image: "/pos_gas_station/static/src/img/products/prod_383003.png", default_code: "383003" },

            // Fila 5
            { id: "v_boc", display_name: "BOC", text_only: true, full_name: "TOSTADA / BOCADILLO", lst_price: 1.70, default_code: "381001" },
            { id: "v_cocatxt", display_name: "COCA COLA LATA", text_only: true, full_name: "LATA COCA-COLA", lst_price: 1.50, default_code: "342001" },
            { id: "v_pan", display_name: "PAN DE TORRIJA", text_only: true, full_name: "PAN PARA LLEVAR", lst_price: 0.60, default_code: "381003" },
            { id: "v_tostada", display_name: "MEDIA TOSTADA", text_only: true, full_name: "MEDIA TOSTADA", lst_price: 1.30, default_code: "381002" }
        ];

        return virtusGridItems;
    }

    get storeFillerSlots() {
        return [];
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
            order = this.pos.add_new_order();
        }
        return order;
    }

    get currentOrderLines() {
        const order = this.pos.get_order();
        if (!order) return [];
        if (typeof order.get_orderlines === "function") {
            return order.get_orderlines();
        }
        return order.orderlines || [];
    }

    get currentTotalAmount() {
        const order = this.pos.get_order();
        if (!order) return 0.0;
        if (typeof order.get_total_with_tax === "function") {
            return order.get_total_with_tax();
        }
        return order.amount_total || 0.0;
    }

    get filteredStoreProducts() {
        if (!this.pos || !this.pos.db) return [];
        const all = Object.values(this.pos.db.product_by_id || {});
        const q = (this.state.storeSearch || "").toLowerCase().trim();
        if (!q) {
            return all.filter(p => {
                const name = (p.display_name || p.name || "").toLowerCase();
                return !name.startsWith("gasóleo") && !name.startsWith("gasoleo") && !name.startsWith("sin plomo") && p.available_in_pos;
            }).slice(0, 40);
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
            if (typeof currentOrder.remove_orderline === "function") {
                currentOrder.remove_orderline(line);
            } else if (typeof currentOrder._unlink_order_line === "function") {
                currentOrder._unlink_order_line(line);
            } else if (typeof currentOrder.removeOrderline === "function") {
                currentOrder.removeOrderline(line);
            }
        } catch (e) {
            try {
                if (typeof line.delete === "function") {
                    line.delete();
                }
            } catch (err) {
                console.error("Error al borrar linea:", err);
            }
        }
        this.state.selectedLineId = null;
        this.state.orderVersion = Date.now();
    }

    deleteSelectedLine() {
        const currentOrder = this.pos.get_order();
        if (!currentOrder) return;
        const line = currentOrder.get_selected_orderline();
        if (line) {
            this.deleteSpecificLine(line);
        } else if (this.currentOrderLines.length > 0) {
            this.deleteSpecificLine(this.currentOrderLines[this.currentOrderLines.length - 1]);
        }
    }

    clearCurrentOrder() {
        const currentOrder = this.pos.get_order();
        if (currentOrder && confirm("¿Desea cancelar y vaciar el ticket actual?")) {
            try {
                const lines = [...this.currentOrderLines];
                for (const l of lines) {
                    this.deleteSpecificLine(l);
                }
                currentOrder.set_note?.("");
            } catch (e) {
                console.debug("Error al vaciar orden:", e);
            }
            this.state.vehiclePlate = "";
            this.state.selectedLineId = null;
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

    get currentOrderPartner() {
        const order = this.pos.get_order();
        return order ? order.get_partner() : null;
    }

    async onClickPartner() {
        const currentPartner = this.currentOrderPartner;
        const { confirmed, payload: newPartner } = await this.pos.showTempScreen(
            "PartnerListScreen",
            { partner: currentPartner }
        );
        if (confirmed) {
            const order = this.pos.get_order();
            if (order) {
                order.set_partner(newPartner);
            }
        }
    }

    async addStoreProductToOrder(virtusItem) {
        if (!virtusItem || virtusItem.is_empty) return;
        const currentOrder = this.getOrCreateOrder();
        if (!currentOrder) return;

        let realProduct = null;
        if (virtusItem && typeof virtusItem.get_unit === "function") {
            realProduct = virtusItem;
        } else if (this.pos.db && this.pos.db.product_by_id) {
            const all = Object.values(this.pos.db.product_by_id);
            const code = (virtusItem.default_code || "").toLowerCase();
            const name = (virtusItem.display_name || virtusItem.full_name || "").toLowerCase();

            realProduct = all.find(p => (p.default_code || "").toLowerCase() === code) ||
                          all.find(p => (p.display_name || p.name || "").toLowerCase().includes(name)) ||
                          all.find(p => !(p.display_name || p.name || "").toLowerCase().includes("gasóleo") && !(p.display_name || p.name || "").toLowerCase().includes("plomo")) ||
                          all[0];
        }

        if (realProduct) {
            const price = virtusItem.lst_price || realProduct.lst_price || 1.0;
            await currentOrder.add_product(realProduct, {
                quantity: 1,
                price: price,
                extras: {
                    price_manually_set: true
                }
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

    findFuelProduct(fuelCode) {
        const allProducts = Object.values(this.pos.db.product_by_id || {});
        let targetName = "Gasóleo A";
        let targetRef = "GAS_A";

        if (fuelCode === "95" || fuelCode === "SP95") {
            targetName = "Sin Plomo 95";
            targetRef = "SP95";
        } else if (fuelCode === "GB") {
            targetName = "Gasóleo B";
            targetRef = "GAS_B";
        } else if (fuelCode === "G+") {
            targetName = "Gasóleo Plus";
            targetRef = "GAS_PLUS";
        }

        let p = allProducts.find(x => x.default_code === targetRef || (x.name && x.name.toLowerCase().includes(targetName.toLowerCase())));
        if (!p) {
            p = allProducts.find(x => x.name && (x.name.toLowerCase().includes("carburante") || x.name.toLowerCase().includes("combustible")));
        }
        if (!p && allProducts.length > 0) {
            p = allProducts[0];
        }
        return p;
    }

    async authorizePreset() {
        const pumpId = this.state.selectedPumpId || 1;
        const targetPump = this.state.pumps.find(p => p.id === pumpId);

        if (targetPump && (targetPump.status === "dispensing" || targetPump.status === "ready" || targetPump.amount > 0 || targetPump.statusText === "AUTORIZADO")) {
            alert(`⚠️ La Calle ${pumpId} ya está ocupada (${targetPump.statusText}).\nDebe cobrarse o liberarse antes de una nueva autorización.`);
            return;
        }

        const currentFuelObj = this.state.availableFuels.find(f => f.code === this.state.selectedFuel) || this.state.availableFuels[0] || { code: "GA", name: "Gasóleo A" };
        const fuelName = currentFuelObj.name;
        const fuelCode = currentFuelObj.code;
        const isMoney = this.state.mode === "money";
        const presetVal = this.state.presetValue;

        if (targetPump) {
            targetPump.status = "dispensing";
            targetPump.statusText = "AUTORIZADO";
            targetPump.fuel = fuelName;
            if (presetVal > 0) {
                targetPump.amount = isMoney ? presetVal : 0;
                targetPump.liters = !isMoney ? presetVal : 0;
            }
        }

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
            this.state.selectedPumpId = pump.id;
        }
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
        
        if (this.pos.mainScreen && (this.pos.mainScreen.name === "ReceiptScreen" || this.pos.mainScreen.name === "TicketScreen")) {
            this.pos.add_new_order();
            this.pos.showScreen("ProductScreen");
        }
        this.pos.config.iface_print_auto = originalPrint;
    }
});
