/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { session } from "@web/session";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { Order } from "@point_of_sale/app/store/models";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { jsonrpc } from "@web/core/network/rpc_service";
import { useService } from "@web/core/utils/hooks";
import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConnectionLostError } from "@web/core/network/rpc_service";
import { _t } from "@web/core/l10n/translation";
import { parseFloat } from "@web/views/fields/parsers";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";

export class GasStationClosePosPopup extends ClosePosPopup {
    static template = "pos_gas_station.ClosePosPopup";
    static components = { ...ClosePosPopup.components };

    async printShiftReport() {
        const sessionId = (this.pos && this.pos.pos_session) ? this.pos.pos_session.id : (this.pos && this.pos.config ? this.pos.config.current_session_id?.[0] : null);
        const configId = this.pos && this.pos.config ? this.pos.config.id : null;
        if (!sessionId) {
            return;
        }
        const printUrl = `/pos_gas_station/shift_report_print/${sessionId}?station_id=${configId || ''}&preview=1`;
        window.open(printUrl, '_blank');
    }

    async downloadSalesReport() {
        return this.printShiftReport();
    }

    getInitialState() {
        const initialState = { notes: "", payments: {} };
        if (this.pos.config.cash_control && this.props.default_cash_details) {
            if (this.props.default_cash_details.name && this.props.default_cash_details.name.toLowerCase().includes("efectivo")) {
                this.props.default_cash_details.name = "Efectivo";
            }
            initialState.payments[this.props.default_cash_details.id] = {
                counted: this.env.utils.formatCurrency(this.props.default_cash_details.payment_amount || 0, false),
            };
        }
        (this.props.other_payment_methods || []).forEach((pm) => {
            if (pm.name) {
                const lower = pm.name.toLowerCase();
                if (lower.includes("banco")) {
                    pm.name = "Tarjeta";
                } else if (lower.includes("efectivo")) {
                    pm.name = "Efectivo";
                } else if (lower.includes("cuenta") || lower.includes("cliente") || lower.includes("customer account") || lower.includes("crédito") || lower.includes("credito")) {
                    pm.name = "Crédito";
                }
            }
            initialState.payments[pm.id] = {
                counted: this.env.utils.formatCurrency(pm.amount || 0, false),
            };
        });
        return initialState;
    }

    //@override
    async confirm() {
        if (!this.pos.config.cash_control || this.env.utils.floatIsZero(this.getMaxDifference())) {
            await this.closeSession();
            return;
        }
        if (this.hasUserAuthority()) {
            const { confirmed } = await this.popup.add(ConfirmPopup, {
                title: _t("Diferencia de Cuadre"),
                body: _t(
                    "¿Desea aceptar la diferencia de importes y cerrar el turno registrando el descuadre?"
                ),
            });
            if (confirmed) {
                await this.closeSession();
            }
            return;
        }
        await this.popup.add(ConfirmPopup, {
            title: _t("Diferencia No Autorizada"),
            body: _t(
                "La diferencia máxima autorizada es de %s.\nPor favor, contacte con el encargado para autorizar el cierre.",
                this.env.utils.formatCurrency(this.props.amount_authorized_diff)
            ),
            confirmText: _t("Aceptar"),
        });
    }

    getDifference(paymentId) {
        const rawCounted = this.state.payments[paymentId]?.counted;
        if (rawCounted === undefined || rawCounted === null || !this.env.utils.isValidFloat(rawCounted)) {
            return NaN;
        }
        const counted = parseFloat(String(rawCounted).replace(',', '.'));
        if (isNaN(counted)) {
            return NaN;
        }
        const expectedAmount =
            paymentId === this.props.default_cash_details?.id
                ? (this.props.default_cash_details.payment_amount || 0)
                : (this.props.other_payment_methods.find((pm) => pm.id === paymentId)?.amount || 0);

        return counted - expectedAmount;
    }

    //@override
    async closeSession() {
        this.customerDisplay?.update({ closeUI: true });

        // Capturar geolocalización GPS para checkout en admin-platform
        let coords = null;
        if (navigator.geolocation) {
            try {
                coords = await new Promise((resolve) => {
                    const timer = setTimeout(() => resolve(null), 1200);
                    navigator.geolocation.getCurrentPosition(
                        (pos) => {
                            clearTimeout(timer);
                            resolve({
                                latitude: pos.coords.latitude,
                                longitude: pos.coords.longitude,
                            });
                        },
                        (err) => {
                            clearTimeout(timer);
                            resolve(null);
                        },
                        { enableHighAccuracy: true, timeout: 1200, maximumAge: 60000 }
                    );
                });
            } catch (e) {
                console.debug("Error obteniendo geolocalización de cierre:", e);
            }
        }

        if (this.pos.pos_session?.id && coords) {
            try {
                await this.orm.call("pos.session", "set_checkout_coordinates", [
                    [this.pos.pos_session.id],
                    coords.latitude,
                    coords.longitude,
                ]);
            } catch (e) {
                console.warn("No se pudieron registrar las coordenadas de cierre:", e);
            }
        }

        const syncSuccess = await this.pos.push_orders_with_closing_popup();
        if (!syncSuccess) {
            return;
        }

        const sessionId = (this.pos && this.pos.pos_session) ? this.pos.pos_session.id : (this.pos && this.pos.config ? this.pos.config.current_session_id?.[0] : null);
        const configId = this.pos && this.pos.config ? this.pos.config.id : null;

        if (this.pos.config.cash_control && this.props.default_cash_details) {
            const rawCounted = this.state.payments[this.props.default_cash_details.id]?.counted;
            const shiftCounted = parseFloat(String(rawCounted || '0').replace(',', '.')) || 0.0;
            const opening = this.props.default_cash_details.opening || 0.0;
            const movesTotal = (this.props.default_cash_details.moves || []).reduce((acc, m) => acc + (m.amount || 0), 0);
            
            // Odoo espera el total contado de caja acumulado (apertura + movimientos + turno)
            const totalCountedCash = shiftCounted + opening + movesTotal;

            const response = await this.orm.call(
                "pos.session",
                "post_closing_cash_details",
                [this.pos.pos_session.id],
                {
                    counted_cash: totalCountedCash,
                }
            );

            if (!response.successful) {
                return this.handleClosingError(response);
            }
        }

        try {
            await this.orm.call("pos.session", "update_closing_control_state_session", [
                this.pos.pos_session.id,
                this.state.notes,
            ]);
        } catch (error) {
            if (!error.data && error.data?.message !== "This session is already closed.") {
                throw error;
            }
        }

        try {
            const bankPaymentMethodDiffPairs = (this.props.other_payment_methods || [])
                .filter((pm) => pm.type == "bank")
                .map((pm) => [pm.id, this.getDifference(pm.id)]);
            const response = await this.orm.call("pos.session", "close_session_from_ui", [
                this.pos.pos_session.id,
                bankPaymentMethodDiffPairs,
            ]);
            if (!response.successful) {
                return this.handleClosingError(response);
            }

            // =========================================================================
            // TURNO CERRADO CON ÉXITO: DISPARAR DIRECTAMENTE LA IMPRESIÓN DEL CIERRE
            // UNA VEZ IMPRESO (O AL PULSAR EL BOTÓN), RETORNA A LA PANTALLA INICIAL
            // =========================================================================
            const returnUrl = configId ? `/pos_gas_station/select_employee?station_id=${configId}` : '/pos_gas_station/select_employee';
            const printUrl = sessionId 
                ? `/pos_gas_station/shift_report_print/${sessionId}?station_id=${configId || ''}&return_url=${encodeURIComponent(returnUrl)}` 
                : `/pos_gas_station/shift_report_print?station_id=${configId || ''}&return_url=${encodeURIComponent(returnUrl)}`;
            
            window.location.href = printUrl;
        } catch (error) {
            if (error instanceof ConnectionLostError) {
                throw error;
            } else {
                await this.popup.add(ErrorPopup, {
                    title: _t("Error al cerrar turno"),
                    body: _t(
                        "Ocurrió un error al cerrar el turno en el servidor.\n" +
                        "Será redirigido para verificar el estado de la sesión."
                    ),
                });
                const returnUrl = configId ? `/pos_gas_station/select_employee?station_id=${configId}` : '/pos_gas_station/select_employee';
                window.location.href = returnUrl;
            }
        }
    }
}

export class UtrecarMainScreen extends Component {
    static template = "pos_gas_station.UtrecarMainScreen";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
        
        const urlParams = new URLSearchParams(window.location.search);
        this.configId = parseInt(urlParams.get("config_id")) || (this.pos.config ? this.pos.config.id : 2);
        
        // Cargar cobros pendientes por calle desde almacenamiento persistente
        if (!this.pos.pendingSales) {
            try {
                const saved = localStorage.getItem(`pos_gas_station_pending_sales_${this.configId}`);
                this.pos.pendingSales = saved ? JSON.parse(saved) : {};
            } catch (e) {
                this.pos.pendingSales = {};
            }
        }
        // Purgar posibles reembolsos espurios con 0 litros y 0 euros generados por errores de temporización previos
        if (this.pos && this.pos.pendingSales) {
            let cleanedPending = false;
            for (const pid in this.pos.pendingSales) {
                if (Array.isArray(this.pos.pendingSales[pid])) {
                    const origLen = this.pos.pendingSales[pid].length;
                    this.pos.pendingSales[pid] = this.pos.pendingSales[pid].filter(s => 
                        !(s.isPrepayRefund && (s.dispensedAmount || 0) <= 0.02 && (s.dispensedLiters || 0) <= 0.02)
                    );
                    if (this.pos.pendingSales[pid].length !== origLen) {
                        cleanedPending = true;
                    }
                }
            }
            if (cleanedPending) {
                try {
                    localStorage.setItem(`pos_gas_station_pending_sales_${this.configId}`, JSON.stringify(this.pos.pendingSales));
                } catch (e) {}
            }
        }

        // Cargar presets/prepagos activos desde almacenamiento persistente
        if (!this.pos.pumpPresets) {
            try {
                const savedPresets = localStorage.getItem(`pos_gas_station_pump_presets_${this.configId}`);
                this.pos.pumpPresets = savedPresets ? JSON.parse(savedPresets) : {};
            } catch (e) {
                this.pos.pumpPresets = {};
            }
        }

        // Cargar productos de tienda vinculados a calles activas
        if (!this.pos.pumpPendingStoreItems) {
            try {
                const savedStore = localStorage.getItem(`pos_gas_station_pending_store_${this.configId}`);
                this.pos.pumpPendingStoreItems = savedStore ? JSON.parse(savedStore) : {};
            } catch (e) {
                this.pos.pumpPendingStoreItems = {};
            }
        }

        // Cargar matriculas vinculadas a calles activas
        if (!this.pos.pumpPendingPlates) {
            try {
                const savedPlates = localStorage.getItem(`pos_gas_station_pending_plates_${this.configId}`);
                this.pos.pumpPendingPlates = savedPlates ? JSON.parse(savedPlates) : {};
            } catch (e) {
                this.pos.pumpPendingPlates = {};
            }
        }

        this.state = useState({
            isCashMoveModalOpen: false,
            cashMoveType: "ingreso_seguridad",
            cashMoveAmount: "500",
            cashMoveNotes: "",
            cashMoveSupplier: null,
            cashMoveSupplierSearch: "",
            cashMoveSupplierResults: [],
            isSearchingSuppliers: false,
            isPendingSalesModalOpen: false,
            pendingModalPump: null,
            isClosedShiftsModalOpen: false,
            closedShiftsLoading: false,
            closedShifts: [],
            closedShiftsSearch: "",
            closedShiftSortField: "start_at",
            closedShiftSortDirection: "desc",
            stationName: (this.pos.config && this.pos.config.name) ? `CONTROL DE PISTA - ${this.pos.config.name.toUpperCase()}` : "CONTROL DE PISTA",
            vehiclePlate: "",
            manualBarcode: "",
            barcodeNotFoundModal: {
                isOpen: false,
                code: ""
            },
            partnerVehicles: [],
            isAddingNewPlate: false,
            newPlateInput: "",
            isSavingPlate: false,
            selectedPumpId: null,
            selectedLineId: null,
            orderVersion: 0,
            trackMode: localStorage.getItem("utrecar_track_mode") || "prepago", // 'atendido' o 'prepago'
            mode: "money", // 'money' o 'liters'
            presetValue: 0,
            selectedFuel: null,
            availableFuels: [
                { code: "GA", name: "Gasóleo A", class: "ga" },
                { code: "95", name: "Sin Plomo 95", class: "sp95" }
            ],
            isGridConfigModalOpen: false,
            gridConfigSearch: "",
            customGridProducts: this.loadSavedCustomGrid(),
            draggedGridIndex: null,
            dragOverGridIndex: null,
            isStoreModalOpen: false,
            isClientModalOpen: false,
            isEditPartnerModalOpen: false,
            isSavingPartner: false,
            editPartnerError: null,
            editingPartner: {
                id: null,
                name: "",
                vat: "",
                ref: "",
                customer_type: "ordinary",
                customer_payment_mode: "cash",
                phone: "",
                mobile: "",
                email: "",
                street: "",
                zip: "",
                city: "",
                state_id: false,
                new_plate: "",
                vehicles: [],
            },
            isAuthModalOpen: false,
            authModalPump: null,
            isCancelModalOpen: false,
            cancelModalPump: null,
            pumpPresets: Object.assign({}, (this.pos && this.pos.pumpPresets) || {}),
            isPageDropdownOpen: false,
            currentStorePage: 1,
            selectedModalCategory: null,
            clientSearch: "",
            clientCodeSearch: "",
            clientSortDirection: "asc",
            clientSortField: "name",
            storeSearch: "",
            storeTarget: null,
                        isShiftOrdersModalOpen: false,
            shiftOrdersLoading: false,
            isStationsModalOpen: false,
            loadingStations: false,
            availableStations: [],
            isAdminUser: false,
            shiftViewSessionId: null,
            shiftSessionInfo: { currentId: null, currentName: '', prevId: null, prevName: '', activeState: 'current' },
            shiftOrders: [],
            shiftSummary: { total_sales: 0, total_cash: 0, total_bank: 0, orders_count: 0 },
            selectedShiftOrder: null,
            shiftActiveTab: 'products',
            shiftOrderSearch: "",
            shiftOrderSortField: "date",
            shiftOrderSortDirection: "desc",
            expandedShiftOrderIds: {},
            isInvoiceModalOpen: false,
            invoicePartnerSearch: "",
            invoicePartnerCodeSearch: "",
            invoiceEmail: "",
            invoicePartnerResults: [],
            invoiceSelectedPartner: null,
            invoiceNewPartner: { name: "", vat: "", street: "", city: "", zip: "", email: "", phone: "" },
            isCreatingPartner: false,
            invoiceLoading: false,
            isConvertAlbaranModalOpen: false,
            isAnnulOrderModalOpen: false,
            annulModalOrder: null,
            annulModalReason: "Anulación a petición del cliente",
            isAnnulingOrder: false,
            convertAlbaranOrder: null,
            convertAlbaranSelectedPartner: null,
            convertAlbaranPartnerSearch: "",
            convertAlbaranPartnerResults: [],
            isCreatingCreditPartner: false,
            albaranNewPartner: { name: "", vat: "", street: "", city: "", zip: "", email: "", phone: "", customer_type: "monthly" },
            convertAlbaranPlate: "",
            convertAlbaranDriver: "",
            convertAlbaranLoading: false,
            isEmailInvoiceModalOpen: false,
            emailInvoiceOrder: null,
            emailInvoiceTarget: "",
            isSendingInvoiceEmail: false,
            emailInvoiceSuccessMessage: "",
            emailInvoiceErrorMessage: "",
            isExtractionModalOpen: false,
            extractionTargetOrder: null,
            extractionReason: "Prueba de probeta / Calibración metrológica",
            extractionNotes: "",
            isSavingExtraction: false,
            pumps: [],
            isConfigDropdownOpen: false,
            isPrinterConfigModalOpen: false,
            printerActiveTab: 'assignments',
            printerConfig: null,
            printerNewName: "",
            printerNewType: "thermal",
            printerSaveSuccessMessage: "",
        });

        this.state.printerConfig = this.getPrinterConfig();

        this.barcodeBuffer = "";
        this.barcodeTimeout = null;

        this.onGlobalKeyDown = (ev) => {
            if (ev.key === 'Escape') {
                if (this.state.isPrinterConfigModalOpen) {
                    this.closePrinterConfigModal();
                    ev.preventDefault();
                    return;
                }
                if (this.state.isConfigDropdownOpen) {
                    this.state.isConfigDropdownOpen = false;
                    ev.preventDefault();
                    return;
                }
                if (this.state.isExtractionModalOpen) {
                    this.closeExtractionModal();
                    ev.preventDefault();
                    return;
                }
                if (this.state.isAnnulOrderModalOpen) {
                    this.closeAnnulOrderModal();
                    ev.preventDefault();
                    return;
                }
                if (this.state.isGridConfigModalOpen) {
                    this.closeGridConfigModal();
                    ev.preventDefault();
                    return;
                }
                if (this.state.isShiftOrdersModalOpen) {
                    if (this.state.selectedShiftOrder) {
                        this.backToShiftOrdersList();
                    } else {
                        this.closeShiftOrdersModal();
                    }
                    ev.preventDefault();
                    return;
                }
                if (this.state.isStoreModalOpen) {
                    this.closeStoreModal();
                    ev.preventDefault();
                    return;
                }
                if (this.state.isClientModalOpen) {
                    this.closeClientModal();
                    ev.preventDefault();
                    return;
                }
            }
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

        this.onGlobalClick = (ev) => {
            if (this.state.isPageDropdownOpen) {
                const dropdownEl = document.querySelector(".btn-dropdown-wrapper");
                if (dropdownEl && !dropdownEl.contains(ev.target)) {
                    this.state.isPageDropdownOpen = false;
                }
            }
            if (this.state.isConfigDropdownOpen) {
                const configDropdownEl = document.querySelector(".pos-config-dropdown-wrapper");
                if (configDropdownEl && !configDropdownEl.contains(ev.target)) {
                    this.state.isConfigDropdownOpen = false;
                }
            }
        };

        this.lastTrackedOrderId = null;

        onMounted(() => {
            this.loadPendingSalesFromServer();
            this.fetchPumpsStatus();
            this.pollInterval = setInterval(() => {
                this.fetchPumpsStatus();
                const ord = this.pos.get_order();
                if (ord) {
                    if (this.lastTrackedOrderId !== ord.uid) {
                        this.lastTrackedOrderId = ord.uid;
                        const lines = ord.get_orderlines ? (ord.get_orderlines() || []) : [];
                        const hasFuelLine = lines.some(l => {
                            if (!l.product) return false;
                            const c = (l.product.default_code || "").toUpperCase();
                            const n = (l.product.display_name || l.product.name || "").toLowerCase();
                            return c.includes("GAS_A") || c.includes("SP95") || c.includes("GAS_PLUS") || c.includes("GAS_B") ||
                                   n.includes("gasóleo") || n.includes("gasoleo") || n.includes("sin plomo") || n.includes("diesel");
                        });
                        if (!hasFuelLine) {
                            this.state.selectedFuel = null;
                            this.state.presetValue = 0;
                        }

                        // Sincronizar cliente y matrículas de la orden activa
                        const p = ord.get_partner ? ord.get_partner() : null;
                        this.state.vehiclePlate = ord.vehicle_plate || "";
                        this.state.isAddingNewPlate = false;
                        if (p && p.id) {
                            this.loadPartnerVehicles(p.id);
                        } else {
                            this.state.partnerVehicles = [];
                        }
                    }
                    const linesCount = (ord.get_orderlines ? (ord.get_orderlines() ? ord.get_orderlines().length : 0) : 0) || (ord.orderlines ? ord.orderlines.length : 0) || 0;
                    const totalAmt = (ord.get_total_with_tax ? ord.get_total_with_tax() : 0) || 0;
                    const v = linesCount * 1000 + totalAmt;
                    if (this.state.orderVersion !== v) {
                        this.state.orderVersion = v;
                    }
                }
            }, 500);
            window.addEventListener("keydown", this.onGlobalKeyDown);
            window.addEventListener("click", this.onGlobalClick);
        });

        onWillUnmount(() => {
            if (this.pollInterval) {
                clearInterval(this.pollInterval);
            }
            window.removeEventListener("keydown", this.onGlobalKeyDown);
            window.removeEventListener("click", this.onGlobalClick);
        });
    }

    findProductByCode(code) {
        const clean = (code || "").trim();
        if (!clean || !this.pos || !this.pos.db) return null;
        if (typeof this.pos.db.get_product_by_barcode === "function") {
            const byBarcode = this.pos.db.get_product_by_barcode(clean);
            if (byBarcode) return byBarcode;
        }
        const lower = clean.toLowerCase();
        const all = Object.values(this.pos.db.product_by_id || {});
        return (
            all.find(p => (p.barcode || "").trim() === clean) ||
            all.find(p => Array.isArray(p.extra_barcodes) && p.extra_barcodes.some(b => (b || "").trim() === clean)) ||
            all.find(p => (p.default_code || "").trim().toLowerCase() === lower) ||
            (clean.length >= 6 ? all.find(p => p.barcode && p.barcode.trim().endsWith(clean)) : null) ||
            null
        );
    }

    handleBarcodeScan(code) {
        const clean = (code || "").trim();
        if (!clean) return;
        const prod = this.findProductByCode(clean);
        if (prod) {
            this.addStoreProductToOrder(prod, true);
        } else {
            this.openBarcodeNotFoundModal(clean);
        }
    }

    onManualBarcodeInput(ev) {
        this.state.manualBarcode = ev.target.value;
    }

    async onManualBarcodeKeyDown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            ev.stopPropagation();
            await this.submitManualBarcode(ev.target.value);
        } else if (ev.key === "Escape") {
            this.state.manualBarcode = "";
            ev.target.value = "";
            ev.target.blur();
        }
    }

    async submitManualBarcode(rawCode) {
        const clean = (rawCode !== undefined ? rawCode : this.state.manualBarcode || "").trim();
        if (!clean) return;
        const prod = this.findProductByCode(clean);
        const inputEl = document.querySelector(".virtus-barcode-input");
        if (prod) {
            await this.addStoreProductToOrder(prod, true);
            this.state.manualBarcode = "";
            if (inputEl) inputEl.value = "";
            if (this.env.services.notification) {
                this.env.services.notification.add(
                    `Añadido: ${prod.display_name || prod.name}`,
                    { type: "success", sticky: false, duration: 2000 }
                );
            }
        } else {
            this.openBarcodeNotFoundModal(clean);
        }
    }

    openBarcodeNotFoundModal(code) {
        this.state.barcodeNotFoundModal = {
            isOpen: true,
            code: (code || "").trim()
        };
    }

    closeBarcodeNotFoundModal() {
        this.state.barcodeNotFoundModal = {
            isOpen: false,
            code: ""
        };
        setTimeout(() => {
            const inputEl = document.querySelector(".virtus-barcode-input");
            if (inputEl) {
                inputEl.focus();
                inputEl.select();
            }
        }, 60);
    }

    get posCategories() {
        if (!this.pos || !this.pos.db || !this.pos.db.category_by_id) return [];
        return Object.values(this.pos.db.category_by_id).filter(c => c.id && c.name);
    }

    selectModalCategory(catId) {
        this.state.selectedModalCategory = catId;
    }

    togglePageDropdown() {
        this.state.isPageDropdownOpen = !this.state.isPageDropdownOpen;
    }

    setStorePage(pageNum) {
        this.state.currentStorePage = pageNum;
        this.state.isPageDropdownOpen = false;
        this.state.isStoreModalOpen = false;
    }

    onCartButtonClick() {
        if (this.state.isStoreModalOpen) {
            this.state.isStoreModalOpen = false;
            return;
        }
        // Advance to next page
        const nextPage = (this.state.currentStorePage % 4) + 1;
        this.state.currentStorePage = nextPage;
        this.state.isPageDropdownOpen = false;
    }

    openStoreModalFromDropdown() {
        this.state.isPageDropdownOpen = false;
        this.openStoreModal();
    }

    getDefaultStoreProducts() {
        return [
            { id: "v_hielo", display_name: "HIELO EN BOLSA", lst_price: 1.90, bg_image: "/pos_gas_station/static/src/img/products/prod_341005.png", is_full_art: true, default_code: "341005" },
            { id: "v_chupa", display_name: "CHUPA CHUPS", lst_price: 0.40, bg_image: "/pos_gas_station/static/src/img/products/prod_312006.png", is_full_art: true, default_code: "312006" },
            { id: "v_kinder", display_name: "KINDER BUENO", lst_price: 1.50, bg_image: "/pos_gas_station/static/src/img/products/prod_311001.png", is_full_art: true, default_code: "311001" },
            { id: "v_mechero", display_name: "MECHERO CLIPPER", lst_price: 1.00, bg_image: "/pos_gas_station/static/src/img/products/prod_323003.png", is_full_art: true, default_code: "323003" },

            { id: "v_butano", display_name: "BOMBONA BUTANO", lst_price: 23.00, bg_image: "/pos_gas_station/static/src/img/products/prod_360014.png", is_full_art: true, default_code: "360014" },
            { id: "v_dulces", display_name: "DULCES DULCESOL", lst_price: 1.00, bg_image: "/pos_gas_station/static/src/img/products/prod_315006.png", is_full_art: true, default_code: "315006" },
            { id: "v_coca", display_name: "LATA COCA-COLA", lst_price: 1.50, bg_image: "/pos_gas_station/static/src/img/products/prod_342001.png", is_full_art: true, default_code: "342001" },
            { id: "v_cocazero", display_name: "COCA-COLA ZERO", lst_price: 1.50, bg_image: "/pos_gas_station/static/src/img/products/prod_342003.png", is_full_art: true, default_code: "342003" },

            { id: "v_aceite2t", display_name: "ACEITE 2T NIPOMIX", lst_price: 1.40, bg_image: "/pos_gas_station/static/src/img/products/prod_331002.png", is_full_art: true, default_code: "331002" },
            { id: "v_castrol", display_name: "ACEITE 2T CASTROL", lst_price: 2.00, bg_image: "/pos_gas_station/static/src/img/products/prod_331001.png", is_full_art: true, default_code: "331001" },
            { id: "v_vaper", display_name: "VAPER SABORES", lst_price: 6.50, bg_image: "/pos_gas_station/static/src/img/products/prod_323006.png", is_full_art: true, default_code: "323006" },
            { id: "v_papel", display_name: "PAPEL DE LIAR", lst_price: 1.00, bg_image: "/pos_gas_station/static/src/img/products/prod_323001.png", is_full_art: true, default_code: "323001" },

            { id: "v_cafe", display_name: "CAFE", lst_price: 1.00, bg_image: "/pos_gas_station/static/src/img/products/prod_382001.png", is_full_art: true, default_code: "382001" },
            { id: "v_zumo", display_name: "ZUMO DE BOTE", lst_price: 1.30, bg_image: "/pos_gas_station/static/src/img/products/prod_382006.png", is_full_art: true, default_code: "382006" },
            { id: "v_bifrutas", display_name: "BI FRUTAS", lst_price: 1.20, bg_image: "/pos_gas_station/static/src/img/products/prod_382008.png", is_full_art: true, default_code: "382008" },
            { id: "v_cubata", display_name: "CUBATAS", lst_price: 4.00, bg_image: "/pos_gas_station/static/src/img/products/prod_383003.png", is_full_art: true, default_code: "383003" },

            { id: "v_boc", display_name: "BOC", text_only: true, full_name: "TOSTADA / BOCADILLO", lst_price: 1.70, default_code: "381001" },
            { id: "v_cocatxt", display_name: "COCA COLA LATA", text_only: true, full_name: "LATA COCA-COLA", lst_price: 1.50, default_code: "342001" },
            { id: "v_pan", display_name: "PAN DE TORRIJA", text_only: true, full_name: "PAN PARA LLEVAR", lst_price: 0.60, default_code: "381003" },
            { id: "v_tostada", display_name: "MEDIA TOSTADA", text_only: true, full_name: "MEDIA TOSTADA", lst_price: 1.30, default_code: "381002" }
        ];
    }

    normalizeProductItem(item) {
        if (!item) return item;
        try {
            const numericId = typeof item.id === 'number' ? item.id : parseInt(item.id, 10);
            if (!isNaN(numericId) && numericId > 0 && this.pos?.db) {
                const dbProd = this.pos.db.get_product_by_id(numericId);
                if (dbProd) {
                    const hasRealImage = Boolean(dbProd.image_128);
                    const imageUrl = hasRealImage && typeof dbProd.getImageUrl === 'function' 
                        ? dbProd.getImageUrl() 
                        : (hasRealImage ? `/web/image?model=product.product&field=image_128&id=${dbProd.id}` : null);
                    return {
                        id: dbProd.id,
                        display_name: dbProd.display_name || item.display_name || "Producto",
                        lst_price: dbProd.lst_price || item.lst_price || 0,
                        default_code: dbProd.default_code || item.default_code || "",
                        barcode: dbProd.barcode || item.barcode || "",
                        bg_image: imageUrl,
                        is_full_art: false,
                        text_only: !hasRealImage,
                    };
                }
            }
            if (typeof item.id === 'string') {
                const defaultItems = this.getDefaultStoreProducts();
                const matched = defaultItems.find(d => d.id === item.id);
                if (matched) {
                    return {
                        ...matched,
                        ...item,
                        lst_price: (item.lst_price !== undefined && item.lst_price !== null) ? item.lst_price : matched.lst_price,
                        is_full_art: matched.is_full_art !== undefined ? matched.is_full_art : (item.bg_image ? !item.text_only : false),
                        text_only: Boolean(matched.text_only),
                    };
                }
                if (item.bg_image && item.bg_image.includes('/pos_gas_station/')) {
                    return {
                        ...item,
                        is_full_art: true,
                        text_only: false,
                    };
                }
            }
            return {
                ...item,
                is_full_art: Boolean(item.is_full_art),
                text_only: !item.bg_image || Boolean(item.text_only),
            };
        } catch (e) {
            console.error("Error in normalizeProductItem", e);
            return item;
        }
    }

    loadSavedCustomGrid() {
        try {
            const key = "pos_custom_store_grid_" + (this.pos?.config?.id || "default");
            const raw = localStorage.getItem(key) || localStorage.getItem("pos_custom_store_grid");
            if (raw) {
                const parsed = JSON.parse(raw);
                if (Array.isArray(parsed) && parsed.length > 0) {
                    return parsed.map(item => this.normalizeProductItem(item));
                }
            }
        } catch(e) {
            console.error("Error cargando cuadrícula personalizada:", e);
        }
        return null;
    }

    openGridConfigModal() {
        if (!this.state.customGridProducts || this.state.customGridProducts.length === 0) {
            this.state.customGridProducts = [...this.getDefaultStoreProducts()];
        } else {
            this.state.customGridProducts = this.state.customGridProducts.map(item => this.normalizeProductItem(item));
        }
        this.state.currentStorePage = 1;
        this.state.gridConfigSearch = "";
        this.state.draggedGridIndex = null;
        this.state.dragOverGridIndex = null;
        this.state.isGridConfigModalOpen = true;
    }

    closeGridConfigModal() {
        this.state.isGridConfigModalOpen = false;
    }

    saveCustomGrid() {
        try {
            const key = "pos_custom_store_grid_" + (this.pos?.config?.id || "default");
            localStorage.setItem(key, JSON.stringify(this.state.customGridProducts));
            localStorage.setItem("pos_custom_store_grid", JSON.stringify(this.state.customGridProducts));
        } catch(e) {
            console.error("Error guardando cuadrícula personalizada:", e);
        }
    }

    // =========================================================================
    // CONFIGURACIÓN DEL TPV E IMPRESORAS PREESTABLECIDAS POR DOCUMENTO
    // =========================================================================

    toggleConfigDropdown(ev) {
        if (ev) {
            ev.stopPropagation();
        }
        this.state.isConfigDropdownOpen = !this.state.isConfigDropdownOpen;
    }

    closeConfigDropdown() {
        this.state.isConfigDropdownOpen = false;
    }

    openPrinterConfigModal() {
        this.state.isConfigDropdownOpen = false;
        this.state.printerConfig = this.getPrinterConfig();
        this.state.printerActiveTab = 'assignments';
        this.state.printerSaveSuccessMessage = "";
        this.state.isPrinterConfigModalOpen = true;
    }

    closePrinterConfigModal() {
        this.state.isPrinterConfigModalOpen = false;
    }

    getPrinterConfig() {
        const storageKey = `pos_gas_station_printer_config_${this.configId}`;
        const defaultPrinters = [
            { id: "epson_tm_t20", name: "EPSON TM-T20III (Térmica Tickets 80mm)", type: "thermal" },
            { id: "epson_wf_m5299", name: "EPSON WF-M5299 (A4 / Documentos)", type: "laser_ink" },
            { id: "windows_default", name: "Impresora Predeterminada del Sistema", type: "system", is_default: true },
            { id: "pdf_print", name: "Microsoft Print to PDF", type: "pdf" },
        ];
        const defaultAssignments = {
            ticket: { printerId: "epson_tm_t20", format: "thermal_80", copies: 1 },
            albaran: { printerId: "epson_wf_m5299", format: "a4", copies: 2 },
            invoice: { printerId: "epson_wf_m5299", format: "a4", copies: 1 },
            shift_report: { printerId: "epson_tm_t20", format: "thermal_80", copies: 1 },
            extraction: { printerId: "epson_tm_t20", format: "thermal_80", copies: 1 },
            annulment: { printerId: "epson_tm_t20", format: "thermal_80", copies: 1 },
        };
        try {
            const raw = localStorage.getItem(storageKey);
            if (raw) {
                const parsed = JSON.parse(raw);
                return {
                    systemPrinters: (parsed.systemPrinters && parsed.systemPrinters.length > 0)
                        ? parsed.systemPrinters
                        : defaultPrinters,
                    assignments: Object.assign({}, defaultAssignments, parsed.assignments || {}),
                    directPrint: parsed.directPrint !== undefined ? parsed.directPrint : true,
                };
            }
        } catch (e) {
            console.warn("Error cargando configuración de impresoras de localStorage:", e);
        }
        return {
            systemPrinters: defaultPrinters,
            assignments: defaultAssignments,
            directPrint: true,
        };
    }

    savePrinterConfig() {
        try {
            const storageKey = `pos_gas_station_printer_config_${this.configId}`;
            localStorage.setItem(storageKey, JSON.stringify(this.state.printerConfig));
            this.state.printerSaveSuccessMessage = "Configuración de impresoras guardada y aplicada con éxito.";
            setTimeout(() => {
                if (this.state) {
                    this.state.printerSaveSuccessMessage = "";
                }
            }, 3000);
        } catch (e) {
            console.error("Error guardando configuración de impresoras:", e);
            alert("Error al guardar la configuración de impresoras: " + e.message);
        }
    }

    toggleDirectPrint(val) {
        if (!this.state.printerConfig) {
            this.state.printerConfig = this.getPrinterConfig();
        }
        this.state.printerConfig.directPrint = Boolean(val);
        this.savePrinterConfig();
    }

    resetPrinterConfigToDefaults() {
        if (!confirm("¿Desea restablecer las asignaciones de impresoras a los valores predeterminados?")) {
            return;
        }
        const storageKey = `pos_gas_station_printer_config_${this.configId}`;
        try {
            localStorage.removeItem(storageKey);
        } catch (e) {}
        this.state.printerConfig = this.getPrinterConfig();
        this.state.printerSaveSuccessMessage = "Valores predeterminados restablecidos.";
        setTimeout(() => {
            if (this.state) {
                this.state.printerSaveSuccessMessage = "";
            }
        }, 3000);
    }

    onPrinterAssignmentChange(docType, field, value) {
        if (!this.state.printerConfig) {
            this.state.printerConfig = this.getPrinterConfig();
        }
        if (!this.state.printerConfig.assignments) {
            this.state.printerConfig.assignments = {};
        }
        if (!this.state.printerConfig.assignments[docType]) {
            this.state.printerConfig.assignments[docType] = {};
        }
        this.state.printerConfig.assignments[docType][field] = value;
        this.savePrinterConfig();
    }

    addNewSystemPrinter() {
        const name = (this.state.printerNewName || "").trim();
        if (!name) {
            alert("Por favor indique el nombre de la impresora tal como está instalada en el sistema.");
            return;
        }
        if (!this.state.printerConfig.systemPrinters) {
            this.state.printerConfig.systemPrinters = [];
        }
        const exists = this.state.printerConfig.systemPrinters.some(p => p.name.toLowerCase() === name.toLowerCase());
        if (exists) {
            alert("Ya existe una impresora registrada con ese nombre.");
            return;
        }
        const id = 'custom_' + Date.now();
        this.state.printerConfig.systemPrinters.push({
            id: id,
            name: name,
            type: this.state.printerNewType || "thermal",
            is_custom: true,
        });
        this.state.printerNewName = "";
        this.savePrinterConfig();
    }

    removeSystemPrinter(printerId) {
        if (!confirm("¿Desea eliminar esta impresora de la lista de impresoras disponibles?")) {
            return;
        }
        this.state.printerConfig.systemPrinters = this.state.printerConfig.systemPrinters.filter(p => p.id !== printerId);
        for (const docKey of Object.keys(this.state.printerConfig.assignments || {})) {
            if (this.state.printerConfig.assignments[docKey].printerId === printerId) {
                this.state.printerConfig.assignments[docKey].printerId = "windows_default";
            }
        }
        this.savePrinterConfig();
    }

    async detectSystemPrinters() {
        try {
            if (window.queryLocalPrinters) {
                const detected = await window.queryLocalPrinters();
                if (detected && detected.length > 0) {
                    let addedCount = 0;
                    for (const pr of detected) {
                        const prName = pr.name;
                        if (!this.state.printerConfig.systemPrinters.some(p => p.name.toLowerCase() === prName.toLowerCase())) {
                            this.state.printerConfig.systemPrinters.push({
                                id: 'sys_' + Math.random().toString(36).substr(2, 9),
                                name: prName,
                                type: prName.toLowerCase().includes('tm-') || prName.toLowerCase().includes('thermal') || prName.toLowerCase().includes('ticket') ? 'thermal' : 'laser_ink',
                                is_detected: true,
                            });
                            addedCount++;
                        }
                    }
                    this.savePrinterConfig();
                    alert(`Se han detectado y añadido ${addedCount} impresoras del sistema.`);
                    return;
                }
            } else if (navigator.printers && navigator.printers.query) {
                const query = await navigator.printers.query();
                if (query && query.length > 0) {
                    let addedCount = 0;
                    for (const pr of query) {
                        const prName = pr.name || pr.printerId;
                        if (!this.state.printerConfig.systemPrinters.some(p => p.name.toLowerCase() === prName.toLowerCase())) {
                            this.state.printerConfig.systemPrinters.push({
                                id: 'sys_' + Math.random().toString(36).substr(2, 9),
                                name: prName,
                                type: prName.toLowerCase().includes('tm-') ? 'thermal' : 'laser_ink',
                                is_detected: true,
                            });
                            addedCount++;
                        }
                    }
                    this.savePrinterConfig();
                    alert(`Se han detectado y añadido ${addedCount} impresoras del sistema.`);
                    return;
                }
            }
            alert("Para añadir impresoras instaladas en este equipo Windows (ej: EPSON TM-T20III, EPSON WF-M5299, etc.), puede escribir su nombre directamente en el apartado 'Añadir Impresora del Sistema' que tiene debajo.");
        } catch (e) {
            console.debug("Detección de impresoras:", e);
            alert("Puede añadir las impresoras instaladas en Windows escribiendo su nombre en 'Añadir Impresora del Sistema'.");
        }
    }

    getAssignedPrinter(docType = 'ticket') {
        const cfg = (this.state && this.state.printerConfig) ? this.state.printerConfig : this.getPrinterConfig();
        const assignments = cfg.assignments || {};
        const assign = assignments[docType] || {
            printerId: "windows_default",
            format: (docType === 'invoice' || docType === 'albaran') ? 'a4' : 'thermal_80',
            copies: docType === 'albaran' ? 2 : 1,
        };
        const printer = (cfg.systemPrinters || []).find(p => p.id === assign.printerId || p.name === assign.printerId) || {
            id: "windows_default",
            name: "Impresora Predeterminada del Sistema",
            type: assign.format === 'a4' ? 'laser_ink' : 'thermal',
        };
        return {
            id: printer.id,
            name: printer.name,
            type: printer.type,
            format: assign.format || (printer.type === 'laser_ink' ? 'a4' : 'thermal_80'),
            copies: assign.copies || 1,
            autoPrint: cfg.directPrint !== false,
        };
    }

    testPrintDocument(docType) {
        const assigned = this.getAssignedPrinter(docType);
        const testOrder = {
            name: docType === 'albaran' ? 'ALB-PRUEBA-001' : (docType === 'invoice' ? 'FTTR-PRUEBA-001' : 'TTTR-PRUEBA-001'),
            is_albaran: docType === 'albaran',
            is_invoiced: docType === 'invoice',
            date_order: new Date().toLocaleString('es-ES'),
            partner_name: "CLIENTE DE PRUEBA S.L.",
            partner_vat: "B12345678",
            partner_street: "Polígono Industrial C/ Principal 12",
            partner_city: "Sevilla",
            vehicle_plate: "1234 BBB",
            vehicle_driver: "Juan Pérez García",
            amount_total: 45.50,
            company: {
                name: (this.pos && this.pos.company && this.pos.company.name) || "ESTACIÓN DE SERVICIO UTRECAR",
                vat: (this.pos && this.pos.company && this.pos.company.vat) || "B-91234567",
                street: (this.pos && this.pos.config && this.pos.config.street) || "Ctra. Nacional IV",
                city: (this.pos && this.pos.config && this.pos.config.city) || "Utrera (Sevilla)",
                phone: (this.pos && this.pos.config && this.pos.config.phone) || "954 860 000",
            },
            lines: [
                { product_name: "Gasóleo A (Diésel)", qty: 25.00, price_unit: 1.420, price_subtotal_incl: 35.50 },
                { product_name: "Lavaparabrisas 5L", qty: 1.00, price_unit: 10.000, price_subtotal_incl: 10.00 },
            ],
            payments: [
                { name: docType === 'albaran' ? "Cuenta de Crédito" : "Tarjeta Bancaria", amount: 45.50 }
            ]
        };

        if (docType === 'shift_report') {
            this.printTestShiftReport(assigned);
        } else {
            this.printShiftOrderTicket(testOrder, false, null);
        }
    }

    printTestShiftReport(assigned) {
        const isDirect = (this.state.printerConfig && this.state.printerConfig.directPrint !== undefined)
            ? Boolean(this.state.printerConfig.directPrint)
            : true;
        const receiptWindow = window.open("", "_blank", "width=420,height=680");
        if (!receiptWindow) {
            alert("Por favor permita las ventanas emergentes en su navegador para imprimir.");
            return;
        }

        const topToolbar = isDirect ? '' : `
            <div class="no-print" style="background: #1e293b; color: white; padding: 8px 12px; margin: -16px -16px 14px -16px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: -16px; z-index: 100;">
                <span style="font-weight: bold; font-size: 12px;">👁️ Vista Previa: Informe Z | 🖨️ ${assigned.name}</span>
                <div>
                    <button onclick="window.print()" style="background: #16a34a; color: white; border: none; padding: 4px 10px; border-radius: 4px; font-weight: bold; cursor: pointer; margin-right: 6px;">🖨️ Imprimir</button>
                    <button onclick="window.close()" style="background: #475569; color: white; border: none; padding: 4px 10px; border-radius: 4px; font-weight: bold; cursor: pointer;">✖ Cerrar</button>
                </div>
            </div>
        `;

        const printScript = isDirect ? `
            <script>
                window.onload = function() {
                    window.print();
                };
            </script>
        ` : '';

        receiptWindow.document.write(`
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>[${assigned.name}] Prueba Cierre de Turno</title>
                <style>
                    body { font-family: 'Courier New', monospace; font-size: 12px; margin: 0; padding: 16px; color: #000; }
                    .header { text-align: center; margin-bottom: 10px; }
                    .header h2 { margin: 0 0 4px 0; font-size: 15px; font-weight: bold; }
                    .divider { border-bottom: 1px dashed #000; margin: 8px 0; }
                    .row { display: flex; justify-content: space-between; margin-bottom: 3px; }
                    .grand-total { font-size: 14px; font-weight: bold; border-top: 1px solid #000; border-bottom: 1px solid #000; padding: 4px 0; margin: 6px 0; }
                    @media print {
                        .no-print { display: none !important; }
                        body { padding: 0; }
                    }
                </style>
            </head>
            <body>
                ${topToolbar}
                <div class="header">
                    <h2>*** PRUEBA CIERRE DE TURNO ***</h2>
                    <div>ESTACIÓN DE SERVICIO UTRECAR</div>
                    <div>Fecha: ${new Date().toLocaleString('es-ES')}</div>
                    <div>Impresora Asignada: <strong>${assigned.name}</strong></div>
                </div>
                <div class="divider"></div>
                <div class="row"><span>Total Ventas Efectivo:</span><strong>150.00 €</strong></div>
                <div class="row"><span>Total Ventas Tarjeta:</span><strong>230.50 €</strong></div>
                <div class="row"><span>Total Crédito:</span><strong>85.00 €</strong></div>
                <div class="grand-total row"><span>TOTAL TURNO:</span><span>465.50 €</span></div>
                <div class="divider"></div>
                <div style="text-align: center; font-size: 11px; margin-top: 10px;">Comprobante de prueba emitido correctamente.</div>
                ${printScript}
            </body>
            </html>
        `);
        receiptWindow.document.close();
    }

    addProductToGrid(prod) {
        if (!prod) return;
        if (!this.state.customGridProducts) {
            this.state.customGridProducts = [...this.getDefaultStoreProducts()];
        }
        const hasRealImage = Boolean(prod.image_128);
        const imageUrl = hasRealImage && typeof prod.getImageUrl === "function" 
            ? prod.getImageUrl() 
            : (hasRealImage ? `/web/image?model=product.product&field=image_128&id=${prod.id}` : null);
        
        const item = {
            id: prod.id,
            display_name: prod.display_name || prod.name || "Producto",
            lst_price: prod.lst_price || prod.list_price || 0,
            default_code: prod.default_code || "",
            barcode: prod.barcode || "",
            bg_image: imageUrl,
            is_full_art: false,
            text_only: !hasRealImage,
        };
        this.state.customGridProducts.push(item);
        this.saveCustomGrid();
    }

    removeProductFromGrid(index) {
        if (!this.state.customGridProducts || index < 0 || index >= this.state.customGridProducts.length) return;
        this.state.customGridProducts.splice(index, 1);
        this.saveCustomGrid();
    }

    moveGridItem(index, direction) {
        if (!this.state.customGridProducts) return;
        const target = index + direction;
        if (target < 0 || target >= this.state.customGridProducts.length) return;
        const temp = this.state.customGridProducts[index];
        this.state.customGridProducts[index] = this.state.customGridProducts[target];
        this.state.customGridProducts[target] = temp;
        this.saveCustomGrid();
    }

    onGridDragStart(ev, index) {
        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("text/plain", index);
        this.state.draggedGridIndex = index;
    }

    onGridDragOver(ev, index) {
        ev.preventDefault();
        ev.dataTransfer.dropEffect = "move";
        this.state.dragOverGridIndex = index;
    }

    onGridDrop(ev, targetIndex) {
        ev.preventDefault();
        const fromIndex = this.state.draggedGridIndex;
        this.state.draggedGridIndex = null;
        this.state.dragOverGridIndex = null;
        if (fromIndex === null || fromIndex === undefined || fromIndex === targetIndex) return;
        const items = [...this.state.customGridProducts];
        const [movedItem] = items.splice(fromIndex, 1);
        items.splice(targetIndex, 0, movedItem);
        this.state.customGridProducts = items;
        this.saveCustomGrid();
    }

    resetGridToDefault() {
        if (confirm("¿Deseas restablecer la cuadrícula a los 20 productos favoritos por defecto?")) {
            this.state.customGridProducts = [...this.getDefaultStoreProducts()];
            this.saveCustomGrid();
        }
    }

    clearAllGridProducts() {
        if (confirm("¿Estás seguro de que deseas vaciar todos los productos de la cuadrícula?")) {
            this.state.customGridProducts = [];
            this.saveCustomGrid();
        }
    }

    onGridConfigSearchInput(ev) {
        this.state.gridConfigSearch = ev.target.value || "";
    }

    clearGridConfigSearch() {
        this.state.gridConfigSearch = "";
    }

    get availableInventoryProducts() {
        if (!this.pos.db || !this.pos.db.product_by_id) return [];
        const all = Object.values(this.pos.db.product_by_id);
        const search = (this.state.gridConfigSearch || "").trim().toLowerCase();
        
        const nonFuels = all.filter(p => {
            const name = (p.display_name || p.name || "").toLowerCase();
            return !name.includes("gasóleo") && !name.includes("gasoleo") && !name.includes("diesel") && 
                   !name.includes("gasolina") && !name.includes("plomo") && !name.includes("combustible");
        });

        if (!search) {
            return nonFuels.slice(0, 60);
        }

        return nonFuels.filter(p => {
            const name = (p.display_name || p.name || "").toLowerCase();
            const code = (p.default_code || "").toLowerCase();
            const barcode = (p.barcode || "").toLowerCase();
            return name.includes(search) || code.includes(search) || barcode.includes(search);
        }).slice(0, 60);
    }

    get popularStoreProducts() {
        if (this.state.currentStorePage === 1 && this.state.customGridProducts && this.state.customGridProducts.length > 0) {
            return this.state.customGridProducts.map(item => this.normalizeProductItem(item));
        }
        const page = this.state.currentStorePage || 1;

        // PÁGINA 1: ARTÍCULOS PRINCIPALES Y FAVORITOS (VIRTUSTPV)
        const page1Items = this.getDefaultStoreProducts().map(item => this.normalizeProductItem(item));

        // PÁGINA 2: BEBIDAS, CAFETERÍA Y REFRESCOS
        const page2Items = [
            { id: "v_agua50", display_name: "AGUA 50CL", text_only: true, full_name: "AGUA MINERAL 50CL", lst_price: 1.00, default_code: "341001" },
            { id: "v_agua15", display_name: "AGUA 1.5L", text_only: true, full_name: "AGUA MINERAL 1.5L", lst_price: 1.50, default_code: "341002" },
            { id: "v_aquarius", display_name: "AQUARIUS 33CL", text_only: true, full_name: "AQUARIUS LIMÓN/NARANJA", lst_price: 1.50, default_code: "342005" },
            { id: "v_nestea", display_name: "NESTEA 33CL", text_only: true, full_name: "NESTEA AL LIMÓN", lst_price: 1.50, default_code: "342006" },

            { id: "v_fanta_n", display_name: "FANTA NARANJA", text_only: true, full_name: "FANTA NARANJA 33CL", lst_price: 1.50, default_code: "342007" },
            { id: "v_fanta_l", display_name: "FANTA LIMON", text_only: true, full_name: "FANTA LIMÓN 33CL", lst_price: 1.50, default_code: "342008" },
            { id: "v_redbull", display_name: "RED BULL 250ML", text_only: true, full_name: "RED BULL ENERGY DRINK", lst_price: 2.20, default_code: "343001" },
            { id: "v_monster", display_name: "MONSTER 500ML", text_only: true, full_name: "MONSTER ENERGY 500ML", lst_price: 2.20, default_code: "343002" },

            { id: "v_cerveza", display_name: "CERVEZA LATA", text_only: true, full_name: "CERVEZA CRUZCAMPO LATA", lst_price: 1.20, default_code: "344001" },
            { id: "v_tercio", display_name: "CERVEZA TERCIO", text_only: true, full_name: "CERVEZA TERCIO ESPECIAL", lst_price: 1.50, default_code: "344002" },
            { id: "v_cafe_solo", display_name: "CAFÉ SOLO", text_only: true, full_name: "CAFÉ SOLO EXPRESS", lst_price: 1.00, default_code: "382002" },
            { id: "v_cafe_leche", display_name: "CAFÉ C/ LECHE", text_only: true, full_name: "CAFÉ CON LECHE", lst_price: 1.20, default_code: "382003" },

            { id: "v_cortado", display_name: "CAFÉ CORTADO", text_only: true, full_name: "CAFÉ CORTADO", lst_price: 1.10, default_code: "382004" },
            { id: "v_colacao", display_name: "COLA CAO", text_only: true, full_name: "VASO COLA CAO CALIENTE", lst_price: 1.30, default_code: "382005" },
            { id: "v_infusion", display_name: "INFUSIONES", text_only: true, full_name: "INFUSIÓN / TÉ VARIADO", lst_price: 1.10, default_code: "382007" },
            { id: "v_batido", display_name: "BATIDO CHOCO", text_only: true, full_name: "BATIDO DE CHOCOLATE", lst_price: 1.20, default_code: "382009" },

            { id: "v_zumo_nar", display_name: "ZUMO NARANJA", text_only: true, full_name: "ZUMO NARANJA NATURAL", lst_price: 2.00, default_code: "382010" },
            { id: "v_zumo_pina", display_name: "ZUMO PIÑA", text_only: true, full_name: "ZUMO DE PIÑA PASCUAL", lst_price: 1.30, default_code: "382011" },
            { id: "v_tonica", display_name: "TÓNICA SCHWEPPES", text_only: true, full_name: "TÓNICA SCHWEPPES", lst_price: 1.50, default_code: "342009" },
            { id: "v_powerade", display_name: "POWERADE 50CL", text_only: true, full_name: "POWERADE AZUL", lst_price: 1.80, default_code: "343003" }
        ];

        // PÁGINA 3: AUTOMÓVIL, ACEITES Y ACCESORIOS
        const page3Items = [
            { id: "v_adblue", display_name: "ADBLUE 10L", text_only: true, full_name: "GARRAFA ADBLUE 10L CON CÁNULA", lst_price: 16.50, default_code: "332001" },
            { id: "v_anticon", display_name: "ANTICONGELANTE 5L", text_only: true, full_name: "ANTICONGELANTE 50% 5L", lst_price: 9.90, default_code: "332002" },
            { id: "v_limpia", display_name: "LIMPIAPARABRISAS", text_only: true, full_name: "LÍQUIDO LIMPIAPARABRISAS 5L", lst_price: 4.50, default_code: "332003" },
            { id: "v_repsol10w", display_name: "ACEITE 10W40", text_only: true, full_name: "ACEITE REPSOL 10W40 5L", lst_price: 28.00, default_code: "331005" },

            { id: "v_repsol5w", display_name: "ACEITE 5W30", text_only: true, full_name: "ACEITE REPSOL 5W30 5L", lst_price: 34.00, default_code: "331006" },
            { id: "v_frenos", display_name: "LÍQUIDO FRENOS", text_only: true, full_name: "LÍQUIDO DE FRENOS DOT-4 500ML", lst_price: 6.50, default_code: "332004" },
            { id: "v_pino", display_name: "AMBIENTADOR PINO", text_only: true, full_name: "AMBIENTADOR ARBRE MAGIQUE", lst_price: 2.20, default_code: "333001" },
            { id: "v_bayeta", display_name: "BAYETA MICROFIBRA", text_only: true, full_name: "BAYETA MICROFIBRA AUTO", lst_price: 1.80, default_code: "333002" },

            { id: "v_bomb_h7", display_name: "BOMBILLA H7", text_only: true, full_name: "BOMBILLA HALÓGENA H7 12V", lst_price: 6.00, default_code: "334001" },
            { id: "v_bomb_h4", display_name: "BOMBILLA H4", text_only: true, full_name: "BOMBILLA HALÓGENA H4 12V", lst_price: 5.50, default_code: "334002" },
            { id: "v_fusibles", display_name: "PACK FUSIBLES", text_only: true, full_name: "KIT FUSIBLES COCHE 10 UDS", lst_price: 3.50, default_code: "334003" },
            { id: "v_pulpo", display_name: "PULPOS SUJECIÓN", text_only: true, full_name: "JUEGO 2 PULPOS ELÁSTICOS", lst_price: 4.00, default_code: "335001" },

            { id: "v_rasqueta", display_name: "RASQUETA HIELO", text_only: true, full_name: "RASQUETA PARA LUNAS", lst_price: 2.50, default_code: "335002" },
            { id: "v_chaleco", display_name: "CHALECO REFLECT", text_only: true, full_name: "CHALECO REFLECTANTE HOMOLOGADO", lst_price: 3.50, default_code: "335003" },
            { id: "v_triang", display_name: "TRIÁNGULOS EMERG", text_only: true, full_name: "SET TRIÁNGULOS V-16", lst_price: 9.00, default_code: "335004" },
            { id: "v_guantes", display_name: "GUANTES TRABAJO", text_only: true, full_name: "GUANTES DE PROTECCIÓN PISTA", lst_price: 2.50, default_code: "335005" },

            { id: "v_cinta", display_name: "CINTA AISLANTE", text_only: true, full_name: "CINTA AISLANTE NEGRA", lst_price: 1.20, default_code: "335006" },
            { id: "v_esponja", display_name: "ESPONJA LAVADO", text_only: true, full_name: "ESPONJA LIMPIEZA CARROCERÍA", lst_price: 1.50, default_code: "333003" },
            { id: "v_bridas", display_name: "PACK BRIDAS", text_only: true, full_name: "BOLSA BRIDAS NYLON 100 UDS", lst_price: 2.50, default_code: "335007" },
            { id: "v_parches", display_name: "KIT REPARA PINCHAZOS", text_only: true, full_name: "KIT REPARACIÓN TUBELLES", lst_price: 8.50, default_code: "335008" }
        ];

        // PÁGINA 4: SNACKS, ALIMENTACIÓN Y DULCES
        const page4Items = [
            { id: "v_patatas", display_name: "PATATAS LAYS", text_only: true, full_name: "PATATAS FRITAS LAYS AL PUNTO", lst_price: 1.60, default_code: "313001" },
            { id: "v_rufas", display_name: "RUFFLES JAMÓN", text_only: true, full_name: "RUFFLES SABOR JAMÓN", lst_price: 1.70, default_code: "313002" },
            { id: "v_doritos", display_name: "DORITOS TEX-MEX", text_only: true, full_name: "DORITOS QUESO TEX MEX", lst_price: 1.70, default_code: "313003" },
            { id: "v_pipas", display_name: "PIPAS FACUNDO", text_only: true, full_name: "PIPAS TOSTADAS CON SAL", lst_price: 1.20, default_code: "313004" },

            { id: "v_frutos", display_name: "FRUTOS SECOS", text_only: true, full_name: "CÓCTEL FRUTOS SECOS BORGES", lst_price: 1.80, default_code: "313005" },
            { id: "v_galletas", display_name: "PRÍNCIPE CHOC", text_only: true, full_name: "GALLETAS PRÍNCIPE DE LU", lst_price: 1.80, default_code: "311005" },
            { id: "v_nestle", display_name: "CHOCO NESTLÉ", text_only: true, full_name: "TABLETA CHOCOLATE CON LECHE", lst_price: 1.60, default_code: "311006" },
            { id: "v_kitkat", display_name: "KIT KAT 4 BARRAS", text_only: true, full_name: "KIT KAT CHOCOLATE NESTLÉ", lst_price: 1.40, default_code: "311002" },

            { id: "v_gominolas", display_name: "GOMINOLAS HARIBO", text_only: true, full_name: "BOLSA HARIBO OSITOS", lst_price: 1.50, default_code: "312001" },
            { id: "v_chicles", display_name: "CHICLES TRIDENT", text_only: true, full_name: "CHICLES TRIDENT HIERBABUENA", lst_price: 1.10, default_code: "312003" },
            { id: "v_halls", display_name: "CARAMELOS HALLS", text_only: true, full_name: "HALLS EXTRA STRONG MENTOL", lst_price: 1.20, default_code: "312005" },
            { id: "v_croissant", display_name: "CROISSANT CHOC", text_only: true, full_name: "CROISSANT RELLENO CACAO", lst_price: 1.20, default_code: "315001" },

            { id: "v_ensaimada", display_name: "ENSAIMADA", text_only: true, full_name: "ENSAIMADA DULCESOL", lst_price: 1.00, default_code: "315002" },
            { id: "v_donut", display_name: "DONUT GLACÉ", text_only: true, full_name: "DONUT CLÁSICO GLASÉ", lst_price: 1.30, default_code: "315003" },
            { id: "v_sandwich", display_name: "SÁNDWICH MIXTO", text_only: true, full_name: "SÁNDWICH JAMÓN Y QUESO", lst_price: 2.20, default_code: "381005" },
            { id: "v_empanada", display_name: "EMPANADILLA ATÚN", text_only: true, full_name: "EMPANADILLA CASERA ATÚN", lst_price: 1.80, default_code: "381006" },

            { id: "v_marlboro", display_name: "MARLBORO GOLD", text_only: true, full_name: "MARLBORO GOLD CAJETILLA", lst_price: 5.75, default_code: "321001" },
            { id: "v_chester", display_name: "CHESTERFIELD", text_only: true, full_name: "CHESTERFIELD ORIGINAL RED", lst_price: 5.40, default_code: "321002" },
            { id: "v_fortuna", display_name: "FORTUNA ROJO", text_only: true, full_name: "FORTUNA ROJO DURO", lst_price: 5.20, default_code: "321003" },
            { id: "v_filtros", display_name: "FILTROS OCB", text_only: true, full_name: "FILTROS OCB SLIM 120 UDS", lst_price: 1.00, default_code: "323002" }
        ];

        if (page === 2) return page2Items;
        if (page === 3) return page3Items;
        if (page === 4) return page4Items;
        return page1Items;
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
            const idleCodes = (this.state && this.state.availableFuels && this.state.availableFuels.length)
                ? this.state.availableFuels.map(f => f.code).join('/')
                : "GA/95/G+";
            return {
                isActive: false,
                type: "idle",
                code: "",
                shortCode: idleCodes,
                name: pump.fuel || "Gasóleo A / Sin Plomo 95",
                category: "DISPONIBLE",
                badgeClass: "fuel-badge-idle",
                icon: "fa-gas-pump"
            };
        }

        if (f.includes("/") || (!rawFuel && isBusy)) {
            return {
                isActive: true,
                type: "dispensing-active",
                code: "SUM",
                shortCode: "SUM",
                name: "Suministro en Curso",
                category: "EN PISTA",
                badgeClass: "fuel-badge-gasolina",
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

    
    async changeCashierName() {
        const currentName = this.pos.user ? this.pos.user.name : "Operador";
        const switchConfirm = confirm(
            "👤 GESTIÓN DE CAJERO Y TURNO\n\n" +
            "Operador actual: " + currentName + "\n\n" +
            "¿Desea cambiar de empleado y abrir la selección de personal de la estación?\n\n" +
            "• Pulse 'Aceptar' para elegir otro empleado de la estación.\n" +
            "• Pulse 'Cancelar' para editar únicamente el nombre en pantalla."
        );

        if (switchConfirm) {
            window.location.href = "/pos_gas_station/switch_cashier?config_id=" + this.configId;
            return;
        }

        const newName = prompt("Introduzca el nombre del operador que atiende en este turno:", currentName);
        if (newName && newName.trim()) {
            if (this.pos.user) {
                this.pos.user.name = newName.trim();
            }
            try {
                await jsonrpc("/pos_gas_station/set_cashier_name", {
                    config_id: this.configId,
                    user_id: this.pos.user ? this.pos.user.id : null,
                    name: newName.trim()
                });
            } catch (e) {
                console.debug("Nombre de cajero actualizado localmente");
            }
            this.state.orderVersion = Date.now();
        }
    }

    get currentDateTimeStr() {
        const d = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
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
        const selectedCat = this.state.selectedModalCategory;

        let shopProducts = all.filter(p => p.active !== false);

        if (selectedCat) {
            shopProducts = shopProducts.filter(p => {
                const catIds = p.pos_categ_ids || (p.pos_categ_id ? [p.pos_categ_id[0] || p.pos_categ_id] : []);
                return catIds.includes(selectedCat);
            });
        }

        if (!q) {
            return shopProducts.filter(p => {
                const name = (p.display_name || p.name || "").toLowerCase();
                return !name.startsWith("gasóleo") && !name.startsWith("gasoleo") && !name.startsWith("sin plomo");
            }).slice(0, 80);
        }

        const terms = q.split(/\s+/).filter(Boolean);
        return shopProducts.filter(p => {
            const name = (p.display_name || p.name || "").toLowerCase();
            const code = (p.default_code || "").toLowerCase();
            const barcode = (p.barcode || "").toLowerCase();

            // Direct exact match on barcode or internal reference
            if (barcode === q || code === q) return true;

            // Multi-token match across name, code, barcode
            return terms.every(t => name.includes(t) || code.includes(t) || barcode.includes(t));
        }).slice(0, 80);
    }

    clearStoreSearch() {
        this.state.storeSearch = "";
    }

    playFuelSound(type = "tick") {
        try {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (!AudioCtx) return;
            if (!this.audioCtx) {
                this.audioCtx = new AudioCtx();
            }
            if (this.audioCtx.state === "suspended") {
                this.audioCtx.resume();
            }
            const now = this.audioCtx.currentTime;
            const ctx = this.audioCtx;
            const tone = (freq, start, dur, vol, wave) => {
                const o = ctx.createOscillator();
                const g = ctx.createGain();
                o.type = wave;
                o.frequency.setValueAtTime(freq, now + start);
                g.gain.setValueAtTime(0.0001, now + start);
                g.gain.exponentialRampToValueAtTime(vol, now + start + 0.015);
                g.gain.exponentialRampToValueAtTime(0.0001, now + start + dur);
                o.connect(g);
                g.connect(ctx.destination);
                o.start(now + start);
                o.stop(now + start + dur + 0.02);
            };
            if (type === "start" || type === "unauthorized_unhook") {
                // Alarma: dos pitidos cortos y agudos (se repite cada segundo mientras siga descolgada)
                tone(1046.5, 0.00, 0.12, 0.20, "square");
                tone(1046.5, 0.18, 0.12, 0.20, "square");
            } else if (type === "done") {
                // Finalizado: arpegio ascendente suave Do-Mi-Sol
                tone(523.25, 0.00, 0.35, 0.16, "sine");
                tone(659.25, 0.12, 0.35, 0.16, "sine");
                tone(783.99, 0.24, 0.55, 0.16, "sine");
            }
        } catch (e) {
            console.debug("Audio pista:", e);
        }
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
                    if (this.state.selectedFuel && !this.state.availableFuels.some(f => f.code === this.state.selectedFuel)) {
                        this.state.selectedFuel = null;
                    }
                }
                if (data.pumps && Array.isArray(data.pumps)) {
                    if (!this.prevPumpsStatus) this.prevPumpsStatus = {};
                    if (!this.prevPumpsLiters) this.prevPumpsLiters = {};
                    if (!this.prevPumpsUnhooked) this.prevPumpsUnhooked = {};
                    let anyUnauthorizedUnhooked = false;

                    data.pumps.forEach(p => {
                        try {
                            p.amount = Number(p.amount || 0);
                        p.liters = Number(p.liters || 0);

                        const isUnhookedNow = this.isNozzleUnhooked(p);
                        const wasUnhookedPrev = Boolean(this.prevPumpsUnhooked[p.id]);

                        let presetInfo = (this.state.pumpPresets && this.state.pumpPresets[p.id]) || (this.pos && this.pos.pumpPresets && this.pos.pumpPresets[p.id]);

                        // ¿Tiene la pista autorización o prefijado activo?
                        const isAuthorizedOrPreset = Boolean(
                            presetInfo ||
                            p.has_prepay ||
                            p.status === "atendido" ||
                            p.status === "postpago" ||
                            p.status === "dispensing" ||
                            (p.statusText || "").includes("AUTORIZADO") ||
                            (p.statusText || "").includes("LLENO")
                        );

                        // SONIDOS DE PISTA:
                        // - Alarma intermitente SOLO mientras una manguera esté descolgada en una calle
                        //   NO autorizada ni prefijada (nunca durante un repostaje autorizado).
                        // - Al colgar la manguera, un único "ding" agradable de finalizado.
                        // La autorización se "engancha" durante todo el descolgado para que el estado
                        // de fin de venta (ready/blocked) no dispare la alarma al colgar, y el colgado
                        // exige ~700 ms estables para ignorar parpadeos del microswitch.
                        if (!this.hoseTrack) this.hoseTrack = {};
                        const ht = this.hoseTrack[p.id] || (this.hoseTrack[p.id] = { unhooked: false, authorized: false, hookedSince: 0 });
                        const tsNow = Date.now();
                        const isAuthNow = isAuthorizedOrPreset || p.amount > 0.02 || p.liters > 0.02;
                        if (isUnhookedNow) {
                            ht.hookedSince = 0;
                            if (!ht.unhooked) {
                                ht.unhooked = true;
                                ht.authorized = isAuthNow;
                            } else if (isAuthNow) {
                                ht.authorized = true;
                            }
                        } else if (ht.unhooked) {
                            if (!ht.hookedSince) ht.hookedSince = tsNow;
                            if (tsNow - ht.hookedSince >= 700) {
                                // El "ding" de finalizado SOLO tras colgar una manguera NO autorizada ni prepagada.
                                // En calles autorizadas o prepagadas no suena nada.
                                const wasUnauthorized = !ht.authorized;
                                ht.unhooked = false;
                                ht.authorized = false;
                                ht.hookedSince = 0;
                                if (wasUnauthorized) {
                                    this.playFuelSound("done");
                                }
                            }
                        }
                        if (ht.unhooked && !ht.authorized) {
                            anyUnauthorizedUnhooked = true;
                        }

                        this.prevPumpsUnhooked[p.id] = isUnhookedNow;
                        this.prevPumpsStatus[p.id] = p.status;
                        this.prevPumpsLiters[p.id] = p.liters;

                        // Reconstrucción automática de preset si el servidor o hardware informa de un sobrante de prepago
                        const isServerPrepayRefund = Boolean(
                            (p.statusText && p.statusText.includes("SOBRANTE")) ||
                            (p.preset_amount > 0 && p.amount > 0 && (p.preset_amount - p.amount) > 0.05 && (p.status === "ready" || p.status === "blocked" || p.has_prepay))
                        );

                        if (!presetInfo && isServerPrepayRefund) {
                            let diffAmt = 0;
                            if (p.preset_amount > p.amount && p.amount > 0) {
                                diffAmt = Math.round((p.preset_amount - p.amount) * 100) / 100;
                            } else if (p.statusText && p.statusText.includes("SOBRANTE")) {
                                const m = p.statusText.match(/SOBRANTE\s*([\d\.,]+)/i);
                                if (m) diffAmt = parseFloat(m[1].replace(',', '.'));
                            }
                            const presetVal = p.preset_amount > 0 ? p.preset_amount : (p.amount + diffAmt);
                            const fuelProd = (p.product_id && this.pos.db && this.pos.db.product_by_id && this.pos.db.product_by_id[p.product_id]) || this.findFuelProduct(p.fuel || "95");
                            const uPrice = p.price || (p.liters > 0 ? (p.amount / p.liters) : 1.55);
                            presetInfo = {
                                amount: presetVal,
                                liters: uPrice > 0 ? Math.round((presetVal / uPrice) * 1000) / 1000 : (p.liters || 0),
                                isMoney: true,
                                hasPrepay: true,
                                fuel: (fuelProd && fuelProd.display_name) || p.fuel || "Sin Plomo 95",
                                code: this.getPumpFuelCode(p) || "95",
                                unitPrice: uPrice,
                                productId: fuelProd ? fuelProd.id : null,
                                hasStartedDispensing: true,
                                maxDispensedAmount: p.amount,
                                maxDispensedLiters: p.liters
                            };
                            if (!this.state.pumpPresets) this.state.pumpPresets = {};
                            this.state.pumpPresets[p.id] = presetInfo;
                            if (this.pos) {
                                if (!this.pos.pumpPresets) this.pos.pumpPresets = {};
                                this.pos.pumpPresets[p.id] = presetInfo;
                            }
                        }

                        if (presetInfo && presetInfo.hasPrepay) {
                            // Rastrear el máximo suministrado en pista durante el repostaje
                            if (p.amount > 0) presetInfo.maxDispensedAmount = Math.max(presetInfo.maxDispensedAmount || 0, p.amount);
                            if (p.liters > 0) presetInfo.maxDispensedLiters = Math.max(presetInfo.maxDispensedLiters || 0, p.liters);

                            // Detectar si el cliente ha iniciado realmente el repostaje (descolgado o litros/euros > 0)
                            const hasStartedDispensing = Boolean(
                                presetInfo.hasStartedDispensing ||
                                p.amount > 0.05 ||
                                p.liters > 0.05 ||
                                (presetInfo.maxDispensedAmount || 0) > 0.05 ||
                                (presetInfo.maxDispensedLiters || 0) > 0.05 ||
                                isUnhookedNow ||
                                wasUnhookedPrev
                            );
                            if (hasStartedDispensing) {
                                presetInfo.hasStartedDispensing = true;
                            }

                            // Detectar si el prepago ha finalizado en hardware/servidor
                            // REGLA CRÍTICA: Un prepago NUNCA finaliza si no ha empezado a suministrar en pista
                            const finalAmt = (p.amount > 0 ? p.amount : (presetInfo.maxDispensedAmount || 0));
                            const finalLts = (p.liters > 0 ? p.liters : (presetInfo.maxDispensedLiters || 0));
                            const presetAmt = presetInfo.amount || 0;
                            const diffAmt = Math.round((presetAmt - finalAmt) * 100) / 100;

                            const isDone = hasStartedDispensing && (
                                (p.status === "ready") || 
                                (!isUnhookedNow && (p.status === "blocked" || p.status === "idle" || p.status === "atendido")) ||
                                (p.status !== "dispensing" && Math.abs(finalAmt - presetAmt) <= 0.05)
                            );

                            if (isDone) {
                                if (diffAmt > 0.05 && finalAmt > 0) {
                                    // SOBRANTE DE PREPAGO DETECTADO: El cliente echó parte del combustible, pero sobró dinero
                                    this.registerPrepayRefund(p, presetInfo, finalAmt, finalLts);
                                } else {
                                    // Prepago completado al 100% (o sin sobrante)
                                    if (this.state.pumpPresets) delete this.state.pumpPresets[p.id];
                                    if (this.pos && this.pos.pumpPresets) delete this.pos.pumpPresets[p.id];
                                    this.savePumpPresets();
                                }
                            } else {
                                // MANTENER EN PANTALLA EL SURTIDOR EN VERDE (AUTORIZADO O SUMINISTRANDO)
                                p.status = "dispensing";
                                if (p.liters > 0 || p.amount > 0) {
                                    p.statusText = `SUMINISTRO ${p.liters.toFixed(2)}L`;
                                } else {
                                    p.statusText = `AUTORIZADO ${presetInfo.amount.toFixed(2)} €`;
                                }
                                p.preset_amount = presetInfo.amount;
                                p.has_prepay = true;
                                if (!p.fuel || p.fuel === "N/A" || p.fuel.includes("/")) {
                                    p.fuel = presetInfo.fuel;
                                }
                            }
                        } else if (presetInfo) {
                            const hasStartedDispensing = Boolean(
                                presetInfo.hasStartedDispensing ||
                                p.amount > 0.05 ||
                                p.liters > 0.05 ||
                                isUnhookedNow ||
                                wasUnhookedPrev
                            );
                            if (hasStartedDispensing) {
                                presetInfo.hasStartedDispensing = true;
                            }

                            const isNonPrepayDone = (p.status === "ready") || 
                                                    (hasStartedDispensing && !isUnhookedNow && (p.status === "blocked" || p.status === "idle"));

                            if (isNonPrepayDone) {
                                if (this.state.pumpPresets) delete this.state.pumpPresets[p.id];
                                if (this.pos && this.pos.pumpPresets) delete this.pos.pumpPresets[p.id];
                                this.savePumpPresets();
                            } else {
                                // Mantener activo mientras espera al cliente o suministra
                                p.status = "dispensing";
                                p.preset_amount = presetInfo.amount;
                                p.has_prepay = false;
                                if (p.liters > 0 || p.amount > 0) {
                                    p.statusText = `SUMINISTRO ${p.liters.toFixed(2)}L`;
                                } else {
                                    p.statusText = presetInfo.isLleno ? "LLENO (POSTPAGO)" : (presetInfo.amount > 0 ? `AUTORIZADO ${presetInfo.amount.toFixed(2)} €` : "AUTORIZADO");
                                }
                                if (!p.fuel || p.fuel === "N/A" || p.fuel.includes("/")) {
                                    p.fuel = presetInfo.fuel;
                                }
                            }
                        }

                        // Si la calle finalizó repostaje (manguera colgada con 'ready' o importe > 0 sin estar suministrando)
                        const isFuelingDone = !isUnhookedNow && (p.status === "ready" || (p.amount > 0 && p.status !== "dispensing")) && !p.has_prepay;
                        if (isFuelingDone && (p.amount > 0 || p.liters > 0)) {
                            if (!this.processedFuelingKeys) this.processedFuelingKeys = {};
                            const fuelingKey = `${p.id}_${p.amount}_${p.liters}_${p.updated_at || ''}`;
                            if (!this.processedFuelingKeys[fuelingKey]) {
                                this.processedFuelingKeys[fuelingKey] = true;

                                const storeItems = (this.pos && this.pos.pumpPendingStoreItems && this.pos.pumpPendingStoreItems[p.id]) || [];
                                if (this.pos && this.pos.pumpPendingStoreItems && this.pos.pumpPendingStoreItems[p.id]) {
                                    delete this.pos.pumpPendingStoreItems[p.id];
                                    this.savePumpPendingStoreItems();
                                }

                                const fuelProd = (p.product_id && this.pos.db.product_by_id[p.product_id]) || this.findFuelProduct(p.fuel || "GA");
                                const fuelInfo = {
                                    name: (fuelProd && fuelProd.display_name) || p.fuel || "Combustible",
                                    liters: p.liters || 0,
                                    price: p.price || (p.liters > 0 ? (p.amount / p.liters) : 1.45),
                                    amount: p.amount || 0,
                                    productId: fuelProd ? fuelProd.id : null,
                                    code: this.getPumpFuelCode(p)
                                };
                                const storeTotal = storeItems.reduce((acc, it) => acc + (it.amount || (it.price * it.qty)), 0);
                                const pendingPlate = (this.pos && this.pos.pumpPendingPlates && this.pos.pumpPendingPlates[p.id]) || p.vehiclePlate || this.state.vehiclePlate || "";
                                if (this.pos && this.pos.pumpPendingPlates && this.pos.pumpPendingPlates[p.id]) {
                                    delete this.pos.pumpPendingPlates[p.id];
                                    this.savePumpPendingPlates();
                                }
                                const pendingSale = {
                                    id: "sale_" + p.id + "_" + Date.now(),
                                    pumpId: p.id,
                                    timestamp: Date.now(),
                                    timeStr: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                                    fuel: fuelInfo,
                                    storeLines: storeItems,
                                    totalAmount: (p.amount || 0) + storeTotal,
                                    vehiclePlate: pendingPlate
                                };
                                if (!this.pos.pendingSales) this.pos.pendingSales = {};
                                if (!this.pos.pendingSales[p.id]) this.pos.pendingSales[p.id] = [];
                                this.pos.pendingSales[p.id].push(pendingSale);
                                this.savePendingSales();

                                // Liberar surtidor en pista para el siguiente vehículo y bloquear en hardware
                                try {
                                    jsonrpc("/pos_gas_station/clear_pump", {
                                        config_id: this.configId,
                                        pump_id: p.id
                                    }).catch(e => console.debug("Liberar bomba tras pasar a monedita:", e));
                                } catch (e) {}

                                p.amount = 0;
                                p.liters = 0;
                                p.preset_amount = 0;
                                p.has_prepay = false;
                                p.is_lleno = false;
                                p.status = "ready";
                                p.statusText = this.pos.pendingSales[p.id].length === 1 ? "COBRAR" : `COBROS (${this.pos.pendingSales[p.id].length})`;
                            }
                        }
                        } catch (pumpErr) {
                            console.error("Error procesando estado de surtidor", p.id, pumpErr);
                        }
                    });

                    // Sincronizar estado visual de cada surtidor según sus monedas pendientes
                    data.pumps.forEach(p => {
                        try {
                            const pCount = (this.pos && this.pos.pendingSales && this.pos.pendingSales[p.id]) ? this.pos.pendingSales[p.id].length : 0;
                        if (pCount > 0 && p.status !== "dispensing") {
                            p.status = "ready";
                            const hasRefund = this.pos.pendingSales[p.id].some(s => s.isPrepayRefund);
                            if (hasRefund) {
                                const refSale = this.pos.pendingSales[p.id].find(s => s.isPrepayRefund);
                                p.statusText = `SOBRANTE ${Math.abs(refSale.refundAmount).toFixed(2)} €`;
                            } else {
                                p.statusText = pCount === 1 ? "COBRAR" : `COBROS (${pCount})`;
                            }
                        } else if (pCount === 0 && p.status !== "dispensing" && p.status !== "atendido") {
                            p.status = "blocked";
                            p.statusText = "PREPAGO";
                        }
                        } catch (syncErr) {
                            console.error("Error sincronizando surtidor", p.id, syncErr);
                        }
                    });

                    // Sonido periódico ÚNICAMENTE mientras haya alguna manguera descolgada NO autorizada ni prefijada
                    const nowTs = Date.now();
                    if (anyUnauthorizedUnhooked) {
                        if (nowTs - (this.lastUnauthorizedSoundTime || 0) > 1000) {
                            this.lastUnauthorizedSoundTime = nowTs;
                            this.playFuelSound("unauthorized_unhook");
                        }
                    }

                    this.state.pumps = data.pumps;
                    const attendedCount = data.pumps.filter(p => p.status === "atendido" || p.status === "postpago").length;
                    const blockedCount = data.pumps.filter(p => p.status === "blocked" || p.status === "prepago").length;
                    if (attendedCount > 0 || blockedCount > 0) {
                        this.state.trackMode = attendedCount >= blockedCount ? "atendido" : "prepago";
                    }
                }
            }
        } catch (err) {
            console.debug("Error al consultar estado de surtidores:", err);
        }
    }

    setVehiclePlate(plate) {
        plate = (plate || "").trim().toUpperCase();
        this.state.vehiclePlate = plate;
        const currentOrder = this.getOrCreateOrder();
        if (currentOrder) {
            currentOrder.vehicle_plate = plate;
            if (currentOrder.set_note) {
                currentOrder.set_note(plate ? `Matrícula: ${plate}` : "");
            }
        }
        this.state.orderVersion = Date.now();
    }

    onPlateChange(ev) {
        const plate = ev.target.value.toUpperCase();
        this.setVehiclePlate(plate);
    }

    onPlateSelect(ev) {
        const val = ev.target.value;
        if (val === "__NEW__") {
            this.state.isAddingNewPlate = true;
            this.state.newPlateInput = "";
            setTimeout(() => {
                const input = document.querySelector(".virtus-new-plate-input");
                if (input) input.focus();
            }, 60);
            return;
        }
        this.setVehiclePlate(val);
    }

    cancelAddNewPlate() {
        this.state.isAddingNewPlate = false;
        this.state.newPlateInput = "";
    }

    async saveNewPlateAndAssign() {
        const plate = this.state.newPlateInput;
        if (!plate || !plate.trim()) return;
        await this.savePlateToPartner(plate);
    }

    onNewPlateKeyDown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.saveNewPlateAndAssign();
        } else if (ev.key === "Escape") {
            this.cancelAddNewPlate();
        }
    }

    async savePlateToPartner(plate) {
        if (this.state.isSavingPlate) return;
        const partner = this.currentOrderPartner;
        if (!partner || !partner.id) return;
        const cleanPlate = (plate || "").trim().toUpperCase();
        if (!cleanPlate || cleanPlate.length < 3) return;

        this.state.isSavingPlate = true;
        try {
            const res = await this.env.services.rpc("/pos_gas_station/save_partner_vehicle", {
                partner_id: partner.id,
                plate: cleanPlate
            });
            if (res && res.status === "success") {
                this.state.partnerVehicles = res.vehicles || [];
                this.state.isAddingNewPlate = false;
                this.state.newPlateInput = "";
                this.setVehiclePlate(cleanPlate);
                if (this.env.services.notification) {
                    this.env.services.notification.add(
                        `Matrícula ${cleanPlate} guardada en la ficha del cliente`,
                        { type: "success", sticky: false, duration: 2500 }
                    );
                }
            } else {
                console.warn("No se pudo guardar la matrícula:", res ? res.message : "Error");
            }
        } catch (e) {
            console.error("Error savePlateToPartner:", e);
        } finally {
            this.state.isSavingPlate = false;
        }
    }

    onPartnerPlateInputChange(ev) {
        const val = ev.target.value;
        if (val && val.trim().length >= 4 && this.currentOrderPartner) {
            this.savePlateToPartner(val);
        }
    }

    onPartnerPlateInputKeyDown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            const val = ev.target.value;
            if (val && val.trim().length >= 3 && this.currentOrderPartner) {
                this.savePlateToPartner(val);
            }
        }
    }

    async loadPartnerVehicles(partnerId) {
        if (!partnerId) {
            this.state.partnerVehicles = [];
            this.state.isAddingNewPlate = false;
            return;
        }
        try {
            const res = await this.env.services.rpc("/pos_gas_station/get_partner_vehicles", {
                partner_id: partnerId
            });
            if (res && res.status === "success") {
                this.state.partnerVehicles = res.vehicles || [];
                this.state.isAddingNewPlate = false;
                // Si el cliente tiene exactamente 1 matrícula registrada y la orden no tiene aún matrícula:
                if (this.state.partnerVehicles.length === 1 && !this.state.vehiclePlate) {
                    this.setVehiclePlate(this.state.partnerVehicles[0].name);
                } else if (this.state.partnerVehicles.length > 0 && this.state.vehiclePlate) {
                    // Si ya tenía matrícula escrita, verificar si coincide con alguna del cliente
                    const found = this.state.partnerVehicles.some(v => v.name === this.state.vehiclePlate);
                    if (!found && this.state.partnerVehicles.length === 1) {
                        this.setVehiclePlate(this.state.partnerVehicles[0].name);
                    }
                }
            }
        } catch (e) {
            console.error("Error al cargar matrículas del cliente:", e);
            this.state.partnerVehicles = [];
        }
    }

    async editLineQuantity(line) {
        if (!line) return;
        this.selectOrderLine(line);
        const currentQty = line.get_quantity();
        const productName = line.product ? line.product.display_name : "Artículo";
        let newQty = null;

        try {
            const isUnit = line.product?.uom_id && (line.product.uom_id[1] === "Units" || line.product.uom_id[1] === "Unidades");
            const { confirmed, payload } = await this.popup.add(NumberPopup, {
                title: `Modificar cantidad: ${productName}`,
                startingValue: currentQty,
                isInputSelected: true,
                nbrDecimal: isUnit ? 0 : 2,
            });
            if (confirmed && payload !== null && payload !== "") {
                newQty = parseFloat(payload);
            }
        } catch (e) {
            console.debug("Aviso abriendo NumberPopup, usando prompt de fallback:", e);
            const input = prompt(`Modificar cantidad para "${productName}":`, currentQty);
            if (input !== null && input.trim() !== "") {
                newQty = parseFloat(input.trim().replace(",", "."));
            }
        }

        if (newQty !== null && !isNaN(newQty)) {
            if (newQty <= 0) {
                this.deleteSpecificLine(line);
            } else {
                line.set_quantity(newQty);
                this.state.orderVersion = Date.now();
            }
        }
    }

    async onProductCardDblClick(virtusItem) {
        if (!virtusItem || virtusItem.is_empty) return;
        const currentOrder = this.getOrCreateOrder();
        if (!currentOrder) return;

        const lines = currentOrder.get_orderlines() || [];
        const code = (virtusItem.default_code || "").toLowerCase();
        const barcode = (virtusItem.barcode || "").toLowerCase();
        const name = (virtusItem.display_name || virtusItem.full_name || "").toLowerCase();

        let targetLine = lines.find(l => {
            if (!l.product) return false;
            if (barcode && (l.product.barcode || "").toLowerCase() === barcode) return true;
            if (code && (l.product.default_code || "").toLowerCase() === code) return true;
            return (l.product.display_name || "").toLowerCase().includes(name);
        });

        if (!targetLine) {
            await this.addStoreProductToOrder(virtusItem, true);
            const updatedLines = currentOrder.get_orderlines() || [];
            targetLine = updatedLines.find(l => {
                if (!l.product) return false;
                if (barcode && (l.product.barcode || "").toLowerCase() === barcode) return true;
                if (code && (l.product.default_code || "").toLowerCase() === code) return true;
                return (l.product.display_name || "").toLowerCase().includes(name);
            });
        }

        if (targetLine) {
            await this.editLineQuantity(targetLine);
        }
    }

    getProductOrderQty(virtusItem) {
        if (!virtusItem) return 0;
        const currentOrder = this.pos ? this.pos.get_order() : null;
        if (!currentOrder) return 0;
        const lines = (typeof currentOrder.get_orderlines === "function" ? currentOrder.get_orderlines() : currentOrder.orderlines) || [];
        const code = (virtusItem.default_code || "").toLowerCase();
        const barcode = (virtusItem.barcode || "").toLowerCase();
        const name = (virtusItem.display_name || virtusItem.full_name || virtusItem.name || "").toLowerCase();

        let total = 0;
        for (const l of lines) {
            if (!l.product) continue;
            const pCode = (l.product.default_code || "").toLowerCase();
            const pBarcode = (l.product.barcode || "").toLowerCase();
            const pName = (l.product.display_name || l.product.name || "").toLowerCase();

            if ((barcode && pBarcode === barcode) || (code && pCode === code) || (pName === name)) {
                total += (typeof l.get_quantity === "function" ? l.get_quantity() : l.quantity) || 0;
            }
        }
        return total;
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

        const pumpId = line.pump_id;
        if (pumpId) {
            const target = this.state.pumps.find(p => p.id === pumpId);
            if (target) {
                target.status = this.state.trackMode === "atendido" ? "atendido" : "blocked";
                target.statusText = this.state.trackMode === "atendido" ? "ATENDIDO" : "SIN PREFIJADO";
                target.amount = 0;
                target.liters = 0;
                target.has_prepay = false;
                target.preset_amount = 0;
            }
            if (this.state.pumpPresets) {
                delete this.state.pumpPresets[pumpId];
            }
            try {
                jsonrpc("/pos_gas_station/clear_pump", {
                    config_id: this.configId,
                    pump_id: pumpId
                }).catch(e => console.debug("Liberar bomba tras borrar linea:", e));
            } catch (e) {
                console.debug("Error al liberar bomba:", e);
            }
        }

        try {
            if (typeof currentOrder.removeOrderline === "function") {
                currentOrder.removeOrderline(line);
            } else if (typeof currentOrder._unlink_order_line === "function") {
                currentOrder._unlink_order_line(line);
            } else if (typeof currentOrder.remove_orderline === "function") {
                currentOrder.remove_orderline(line);
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

    async resetAndLockPump(pumpId, autoAnnulPrepay = true, forceAnnul = false) {
        const target = this.state.pumps.find(p => p.id === pumpId);
        const preset = (this.state.pumpPresets && this.state.pumpPresets[pumpId]) || 
                       (this.pos && this.pos.pumpPresets && this.pos.pumpPresets[pumpId]);
        const isPrepay = Boolean((target && (target.has_prepay || (target.amount > 0 && target.statusText !== 'SIN PREFIJADO'))) || (preset && (preset.hasPrepay || preset.amount > 0)));
        const orderRef = (preset && (preset.orderRef || preset.orderPosRef || preset.orderTicketName)) || null;
        const orderId = (preset && preset.orderBackendId) || null;
        const posRef = preset ? preset.pos_reference : null;
        const dispensedLts = (target && typeof target.liters === 'number') ? target.liters : 0;

        if (target) {
            target.status = "blocked";
            target.statusText = "SIN PREFIJADO";
            target.amount = 0;
            target.liters = 0;
            target.has_prepay = false;
            target.preset_amount = 0;
            target.is_lleno = false;
        }
        if (this.state.pumpPresets) {
            delete this.state.pumpPresets[pumpId];
        }
        if (this.pos && this.pos.pumpPresets) {
            delete this.pos.pumpPresets[pumpId];
        }
        if (typeof this.savePumpPresets === 'function') {
            this.savePumpPresets();
        }

        const currentOrder = this.pos.get_order();
        if (currentOrder) {
            if (currentOrder.pending_prepay && currentOrder.pending_prepay.pump_id === pumpId) {
                currentOrder.pending_prepay = null;
            }
            const line = currentOrder.get_orderlines().find(l => l.pump_id === pumpId || (l.customerNote && l.customerNote.includes(`Calle ${pumpId}`)));
            if (line) {
                try {
                    if (typeof currentOrder.removeOrderline === "function") {
                        currentOrder.removeOrderline(line);
                    } else if (typeof currentOrder._unlink_order_line === "function") {
                        currentOrder._unlink_order_line(line);
                    } else if (typeof currentOrder.remove_orderline === "function") {
                        currentOrder.remove_orderline(line);
                    } else if (typeof line.delete === "function") {
                        line.delete();
                    }
                } catch (e) {
                    console.debug("Error eliminando linea de pedido:", e);
                }
            }
        }
        try {
            await jsonrpc("/pos_gas_station/clear_pump", {
                config_id: this.configId,
                pump_id: pumpId
            });
        } catch (e) {
            console.debug("Error al resetear y bloquear bomba:", e);
        }

        // Si la calle estaba en modalidad PREPAGO ya cobrado y se cancela antes de dispensar (o forceAnnul desde confirmación de cancelación),
        // generar de forma automática el ticket/albarán negativo/factura rectificativa sobre esa operación
        if (autoAnnulPrepay && (forceAnnul || (isPrepay && dispensedLts <= 0.05))) {
            try {
                const res = await jsonrpc("/pos_gas_station/annul_order", {
                    config_id: this.configId,
                    pump_id: pumpId,
                    order_id: orderId,
                    order_ref: orderRef,
                    pos_reference: posRef,
                    is_albaran: Boolean(preset && preset.isAlbaran),
                    is_invoice: Boolean(preset && preset.isInvoice),
                    reason: `Cancelación de pista en prepago (Calle ${pumpId})`
                });
                if (res && res.status === "success") {
                    if (typeof this.loadShiftOrders === "function") {
                        await this.loadShiftOrders();
                    }
                } else if (res && res.status === "error") {
                    console.warn("Aviso al anular automáticamente documento de prepago cancelado:", res.message);
                }
            } catch (err) {
                console.error("Error al anular automáticamente documento de prepago cancelado:", err);
            }
        }

        this.state.orderVersion = Date.now();
    }

    async deleteSelectedLine() {
        const currentOrder = this.pos.get_order();
        let line = null;
        if (this.state.selectedLineId && this.currentOrderLines) {
            line = this.currentOrderLines.find(l => l.id === this.state.selectedLineId);
        }
        if (!line && currentOrder) {
            line = currentOrder.get_selected_orderline();
        }
        if (!line && this.currentOrderLines && this.currentOrderLines.length > 0) {
            line = this.currentOrderLines[this.currentOrderLines.length - 1];
        }

        if (line) {
            await this.deleteSpecificLine(line);
            this.state.selectedLineId = null;
            return;
        }

        // Si el ticket está vacío pero hay una calle seleccionada o activa que no está bloqueada (Lleno / Suministro / Prepago)
        let targetPump = null;
        if (this.state.selectedPumpId) {
            targetPump = this.state.pumps.find(p => p.id === this.state.selectedPumpId);
        }
        if (!targetPump) {
            const activePumps = this.state.pumps.filter(p => p.status !== "blocked" || p.amount > 0 || p.preset_amount > 0);
            if (activePumps.length === 1) {
                targetPump = activePumps[0];
            }
        }
        if (targetPump && (targetPump.status !== "blocked" || targetPump.amount > 0 || targetPump.preset_amount > 0)) {
            if (confirm(`¿Desea borrar la autorización y bloquear la Calle ${targetPump.id}?`)) {
                await this.resetAndLockPump(targetPump.id);
                this.state.selectedPumpId = null;
            }
        }
    }

    async clearCurrentOrder() {
        const currentOrder = this.pos.get_order();
        const hasLines = this.currentOrderLines && this.currentOrderLines.length > 0;
        
        // Identificar qué bombas están implicadas para liberarlas/bloquearlas
        const pumpsToClear = new Set();
        if (hasLines) {
            for (const l of this.currentOrderLines) {
                if (l.pump_id) {
                    pumpsToClear.add(l.pump_id);
                }
            }
        }

        // Si hay una bomba seleccionada y NO está bloqueada (está en atendido/lleno, autorizada, suministrando o lista)
        if (this.state.selectedPumpId) {
            const selPump = this.state.pumps.find(p => p.id === this.state.selectedPumpId);
            if (selPump && (selPump.status !== "blocked" || selPump.amount > 0 || selPump.preset_amount > 0)) {
                pumpsToClear.add(this.state.selectedPumpId);
            }
        } else {
            // O si hay alguna bomba en la pista abierta/no bloqueada y el ticket está vacío
            const activePumps = this.state.pumps.filter(p => p.status !== "blocked" || p.amount > 0);
            if (activePumps.length === 1 && !hasLines) {
                pumpsToClear.add(activePumps[0].id);
            } else if (activePumps.length > 1 && !hasLines) {
                for (const ap of activePumps) {
                    pumpsToClear.add(ap.id);
                }
            }
        }

        let confirmMsg = "¿Desea cancelar el pedido actual?";
        if (pumpsToClear.size > 0) {
            const listStr = Array.from(pumpsToClear).join(", ");
            confirmMsg = `¿Desea cancelar el pedido y bloquear la Calle ${listStr}?`;
        }

        if (confirm(confirmMsg)) {
            // 1. Resetear y bloquear todas las bombas detectadas
            for (const pid of pumpsToClear) {
                await this.resetAndLockPump(pid);
            }

            // 2. Vaciar las líneas del ticket
            if (currentOrder) {
                currentOrder.pending_prepay = null;
                try {
                    const lines = [...this.currentOrderLines];
                    for (const l of lines) {
                        this.deleteSpecificLine(l);
                    }
                    if (currentOrder.set_note) currentOrder.set_note("");
                } catch (e) {
                    console.debug("Error al vaciar orden:", e);
                }
            }
            // 3. Quitar cliente asignado si existiera previamente
            this.removeClient();

            this.state.vehiclePlate = "";
            this.state.selectedLineId = null;
            this.state.selectedPumpId = null;
            this.state.orderVersion = Date.now();
        }
    }

    async openClosedShiftsModal() {
        this.state.isClosedShiftsModalOpen = true;
        this.state.closedShiftsSearch = "";
        this.state.closedShiftSortField = "start_at";
        this.state.closedShiftSortDirection = "desc";
        await this.loadClosedShifts();
    }

    closeClosedShiftsModal() {
        this.state.isClosedShiftsModalOpen = false;
        this.state.closedShifts = [];
        this.state.closedShiftsSearch = "";
    }

    sortClosedShifts(field) {
        if (this.state.closedShiftSortField === field) {
            this.state.closedShiftSortDirection = this.state.closedShiftSortDirection === "asc" ? "desc" : "asc";
        } else {
            this.state.closedShiftSortField = field;
            if (field === "start_at" || field === "stop_at" || field === "total" || field === "orders" || field === "arqueo") {
                this.state.closedShiftSortDirection = "desc";
            } else {
                this.state.closedShiftSortDirection = "asc";
            }
        }
    }

    getClosedShiftSortIcon(field) {
        if (this.state.closedShiftSortField === field) {
            return this.state.closedShiftSortDirection === "asc" ? "fa-sort-asc sort-icon active" : "fa-sort-desc sort-icon active";
        }
        return "fa-sort sort-icon inactive";
    }

    async loadClosedShifts() {
        this.state.closedShiftsLoading = true;
        try {
            const configId = this.pos.config ? this.pos.config.id : null;
            const res = await jsonrpc("/pos_gas_station/get_closed_shifts", {
                config_id: configId
            });
            if (res && res.status === "success") {
                this.state.closedShifts = res.shifts || [];
            } else {
                this.state.closedShifts = [];
            }
        } catch (e) {
            console.error("Error al cargar historial de turnos cerrados:", e);
            this.state.closedShifts = [];
        } finally {
            this.state.closedShiftsLoading = false;
        }
    }

    get filteredClosedShifts() {
        const query = (this.state.closedShiftsSearch || "").trim().toLowerCase();
        let list = (this.state.closedShifts || []);
        if (query) {
            list = list.filter(s => 
                (s.name && s.name.toLowerCase().includes(query)) ||
                (s.employee_name && s.employee_name.toLowerCase().includes(query)) ||
                (s.start_at && s.start_at.toLowerCase().includes(query)) ||
                (s.stop_at && s.stop_at.toLowerCase().includes(query))
            );
        }

        const field = this.state.closedShiftSortField || "start_at";
        const direction = this.state.closedShiftSortDirection || "desc";
        const modifier = direction === "desc" ? -1 : 1;

        return [...list].sort((a, b) => {
            let diff = 0;
            switch (field) {
                case "name": {
                    const valA = a.name || "";
                    const valB = b.name || "";
                    diff = valA.localeCompare(valB, undefined, { numeric: true, sensitivity: "base" });
                    break;
                }
                case "employee": {
                    const valA = a.employee_name || "";
                    const valB = b.employee_name || "";
                    diff = valA.localeCompare(valB, undefined, { sensitivity: "base" });
                    break;
                }
                case "start_at": {
                    const valA = a.start_at_raw || a.start_at || "";
                    const valB = b.start_at_raw || b.start_at || "";
                    diff = valA.localeCompare(valB);
                    break;
                }
                case "stop_at": {
                    const valA = a.stop_at_raw || a.stop_at || "";
                    const valB = b.stop_at_raw || b.stop_at || "";
                    diff = valA.localeCompare(valB);
                    break;
                }
                case "orders": {
                    diff = (Number(a.orders_count) || 0) - (Number(b.orders_count) || 0);
                    break;
                }
                case "total": {
                    diff = (Number(a.total_amount) || 0) - (Number(b.total_amount) || 0);
                    break;
                }
                case "arqueo": {
                    diff = (Number(a.difference) || 0) - (Number(b.difference) || 0);
                    break;
                }
                default:
                    diff = (a.id || 0) - (b.id || 0);
            }
            if (diff === 0) {
                diff = (a.id || 0) - (b.id || 0);
            }
            return diff * modifier;
        });
    }

    viewClosedShiftReport(shift) {
        if (!shift || !shift.id) return;
        window.open(`/pos_gas_station/shift_report_print/${shift.id}`, '_blank');
    }

    downloadClosedShiftPdf(shift) {
        if (!shift || !shift.id) return;
        window.open(`/pos_gas_station/shift_report_pdf/${shift.id}`, '_blank');
    }

    openRefundScreen() {
        this.openShiftOrdersModal();
    }

    async openShiftOrdersModal() {
        this.state.isShiftOrdersModalOpen = true;
        this.state.selectedShiftOrder = null;
        this.state.shiftOrderSearch = "";
        this.state.shiftOrdersLoading = true;
        await this.loadShiftOrders();
    }

    closeShiftOrdersModal() {
        this.state.isShiftOrdersModalOpen = false;
        this.state.selectedShiftOrder = null;
    }

    async loadShiftOrders() {
        this.state.shiftOrdersLoading = true;
        try {
            const currentSessionId = this.pos.pos_session ? this.pos.pos_session.id : null;
            const configId = this.pos.config ? this.pos.config.id : null;
            const sid = currentSessionId;
            const res = await this.env.services.rpc("/pos_gas_station/get_shift_orders", {
                session_id: sid,
                config_id: configId,
            });
            if (res && res.status === "success") {
                this.state.shiftOrders = res.orders || [];
                this.state.shiftSummary = res.summary || { total_sales: 0, total_cash: 0, total_bank: 0, orders_count: 0 };
                this.state.shiftViewSessionId = res.session_id;
                this.state.shiftSessionInfo = {
                    currentId: currentSessionId,
                    currentName: this.pos.pos_session ? this.pos.pos_session.name : `Sesión ${currentSessionId}`,
                    viewId: res.session_id,
                    viewName: res.session_name,
                    prevId: null,
                    prevName: null,
                    isCurrent: true
                };
            } else {
                console.error("Error al cargar pedidos del turno:", res ? res.message : '');
            }
        } catch (e) {
            console.error("Error RPC loadShiftOrders:", e);
        } finally {
            this.state.shiftOrdersLoading = false;
        }
    }

    get filteredShiftOrders() {
        if (!this.state.shiftOrders) return [];
        let list = this.state.shiftOrders;
        const q = (this.state.shiftOrderSearch || "").toLowerCase().trim();
        if (q) {
            list = list.filter(o => 
                (o.name && o.name.toLowerCase().includes(q)) ||
                (o.pos_reference && o.pos_reference.toLowerCase().includes(q)) ||
                (o.partner_name && o.partner_name.toLowerCase().includes(q)) ||
                (o.partner_vat && o.partner_vat.toLowerCase().includes(q)) ||
                (o.account_move_name && o.account_move_name.toLowerCase().includes(q)) ||
                (o.pump_id && `calle ${o.pump_id}`.includes(q)) ||
                (o.pump_name && o.pump_name.toLowerCase().includes(q)) ||
                String(o.amount_total).includes(q)
            );
        }

        const field = this.state.shiftOrderSortField || "date";
        const dir = this.state.shiftOrderSortDirection || "desc";
        const modifier = dir === "asc" ? 1 : -1;

        return [...list].sort((a, b) => {
            let diff = 0;
            switch (field) {
                case "date": {
                    const valA = a.date_order_raw || a.id;
                    const valB = b.date_order_raw || b.id;
                    diff = valA > valB ? 1 : (valA < valB ? -1 : 0);
                    break;
                }
                case "ticket": {
                    const valA = a.name || "";
                    const valB = b.name || "";
                    diff = valA.localeCompare(valB, undefined, { numeric: true, sensitivity: "base" });
                    break;
                }
                case "pump": {
                    const valA = Number(a.pump_id) || 0;
                    const valB = Number(b.pump_id) || 0;
                    diff = valA - valB;
                    break;
                }
                case "receipt": {
                    const valA = a.pos_reference || a.name || "";
                    const valB = b.pos_reference || b.name || "";
                    diff = valA.localeCompare(valB, undefined, { numeric: true, sensitivity: "base" });
                    break;
                }
                case "partner": {
                    const valA = a.partner_name || "";
                    const valB = b.partner_name || "";
                    if (!valA && valB) diff = 1;
                    else if (valA && !valB) diff = -1;
                    else diff = valA.localeCompare(valB, undefined, { sensitivity: "base" });
                    break;
                }
                case "total": {
                    const valA = Number(a.amount_total) || 0;
                    const valB = Number(b.amount_total) || 0;
                    diff = valA - valB;
                    break;
                }
                default:
                    diff = (a.id || 0) - (b.id || 0);
            }
            if (diff === 0) {
                diff = (a.id || 0) - (b.id || 0);
            }
            return diff * modifier;
        });
    }

    sortShiftOrders(field) {
        if (this.state.shiftOrderSortField === field) {
            this.state.shiftOrderSortDirection = this.state.shiftOrderSortDirection === "asc" ? "desc" : "asc";
        } else {
            this.state.shiftOrderSortField = field;
            if (field === "date" || field === "total") {
                this.state.shiftOrderSortDirection = "desc";
            } else {
                this.state.shiftOrderSortDirection = "asc";
            }
        }
    }

    getSortIcon(field) {
        if (this.state.shiftOrderSortField === field) {
            return this.state.shiftOrderSortDirection === "asc" ? "fa-sort-asc sort-icon active" : "fa-sort-desc sort-icon active";
        }
        return "fa-sort sort-icon inactive";
    }

    toggleOrderHistory(orderId) {
        if (!this.state.expandedShiftOrderIds) {
            this.state.expandedShiftOrderIds = {};
        }
        this.state.expandedShiftOrderIds[orderId] = !this.state.expandedShiftOrderIds[orderId];
    }

    isOrderExpanded(orderId) {
        return Boolean(this.state.expandedShiftOrderIds && this.state.expandedShiftOrderIds[orderId]);
    }

    printAnnulmentReceipt(order, historyItem, autoPrint = true) {
        if (!order) return;
        const comp = order.company || {};
        const refAnnul = (historyItem && historyItem.ref) ? historyItem.ref : (order.annulment_ref || 'TTTR_ANUL');
        const dateAnnul = (historyItem && historyItem.date) ? historyItem.date : (order.annulment_date || order.date_order);
        const reasonAnnul = (historyItem && historyItem.description) ? historyItem.description : (order.annulment_reason || 'Anulación oficial de ticket');

        const linesHtml = (order.lines || []).map(l => `
            <tr>
                <td style="text-align: left; padding: 4px 0;">${l.product_name}</td>
                <td style="text-align: right; padding: 4px 0;">-${Number(l.qty).toFixed(2)}</td>
                <td style="text-align: right; padding: 4px 0;">${Number(l.price_unit).toFixed(3)} €</td>
                <td style="text-align: right; padding: 4px 0; font-weight: bold; color: #b71c1c;">-${Number(l.price_subtotal_incl).toFixed(2)} €</td>
            </tr>
        `).join("");

        const receiptWindow = window.open("", "_blank", "width=420,height=680");
        if (!receiptWindow) {
            alert("Por favor permita las ventanas emergentes en su navegador para imprimir o visualizar.");
            return;
        }

        const isAlbaran = order.is_albaran || (historyItem && historyItem.type_label && historyItem.type_label.includes('Albarán'));
        const isInvoice = order.is_invoiced || (historyItem && historyItem.type_label && historyItem.type_label.includes('Factura'));
        const docTitle = isAlbaran ? 'ALBARÁN NEGATIVO' : (isInvoice ? 'FACTURA DE ANULACIÓN' : 'JUSTIFICANTE DE ANULACIÓN');
        const docRefLabel = isAlbaran ? 'Nº ALBARÁN NEGATIVO' : (isInvoice ? 'Nº FACTURA ANULACIÓN' : 'Nº ANULACIÓN');
        const origDocLabel = isAlbaran ? 'ALBARÁN ORIGINAL' : (isInvoice ? 'FACTURA ORIGINAL' : 'TICKET ORIGINAL ANULADO');
        const assignedPrinter = this.getAssignedPrinter('annulment');

        const topToolbar = autoPrint ? '' : `
            <div class="no-print" style="background: #1e293b; color: white; padding: 8px 12px; margin: -10px -10px 12px -10px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: -10px; z-index: 100; box-shadow: 0 2px 4px rgba(0,0,0,0.15); font-family: system-ui, sans-serif;">
                <span style="font-weight: bold; font-size: 13px;">👁️ Vista Previa: ${docTitle} &nbsp;|&nbsp; 🖨️ <span style="color: #60a5fa;">${assignedPrinter.name}</span></span>
                <div>
                    <button onclick="window.print()" style="background: #16a34a; color: white; border: none; padding: 5px 12px; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 12px; margin-right: 6px;">🖨️ Imprimir</button>
                    <button onclick="window.close()" style="background: #475569; color: white; border: none; padding: 5px 10px; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 12px;">✖ Cerrar</button>
                </div>
            </div>
        `;

        const printScript = autoPrint ? `
            <script>
                window.onload = function() {
                    window.print();
                    window.close();
                };
            </script>
        ` : '';

        receiptWindow.document.write(`
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>[${assignedPrinter.name}] ${docTitle} ${refAnnul}</title>
                <style>
                    @page {
                        size: ${assignedPrinter.format === 'a4' ? 'A4 portrait' : '80mm auto'};
                        margin: ${assignedPrinter.format === 'a4' ? '12mm' : '0'};
                    }
                    @media print { .no-print { display: none !important; } }
                    body { font-family: monospace, sans-serif; font-size: 12px; margin: 0; padding: 10px; color: #000; }
                    .text-center { text-align: center; }
                    .fw-bold { font-weight: bold; }
                    .divider { border-bottom: 1px dashed #000; margin: 8px 0; }
                    .annul-box {
                        border: 2px dashed #b71c1c;
                        background: #ffebee;
                        color: #b71c1c;
                        padding: 8px;
                        text-align: center;
                        margin-bottom: 10px;
                        font-weight: bold;
                    }
                </style>
            </head>
            <body>
                ${topToolbar}
                <div class="text-center fw-bold" style="font-size: 15px;">${comp.name || 'UTRECAR S.L.'}</div>
                <div class="text-center" style="font-size: 11px;">
                    ${comp.vat ? `CIF: ${comp.vat}<br/>` : ''}
                    ${comp.street || ''} ${comp.city || ''}<br/>
                    ${comp.phone ? `Tlf: ${comp.phone}` : ''}
                </div>
                <div class="divider"></div>
                
                <div class="annul-box">
                    <div style="font-size: 13px; letter-spacing: 1px;">*** ${docTitle} ***</div>
                    <div style="font-size: 15px; margin-top: 3px;">${docRefLabel}: ${refAnnul}</div>
                    <div style="font-size: 11px; margin-top: 2px;">FECHA: ${dateAnnul}</div>
                </div>

                <div style="font-size: 11px; margin-bottom: 6px;">
                    <div><strong>${origDocLabel}:</strong> ${order.name}</div>
                    <div><strong>FECHA EMISIÓN:</strong> ${order.date_order}</div>
                    ${order.pump_name ? `<div><strong>CALLE / SURTIDOR:</strong> ${order.pump_name}</div>` : (order.pump_id ? `<div><strong>CALLE:</strong> Calle ${order.pump_id}</div>` : '')}
                    ${order.partner_name ? `<div><strong>CLIENTE:</strong> ${order.partner_name}</div>` : ''}
                    <div style="margin-top: 4px; font-style: italic;"><strong>MOTIVO:</strong> ${reasonAnnul}</div>
                </div>

                <div class="divider"></div>
                <table style="width: 100%; border-collapse: collapse; font-size: 11px;">
                    <thead>
                        <tr style="border-bottom: 1px solid #000;">
                            <th style="text-align: left; padding-bottom: 3px;">Artículo</th>
                            <th style="text-align: right; padding-bottom: 3px;">Cant.</th>
                            <th style="text-align: right; padding-bottom: 3px;">Precio</th>
                            <th style="text-align: right; padding-bottom: 3px;">Rectificado</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${linesHtml}
                    </tbody>
                </table>
                <div class="divider"></div>

                <div style="display: flex; justify-content: space-between; font-size: 14px; font-weight: bold; color: #b71c1c; margin-top: 6px;">
                    <span>TOTAL RECTIFICADO:</span>
                    <span>-${Number(order.amount_total).toFixed(2)} €</span>
                </div>

                <div class="divider"></div>
                <div class="text-center" style="font-size: 10px; margin-top: 10px; color: #444;">
                    Documento de trazabilidad fiscal y rectificación de ticket.<br/>
                    Conservar junto con el cierre de turno.
                </div>
                ${printScript}
            </body>
            </html>
        `);
        receiptWindow.document.close();
    }

    selectShiftOrder(order) {
        this.state.selectedShiftOrder = order;
        this.state.shiftActiveTab = 'products';
    }

    backToShiftOrdersList() {
        this.state.selectedShiftOrder = null;
    }

    setShiftTab(tab) {
        this.state.shiftActiveTab = tab;
    }

    printShiftOrderTicket(order, isCopy = false, autoPrint = null) {
        if (!order) return;
        if (order.doc_type === 'invoice' || order.is_invoiced) {
            return this.printShiftOrderInvoice(order);
        }
        const comp = order.company || {};
        const linesHtml = (order.lines || []).map(l => `
            <tr>
                <td style="text-align: left; padding: 4px 0;">${l.product_name}</td>
                <td style="text-align: right; padding: 4px 0;">${Number(l.qty).toFixed(2)}</td>
                <td style="text-align: right; padding: 4px 0;">${Number(l.price_unit).toFixed(3)} €</td>
                <td style="text-align: right; padding: 4px 0; font-weight: bold;">${Number(l.price_subtotal_incl).toFixed(2)} €</td>
            </tr>
        `).join("");

        const paymentsHtml = order.is_albaran ? `
            <div style="display: flex; justify-content: space-between; margin-bottom: 2px; font-weight: bold;">
                <span>Forma de Pago:</span>
                <span>A CUENTA (CRÉDITO)</span>
            </div>
        ` : (order.payments || []).map(p => `
            <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                <span>${p.name}:</span>
                <span style="font-weight: bold;">${Number(p.amount).toFixed(2)} €</span>
            </div>
        `).join("");

        const clientHtml = order.partner_name ? `
            <div style="margin-top: 6px; font-size: 11px; border: ${order.is_albaran ? '1px solid #000' : '1px dashed #bbb'}; padding: 6px; border-radius: 4px;">
                <strong>${order.is_albaran ? 'CLIENTE DE CRÉDITO:' : 'CLIENTE:'}</strong> ${order.partner_name}<br/>
                ${order.partner_vat ? `<strong>CIF/NIF:</strong> ${order.partner_vat}<br/>` : ''}
                ${order.partner_street ? `${order.partner_street}, ${order.partner_zip ? order.partner_zip + " " : ""}${order.partner_city || ''}<br/>` : ''}
                ${order.vehicle_plate ? `<strong>MATRÍCULA:</strong> ${order.vehicle_plate}<br/>` : ''}
                ${order.vehicle_driver ? `<strong>CONDUCTOR / DNI:</strong> ${order.vehicle_driver}<br/>` : ''}
            </div>
        ` : (order.vehicle_plate ? `
            <div style="margin-top: 6px; font-size: 12px; border: 1.5px dashed #333; padding: 5px 8px; border-radius: 4px; text-align: center; background-color: #f8fafc;">
                <strong>MATRÍCULA:</strong> <span style="font-size: 14px; font-weight: 900; letter-spacing: 1.5px; font-family: monospace;">${order.vehicle_plate}</span>
            </div>
        ` : '');

        const invoiceHtml = order.is_invoiced ? `
            <div style="margin-top: 6px; padding: 4px; background: #e8f5e9; border: 1px solid #81c784; text-align: center; font-weight: bold; font-size: 11px; border-radius: 4px;">
                FACTURA ASOCIADA: ${order.account_move_name}
            </div>
        ` : '';

        const copyBanner = isCopy ? `
            <div style="border: 2px solid #000; padding: 6px; text-align: center; font-weight: bold; font-size: 14px; margin-bottom: 8px; letter-spacing: 2px;">
                *** COPIA DE ${order.is_albaran ? 'ALBARÁN' : 'TICKET'} ***
            </div>
        ` : '';

        const albaranBanner = order.is_albaran ? `
            <div style="border: 2px solid #000; padding: 6px; text-align: center; margin-bottom: 8px;">
                <div style="font-size: 13px; font-weight: 900; letter-spacing: 1px;">ALBARÁN DE SUMINISTRO A CRÉDITO</div>
                <div style="font-size: 16px; font-weight: 900; margin-top: 2px;">ALBARÁN Nº: ${order.name}</div>
            </div>
        ` : '';

        const isAnnulled = order.is_ticket_annulled || Boolean(order.annulment_ref);
        const annulBanner = isAnnulled ? `
            <div style="border: 2px dashed #b71c1c; background: #ffebee; color: #b71c1c; padding: 6px; text-align: center; margin-bottom: 8px; font-weight: bold; font-size: 11px;">
                <div style="font-size: 13px; letter-spacing: 1px;">*** DOCUMENTO ANULADO ***</div>
                <div>REF. ANULACIÓN: ${order.annulment_ref || 'TTTR_ANUL'}</div>
                ${order.is_invoiced ? `<div>SUSTITUIDO POR FACTURA: ${order.account_move_name}</div>` : ''}
            </div>
        ` : '';

        const albaranSignature = order.is_albaran ? `
            <div style="border-top: 1px solid #000; margin-top: 15px; padding-top: 8px; font-size: 11px;">
                <div style="font-weight: bold; margin-bottom: 22px;">Firma del Conductor / Conforme:</div>
                <div style="height: 35px; border-bottom: 1px solid #555; margin-bottom: 6px;"></div>
                <div>Nombre / DNI: ${order.vehicle_driver || '__________________________________'}</div>
                <div style="margin-top: 2px;">Matrícula: ${order.vehicle_plate || '__________________________________'}</div>
                <div style="text-align: center; font-size: 10px; margin-top: 8px; font-style: italic;">
                    Documento de entrega de mercancía a crédito.<br/>Facturación agrupada a fin de periodo.
                </div>
            </div>
        ` : '';

        const docType = order.is_albaran ? 'albaran' : (order.is_invoiced ? 'invoice' : 'ticket');
        const assignedPrinter = this.getAssignedPrinter(docType);

        const shouldAutoPrint = (autoPrint !== null && autoPrint !== undefined)
            ? Boolean(autoPrint)
            : (this.state.printerConfig && this.state.printerConfig.directPrint !== undefined
                ? Boolean(this.state.printerConfig.directPrint)
                : Boolean(assignedPrinter.autoPrint));

        const receiptWindow = window.open("", "_blank", "width=420,height=680");
        if (!receiptWindow) {
            alert("Por favor permita las ventanas emergentes en su navegador para imprimir o visualizar.");
            return;
        }

        const topToolbar = shouldAutoPrint ? '' : `
            <div class="no-print" style="background: #1e293b; color: white; padding: 8px 12px; margin: -16px -16px 14px -16px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: -16px; z-index: 100; box-shadow: 0 2px 4px rgba(0,0,0,0.15); font-family: system-ui, sans-serif;">
                <span style="font-weight: bold; font-size: 13px;">👁️ Vista Previa: ${order.is_albaran ? 'Albarán de Crédito' : 'Ticket de Venta'} &nbsp;|&nbsp; 🖨️ <span style="color: #60a5fa;">${assignedPrinter.name}</span> (${assignedPrinter.format === 'a4' ? 'A4' : '80mm'})</span>
                <div>
                    <button onclick="window.print()" style="background: #16a34a; color: white; border: none; padding: 5px 12px; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 12px; margin-right: 6px;">🖨️ Imprimir</button>
                    <button onclick="window.close()" style="background: #475569; color: white; border: none; padding: 5px 10px; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 12px;">✖ Cerrar</button>
                </div>
            </div>
        `;

        const printScript = shouldAutoPrint ? `
            <script>
                window.onload = function() {
                    window.print();
                };
            </script>
        ` : '';

        receiptWindow.document.write(`
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>[${assignedPrinter.name}] ${order.is_albaran ? 'Albarán' : 'Ticket'} ${order.name}${isCopy ? ' (COPIA)' : ''}</title>
                <style>
                    body { font-family: 'Courier New', monospace; font-size: 12px; margin: 0; padding: 16px; color: #000; }
                    .header { text-align: center; margin-bottom: 10px; }
                    .header h2 { margin: 0 0 4px 0; font-size: 15px; font-weight: bold; }
                    .header p { margin: 1px 0; font-size: 11px; }
                    .divider { border-bottom: 1px dashed #000; margin: 8px 0; }
                    .meta { font-size: 11px; margin-bottom: 8px; }
                    .meta-row { display: flex; justify-content: space-between; margin-bottom: 2px; }
                    table { width: 100%; border-collapse: collapse; font-size: 11px; }
                    th { border-bottom: 1px solid #000; padding: 3px 0; font-size: 11px; }
                    .total-section { margin-top: 8px; font-size: 12px; }
                    .total-row { display: flex; justify-content: space-between; margin-bottom: 3px; }
                    .grand-total { font-size: 15px; font-weight: bold; border-top: 1px solid #000; border-bottom: 1px solid #000; padding: 4px 0; margin: 6px 0; }
                    .footer { text-align: center; margin-top: 15px; font-size: 11px; }
                    @page {
                        size: ${assignedPrinter.format === 'a4' ? 'A4 portrait' : '80mm auto'};
                        margin: ${assignedPrinter.format === 'a4' ? '12mm' : '0'};
                    }
                    @media print {
                        .no-print { display: none !important; }
                        body { padding: 0; }
                    }
                </style>
            </head>
            <body>
                ${topToolbar}
                ${copyBanner}
                ${albaranBanner}
                ${annulBanner}
                <div class="header">
                    <h2>${comp.name || 'ESTACIÓN DE SERVICIO'}</h2>
                    ${comp.vat ? `<p>CIF: ${comp.vat}</p>` : ''}
                    ${comp.street ? `<p>${comp.street}</p>` : ''}
                    ${comp.city ? `<p>${comp.city}</p>` : ''}
                    ${comp.phone ? `<p>Tel: ${comp.phone}</p>` : ''}
                </div>
                <div class="divider"></div>
                <div class="meta">
                    ${isCopy ? `<div class="meta-row"><span>DOCUMENTO:</span><strong>COPIA</strong></div>` : ''}
                    <div class="meta-row"><span>${order.is_albaran ? 'Nº ALBARÁN:' : 'Nº TICKET (SERIE):'}</span><strong>${order.name}</strong></div>
                    ${order.is_albaran ? '<div class="meta-row"><span>MODALIDAD:</span><strong>CRÉDITO (ALBARÁN)</strong></div>' : ''}
                    ${isAnnulled ? `<div class="meta-row"><span>ESTADO:</span><strong style="color: #b71c1c;">ANULADO (${order.annulment_ref})</strong></div>` : ''}
                    <div class="meta-row"><span>FECHA:</span><span>${order.date_order}</span></div>
                    <div class="meta-row"><span>SESIÓN:</span><span>${order.session_name}</span></div>
                    <div class="meta-row"><span>REF:</span><span>${order.pos_reference}</span></div>
                </div>
                ${clientHtml}
                ${invoiceHtml}
                <div class="divider"></div>
                <table>
                    <thead>
                        <tr>
                            <th style="text-align: left;">DESCRIPCIÓN</th>
                            <th style="text-align: right;">CANT</th>
                            <th style="text-align: right;">PRECIO</th>
                            <th style="text-align: right;">TOTAL</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${linesHtml}
                    </tbody>
                </table>
                <div class="divider"></div>
                <div class="total-section">
                    <div class="total-row"><span>Base Imponible:</span><span>${(order.amount_total - order.amount_tax).toFixed(2)} €</span></div>
                    <div class="total-row"><span>IVA:</span><span>${Number(order.amount_tax).toFixed(2)} €</span></div>
                    <div class="total-row grand-total"><span>TOTAL:</span><span>${Number(order.amount_total).toFixed(2)} €</span></div>
                </div>
                <div style="margin-top: 6px;">
                    ${paymentsHtml}
                </div>
                ${albaranSignature}
                <div class="footer">
                    <p>*** ${order.is_albaran ? 'ALBARÁN FIRMADO POR EL CLIENTE' : 'GRACIAS POR SU VISITA'} ***</p>
                </div>
                ${printScript}
            </body>
            </html>
        `);
        receiptWindow.document.close();
    }

    openInvoiceModal(order) {
        if (!order) return;
        if (order.is_ticket_annulled || order.has_annulment || order.state === 'cancel' || (order.amount_total || 0) <= 0) {
            alert("⚠️ Un ticket que ha sido anulado o un ticket de anulación no se puede facturar.");
            return;
        }
        if (order.is_invoiced) {
            alert("⚠️ Este ticket ya ha sido facturado.");
            return;
        }
        this.state.isInvoiceModalOpen = true;
        this.state.invoicePartnerSearch = "";
        this.state.invoicePartnerCodeSearch = "";
        this.state.invoicePartnerResults = [];
        this.state.invoiceSelectedPartner = order.partner_id ? {
            id: order.partner_id,
            name: order.partner_name,
            vat: order.partner_vat,
            street: order.partner_street,
            city: order.partner_city,
            zip: order.partner_zip
        } : null;
        this.state.invoiceNewPartner = { name: "", vat: "", street: "", city: "", zip: "", email: "", phone: "" };
        this.state.isCreatingPartner = !order.partner_id;
    }

    closeInvoiceModal() {
        this.state.isInvoiceModalOpen = false;
        this.state.invoiceSelectedPartner = null;
        this.state.invoicePartnerSearch = "";
        this.state.invoicePartnerCodeSearch = "";
        this.state.invoicePartnerResults = [];
    }

    async onInvoicePartnerCodeSearch(ev) {
        this.state.invoicePartnerCodeSearch = ev.target.value;
        await this.searchInvoicePartners();
    }

    async onInvoicePartnerSearch(ev) {
        this.state.invoicePartnerSearch = ev.target.value;
        await this.searchInvoicePartners();
    }

    async clearInvoicePartnerCodeSearch() {
        this.state.invoicePartnerCodeSearch = "";
        await this.searchInvoicePartners();
    }

    async clearInvoicePartnerSearch() {
        this.state.invoicePartnerSearch = "";
        await this.searchInvoicePartners();
    }

    async searchInvoicePartners() {
        const query = (this.state.invoicePartnerSearch || "").trim();
        const codeQuery = (this.state.invoicePartnerCodeSearch || "").trim();

        if (codeQuery.length >= 1 || query.length >= 2) {
            try {
                const configId = this.configId || (this.pos && this.pos.config ? this.pos.config.id : null);
                const companyId = this.pos && this.pos.company ? this.pos.company.id : (this.pos && this.pos.config && this.pos.config.company_id ? (Array.isArray(this.pos.config.company_id) ? this.pos.config.company_id[0] : this.pos.config.company_id.id || this.pos.config.company_id) : null);
                const res = await this.env.services.rpc("/pos_gas_station/search_partners", {
                    query: query,
                    code_query: codeQuery,
                    config_id: configId,
                    company_id: companyId
                });
                if (res && res.status === "success") {
                    this.state.invoicePartnerResults = res.partners || [];
                }
            } catch (e) {
                console.error("Error search_partners:", e);
            }
        } else {
            this.state.invoicePartnerResults = [];
        }
    }

    selectPartnerForInvoice(partner) {
        this.state.invoiceSelectedPartner = partner;
        this.state.invoicePartnerResults = [];
        this.state.invoicePartnerSearch = partner.name + (partner.vat ? ` (${partner.vat})` : "");
        this.state.invoicePartnerCodeSearch = partner.ref || "";
        this.state.invoiceEmail = partner.email || "";
        this.state.isCreatingPartner = false;
    }

    clearSelectedPartnerForInvoice() {
        this.state.invoiceSelectedPartner = null;
        this.state.invoicePartnerSearch = "";
        this.state.invoicePartnerCodeSearch = "";
        this.state.invoiceEmail = "";
    }

    toggleCreatePartnerMode() {
        this.state.isCreatingPartner = !this.state.isCreatingPartner;
        if (this.state.isCreatingPartner) {
            this.state.invoiceSelectedPartner = null;
        }
    }

    async confirmInvoiceOrder(deliveryMethod = 'both') {
        const order = this.state.selectedShiftOrder;
        if (!order) return;

        let partnerId = this.state.invoiceSelectedPartner ? this.state.invoiceSelectedPartner.id : null;
        let partnerData = null;

        if (!partnerId) {
            const p = this.state.invoiceNewPartner;
            if (!p.vat || !p.vat.trim()) {
                alert("⚠️ Debe indicar el NIF/CIF del cliente para facturar.");
                return;
            }
            if (!p.name || !p.name.trim()) {
                alert("⚠️ Debe indicar el nombre o razón social del cliente.");
                return;
            }
            partnerData = { ...p, email: (this.state.invoiceEmail || p.email || '').trim() };
        }

        let targetEmail = (this.state.invoiceEmail || (partnerData ? partnerData.email : '')).trim();
        if (deliveryMethod === 'email' || deliveryMethod === 'both') {
            if (!targetEmail || !targetEmail.includes('@')) {
                const asked = prompt("Introduzca el correo electrónico del cliente para enviar la factura:", targetEmail || "");
                if (!asked || !asked.includes('@')) {
                    alert("⚠️ Debe indicar un correo electrónico válido para enviar la factura por email.");
                    return;
                }
                targetEmail = asked.trim();
                this.state.invoiceEmail = targetEmail;
            }
        }

        this.state.invoiceLoading = true;
        try {
            const res = await this.env.services.rpc("/pos_gas_station/invoice_order", {
                order_id: order.id,
                partner_id: partnerId,
                partner_data: partnerData,
                delivery_method: deliveryMethod,
                target_email: targetEmail
            });

            if (res && res.status === "success") {
                order.is_invoiced = true;
                order.state = 'invoiced';
                order.is_ticket_annulled = true;
                order.annulment_ref = res.annulment_ref;
                order.annulment_reason = `Sustituido por Factura ${res.account_move_name}`;
                order.account_move_id = res.account_move_id;
                order.account_move_name = res.account_move_name;
                order.invoice_url = res.invoice_url;
                order.partner_email = targetEmail;
                if (partnerData) {
                    order.partner_name = partnerData.name;
                    order.partner_vat = partnerData.vat;
                } else if (this.state.invoiceSelectedPartner) {
                    order.partner_name = this.state.invoiceSelectedPartner.name;
                    order.partner_vat = this.state.invoiceSelectedPartner.vat;
                }
                this.closeInvoiceModal();
                
                let msg = `✅ Factura ${res.account_move_name} generada con éxito.\nEl ticket ${order.name} ha sido anulado con Ref: ${order.annulment_ref}.`;
                if (res.email_sent) {
                    msg += `\n\n📧 Enviada por correo a: ${res.email_to}`;
                } else if (res.email_error) {
                    msg += `\n\n⚠️ Aviso email: ${res.email_error}`;
                }
                alert(msg);

                if ((deliveryMethod === 'paper' || deliveryMethod === 'both') && res.invoice_url) {
                    window.open(res.invoice_url, "_blank");
                }
                await this.loadShiftOrders();
            } else {
                alert("Error al facturar: " + (res ? res.message : "Error desconocido"));
            }
        } catch (e) {
            console.error("Error confirmInvoiceOrder:", e);
            alert("Error al comunicarse con el servidor al facturar: " + e.message);
        } finally {
            this.state.invoiceLoading = false;
        }
    }

    openAnnulOrderModal(order) {
        if (!order) return;
        this.state.annulModalOrder = order;
        this.state.isAnnulingOrder = false;
        this.state.isAnnulOrderModalOpen = true;
    }

    closeAnnulOrderModal() {
        this.state.isAnnulOrderModalOpen = false;
        this.state.annulModalOrder = null;
        this.state.isAnnulingOrder = false;
    }

    async executeAnnulOrder() {
        if (!this.state.annulModalOrder || this.state.isAnnulingOrder) return;
        this.state.isAnnulingOrder = true;
        const order = this.state.annulModalOrder;
        const isInv = Boolean(order.is_invoiced || order.doc_type === 'invoice');
        const isAlb = Boolean(order.is_albaran || order.doc_type === 'albaran');
        const docLabel = isInv ? "Factura" : (isAlb ? "Albarán" : "Ticket");
        const reason = `Anulación de ${docLabel.toLowerCase()}`;

        try {
            const res = await this.env.services.rpc("/pos_gas_station/annul_order", {
                order_id: order.id,
                reason: reason
            });
            if (res && res.status === "success") {
                order.is_ticket_annulled = true;
                order.state = "annulled";
                order.annulment_ref = res.annulment_ref;
                order.annulment_reason = res.annulment_reason;
                if (this.state.selectedShiftOrder && this.state.selectedShiftOrder.id === order.id) {
                    this.state.selectedShiftOrder.is_ticket_annulled = true;
                    this.state.selectedShiftOrder.state = "annulled";
                    this.state.selectedShiftOrder.annulment_ref = res.annulment_ref;
                    this.state.selectedShiftOrder.annulment_reason = res.annulment_reason;
                }
                this.closeAnnulOrderModal();
                await this.loadShiftOrders();
            } else {
                alert(`Error al anular ${docLabel.toLowerCase()}: ` + (res ? res.message : "Error desconocido"));
            }
        } catch (e) {
            console.error("Error executeAnnulOrder:", e);
            alert("Error al comunicarse con el servidor: " + e.message);
        } finally {
            this.state.isAnnulingOrder = false;
        }
    }

    openConvertAlbaranModal(order) {
        if (!order) return;
        this.state.convertAlbaranOrder = order;
        this.state.convertAlbaranPlate = order.vehicle_plate || "";
        this.state.convertAlbaranDriver = order.vehicle_driver || "";
        this.state.convertAlbaranPartnerSearch = "";
        this.state.convertAlbaranPartnerResults = [];
        this.state.convertAlbaranLoading = false;

        const hasCredit = (order.partner_customer_payment_mode === 'credit' || order.partner_customer_type === 'credit' || order.partner_customer_type === 'monthly') && !order.partner_credit_blocked;

        if (order.partner_id && hasCredit) {
            this.state.convertAlbaranSelectedPartner = {
                id: order.partner_id,
                name: order.partner_name,
                vat: order.partner_vat,
                street: order.partner_street,
                city: order.partner_city,
                customer_type: order.partner_customer_type,
                customer_payment_mode: order.partner_customer_payment_mode,
                credit_blocked: order.partner_credit_blocked,
                hasCredit: true,
                vehicles: order.partner_vehicles || []
            };
        } else {
            this.state.convertAlbaranSelectedPartner = null;
        }

        this.state.isConvertAlbaranModalOpen = true;
        if (!this.state.convertAlbaranSelectedPartner) {
            this.loadCreditPartnersForAlbaran("");
        }
    }

    closeConvertAlbaranModal() {
        this.state.isConvertAlbaranModalOpen = false;
        this.state.convertAlbaranOrder = null;
        this.state.convertAlbaranSelectedPartner = null;
        this.state.convertAlbaranPartnerResults = [];
    }

    onConvertAlbaranPartnerSearch(ev) {
        const val = (ev.target.value || "").trim();
        this.state.convertAlbaranPartnerSearch = val;
        this.loadCreditPartnersForAlbaran(val);
    }

    async loadCreditPartnersForAlbaran(query = "") {
        this.state.convertAlbaranLoading = true;
        try {
            const configId = this.configId || (this.pos && this.pos.config ? this.pos.config.id : null);
            const companyId = this.pos && this.pos.company ? this.pos.company.id : (this.pos && this.pos.config && this.pos.config.company_id ? (Array.isArray(this.pos.config.company_id) ? this.pos.config.company_id[0] : this.pos.config.company_id.id || this.pos.config.company_id) : null);
            const res = await this.env.services.rpc("/pos_gas_station/search_partners", {
                query: (query || "").trim(),
                credit_only: true,
                config_id: configId,
                company_id: companyId
            });
            if (res && res.status === "success") {
                this.state.convertAlbaranPartnerResults = (res.partners || []).map(p => ({
                    ...p,
                    hasCredit: (p.customer_payment_mode === 'credit' || p.customer_type === 'credit' || p.customer_type === 'monthly') && !p.credit_blocked
                }));
            } else {
                this.state.convertAlbaranPartnerResults = [];
            }
        } catch (e) {
            console.error("Error search_partners credit:", e);
            this.state.convertAlbaranPartnerResults = [];
        } finally {
            this.state.convertAlbaranLoading = false;
        }
    }

    selectPartnerForConvertAlbaran(partner) {
        if (!partner.hasCredit) {
            alert("⚠️ El cliente seleccionado no tiene crédito autorizado en Administración.");
            return;
        }
        if (partner.credit_blocked) {
            alert("⚠️ El cliente seleccionado tiene el crédito bloqueado en Administración.");
            return;
        }
        this.state.convertAlbaranSelectedPartner = partner;
        if (partner && partner.vehicles && partner.vehicles.length > 0 && !this.state.convertAlbaranPlate) {
            this.state.convertAlbaranPlate = partner.vehicles[0].name;
        }
    }

    clearSelectedPartnerForConvertAlbaran() {
        this.state.convertAlbaranSelectedPartner = null;
        this.state.convertAlbaranPartnerSearch = "";
        this.loadCreditPartnersForAlbaran("");
    }

    async confirmConvertToAlbaran() {
        const order = this.state.convertAlbaranOrder;
        if (!order) return;

        const partner = this.state.convertAlbaranSelectedPartner;
        if (!partner) {
            alert("⚠️ Por favor seleccione un cliente con crédito autorizado de la lista.");
            return;
        }

        const confirmText = order.is_invoiced
            ? `¿Está seguro de que desea anular la factura ${order.account_move_name} y convertir este pedido en Albarán de Crédito para ${partner.name}?`
            : `¿Está seguro de que desea convertir el ticket ${order.name} en Albarán de Crédito para ${partner.name}?`;

        if (!confirm(confirmText)) return;

        this.state.convertAlbaranLoading = true;
        try {
            const res = await this.env.services.rpc("/pos_gas_station/convert_to_albaran", {
                order_id: order.id,
                partner_id: partner.id,
                vehicle_plate: this.state.convertAlbaranPlate,
                vehicle_driver: this.state.convertAlbaranDriver
            });

            if (res && res.status === "success") {
                this.closeConvertAlbaranModal();
                alert(`✅ ${res.message || "Pedido convertido con éxito en Albarán de Crédito."}`);
                await this.loadShiftOrders();

                const updatedOrder = (this.state.shiftOrders || []).find(o => o.id === order.id);
                if (updatedOrder) {
                    this.state.selectedShiftOrder = updatedOrder;
                    if (confirm("¿Desea imprimir el Albarán de Crédito firmado ahora?")) {
                        this.printShiftOrderTicket(updatedOrder, false);
                    }
                }
            } else {
                alert("Error al convertir a albarán: " + (res ? res.message : "Error desconocido"));
            }
        } catch (e) {
            console.error("Error confirmConvertToAlbaran:", e);
            alert("Error al comunicarse con el servidor: " + (e.message || e));
        } finally {
            this.state.convertAlbaranLoading = false;
        }
    }

    canOrderBeExtracted(ord) {
        if (!ord) return false;
        if (ord.is_albaran || ord.doc_type === 'albaran') return false;
        if (ord.is_invoiced || ord.doc_type === 'invoice') return false;
        if (ord.is_ticket_annulled || ord.has_annulment || ord.annulment_ref) return false;
        if (ord.is_extraction) return false;
        if ((ord.amount_total || 0) <= 0) return false;
        return true;
    }

    openShiftOrderExtractionModal(order) {
        if (!order) return;
        this.state.extractionTargetOrder = order;
        this.state.extractionReason = "Prueba de probeta / Calibración metrológica";
        this.state.extractionNotes = "";
        this.state.isSavingExtraction = false;
        this.state.isExtractionModalOpen = true;
    }

    get extractionDisplayLines() {
        if (this.state.extractionTargetOrder && this.state.extractionTargetOrder.lines) {
            return this.state.extractionTargetOrder.lines;
        }
        return this.currentOrderLines || [];
    }

    get extractionDisplayTotalLiters() {
        if (this.state.extractionTargetOrder) {
            if (this.state.extractionTargetOrder.lines) {
                return this.state.extractionTargetOrder.lines.reduce((tot, l) => tot + (l.quantity || l.qty || 0), 0.0);
            }
            return 0.0;
        }
        return this.currentOrderTotalLiters;
    }

    get currentOrderTotalLiters() {
        const lines = this.currentOrderLines;
        if (!lines) return 0.0;
        let tot = 0.0;
        for (const l of lines) {
            tot += (l.quantity || l.qty || 0);
        }
        return tot;
    }

    openExtractionModal() {
        if (!this.currentOrderLines || this.currentOrderLines.length === 0) {
            alert("⚠️ No hay ningún suministro o producto en el ticket actual para registrar como extracción.");
            return;
        }
        this.state.extractionTargetOrder = null;
        this.state.extractionReason = "Prueba de probeta / Calibración metrológica";
        this.state.extractionNotes = "";
        this.state.isSavingExtraction = false;
        this.state.isExtractionModalOpen = true;
    }

    closeExtractionModal() {
        this.state.isExtractionModalOpen = false;
        this.state.isSavingExtraction = false;
        this.state.extractionTargetOrder = null;
    }

    async confirmExtraction() {
        this.state.isSavingExtraction = true;
        try {
            // CASO 1: Extracción realizada sobre un ticket existente en el historial
            if (this.state.extractionTargetOrder) {
                const targetOrder = this.state.extractionTargetOrder;
                const pumpVal = targetOrder.pump_id || (targetOrder.lines && targetOrder.lines[0] ? targetOrder.lines[0].pump_id : 0) || 0;
                const res = await this.env.services.rpc("/pos_gas_station/register_extraction", {
                    order_id: targetOrder.id,
                    reason: this.state.extractionReason,
                    notes: this.state.extractionNotes,
                    pump_id: pumpVal
                });

                if (res && res.status === "success") {
                    this.closeExtractionModal();
                    alert(`✅ Extracción registrada con éxito.\n${(res.liters || 0).toFixed(2)} Litros retornados al depósito.\nNo se descuenta de existencias ni se le resta al empleado.`);
                    await this.loadShiftOrders();
                    if (this.state.selectedShiftOrder && this.state.selectedShiftOrder.id === targetOrder.id) {
                        const updatedOrder = (this.state.shiftOrders || []).find(o => o.id === targetOrder.id);
                        if (updatedOrder) {
                            this.state.selectedShiftOrder = updatedOrder;
                        }
                    }
                } else {
                    alert("Error al registrar extracción: " + (res ? res.message : "Error desconocido"));
                }
                return;
            }

            // CASO 2: Extracción desde el ticket activo del TPV
            const lines = this.currentOrderLines;
            if (!lines || lines.length === 0) return;

            const orderLinesData = lines.map(l => ({
                product_id: l.product_id ? l.product_id.id : null,
                qty: l.quantity || l.qty || 0,
                price_unit: l.price_unit || 0,
                pump_id: l.pump_id || 0,
                fuel_code: l.fuel_code || ''
            }));

            const sessionId = (this.pos && this.pos.pos_session) ? this.pos.pos_session.id : (this.state.shiftViewSessionId || null);

            const res = await this.env.services.rpc("/pos_gas_station/register_extraction", {
                session_id: sessionId,
                order_lines: orderLinesData,
                reason: this.state.extractionReason,
                pump_id: lines[0] ? (lines[0].pump_id || 0) : 0,
                notes: this.state.extractionNotes
            });

            if (res && res.status === "success") {
                this.closeExtractionModal();
                this.clearCurrentOrder();
                alert(`✅ Extracción registrada con éxito.\n${res.liters.toFixed(2)} Litros retornados al depósito.\nNo se descuenta de existencias ni se le resta al empleado.`);
                await this.loadShiftOrders();
            } else {
                alert("Error al registrar extracción: " + (res ? res.message : "Error desconocido"));
            }
        } catch (e) {
            console.error("Error confirmExtraction:", e);
            alert("Error al registrar extracción: " + (e.message || e));
        } finally {
            this.state.isSavingExtraction = false;
        }
    }

    printShiftReport() {
        alert("El informe de cierre de turno solo se puede imprimir una vez que el turno haya sido formalmente cerrado.");
    }

    printShiftOrderInvoice(order) {
        if (!order || !order.invoice_url) {
            alert("Este pedido aún no tiene factura generada.");
            return;
        }
        window.open(order.invoice_url, "_blank");
    }

    printShiftOrderRefundInvoice(order, historyItem) {
        const invUrl = (historyItem && historyItem.invoice_url) || (order && order.invoice_url);
        if (!invUrl) {
            alert("No se ha encontrado el documento PDF de la Factura Rectificativa.");
            return;
        }
        window.open(invUrl, "_blank");
    }

    emailShiftOrderInvoice(order) {
        if (!order) return;
        this.state.emailInvoiceOrder = order;
        this.state.emailInvoiceTarget = order.partner_email || order.email || "";
        this.state.isSendingInvoiceEmail = false;
        this.state.emailInvoiceSuccessMessage = "";
        this.state.emailInvoiceErrorMessage = "";
        this.state.wasShiftOrdersOpenBeforeEmail = this.state.isShiftOrdersModalOpen;
        this.state.savedShiftOrderBeforeEmail = this.state.selectedShiftOrder;

        // Cerrar la ventana flotante actual (pedidos) para que la de email quede sola y activa en primer plano
        this.state.isShiftOrdersModalOpen = false;
        this.state.isEmailInvoiceModalOpen = true;
    }

    emailShiftOrderRefundInvoice(order, historyItem) {
        if (!order) return;
        const refundMoveId = (historyItem && historyItem.account_move_id) || order.account_move_id;
        const refundRef = (historyItem && historyItem.ref) || order.annulment_ref;
        const refundOrder = Object.assign({}, order, {
            account_move_id: refundMoveId,
            name: refundRef,
            account_move_name: refundRef,
            invoice_url: (historyItem && historyItem.invoice_url) || order.invoice_url
        });
        this.emailShiftOrderInvoice(refundOrder);
    }

    closeEmailInvoiceModal() {
        this.state.isEmailInvoiceModalOpen = false;
        const reopen = this.state.wasShiftOrdersOpenBeforeEmail;
        const savedOrder = this.state.savedShiftOrderBeforeEmail;
        this.state.emailInvoiceOrder = null;
        this.state.emailInvoiceTarget = "";
        this.state.isSendingInvoiceEmail = false;
        this.state.emailInvoiceSuccessMessage = "";
        this.state.emailInvoiceErrorMessage = "";
        this.state.wasShiftOrdersOpenBeforeEmail = false;
        this.state.savedShiftOrderBeforeEmail = null;

        // Si venía de la ventana flotante de pedidos, volver a abrirla para continuar
        if (reopen) {
            this.state.selectedShiftOrder = savedOrder;
            this.state.isShiftOrdersModalOpen = true;
        }
    }

    async confirmSendInvoiceEmail() {
        const order = this.state.emailInvoiceOrder;
        if (!order) return;

        const email = (this.state.emailInvoiceTarget || "").trim();
        if (!email || !email.includes("@")) {
            this.state.emailInvoiceErrorMessage = "Por favor, introduzca una dirección de correo válida (ej: cliente@correo.com).";
            return;
        }

        this.state.isSendingInvoiceEmail = true;
        this.state.emailInvoiceErrorMessage = "";
        this.state.emailInvoiceSuccessMessage = "";

        try {
            const res = await this.env.services.rpc("/pos_gas_station/send_invoice_email", {
                move_id: order.account_move_id || null,
                order_id: order.id || null,
                order_name: order.name || null,
                order_ref: order.pos_reference || null,
                move_name: order.account_move_name || null,
                email: email
            });

            if (res && res.status === "success") {
                this.state.emailInvoiceSuccessMessage = `La factura ${order.account_move_name || ''} ha sido enviada con éxito a ${res.email_to || email} con el PDF adjunto.`;
                order.partner_email = email;
                if (this.state.selectedShiftOrder && this.state.selectedShiftOrder.id === order.id) {
                    this.state.selectedShiftOrder.partner_email = email;
                }
                if (this.state.savedShiftOrderBeforeEmail && this.state.savedShiftOrderBeforeEmail.id === order.id) {
                    this.state.savedShiftOrderBeforeEmail.partner_email = email;
                }
            } else {
                this.state.emailInvoiceErrorMessage = res ? res.message : "No se pudo enviar el correo.";
            }
        } catch (e) {
            console.error("Error confirmSendInvoiceEmail:", e);
            this.state.emailInvoiceErrorMessage = "Error de comunicación con el servidor: " + (e.message || e);
        } finally {
            this.state.isSendingInvoiceEmail = false;
        }
    }

    goToPayment() {
        const currentOrder = this.pos.get_order();
        if (!currentOrder || this.currentOrderLines.length === 0) {
            alert("No hay artículos en el ticket para cobrar.");
            return;
        }
        if (this.state.vehiclePlate) {
            currentOrder.vehicle_plate = this.state.vehiclePlate;
        }
        // Limpiar cualquier línea de pago residual previa para arrancar el cobro limpio a 0,00 €
        if (currentOrder.get_paymentlines) {
            for (const pl of [...currentOrder.get_paymentlines()]) {
                currentOrder.remove_paymentline(pl);
            }
        }
        this.pos.showScreen("PaymentScreen");
    }

    openStoreModal() {
        this.state.storeSearch = "";
        this.state.isPageDropdownOpen = false;
        this.state.isStoreModalOpen = true;
        setTimeout(() => {
            const input = document.querySelector(".store-search-input");
            if (input) input.focus();
        }, 100);
    }

    closeStoreModal() {
        this.state.isStoreModalOpen = false;
        this.state.storeSearch = "";
        // Si se abrió desde la monedita, volver a la ventana de cobros pendientes de esa calle
        const t = this.state.storeTarget;
        if (t) {
            this.state.storeTarget = null;
            const pump = (this.state.pumps || []).find(p => String(p.id) === String(t.pumpId)) || t.pump;
            if (pump) this.openPendingSalesModal(pump);
        }
    }

    onStoreSearchInput(ev) {
        this.state.storeSearch = ev.target.value;
    }

    get currentOrderPartner() {
        const order = this.pos.get_order();
        return order ? order.get_partner() : null;
    }

    openClientModal() {
        this.state.isClientModalOpen = true;
        this.state.clientSearch = "";
        this.state.clientCodeSearch = "";
        setTimeout(() => {
            const input = document.querySelector(".client-search-code-input") || document.querySelector(".client-search-input");
            if (input) input.focus();
        }, 100);
    }

    closeClientModal() {
        this.state.isClientModalOpen = false;
        this.state.clientSearch = "";
        this.state.clientCodeSearch = "";
    }

    clearClientSearch() {
        this.state.clientSearch = "";
    }

    clearClientCodeSearch() {
        this.state.clientCodeSearch = "";
    }

    onClientCodeSearchInput(ev) {
        this.state.clientCodeSearch = ev.target.value;
    }

    setConvertAlbaranPlate(plate) {
        this.state.convertAlbaranPlate = plate || "";
    }

    onEditingPartnerNewPlateKeyDown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.addVehicleToEditingPartner();
        }
    }

    get currentCompanyName() {
        if (this.pos.company && this.pos.company.name) {
            return this.pos.company.name;
        }
        if (this.pos.config && this.pos.config.company_id) {
            if (Array.isArray(this.pos.config.company_id)) {
                return this.pos.config.company_id[1];
            }
            if (this.pos.companies && Array.isArray(this.pos.companies)) {
                const c = this.pos.companies.find(comp => comp.id === this.pos.config.company_id);
                if (c) return c.name;
            }
        }
        return "";
    }

    onClientSearchInput(ev) {
        this.state.clientSearch = ev.target.value;
    }

    toggleClientSort(field = "name") {
        if (this.state.clientSortField === field) {
            this.state.clientSortDirection = this.state.clientSortDirection === "asc" ? "desc" : "asc";
        } else {
            this.state.clientSortField = field;
            this.state.clientSortDirection = "asc";
        }
    }

    get spanishStates() {
        if (!this.pos.states || !Array.isArray(this.pos.states)) return [];
        return [...this.pos.states].sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    }

    get filteredClients() {
        const codeSearch = (this.state.clientCodeSearch || "").toLowerCase().trim();
        const search = (this.state.clientSearch || "").toLowerCase().trim();
        const allPartners = Object.values(this.pos.db.partner_by_id || {});
        // Filtrar estrictamente por la empresa asignada a la estación (no por estación ni clientes sin empresa)
        const configCompanyId = this.pos.config.company_id ? (Array.isArray(this.pos.config.company_id) ? this.pos.config.company_id[0] : this.pos.config.company_id) : null;
        let list = allPartners.filter(p => {
            const pCompId = p.company_id ? (Array.isArray(p.company_id) ? p.company_id[0] : p.company_id) : null;
            return pCompId && pCompId === configCompanyId;
        });
        if (codeSearch) {
            list = list.filter(p => {
                const ref = (p.ref || "").toLowerCase();
                return ref.includes(codeSearch);
            });
        }
        if (search) {
            list = list.filter(p => {
                const name = (p.name || "").toLowerCase();
                const vat = (p.vat || "").toLowerCase();
                const ref = (p.ref || "").toLowerCase();
                const phone = (p.phone || p.mobile || "").toLowerCase();
                const email = (p.email || "").toLowerCase();
                const barcode = (p.barcode || "").toLowerCase();
                return name.includes(search) || vat.includes(search) || ref.includes(search) || phone.includes(search) || email.includes(search) || barcode.includes(search);
            });
        }
        const field = this.state.clientSortField || "name";
        const isAsc = (this.state.clientSortDirection || "asc") === "asc";

        return [...list].sort((a, b) => {
            let valA = (a[field] || "").toString().toLowerCase();
            let valB = (b[field] || "").toString().toLowerCase();
            let comp = valA.localeCompare(valB, undefined, { numeric: true });
            return isAsc ? comp : -comp;
        }).slice(0, 50);
    }

    recheckFuelLinesRounding(order) {
        if (!order) return;
        const lines = order.get_orderlines ? order.get_orderlines() : [];
        for (const line of lines) {
            const target = line.target_total || (line.pump_id && order.pending_prepay ? order.pending_prepay.amount : null);
            if (target && target > 0) {
                line.price_type = "manual";
                line.target_total = target;
                if (line.get_display_price) {
                    const curDisp = line.get_display_price();
                    const diff = Math.round((target - curDisp) * 100) / 100;
                    if (Math.abs(diff) >= 0.005) {
                        const q = line.get_quantity() || 1;
                        const taxes = line.get_taxes ? line.get_taxes() : [];
                        let taxFactor = 1.0;
                        if (taxes && taxes.length > 0 && !taxes[0].price_include) {
                            const taxRate = taxes.reduce((s, t) => s + (t.amount || 0), 0);
                            taxFactor = 1.0 + (taxRate / 100.0);
                        }
                        line.set_unit_price(line.get_unit_price() + (diff / (q * taxFactor)));
                    }
                }
            }
        }
    }

    async selectClient(partner) {
        const order = this.pos.get_order();
        const prevPartner = order && order.get_partner ? order.get_partner() : null;
        if (order) {
            order.set_partner(partner);
            this.recheckFuelLinesRounding(order);
            this.state.orderVersion = Date.now();
        }
        this.closeClientModal();
        if (partner && partner.id) {
            if (prevPartner && prevPartner.id && prevPartner.id !== partner.id) {
                this.setVehiclePlate("");
            }
            await this.loadPartnerVehicles(partner.id);
            if (this.state.vehiclePlate && (!this.state.partnerVehicles || this.state.partnerVehicles.length === 0)) {
                await this.savePlateToPartner(this.state.vehiclePlate);
            }
        } else {
            this.state.partnerVehicles = [];
            this.state.isAddingNewPlate = false;
        }
    }

    removeClient() {
        const order = this.pos.get_order();
        if (order) {
            order.set_partner(null);
            this.state.orderVersion = Date.now();
        }
        this.state.partnerVehicles = [];
        this.state.isAddingNewPlate = false;
        this.closeClientModal();
    }

    editClient(partner) {
        this.openEditPartnerModal(partner);
    }

    createNewClient() {
        this.openEditPartnerModal(null);
    }

    openEditPartnerModal(partner = null) {
        if (partner) {
            const stateId = partner.state_id ? (Array.isArray(partner.state_id) ? partner.state_id[0] : partner.state_id) : false;
            this.state.editingPartner = {
                id: partner.id,
                name: partner.name || "",
                vat: partner.vat || "",
                ref: partner.ref || "",
                customer_type: partner.customer_type || "ordinary",
                customer_payment_mode: partner.customer_payment_mode || "cash",
                phone: partner.phone || "",
                mobile: partner.mobile || "",
                email: partner.email || "",
                street: partner.street || "",
                zip: partner.zip || "",
                city: partner.city || "",
                state_id: stateId,
                new_plate: "",
                vehicles: (partner.vehicles && Array.isArray(partner.vehicles)) ? [...partner.vehicles] : [],
            };
            this.loadEditPartnerVehicles(partner.id);
        } else {
            const defaultState = this.pos.company && this.pos.company.state_id ? (Array.isArray(this.pos.company.state_id) ? this.pos.company.state_id[0] : this.pos.company.state_id) : false;
            this.state.editingPartner = {
                id: null,
                name: "",
                vat: "",
                ref: "",
                customer_type: "ordinary",
                customer_payment_mode: "cash",
                phone: "",
                mobile: "",
                email: "",
                street: "",
                zip: "",
                city: "",
                state_id: defaultState,
                new_plate: "",
                vehicles: [],
            };
        }
        this.state.editPartnerError = null;
        this.state.isSavingPartner = false;
        this.state.isEditPartnerModalOpen = true;
    }

    closeEditPartnerModal() {
        this.state.isEditPartnerModalOpen = false;
        this.state.editPartnerError = null;
    }

    async loadEditPartnerVehicles(partnerId) {
        if (!partnerId) return;
        try {
            const res = await this.env.services.rpc("/pos_gas_station/get_partner_vehicles", {
                partner_id: partnerId
            });
            if (res && res.status === "success" && this.state.editingPartner && this.state.editingPartner.id === partnerId) {
                this.state.editingPartner.vehicles = res.vehicles || [];
            }
        } catch (e) {
            console.error("Error al cargar matrículas de edición:", e);
        }
    }

    async addVehicleToEditingPartner() {
        const plate = (this.state.editingPartner.new_plate || "").trim().toUpperCase();
        if (!plate || plate.length < 3) return;
        if (this.state.editingPartner.id) {
            try {
                const res = await this.env.services.rpc("/pos_gas_station/save_partner_vehicle", {
                    partner_id: this.state.editingPartner.id,
                    plate: plate
                });
                if (res && res.status === "success") {
                    this.state.editingPartner.vehicles = res.vehicles || [];
                    this.state.editingPartner.new_plate = "";
                }
            } catch (e) {
                console.error("Error guardando matrícula:", e);
            }
        } else {
            if (!this.state.editingPartner.vehicles.some(v => v.name === plate)) {
                this.state.editingPartner.vehicles.push({ id: null, name: plate });
            }
            this.state.editingPartner.new_plate = "";
        }
    }

    async removeVehicleFromEditingPartner(veh) {
        if (veh.id) {
            try {
                const res = await this.env.services.rpc("/pos_gas_station/remove_partner_vehicle", {
                    vehicle_id: veh.id
                });
                if (res && res.status === "success") {
                    this.state.editingPartner.vehicles = res.vehicles || [];
                }
            } catch (e) {
                console.error("Error eliminando matrícula:", e);
            }
        } else {
            this.state.editingPartner.vehicles = this.state.editingPartner.vehicles.filter(v => v !== veh);
        }
    }

    async saveEditPartner() {
        const p = this.state.editingPartner;
        if (!p.name || !p.name.trim()) {
            this.state.editPartnerError = "El Nombre o Razón Social es obligatorio.";
            return;
        }
        this.state.isSavingPartner = true;
        this.state.editPartnerError = null;
        try {
            const partnerData = {
                id: p.id || false,
                name: p.name.trim(),
                vat: (p.vat || "").trim().toUpperCase(),
                ref: (p.ref || "").trim(),
                phone: (p.phone || "").trim(),
                mobile: (p.mobile || "").trim(),
                email: (p.email || "").trim(),
                street: (p.street || "").trim(),
                zip: (p.zip || "").trim(),
                city: (p.city || "").trim(),
                state_id: p.state_id ? parseInt(p.state_id) : false,
                config_id: this.pos.config.id,
                company_id: this.pos.config.company_id ? (Array.isArray(this.pos.config.company_id) ? this.pos.config.company_id[0] : this.pos.config.company_id) : false,
                new_plate: (p.new_plate || "").trim().toUpperCase(),
            };

            const res = await this.env.services.rpc("/pos_gas_station/save_partner", {
                partner_data: partnerData
            });

            if (res && res.status === "success" && res.partner) {
                const saved = res.partner;
                // Si había matrículas en memoria añadidas antes de guardar el cliente nuevo:
                if (!p.id && p.vehicles && p.vehicles.length > 0) {
                    for (const v of p.vehicles) {
                        if (v.name && v.name !== partnerData.new_plate) {
                            try {
                                await this.env.services.rpc("/pos_gas_station/save_partner_vehicle", {
                                    partner_id: saved.id,
                                    plate: v.name
                                });
                            } catch (ve) {
                                console.error("Error guardando matrícula secundaria:", ve);
                            }
                        }
                    }
                }

                // Actualizar en memoria POS
                this.pos.db.partner_by_id[saved.id] = Object.assign(this.pos.db.partner_by_id[saved.id] || {}, saved);
                if (typeof this.pos._loadPartners === "function") {
                    await this.pos._loadPartners([saved.id]);
                }

                // Actualizar orden actual si corresponde
                const order = this.pos.get_order();
                if (order && ((order.get_partner() && order.get_partner().id === saved.id) || !p.id)) {
                    order.set_partner(saved);
                    await this.loadPartnerVehicles(saved.id);
                }

                this.state.orderVersion = Date.now();
                this.closeEditPartnerModal();

                if (this.env.services.notification) {
                    this.env.services.notification.add(
                        p.id ? "Ficha de cliente actualizada correctamente" : "Nuevo cliente creado correctamente",
                        { type: "success" }
                    );
                }
            } else {
                this.state.editPartnerError = res?.message || "Error al guardar el cliente.";
            }
        } catch (e) {
            console.error("Error al guardar cliente:", e);
            this.state.editPartnerError = e.message || "Error al conectar con el servidor.";
        } finally {
            this.state.isSavingPartner = false;
        }
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
                this.recheckFuelLinesRounding(order);
            }
            if (newPartner && newPartner.id) {
                await this.loadPartnerVehicles(newPartner.id);
            }
            this.state.orderVersion = Date.now();
        }
    }

    async addStoreProductToOrder(virtusItem, keepOpen = false) {
        if (!virtusItem || virtusItem.is_empty) return;
        const currentOrder = this.getOrCreateOrder();
        if (!currentOrder) return;

        let realProduct = null;
        if (virtusItem && typeof virtusItem.get_unit === "function") {
            realProduct = virtusItem;
        } else if (this.pos.db && this.pos.db.product_by_id) {
            const all = Object.values(this.pos.db.product_by_id);
            const code = (virtusItem.default_code || "").toLowerCase();
            const barcode = (virtusItem.barcode || "").toLowerCase();
            const name = (virtusItem.display_name || virtusItem.full_name || "").toLowerCase();

            realProduct = (typeof virtusItem.id === "number" ? this.pos.db.get_product_by_id(virtusItem.id) : null) ||
                          (barcode ? all.find(p => (p.barcode || "").toLowerCase() === barcode) : null) ||
                          (code ? all.find(p => (p.default_code || "").toLowerCase() === code) : null) ||
                          all.find(p => (p.display_name || p.name || "").toLowerCase().includes(name)) ||
                          all.find(p => !(p.display_name || p.name || "").toLowerCase().includes("gasóleo") && !(p.display_name || p.name || "").toLowerCase().includes("plomo")) ||
                          all[0];
        }

        if (realProduct) {
            const price = virtusItem.lst_price || virtusItem.list_price || realProduct.lst_price || 1.0;
            await currentOrder.add_product(realProduct, {
                quantity: 1,
                price: price,
                extras: {
                    price_manually_set: true
                }
            });
            if (this.state.vehiclePlate) {
                if (currentOrder.set_note) currentOrder.set_note(`Matrícula: ${this.state.vehiclePlate}`);
            }
            this.state.orderVersion = Date.now();
        }
        if (!keepOpen) {
            this.closeStoreModal();
        }
    }

    shouldShowPrepayCoin(pump) {
        if (!pump) return false;

        // Si la calle tiene cobros o sobrantes pendientes aparcados en su monedita (badge numérico > 0), SIEMPRE mostrarla
        if (this.getPumpPendingSalesCount(pump) > 0) {
            return true;
        }

        // Si la calle indica un sobrante en su texto de estado
        if ((pump.statusText || "").includes("SOBRANTE")) {
            return true;
        }

        // Si la calle tiene productos de tienda vinculados a la espera de cobro, mostrar la monedita
        if (this.hasPumpPendingStoreItems(pump.id)) {
            return true;
        }

        // Si está en 'ready' con saldo positivo pendiente
        if (pump.status === "ready" && pump.amount > 0) {
            return true;
        }

        return false;
    }

    registerPrepayRefund(pump, presetInfo, finalAmt, finalLts) {
        if ((finalAmt || 0) <= 0.02 && (finalLts || 0) <= 0.02) {
            // Protección: No se suministró combustible en pista; no generar falso sobrante de prepago
            return;
        }
        const isMoney = Boolean(presetInfo.isMoney);
        const unitPrice = presetInfo.unitPrice || pump.price || 1.45;
        let diffAmt = 0;
        let diffLts = 0;

        if (isMoney) {
            diffAmt = Math.round((presetInfo.amount - finalAmt) * 100) / 100;
            diffLts = unitPrice > 0 ? Math.round((diffAmt / unitPrice) * 1000) / 1000 : 0;
        } else {
            diffLts = Math.round((presetInfo.liters - finalLts) * 1000) / 1000;
            diffAmt = Math.round((diffLts * unitPrice) * 100) / 100;
        }

        if (diffAmt <= 0.02 && diffLts <= 0.02) {
            return;
        }

        if (!this.pos.pendingSales) {
            this.pos.pendingSales = {};
        }
        if (!this.pos.pendingSales[pump.id]) {
            this.pos.pendingSales[pump.id] = [];
        }

        // Evitar duplicar el sobrante si ya existe para este ticket/operación
        const alreadyRegistered = this.pos.pendingSales[pump.id].some(s => 
            s.isPrepayRefund && s.orderRef === presetInfo.orderRef && Math.abs(s.refundAmount - (-diffAmt)) < 0.05
        );

        if (!alreadyRegistered) {
            const refundSale = {
                id: "refund_" + pump.id + "_" + Date.now(),
                pumpId: pump.id,
                isPrepayRefund: true,
                orderRef: presetInfo.orderRef || "",
                timestamp: Date.now(),
                timeStr: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                vehiclePlate: presetInfo.vehiclePlate || pump.vehiclePlate || "",
                partner: presetInfo.partner || null,
                presetAmount: presetInfo.amount || (presetInfo.liters * unitPrice),
                presetLiters: presetInfo.liters || (unitPrice > 0 ? presetInfo.amount / unitPrice : 0),
                isMoney: isMoney,
                dispensedAmount: finalAmt,
                dispensedLiters: finalLts,
                refundAmount: -diffAmt, // NEGATIVO e.g. -5.00 €
                refundLiters: -diffLts, // NEGATIVO e.g. -3.448 L
                totalAmount: -diffAmt,  // NEGATIVO
                fuel: {
                    name: presetInfo.fuel || pump.fuel || "Combustible",
                    code: presetInfo.code || "GA",
                    unitPrice: unitPrice,
                    productId: presetInfo.productId || presetInfo.product_id
                }
            };
            this.pos.pendingSales[pump.id].push(refundSale);
            this.savePendingSales();
        }

        // Limpiar el preset
        if (this.state.pumpPresets) delete this.state.pumpPresets[pump.id];
        if (this.pos && this.pos.pumpPresets) delete this.pos.pumpPresets[pump.id];
        this.savePumpPresets();

        // Liberar y cerrar físicamente la bomba en backend
        try {
            jsonrpc("/pos_gas_station/clear_pump", {
                config_id: this.configId,
                pump_id: pump.id
            }).catch(e => console.debug("Liberar bomba tras sobrante:", e));
        } catch (e) {}

        pump.status = "ready";
        pump.statusText = `SOBRANTE ${diffAmt.toFixed(2)} €`;
        pump.amount = 0;
        pump.liters = 0;
        pump.has_prepay = false;
        pump.preset_amount = 0;
    }


    async openStationsSelector() {
        this.state.isStationsModalOpen = true;
        this.state.loadingStations = true;
        try {
            const res = await this.orm.call("pos.config", "get_user_available_stations", [this.configId]);
            this.state.availableStations = (res && res.stations) ? res.stations : [];
            this.state.isAdminUser = Boolean(res && res.is_admin);
        } catch (e) {
            console.error("Error al obtener estaciones disponibles:", e);
            this.state.availableStations = [];
        } finally {
            this.state.loadingStations = false;
        }
    }

    closeStationsSelector() {
        this.state.isStationsModalOpen = false;
    }

    switchToStation(targetStationId) {
        if (!targetStationId || targetStationId === this.configId) {
            this.closeStationsSelector();
            return;
        }
        window.location.href = `/pos/ui?config_id=${targetStationId}`;
    }

    goToDashboard() {
        window.location.href = "/web#action=pos_gas_station.action_gas_station_dashboard";
    }

    switchCashierUser() {
        window.location.href = `/pos_gas_station/switch_cashier?config_id=${this.configId}`;
    }

    async openCloseSessionPopup() {
        try {
            const info = await this.pos.getClosePosInfo();
            await this.popup.add(GasStationClosePosPopup, { ...info });
        } catch (e) {
            console.error("Error abriendo ClosePosPopup:", e);
        }
    }

    savePendingSales() {
        try {
            localStorage.setItem(`pos_gas_station_pending_sales_${this.configId}`, JSON.stringify(this.pos.pendingSales || {}));
        } catch (e) {
            console.debug("Error guardando pendingSales:", e);
        }
        // Copia en servidor: las moneditas no pueden perderse al recargar el TPV o cambiar de navegador
        if (!this.pendingSalesServerLoaded) return; // no pisar el servidor antes de haber leído su copia
        jsonrpc("/pos_gas_station/pending_sales/set", {
            config_id: this.configId,
            pending_sales: this.pos.pendingSales || {},
        }).catch(e => console.warn("No se pudieron guardar las moneditas en servidor:", e));
    }

    async loadPendingSalesFromServer() {
        try {
            const res = await jsonrpc("/pos_gas_station/pending_sales/get", { config_id: this.configId });
            if (res && res.exists) {
                const server = res.pending_sales || {};
                const savedAt = Number(res.saved_at || 0);
                const local = this.pos.pendingSales || {};
                // Conservar operaciones locales creadas después de la última copia del servidor
                for (const pid in local) {
                    for (const sale of (local[pid] || [])) {
                        const known = (server[pid] || []).some(s => s.id === sale.id);
                        if (!known && Number(sale.timestamp || 0) > savedAt) {
                            if (!server[pid]) server[pid] = [];
                            server[pid].push(sale);
                        }
                    }
                }
                this.pos.pendingSales = server;
            }
            this.pendingSalesServerLoaded = true;
            this.savePendingSales();
        } catch (e) {
            console.warn("No se pudieron cargar las moneditas del servidor:", e);
            // Reintentar en el siguiente arranque; mientras tanto se usa la copia local
            setTimeout(() => { if (!this.pendingSalesServerLoaded) this.loadPendingSalesFromServer(); }, 5000);
        }
    }

    savePumpPresets() {
        try {
            if (this.state && this.state.pumpPresets && this.pos) {
                this.pos.pumpPresets = Object.assign({}, this.state.pumpPresets);
            }
            localStorage.setItem(`pos_gas_station_pump_presets_${this.configId}`, JSON.stringify((this.pos && this.pos.pumpPresets) || {}));
        } catch (e) {
            console.debug("Error guardando pumpPresets:", e);
        }
    }

    savePumpPendingStoreItems() {
        try {
            localStorage.setItem(`pos_gas_station_pending_store_${this.configId}`, JSON.stringify(this.pos.pumpPendingStoreItems || {}));
        } catch (e) {
            console.debug("Error guardando pumpPendingStoreItems:", e);
        }
    }

    savePumpPendingPlates() {
        try {
            localStorage.setItem(`pos_gas_station_pending_plates_${this.configId}`, JSON.stringify(this.pos.pumpPendingPlates || {}));
        } catch (e) {
            console.debug("Error guardando pumpPendingPlates:", e);
        }
    }

    hasPumpPendingStoreItems(pumpId) {
        return Boolean(this.pos && this.pos.pumpPendingStoreItems && this.pos.pumpPendingStoreItems[pumpId] && this.pos.pumpPendingStoreItems[pumpId].length > 0);
    }

    isCreditCustomerForSale(sale) {
        const partner = (sale && sale.partner) || this.currentOrderPartner;
        if (!partner) return false;
        if (partner.credit_blocked) return false;
        if (partner.customer_type === 'credit') return true;
        if (partner.customer_type === 'monthly') return false;
        return Boolean(partner.customer_payment_mode === 'credit');
    }

    hasPumpPendingRefund(pump) {
        if (!pump) return false;
        const sales = this.getPumpPendingSales(pump.id);
        return sales.some(s => s.isPrepayRefund);
    }

    getPumpPendingRefundAmount(pump) {
        if (!pump) return 0;
        const sales = this.getPumpPendingSales(pump.id);
        const refunds = sales.filter(s => s.isPrepayRefund);
        return refunds.reduce((sum, r) => sum + (r.refundAmount || 0), 0);
    }

    getPumpPendingSalesCount(pump) {
        if (!pump) return 0;
        return (this.pos.pendingSales && this.pos.pendingSales[pump.id]) ? this.pos.pendingSales[pump.id].length : 0;
    }

    getPumpPendingSales(pumpId) {
        return (this.pos.pendingSales && this.pos.pendingSales[pumpId]) ? this.pos.pendingSales[pumpId] : [];
    }

    getPumpTotalPendingAmount(pump) {
        if (!pump) return 0;
        const sales = this.getPumpPendingSales(pump.id);
        return sales.reduce((sum, s) => sum + (s.totalAmount || (s.fuel && s.fuel.amount) || 0), 0);
    }

    hasPumpLineInCurrentOrder() {
        const order = this.pos.get_order();
        if (!order) return false;
        const lines = order.get_orderlines ? order.get_orderlines() : (order.orderlines || []);
        if (!lines || lines.length === 0) return false;
        return lines.some(l => {
            if (l.pump_id) return true;
            const p = l.product || (l.product_id ? (this.pos.db ? this.pos.db.get_product_by_id(l.product_id.id || l.product_id) : null) : null);
            if (p) {
                const name = (p.display_name || p.name || "").toLowerCase();
                const code = (p.default_code || "").toUpperCase();
                if (code.includes("GAS") || code.includes("SP95") || code.includes("DIESEL") || code.includes("CARBURANTE")) return true;
                if (name.includes("gasóleo") || name.includes("gasoleo") || name.includes("sin plomo") || name.includes("gasolina") || name.includes("combustible") || name.includes("diesel")) return true;
            }
            return false;
        });
    }

    async onCoinBadgeClick(pump) {
        // Consolidar venta como pendingSale en la monedita si no se había registrado aún
        const count = this.getPumpPendingSalesCount(pump);
        if (count === 0 && (pump.status === "ready" || pump.amount > 0 || (pump.statusText || "").includes("SOBRANTE"))) {
            if ((pump.statusText || "").includes("SOBRANTE") || (pump.has_prepay && pump.preset_amount > pump.amount)) {
                // Registrar como sobrante de prepago
                let diff = (pump.preset_amount > pump.amount && pump.amount > 0) ? (pump.preset_amount - pump.amount) : 0;
                if (!diff && (pump.statusText || "").includes("SOBRANTE")) {
                    const m = pump.statusText.match(/SOBRANTE\s*([\d\.,]+)/i);
                    if (m) diff = parseFloat(m[1].replace(',', '.'));
                }
                const presetVal = pump.preset_amount > 0 ? pump.preset_amount : (pump.amount + diff);
                const fuelProd = (pump.product_id && this.pos.db && this.pos.db.product_by_id && this.pos.db.product_by_id[pump.product_id]) || this.findFuelProduct(pump.fuel || "95");
                const uPrice = pump.price || (pump.liters > 0 ? (pump.amount / pump.liters) : 1.55);
                const preset = {
                    amount: presetVal,
                    liters: uPrice > 0 ? Math.round((presetVal / uPrice) * 1000) / 1000 : (pump.liters || 0),
                    isMoney: true,
                    hasPrepay: true,
                    fuel: (fuelProd && fuelProd.display_name) || pump.fuel || "Sin Plomo 95",
                    code: this.getPumpFuelCode(pump) || "95",
                    unitPrice: uPrice,
                    productId: fuelProd ? fuelProd.id : null,
                    hasStartedDispensing: true,
                    maxDispensedAmount: pump.amount,
                    maxDispensedLiters: pump.liters
                };
                this.registerPrepayRefund(pump, preset, pump.amount, pump.liters);
            } else {
                const fuelProd = (pump.product_id && this.pos.db.product_by_id[pump.product_id]) || this.findFuelProduct(pump.fuel || "GA");
                const pendingSale = {
                    id: "sale_" + pump.id + "_" + Date.now(),
                    pumpId: pump.id,
                    timestamp: Date.now(),
                    timeStr: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                    fuel: {
                        name: (fuelProd && fuelProd.display_name) || pump.fuel || "Combustible",
                        liters: pump.liters || 0,
                        price: pump.price || (pump.liters > 0 ? (pump.amount / pump.liters) : 1.45),
                        amount: pump.amount || 0,
                        productId: fuelProd ? fuelProd.id : null,
                        code: this.getPumpFuelCode(pump)
                    },
                    storeLines: [],
                    totalAmount: pump.amount || 0,
                    vehiclePlate: pump.vehiclePlate || ""
                };
                if (!this.pos.pendingSales) this.pos.pendingSales = {};
                if (!this.pos.pendingSales[pump.id]) this.pos.pendingSales[pump.id] = [];
                this.pos.pendingSales[pump.id].push(pendingSale);
                this.savePendingSales();
            }
        }

        // REGLA CRÍTICA DE OPERATIVA:
        // Aunque exista una sola monedita, SIEMPRE se abre la ventana flotante con las operaciones pendientes.
        // NUNCA se carga automáticamente el ticket en la pantalla del TPV al pulsar la moneda para evitar borrados accidentales de líneas.
        this.openPendingSalesModal(pump);
    }

    async dismissRefund(sale) {
        if (!confirm(`¿Desea anular y cancelar este sobrante de ${sale.refundAmount.toFixed(2)} €?\nEsta operación se descartará y la monedita desaparecerá.`)) {
            return;
        }
        const pid = sale.pumpId;
        if (this.pos.pendingSales && this.pos.pendingSales[pid]) {
            this.pos.pendingSales[pid] = this.pos.pendingSales[pid].filter(s => s.id !== sale.id);
            if (this.pos.pendingSales[pid].length === 0) {
                delete this.pos.pendingSales[pid];
            }
            this.savePendingSales();
        }
        const remaining = (this.pos.pendingSales && this.pos.pendingSales[pid] && this.pos.pendingSales[pid].length) || 0;
        const targetPump = this.state && this.state.pumps && this.state.pumps.find(p => String(p.id) === String(pid));
        if (targetPump && targetPump.status !== "dispensing") {
            if (remaining === 0) {
                targetPump.status = "blocked";
                targetPump.statusText = "PREPAGO";
                targetPump.amount = 0;
                targetPump.liters = 0;
            } else {
                targetPump.status = "ready";
                targetPump.statusText = remaining === 1 ? "COBRAR" : `COBROS (${remaining})`;
            }
        }
        this.closePendingSalesModal();
    }

    async anularYDescontarDeCaja(sale) {
        const refundAmt = Math.abs(sale.refundAmount || sale.totalAmount || 0);
        if (!confirm(`¿Desea anular este sobrante de ${refundAmt.toFixed(2)} € y descontarlo directamente de la caja registradora como salida de efectivo?`)) {
            return;
        }

        const pid = sale.pumpId;
        const reason = `Devolución sobrante prepago Calle ${pid} (Prefijado: ${(sale.presetAmount || 0).toFixed(2)}€ - Repostado: ${(sale.dispensedAmount || 0).toFixed(2)}€)`;
        const formattedAmount = `${refundAmt.toFixed(2)} €`;

        try {
            let recorded = false;
            try {
                const res = await this.env.services.rpc("/pos_gas_station/cash_move", {
                    session_id: this.pos.pos_session?.id,
                    amount: refundAmt,
                    reason: reason,
                    translated_type: "Salida",
                    partner_id: sale.partner ? sale.partner.id : null,
                });
                if (res && res.status === "success") {
                    recorded = true;
                }
            } catch (rpcErr) {
                console.warn("Aviso en /pos_gas_station/cash_move para sobrante:", rpcErr);
            }

            if (!recorded && this.pos.pos_session?.id && this.orm) {
                await this.orm.call("pos.session", "try_cash_in_out", [
                    [this.pos.pos_session.id],
                    "out",
                    refundAmt,
                    reason,
                    {
                        formattedAmount: formattedAmount,
                        translatedType: "Salida",
                    },
                ]);
            }
        } catch (e) {
            console.error("Error al registrar salida de caja para sobrante:", e);
            alert(`⚠️ Error al descontar de caja: ${e.message || e}`);
            return;
        }

        // Eliminar el sobrante de pendingSales
        if (this.pos.pendingSales && this.pos.pendingSales[pid]) {
            this.pos.pendingSales[pid] = this.pos.pendingSales[pid].filter(s => s.id !== sale.id);
            if (this.pos.pendingSales[pid].length === 0) {
                delete this.pos.pendingSales[pid];
            }
            this.savePendingSales();
        }

        const remaining = (this.pos.pendingSales && this.pos.pendingSales[pid] && this.pos.pendingSales[pid].length) || 0;
        const targetPump = this.state && this.state.pumps && this.state.pumps.find(p => String(p.id) === String(pid));
        if (targetPump && targetPump.status !== "dispensing") {
            if (remaining === 0) {
                targetPump.status = "blocked";
                targetPump.statusText = "PREPAGO";
                targetPump.amount = 0;
                targetPump.liters = 0;
            } else {
                targetPump.status = "ready";
                targetPump.statusText = remaining === 1 ? "COBRAR" : `COBROS (${remaining})`;
            }
        }

        try {
            jsonrpc("/pos_gas_station/clear_pump", {
                config_id: this.configId,
                pump_id: pid
            }).catch(e => console.debug("Liberar bomba tras anular sobrante:", e));
        } catch (e) {}

        this.closePendingSalesModal();
        alert(`✅ Sobrante de ${formattedAmount} anulado correctamente y descontado de la caja.`);
    }

    onAuthorizeNewSaleFromModal(pump) {
        this.closePendingSalesModal();
        if (pump) {
            this.openAuthorizeModal(pump);
        }
    }

    openPendingSalesModal(pump) {
        this.state.pendingModalPump = pump;
        this.state.isPendingSalesModalOpen = true;
    }

    closePendingSalesModal() {
        this.state.isPendingSalesModalOpen = false;
        this.state.pendingModalPump = null;
    }

    // ------------------------------------------------------------------
    // AÑADIR / QUITAR ARTÍCULOS DE TIENDA EN UNA VENTA PENDIENTE (MONEDITA)
    // ------------------------------------------------------------------
    findPendingSale(pumpId, saleId) {
        const list = (this.pos.pendingSales && this.pos.pendingSales[pumpId]) || [];
        return list.find(s => s.id === saleId) || null;
    }

    recalcPendingSaleTotal(sale) {
        const fuelAmt = sale.fuel ? Number(sale.fuel.amount || 0) : 0;
        const storeAmt = (sale.storeLines || []).reduce((acc, it) => acc + Number(it.amount || 0), 0);
        sale.totalAmount = Math.round((fuelAmt + storeAmt) * 100) / 100;
    }

    commitPendingSaleChange(pumpId) {
        // Reasignar el array para forzar el refresco reactivo de la ventana flotante
        if (this.pos.pendingSales && this.pos.pendingSales[pumpId]) {
            this.pos.pendingSales[pumpId] = [...this.pos.pendingSales[pumpId]];
        }
        this.savePendingSales();
        this.state.orderVersion = Date.now();
    }

    openStorePickerForPendingSale(sale) {
        const pump = this.state.pendingModalPump;
        this.state.storeTarget = { pumpId: sale.pumpId, saleId: sale.id, pump };
        this.closePendingSalesModal();
        this.openStoreModal();
    }

    onStoreProductPick(product) {
        if (this.state.storeTarget) {
            this.addProductToPendingSale(product);
        } else {
            this.addStoreProductToOrder(product, true);
        }
    }

    onStoreProductDblPick(product) {
        if (this.state.storeTarget) return; // en modo monedita cada clic suma 1 unidad
        this.onProductCardDblClick(product);
    }

    getStorePickerQty(product) {
        const t = this.state.storeTarget;
        if (!t) return this.getProductOrderQty(product);
        const sale = this.findPendingSale(t.pumpId, t.saleId);
        if (!sale) return 0;
        const line = (sale.storeLines || []).find(l => l.productId === product.id);
        return line ? line.qty : 0;
    }

    addProductToPendingSale(product) {
        const t = this.state.storeTarget;
        const sale = t && this.findPendingSale(t.pumpId, t.saleId);
        if (!sale) {
            alert("La venta pendiente ya no existe (puede que se haya cobrado).");
            this.closeStoreModal();
            return;
        }
        if (!sale.storeLines) sale.storeLines = [];
        const price = Number(product.lst_price || product.list_price || 0);
        let line = sale.storeLines.find(l => l.productId === product.id);
        if (line) {
            line.qty = Number(line.qty || 0) + 1;
            line.amount = Math.round(line.qty * Number(line.price || price) * 100) / 100;
        } else {
            sale.storeLines.push({
                name: product.display_name || product.name,
                qty: 1,
                price: price,
                amount: Math.round(price * 100) / 100,
                productId: product.id,
            });
        }
        this.recalcPendingSaleTotal(sale);
        this.commitPendingSaleChange(t.pumpId);
    }

    removeOneFromPendingSale(sale, item) {
        if (!sale || sale.isPrepayRefund) return;
        const real = this.findPendingSale(sale.pumpId, sale.id);
        if (!real || !real.storeLines) return;
        const line = real.storeLines.find(l => l.productId === item.productId);
        if (!line) return;
        line.qty = Number(line.qty || 0) - 1;
        if (line.qty <= 0) {
            real.storeLines = real.storeLines.filter(l => l !== line);
        } else {
            line.amount = Math.round(line.qty * Number(line.price || 0) * 100) / 100;
        }
        this.recalcPendingSaleTotal(real);
        this.commitPendingSaleChange(real.pumpId);
    }

    async parkCurrentPumpSale() {
        const order = this.pos.get_order();
        if (!order) return;
        const lines = order.get_orderlines ? order.get_orderlines() : [];
        const pumpLine = lines.find(l => l.pump_id);
        if (!pumpLine) {
            alert("No hay ningún repostaje de calle en el ticket actual para dejar pendiente.");
            return;
        }
        const pumpId = pumpLine.pump_id;
        const targetPump = this.state.pumps.find(p => p.id === pumpId);

        let fuelInfo = null;
        const storeItems = [];
        let total = 0;

        for (const l of lines) {
            const lPrice = l.get_display_price ? l.get_display_price() : (l.price * l.quantity);
            total += lPrice;
            if (l.pump_id === pumpId) {
                fuelInfo = {
                    name: l.product.display_name,
                    liters: l.get_quantity ? l.get_quantity() : 1,
                    price: l.fuel_display_price || (l.get_unit_price ? l.get_unit_price() : 0),
                    amount: lPrice,
                    productId: l.product.id
                };
            } else {
                storeItems.push({
                    name: l.product.display_name,
                    qty: l.get_quantity ? l.get_quantity() : 1,
                    price: l.get_unit_price ? l.get_unit_price() : l.price,
                    amount: lPrice,
                    productId: l.product.id
                });
            }
        }

        const pPlate = (this.pos && this.pos.pumpPendingPlates && this.pos.pumpPendingPlates[pumpId]) || this.state.vehiclePlate || (order && order.vehicle_plate) || "";
        if (this.pos && this.pos.pumpPendingPlates && this.pos.pumpPendingPlates[pumpId]) {
            delete this.pos.pumpPendingPlates[pumpId];
            this.savePumpPendingPlates();
        }

        const pendingSale = {
            id: "sale_" + Date.now() + "_" + Math.floor(Math.random() * 1000),
            pumpId: pumpId,
            timestamp: Date.now(),
            timeStr: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            fuel: fuelInfo,
            storeLines: storeItems,
            totalAmount: total,
            vehiclePlate: pPlate
        };

        if (!this.pos.pendingSales) {
            this.pos.pendingSales = {};
        }
        if (!this.pos.pendingSales[pumpId]) {
            this.pos.pendingSales[pumpId] = [];
        }
        this.pos.pendingSales[pumpId].push(pendingSale);
        this.savePendingSales();

        // Liberar y reabrir la calle en pista para el siguiente cliente
        try {
            await jsonrpc("/pos_gas_station/clear_pump", {
                config_id: this.configId,
                pump_id: pumpId
            });
        } catch (e) {
            console.debug("Error liberando calle tras aparcar venta:", e);
        }

        if (targetPump) {
            targetPump.status = "atendido";
            targetPump.statusText = "LLENO (LIBRE)";
            targetPump.amount = 0;
            targetPump.liters = 0;
            targetPump.preset_amount = 0;
            targetPump.has_prepay = false;
        }

        // Dejar el ticket activo en blanco para atender a otro cliente
        this.pos.removeOrder(order);
        this.pos.add_new_order();
        this.state.selectedLineId = null;
        this.state.vehiclePlate = "";
        this.state.orderVersion = Date.now();
    }

    async checkoutPendingSale(sale) {
        this.closePendingSalesModal();
        let currentOrder = this.pos.get_order();

        // Si la orden actual ya contiene cargado exactamente este cobro pendiente, no duplicar líneas y abrir la pantalla de cobro
        if (currentOrder && currentOrder.pending_sale_id === sale.id) {
            this.pos.showScreen("PaymentScreen");
            return;
        }

        const hasOtherFuel = currentOrder && currentOrder.get_orderlines && currentOrder.get_orderlines().some(l => this.isFuelProduct(l.product));
        if (!currentOrder || hasOtherFuel) {
            currentOrder = this.pos.add_new_order();
        }

        currentOrder.pending_sale_id = sale.id;
        currentOrder.pending_pump_id = sale.pumpId;
        currentOrder.pump_id = sale.pumpId;

        // 1. Añadir combustible
        if (sale.fuel) {
            const product = this.pos.db.get_product_by_id(sale.fuel.productId) || this.findFuelProduct(sale.fuel.name);
            if (product) {
                const targetTotal = sale.fuel.amount;
                const qty = sale.fuel.liters;
                const unitPrice = this.getNetPriceForTargetTotal ? this.getNetPriceForTargetTotal(product, targetTotal, qty, currentOrder) : (sale.fuel.price || product.lst_price);
                await currentOrder.add_product(product, {
                    quantity: qty,
                    price: unitPrice,
                    extras: {
                        price_manually_set: true,
                        price_type: "manual",
                        pump_id: sale.pumpId,
                        fuel_display_price: sale.fuel.price,
                        target_total: targetTotal,
                        customerNote: `Calle ${sale.pumpId} - ${sale.fuel.name} (${sale.fuel.liters.toFixed(2)}L)`
                    }
                });
                const activeLine = currentOrder.get_last_orderline();
                if (activeLine) {
                    activeLine.pump_id = sale.pumpId;
                    activeLine.fuel_display_price = sale.fuel.price;
                    activeLine.target_total = targetTotal;
                    activeLine.price_type = "manual";
                    if (activeLine.set_customer_note) {
                        activeLine.set_customer_note(`Calle ${sale.pumpId} - ${sale.fuel.name} (${sale.fuel.liters.toFixed(2)}L)`);
                    }
                    if (targetTotal > 0) {
                        const currentDisp = activeLine.get_display_price ? activeLine.get_display_price() : (activeLine.price * activeLine.quantity);
                        const diff = Math.round((targetTotal - currentDisp) * 100) / 100;
                        if (Math.abs(diff) >= 0.005) {
                            const curQty = activeLine.get_quantity() || 1;
                            const taxes = activeLine.get_taxes ? activeLine.get_taxes() : [];
                            let taxFactor = 1.0;
                            if (taxes && taxes.length > 0 && !taxes[0].price_include) {
                                const taxRate = taxes.reduce((s, t) => s + (t.amount || 0), 0);
                                taxFactor = 1.0 + (taxRate / 100.0);
                            }
                            activeLine.set_unit_price(activeLine.get_unit_price() + (diff / (curQty * taxFactor)));
                        }
                    }
                }
            }
        }

        // 2. Añadir artículos de tienda si los había
        if (sale.storeLines && sale.storeLines.length > 0) {
            for (const item of sale.storeLines) {
                const stProd = this.pos.db.get_product_by_id(item.productId);
                if (stProd) {
                    await currentOrder.add_product(stProd, {
                        quantity: item.qty,
                        price: item.price
                    });
                }
            }
        }

        if (sale.vehiclePlate) {
            this.state.vehiclePlate = sale.vehiclePlate;
            currentOrder.vehicle_plate = sale.vehiclePlate;
            if (currentOrder.set_note) currentOrder.set_note(`Matrícula: ${sale.vehiclePlate}`);
        }

        this.state.orderVersion = Date.now();
        // Limpiar cualquier línea de pago previa para arrancar el cobro limpio a 0,00 €
        if (currentOrder.get_paymentlines) {
            for (const pl of [...currentOrder.get_paymentlines()]) {
                currentOrder.remove_paymentline(pl);
            }
        }
        this.state.orderVersion = Date.now();
        // Abrir la pantalla de cobro / calculadora
        this.pos.showScreen("PaymentScreen");
    }

    async processRefundAction(sale, actionType) {
        this.closePendingSalesModal();

        // 1. Obtener o crear orden limpia en TPV
        let currentOrder = this.pos.get_order();
        if (!currentOrder || (currentOrder.get_orderlines && currentOrder.get_orderlines().length > 0)) {
            currentOrder = this.pos.add_new_order();
        }

        currentOrder.pending_sale_id = sale.id;
        currentOrder.pending_pump_id = sale.pumpId;
        currentOrder.is_refund_order = true;

        // 2. Localizar el producto de combustible
        const product = (sale.fuel && sale.fuel.productId ? this.pos.db.get_product_by_id(sale.fuel.productId) : null)
                        || this.findFuelProduct(sale.fuel.code || "GA");
        if (!product) {
            alert("No se encontró el producto de combustible en el catálogo.");
            return;
        }

        const unitPrice = sale.fuel.unitPrice || product.lst_price || 1.45;

        // Según 'PUNTO 2': 1 Línea en negativo del sobrante no echado con nota descriptiva del prefijado
        // Cantidad en negativo: refundQty (ej: -3.448 o -5.000)
        // Total en negativo: refundTotal (ej: -5.00 €)
        const refundQty = sale.refundLiters; 
        const refundTotal = sale.refundAmount; 

        // Calculamos precio unitario para el total neto objetivo
        const netPrice = this.getNetPriceForTargetTotal(product, Math.abs(refundTotal), Math.abs(refundQty), currentOrder);

        const rectRef = sale.orderRef ? ` | Rectifica: ${sale.orderRef}` : "";
        const descNota = (sale.isMoney
            ? `Calle ${sale.pumpId} - Sobrante de Prefijado [Prefijado: ${sale.presetAmount.toFixed(2)}€ | Repostado: ${sale.dispensedAmount.toFixed(2)}€ (${sale.dispensedLiters.toFixed(2)}L)]`
            : `Calle ${sale.pumpId} - Sobrante de Prefijado [Prefijado: ${sale.presetLiters.toFixed(2)}L | Repostado: ${sale.dispensedLiters.toFixed(2)}L (${sale.dispensedAmount.toFixed(2)}€)]`) + rectRef;

        await currentOrder.add_product(product, {
            quantity: refundQty, // ¡CANTIDAD EN NEGATIVO!
            price: netPrice,
            extras: {
                price_manually_set: true,
                pump_id: sale.pumpId,
                fuel_display_price: unitPrice,
                customerNote: descNota
            }
        });

        const activeLine = currentOrder.get_last_orderline();
        if (activeLine) {
            activeLine.pump_id = sale.pumpId;
            activeLine.fuel_display_price = unitPrice;
            if (activeLine.set_customer_note) {
                activeLine.set_customer_note(descNota);
            }

            // Ajuste fino milimétrico para que el total con impuestos sea exactamente refundTotal
            const curTotal = currentOrder.get_total_with_tax();
            const diff = Math.round((refundTotal - curTotal) * 100) / 100;
            if (Math.abs(diff) >= 0.01) {
                const q = Math.abs(activeLine.get_quantity()) || 1;
                activeLine.set_unit_price(activeLine.get_unit_price() - (diff / q));
            }
        }

        // Asignar cliente previo si existía en la orden original
        if (sale.partner) {
            currentOrder.set_partner(sale.partner);
        }
        if (sale.vehiclePlate) {
            this.state.vehiclePlate = sale.vehiclePlate;
            currentOrder.vehicle_plate = sale.vehiclePlate;
            if (currentOrder.set_note) currentOrder.set_note(`Matrícula: ${sale.vehiclePlate} | ${descNota}`);
        } else if (currentOrder.set_note) {
            currentOrder.set_note(descNota);
        }

        // Limpiar payment lines previas para arrancar limpio
        if (currentOrder.get_paymentlines) {
            for (const pl of [...currentOrder.get_paymentlines()]) {
                currentOrder.remove_paymentline(pl);
            }
        }

        this.state.orderVersion = Date.now();

        // 3. Ejecutar la acción seleccionada (Requirement 10)
        if (actionType === 'ticket') {
            // Hacer Ticket: abre pantalla de pago con el total negativo preparado para devolver en efectivo o tarjeta
            this.pos.showScreen("PaymentScreen");
        } else if (actionType === 'factura') {
            currentOrder.set_to_invoice(true);
            this.pos.showScreen("PaymentScreen");
            if (!currentOrder.get_partner()) {
                setTimeout(() => {
                    const clientBtn = document.querySelector(".button.set-partner");
                    if (clientBtn) clientBtn.click();
                }, 200);
            }
        } else if (actionType === 'albaran') {
            currentOrder.is_albaran = true;
            currentOrder.set_to_invoice(false);
            const targetPartner = (sale && sale.partner) || this.currentOrderPartner;
            if (targetPartner && !currentOrder.get_partner()) {
                currentOrder.set_partner(targetPartner);
            }
            this.pos.showScreen("PaymentScreen");
            if (!currentOrder.get_partner()) {
                setTimeout(() => {
                    const clientBtn = document.querySelector(".button.set-partner");
                    if (clientBtn) clientBtn.click();
                }, 200);
            }
        }
    }



    getNetPriceForTargetTotal(product, targetTotal, qty, order = null) {
        if (!product || !qty || qty <= 0) return targetTotal;
        const currentOrder = order || this.getOrCreateOrder();
        const taxesIds = product.taxes_id || [];
        const productTaxes = this.pos.get_taxes_after_fp(taxesIds, (currentOrder ? currentOrder.fiscal_position : null));

        if (!productTaxes || productTaxes.length === 0) {
            return targetTotal / qty;
        }

        const allIncluded = productTaxes.every(t => t.price_include);
        if (allIncluded) {
            return targetTotal / qty;
        }

        try {
            const sampleRes = this.pos.compute_all(productTaxes, 1.0, 1, this.pos.currency.rounding, false);
            const factor = sampleRes.total_included > 0 ? sampleRes.total_included : 1.0;
            const netTotal = targetTotal / factor;
            return netTotal / qty;
        } catch (e) {
            const taxSum = productTaxes.reduce((sum, t) => sum + (t.amount || 0), 0);
            const factor = 1.0 + (taxSum / 100.0);
            return (targetTotal / factor) / qty;
        }
    }

    getLineDisplayUnitPrice(line) {
        if (!line) return "0.000";
        if (line.fuel_display_price) {
            return Number(line.fuel_display_price).toFixed(3);
        }
        if (line.product && line.product.lst_price) {
            return Number(line.product.lst_price).toFixed(3);
        }
        const qty = Math.abs(line.get_quantity()) || 1;
        return (line.get_display_price() / qty).toFixed(3);
    }

    isNozzleUnhooked(pump) {
        if (!pump) return false;
        // Estado físico reportado directamente por el microswitch del surtidor (SDES)
        if (pump.is_descolgada === true) {
            return true;
        }
        // Si no hay telemetría explícita de microswitch pero el medidor físico ya está suministrando litros activamente (>0.02L)
        if (pump.status === "dispensing" && Number(pump.liters || 0) > 0.02) {
            return true;
        }
        return false;
    }

    isPumpDispensing(pump) {
        if (!pump) return false;
        return (pump.status === "dispensing" && (Number(pump.liters || 0) > 0.02 || (pump.statusText || "").includes("SUMINISTRO") || (pump.statusText || "").includes("AUTORIZADO") || (pump.statusText || "").includes("LLENO")));
    }

    getPumpPresetAmount(pump) {
        if (!pump) return 0;
        // Si la pista está bloqueada, en reposo o con cobros pendientes, el importe en display es estrictamente 0
        if (pump.status === "blocked" || pump.status === "idle" || pump.status === "ready" || (pump.statusText || "").includes("SIN PREFIJADO") || (pump.statusText || "").includes("COBROS")) {
            return 0;
        }
        if (pump.preset_amount && pump.preset_amount > 0) return pump.preset_amount;
        if (this.state.pumpPresets && this.state.pumpPresets[pump.id]) {
            return this.state.pumpPresets[pump.id].amount || 0;
        }
        return 0;
    }

    getPumpFuelCode(pump) {
        if (!pump) return 'GA';
        if (pump.fuel && pump.fuel !== 'N/A') {
            const f = pump.fuel.toLowerCase();
            // Si es la etiqueta generica de surtidor libre / multiproducto en reposo
            if (f.includes('/') || f.includes('libre') || (f.includes('gasóleo a') && f.includes('95'))) {
                if (this.state && this.state.pumpPresets && this.state.pumpPresets[pump.id]) {
                    return this.state.pumpPresets[pump.id].code || 'GA';
                }
                return (this.state && this.state.selectedFuel) ? this.state.selectedFuel : 'GA';
            }
            if (f.includes('plus') || f.includes('g+')) return 'G+';
            if (f.includes('95') || f.includes('plomo')) return '95';
            if (f.includes('gasóleo b') || f.includes('diesel b')) return 'GB';
            if (f.includes('gasóleo a') || f.includes('diesel a') || f.includes('ga')) return 'GA';
            return 'GA';
        }
        if (this.state.pumpPresets && this.state.pumpPresets[pump.id]) {
            return this.state.pumpPresets[pump.id].code || 'GA';
        }
        return (this.state && this.state.selectedFuel) ? this.state.selectedFuel : 'GA';
    }

    openCancelModal(pump) {
        if (!pump) return;
        this.state.selectedPumpId = pump.id;
        this.state.cancelModalPump = pump;
        this.state.isCancelModalOpen = true;
    }

    closeCancelModal() {
        this.state.isCancelModalOpen = false;
        this.state.cancelModalPump = null;
    }

    async cancelPumpAuthorization(pump) {
        const pumpId = pump ? pump.id : this.state.selectedPumpId;
        if (!pumpId) return;

        this.closeCancelModal();

        // Si la calle tenía matricula vinculada, restaurarla
        if (this.pos && this.pos.pumpPendingPlates && this.pos.pumpPendingPlates[pumpId]) {
            const savedPlate = this.pos.pumpPendingPlates[pumpId];
            delete this.pos.pumpPendingPlates[pumpId];
            this.savePumpPendingPlates();
            if (savedPlate && !this.state.vehiclePlate) {
                this.setVehiclePlate(savedPlate);
            }
        }

        // Si la calle tenía productos de tienda vinculados, restaurarlos en el ticket actual para no perderlos
        if (this.pos && this.pos.pumpPendingStoreItems && this.pos.pumpPendingStoreItems[pumpId]) {
            const storeItems = this.pos.pumpPendingStoreItems[pumpId];
            delete this.pos.pumpPendingStoreItems[pumpId];
            this.savePumpPendingStoreItems();
            const currentOrder = this.getOrCreateOrder();
            for (const item of storeItems) {
                const prod = this.pos.db.get_product_by_id(item.productId);
                if (prod) {
                    await currentOrder.add_product(prod, {
                        quantity: item.qty,
                        price: item.price,
                        extras: { price_manually_set: true }
                    });
                }
            }
        }

        await this.resetAndLockPump(pumpId, true, true);

        // REGLA USUARIO: Si ese surtidor tuviese alguna monedita pendiente previamente,
        // la pista se cierra pero el color del surtidor debe quedar NARANJA con sus moneditas.
        // Si ya no quedan monedas pendientes, es cuando debe quedar en ROJO.
        const targetPump = this.state.pumps && this.state.pumps.find(p => p.id === pumpId);
        if (targetPump) {
            const pendingCount = this.getPumpPendingSalesCount(targetPump);
            if (pendingCount > 0) {
                targetPump.status = "ready";
                targetPump.statusText = pendingCount === 1 ? "COBRAR" : `COBROS (${pendingCount})`;
            } else {
                targetPump.status = "blocked";
                targetPump.statusText = "PREPAGO";
            }
        }

        this.state.orderVersion = Date.now();
    }

    get selectedFuelObj() {
        if (!this.state.selectedFuel) return null;
        return this.state.availableFuels.find(f => f.code === this.state.selectedFuel) || null;
    }

    removeLineFromOrder(currentOrder, line) {
        if (!currentOrder || !line) return;
        try {
            if (typeof currentOrder.removeOrderline === "function") {
                currentOrder.removeOrderline(line);
            } else if (typeof currentOrder._unlink_order_line === "function") {
                currentOrder._unlink_order_line(line);
            } else if (typeof currentOrder.remove_orderline === "function") {
                currentOrder.remove_orderline(line);
            } else if (typeof line.delete === "function") {
                line.delete();
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
    }

    isFuelProduct(product) {
        if (!product) return false;
        const c = (product.default_code || "").toUpperCase();
        const n = (product.display_name || product.name || "").toLowerCase();
        return c.includes("GAS_") || c.includes("SP95") || c.includes("DIESEL") ||
               n.includes("gasóleo") || n.includes("gasoleo") || n.includes("sin plomo") || n.includes("diesel") || n.includes("gasolina");
    }

    removePendingFuelLinesFromOrder(currentOrder) {
        if (!currentOrder) return;
        const lines = (currentOrder.get_orderlines ? currentOrder.get_orderlines() : []).slice();
        for (const l of lines) {
            if (this.isFuelProduct(l.product)) {
                this.removeLineFromOrder(currentOrder, l);
            }
        }
        if (currentOrder.pending_prepay) {
            currentOrder.pending_prepay = null;
        }
        this.state.orderVersion = Date.now();
    }

    async preparePrepayOrderLine(pumpId, fuelCode, presetVal, isMoney) {
        const currentOrder = this.getOrCreateOrder();
        if (!currentOrder) return null;

        const product = this.findFuelProduct(fuelCode);
        if (!product) return null;

        // Limpiar cualquier otra línea de combustible previa en este ticket
        // garantizando que sólo quede la operación actual (sin alterar los productos de tienda/inventario)
        const allLines = (currentOrder.get_orderlines ? currentOrder.get_orderlines() : []).slice();
        for (const l of allLines) {
            if (this.isFuelProduct(l.product) && l.pump_id !== pumpId) {
                this.removeLineFromOrder(currentOrder, l);
            }
        }

        const currentFuelPrice = product.lst_price > 0 ? product.lst_price : (fuelCode === 'GA' ? 1.78 : 1.66);
        let qty = 1;
        let targetTotal = presetVal;

        if (isMoney) {
            targetTotal = presetVal;
            qty = parseFloat((presetVal / currentFuelPrice).toFixed(3));
            if (qty <= 0) qty = 1;
        } else {
            qty = presetVal;
            targetTotal = presetVal * currentFuelPrice;
        }

        const unitPrice = this.getNetPriceForTargetTotal(product, targetTotal, qty, currentOrder);

        const lines = currentOrder.get_orderlines();
        const existingLine = lines.find(l => 
            l.pump_id === pumpId || 
            (!l.pump_id && this.isFuelProduct(l.product)) ||
            (l.customerNote && l.customerNote.includes(`Calle ${pumpId}`))
        );

        let activeLine = existingLine;
        if (existingLine) {
            existingLine.product = product;
            existingLine.set_quantity(qty);
            existingLine.set_unit_price(unitPrice);
            existingLine.pump_id = pumpId;
            existingLine.fuel_display_price = currentFuelPrice;
            existingLine.target_total = targetTotal;
            existingLine.price_type = "manual";
        } else {
            await currentOrder.add_product(product, {
                quantity: qty,
                price: unitPrice,
                extras: {
                    price_manually_set: true,
                    price_type: "manual",
                    pump_id: pumpId,
                    fuel_display_price: currentFuelPrice,
                    target_total: targetTotal
                }
            });
            activeLine = currentOrder.get_last_orderline();
            if (activeLine) {
                activeLine.pump_id = pumpId;
                activeLine.fuel_display_price = currentFuelPrice;
                activeLine.target_total = targetTotal;
                activeLine.price_type = "manual";
            }
        }

        // Blindaje milimétrico de redondeo: garantiza que el importe sea exactamente presetVal (sin saltos de céntimo)
        if (activeLine && targetTotal > 0) {
            const currentDisp = activeLine.get_display_price();
            const diff = Math.round((targetTotal - currentDisp) * 100) / 100;
            if (Math.abs(diff) >= 0.005) {
                const curQty = activeLine.get_quantity() || 1;
                const taxes = activeLine.get_taxes ? activeLine.get_taxes() : [];
                let taxFactor = 1.0;
                if (taxes && taxes.length > 0 && !taxes[0].price_include) {
                    const taxRate = taxes.reduce((s, t) => s + (t.amount || 0), 0);
                    taxFactor = 1.0 + (taxRate / 100.0);
                }
                activeLine.set_unit_price(activeLine.get_unit_price() + (diff / (curQty * taxFactor)));
            }
        }

        const fuelObj = this.state.availableFuels.find(f => f.code === fuelCode) || { name: product.display_name };
        const plateInfo = this.state.vehiclePlate ? `Matrícula: ${this.state.vehiclePlate} | ` : "";
        if (currentOrder.set_note) {
            currentOrder.set_note(`${plateInfo}Calle ${pumpId} [Prepago: ${presetVal.toFixed(2)} ${isMoney ? '€' : 'L'}]`);
        }

        currentOrder.pump_id = pumpId;
        if (activeLine && activeLine.set_customer_note) {
            activeLine.set_customer_note(`Calle ${pumpId} [Prepago: ${presetVal.toFixed(2)} ${isMoney ? '€' : 'L'}]`);
        }

        currentOrder.pending_prepay = {
            pump_id: pumpId,
            fuel: fuelCode,
            fuelName: fuelObj.name || product.display_name,
            amount: isMoney ? presetVal : 0,
            liters: !isMoney ? presetVal : 0,
            isMoney: isMoney,
            presetVal: presetVal,
            productId: product.id,
            vehiclePlate: (this.state && this.state.vehiclePlate) || ""
        };

        this.state.orderVersion = Date.now();
        return activeLine;
    }

    async onPumpCardClick(pump) {
        this.state.selectedPumpId = pump.id;

        // 1. Si está suministrando activamente o autorizada a Lleno/Postpago: abrir ventana de cancelación
        if (this.isPumpDispensing(pump) || pump.status === 'dispensing' || (pump.statusText || '').includes('AUTORIZADO') || (pump.statusText || '').includes('SUMINISTRO')) {
            this.openCancelModal(pump);
            return;
        }

        // 2. El importe prefijado ÚNICAMENTE proviene del valor tecleado en el teclado numérico / billetes de pista.
        let presetVal = this.state.presetValue || 0;
        let fuelCode = this.state.selectedFuel;

        // Solo si la orden actual ya contiene un prepago pendiente específico de ESTA MISMA calle
        const currentOrder = this.getOrCreateOrder();
        if (currentOrder && (!presetVal || presetVal <= 0) && currentOrder.pending_prepay && currentOrder.pending_prepay.pump_id === pump.id) {
            presetVal = currentOrder.pending_prepay.presetVal || currentOrder.pending_prepay.amount || 0;
            fuelCode = currentOrder.pending_prepay.fuel || fuelCode;
            this.state.selectedFuel = fuelCode;
        }

        const isMoney = this.state.mode === "money";
        const isLleno = (presetVal === 0 || (!isMoney && presetVal >= 999));
        const isPrepay = Boolean(presetVal > 0 && !isLleno);

        // === CASO PRE-PAGO (El cajero tecleó un importe > 0 expresamente para prepago) ===
        if (isPrepay) {
            if (!this.state.selectedFuel) {
                // Abrir modal de confirmación para que seleccione el combustible del prepago
                this.openAuthorizeModal(pump);
                return;
            }

            if (this.isPumpDispensing(pump) || pump.is_descolgada || (pump.status === "dispensing" && pump.liters > 0.05)) {
                alert(`⚠️ La Calle ${pump.id} está suministrando activamente en pista.\nEspere a que el cliente cuelgue la manguera para una nueva autorización.`);
                return;
            }

            await this.preparePrepayOrderLine(pump.id, this.state.selectedFuel, presetVal, isMoney);
            this.state.presetValue = 0;
            this.state.selectedFuel = null;
            this.goToPayment();
            return;
        }

        // === CASO SUMINISTRO LIBRE CON COMBUSTIBLE SELECCIONADO EN PANTALLA ===
        if (this.state.selectedFuel) {
            await this.executeAuthorizePump(pump.id);
            this.state.selectedFuel = null;
            return;
        }

        // === CASO SIN COMBUSTIBLE PREVIO: ABRIR MODAL PARA SELECCIONAR COMBUSTIBLE Y AUTORIZAR ===
        // REGLA CRÍTICA DE OPERATIVA DE PISTA:
        // Hacer clic en la tarjeta del surtidor NUNCA carga el ticket ni altera las monedas pendientes.
        // El ticket para cobro se carga ÚNICAMENTE haciendo clic sobre la monedita dorada.
        // Por tanto, pulsar sobre el surtidor abre SIEMPRE el modal de autorización para permitir
        // autorizar a un nuevo cliente (incluso si la calle tiene 1 o varias monedas pendientes de cobro).
        this.openAuthorizeModal(pump);
    }

    openAuthorizeModal(pump) {
        if (!pump) return;
        this.state.selectedPumpId = pump.id;
        this.state.authModalPump = pump;

        // Si la calle ya tiene un preset o combustible previo en curso, fijarlo a ese combustible
        if (this.state.pumpPresets && this.state.pumpPresets[pump.id] && this.state.pumpPresets[pump.id].code) {
            this.state.selectedFuel = this.state.pumpPresets[pump.id].code;
        }

        this.state.isAuthModalOpen = true;
    }

    closeAuthorizeModal() {
        this.state.isAuthModalOpen = false;
        this.state.authModalPump = null;
    }

    async confirmAndAuthorize() {
        const pump = this.state.authModalPump || this.state.pumps.find(p => p.id === this.state.selectedPumpId);
        if (pump) {
            const isMoney = this.state.mode === "money";
            const presetVal = this.state.presetValue || 0;
            const isLleno = (presetVal === 0 || (!isMoney && presetVal >= 999));
            const isPrepay = Boolean(presetVal > 0 && !isLleno);

            if (!this.state.selectedFuel) {
                this.state.presetValue = 0;
                this.removePendingFuelLinesFromOrder(this.pos.get_order());
                alert(`⚠️ ¡ATENCIÓN! Debe seleccionar obligatoriamente el tipo de combustible (Gasóleo A, Sin Plomo 95...) antes de confirmar la apertura de la calle.\n\nPor seguridad del vehículo no está permitido el suministro multiproducto.`);
                return;
            }

            this.closeAuthorizeModal();

            if (isPrepay) {
                await this.preparePrepayOrderLine(pump.id, this.state.selectedFuel, presetVal, isMoney);
                this.state.presetValue = 0;
                this.state.selectedFuel = null;
                this.goToPayment();
            } else {
                await this.executeAuthorizePump(pump.id);
                this.state.selectedFuel = null;
            }
        }
    }

    toggleMode() {
        this.state.mode = this.state.mode === "money" ? "liters" : "money";
        this.state.presetValue = 0;
    }

    addPreset(val) {
        this.state.presetValue = (this.state.presetValue || 0) + val;
    }

    selectFuel(fuel) {
        if (this.state.selectedFuel === fuel) {
            this.state.selectedFuel = null;
            return;
        }
        this.state.selectedFuel = fuel;
        // Si hay una linea de combustible en la orden activa que aun no ha sido autorizada en bomba, actualizar su producto
        const currentOrder = this.pos.get_order();
        if (currentOrder) {
            const product = this.findFuelProduct(fuel);
            if (product) {
                const lines = currentOrder.get_orderlines();
                const unlinkedFuelLine = lines.find(l => {
                    if (!l.product || l.pump_id) return false;
                    const c = (l.product.default_code || "").toUpperCase();
                    const n = (l.product.display_name || l.product.name || "").toLowerCase();
                    return c.includes("GAS_A") || c.includes("SP95") || c.includes("GAS_PLUS") || c.includes("GAS_B") ||
                           n.includes("gasóleo") || n.includes("gasoleo") || n.includes("sin plomo") || n.includes("diesel");
                });
                if (unlinkedFuelLine && unlinkedFuelLine.product.id !== product.id) {
                    unlinkedFuelLine.product = product;
                    unlinkedFuelLine.set_unit_price(product.lst_price);
                    this.state.orderVersion = Date.now();
                }
            }
        }
    }

    
    async toggleTrackMode() {
        const nextMode = this.state.trackMode === "atendido" ? "prepago" : "atendido";
        this.state.trackMode = nextMode;
        localStorage.setItem("utrecar_track_mode", nextMode);
        
        // Update idle pumps instantly in memory
        if (this.state.pumps && Array.isArray(this.state.pumps)) {
            for (const pump of this.state.pumps) {
                if (pump.status === "idle" || pump.status === "blocked" || pump.status === "atendido") {
                    if (nextMode === "atendido") {
                        pump.status = "atendido";
                        pump.statusText = "LIBRE";
                    } else {
                        pump.status = "blocked";
                        pump.statusText = "PREPAGO";
                    }
                }
            }
        }
        this.state.orderVersion = Date.now();

        // Enviar orden al backend Odoo y hardware de pista
        try {
            await jsonrpc("/pos_gas_station/set_track_mode", {
                config_id: this.pos.config.id,
                mode: nextMode
            });
        } catch (err) {
            console.error("Error al sincronizar modo global de pista:", err);
        }
    }

    async togglePumpMode(pump, ev) {
        if (ev) {
            ev.stopPropagation();
            ev.preventDefault();
        }
        if (!pump) return;
        // No conmutar si la pista está en pleno repostaje o pendiente de cobro
        if (pump.status === "dispensing" || pump.status === "ready") {
            return;
        }

        const isCurrentlyOpen = (pump.status === "atendido" || pump.status === "postpago");
        const nextPumpMode = isCurrentlyOpen ? "prepago" : "atendido";

        // Actualizar visualmente de inmediato
        pump.status = nextPumpMode === "atendido" ? "atendido" : "blocked";
        pump.statusText = nextPumpMode === "atendido" ? "LIBRE" : "PREPAGO";
        this.state.orderVersion = Date.now();

        // Enviar orden al backend Odoo y hardware de pista para esta calle específica
        try {
            await jsonrpc("/pos_gas_station/set_track_mode", {
                config_id: this.pos.config.id,
                mode: nextPumpMode,
                pump_id: pump.id
            });
        } catch (err) {
            console.error(`Error al sincronizar modo de Calle ${pump.id}:`, err);
        }
    }

    promptCustomAmount() {
        const unit = this.state.mode === "money" ? "€" : "Litros";
        const currentVal = this.state.presetValue > 0 ? this.state.presetValue.toString() : "";
        const input = prompt(`⌨️ INTRODUCIR CANTIDAD CON DECIMALES (${unit}):\n(Ejemplo: 15.50 o 32,80)`, currentVal);
        if (input !== null) {
            const clean = input.trim().replace(",", ".");
            if (clean === "" || clean === "0") {
                this.state.presetValue = 0;
            } else {
                const parsed = parseFloat(clean);
                if (!isNaN(parsed) && parsed > 0) {
                    this.state.presetValue = parseFloat(parsed.toFixed(2));
                } else {
                    alert("Por favor, introduzca un número válido con punto o coma decimal.");
                }
            }
        }
    }

    clearPreset() {
        this.state.presetValue = 0;
        this.state.selectedFuel = null;
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

    authorizePreset(targetPumpId = null) {
        const targetId = targetPumpId || this.state.selectedPumpId;
        if (!targetId) return;
        const pump = this.state.pumps.find(p => p.id === targetId);
        if (pump) {
            this.onPumpCardClick(pump);
        }
    }

    async executeAuthorizePump(pumpId) {
        this.state.selectedPumpId = pumpId;
        const targetPump = this.state.pumps.find(p => p.id === pumpId);

        if (targetPump && (this.isPumpDispensing(targetPump) || targetPump.is_descolgada || (targetPump.status === "dispensing" && targetPump.liters > 0.05))) {
            alert(`⚠️ La Calle ${pumpId} está suministrando activamente en pista.\nEspere a que el cliente cuelgue la manguera para una nueva autorización.`);
            return;
        }

        const isMoney = this.state.mode === "money";
        const presetVal = this.state.presetValue;

        const isLleno = (presetVal === 0 || (!isMoney && presetVal >= 999));
        const isPrepay = Boolean(presetVal > 0 && !isLleno);

        if (isPrepay) {
            if (!this.state.selectedFuel) {
                alert(`⚠️ Ha indicado un importe prefijado (${presetVal.toFixed(2)} ${isMoney ? '€' : 'L'}).\nDebe seleccionar el tipo de combustible antes de continuar.`);
                return;
            }
            await this.preparePrepayOrderLine(pumpId, this.state.selectedFuel, presetVal, isMoney);
            this.state.presetValue = 0;
            this.state.selectedFuel = null;
            this.goToPayment();
            return;
        }

        if (!this.state.selectedFuel) {
            alert(`⚠️ ¡ATENCIÓN! Debe seleccionar obligatoriamente el tipo de combustible (Gasóleo A, Sin Plomo 95...) antes de autorizar la Calle ${pumpId}.\n\nPor seguridad no está permitido el suministro multiproducto.`);
            return;
        }

        const currentFuelObj = this.selectedFuelObj;
        const fuelName = currentFuelObj ? currentFuelObj.name : "Combustible";
        const fuelCode = currentFuelObj ? currentFuelObj.code : this.state.selectedFuel;

        if (!this.state.pumpPresets) {
            this.state.pumpPresets = {};
        }
        this.state.pumpPresets[pumpId] = {
            amount: presetVal,
            fuel: fuelName,
            code: fuelCode,
            isMoney: isMoney,
            hasPrepay: isPrepay,
            isLleno: isLleno
        };

        if (targetPump) {
            targetPump.status = "dispensing";
            targetPump.statusText = isLleno ? "LLENO (POSTPAGO)" : "AUTORIZADO";
            targetPump.fuel = fuelName;
            targetPump.preset_amount = presetVal;
            targetPump.has_prepay = isPrepay;
            targetPump.is_lleno = isLleno;
            if (presetVal > 0) {
                targetPump.amount = isMoney ? presetVal : 0;
                targetPump.liters = !isMoney ? presetVal : 0;
            } else {
                targetPump.amount = 0;
                targetPump.liters = 0;
            }
        }

        if (presetVal > 0) {
            const currentOrder = this.getOrCreateOrder();
            if (currentOrder) {
                const product = this.findFuelProduct(fuelCode);

                if (product) {
                    const currentFuelPrice = product.lst_price > 0 ? product.lst_price : (fuelCode === 'GA' ? 1.78 : 1.66);
                    let qty = 1;
                    let targetTotal = presetVal;

                    if (isMoney) {
                        targetTotal = presetVal;
                        // Usar 3 decimales para litros (mililitros en combustible) para evitar saltos de céntimo
                        qty = parseFloat((presetVal / currentFuelPrice).toFixed(3));
                        if (qty <= 0) qty = 1;
                    } else {
                        qty = presetVal;
                        targetTotal = presetVal * currentFuelPrice;
                    }

                    const unitPrice = this.getNetPriceForTargetTotal(product, targetTotal, qty, currentOrder);

                    const existingLine = currentOrder.get_orderlines().find(l => l.pump_id === pumpId || (l.customerNote && l.customerNote.includes(`Calle ${pumpId}`)));
                    let activeLine = existingLine;
                    if (existingLine) {
                        existingLine.set_quantity(qty);
                        existingLine.set_unit_price(unitPrice);
                        existingLine.fuel_display_price = currentFuelPrice;
                        existingLine.target_total = targetTotal;
                        existingLine.price_type = "manual";
                    } else {
                        await currentOrder.add_product(product, {
                            quantity: qty,
                            price: unitPrice,
                            extras: {
                                price_manually_set: true,
                                price_type: "manual",
                                pump_id: pumpId,
                                fuel_display_price: currentFuelPrice,
                                target_total: targetTotal
                            }
                        });
                        activeLine = currentOrder.get_last_orderline();
                        if (activeLine) {
                            activeLine.pump_id = pumpId;
                            activeLine.fuel_display_price = currentFuelPrice;
                            activeLine.target_total = targetTotal;
                            activeLine.price_type = "manual";
                        }
                    }

                    // Blindaje milimétrico de redondeo: garantiza que el importe sea exactamente presetVal (sin .01 ni .99)
                    if (activeLine && targetTotal > 0) {
                        const currentDisp = activeLine.get_display_price();
                        const diff = Math.round((targetTotal - currentDisp) * 100) / 100;
                        if (Math.abs(diff) >= 0.005) {
                            const curQty = activeLine.get_quantity() || 1;
                            const taxes = activeLine.get_taxes ? activeLine.get_taxes() : [];
                            let taxFactor = 1.0;
                            if (taxes && taxes.length > 0 && !taxes[0].price_include) {
                                const taxRate = taxes.reduce((s, t) => s + (t.amount || 0), 0);
                                taxFactor = 1.0 + (taxRate / 100.0);
                            }
                            activeLine.set_unit_price(activeLine.get_unit_price() + (diff / (curQty * taxFactor)));
                        }
                    }

                    const plateInfo = this.state.vehiclePlate ? `Matrícula: ${this.state.vehiclePlate} | ` : "";
                    if (currentOrder.set_note) currentOrder.set_note(`${plateInfo}Calle ${pumpId} [Prepago: ${presetVal} ${isMoney ? '€' : 'L'}]`);
                    this.state.orderVersion = Date.now();
                }
            }
        }

        // Si la orden actual contiene productos de tienda/inventario (ej. Coca-Cola, snacks)
        // o se ha especificado una matrícula, se vinculan a la calle autorizada para que pasen a la monedita con el combustible,
        // dejando el ticket actual en blanco para atender o autorizar a otro cliente de inmediato.
        if (!isPrepay) {
            const currentOrder = this.pos.get_order();
            if (currentOrder) {
                const lines = (currentOrder.get_orderlines ? currentOrder.get_orderlines() : []).slice();
                const storeItems = [];
                for (const l of lines) {
                    if (!this.isFuelProduct(l.product)) {
                        storeItems.push({
                            productId: l.product.id,
                            name: l.product.display_name,
                            qty: l.get_quantity ? l.get_quantity() : 1,
                            price: l.get_unit_price ? l.get_unit_price() : l.price,
                            discount: l.get_discount ? l.get_discount() : 0,
                            amount: l.get_display_price ? l.get_display_price() : (l.price * l.quantity),
                            customerNote: l.get_customer_note ? l.get_customer_note() : ""
                        });
                    }
                }
                const pendingPlate = (this.state && this.state.vehiclePlate) || (currentOrder.vehicle_plate) || "";
                if (pendingPlate) {
                    if (!this.pos.pumpPendingPlates) {
                        this.pos.pumpPendingPlates = {};
                    }
                    this.pos.pumpPendingPlates[pumpId] = pendingPlate;
                    this.savePumpPendingPlates();
                }
                if (storeItems.length > 0 || pendingPlate) {
                    if (storeItems.length > 0) {
                        if (!this.pos.pumpPendingStoreItems) {
                            this.pos.pumpPendingStoreItems = {};
                        }
                        this.pos.pumpPendingStoreItems[pumpId] = storeItems;
                        this.savePumpPendingStoreItems();
                    }

                    // Dejar el ticket activo en blanco de inmediato
                    this.pos.removeOrder(currentOrder);
                    this.pos.add_new_order();
                    this.state.selectedLineId = null;
                    this.state.vehiclePlate = "";
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
                liters: !isMoney ? presetVal : 0,
                has_prepay: Boolean(isPrepay)
            });
        } catch (e) {
            console.debug("Orden de autorización enviada:", e);
        }

        this.state.presetValue = 0;
        this.state.selectedFuel = null;
        this.state.selectedPumpId = pumpId;
    }

    onSecurityDepositClick() {
        this.openCashMoveModal();
    }

    openCashMoveModal() {
        this.state.isCashMoveModalOpen = true;
        this.state.cashMoveType = "ingreso_seguridad";
        this.state.cashMoveAmount = "500";
        this.state.cashMoveNotes = "";
        this.state.cashMoveSupplier = null;
        this.state.cashMoveSupplierSearch = "";
        this.state.cashMoveSupplierResults = [];
        this.state.isSearchingSuppliers = false;
    }

    closeCashMoveModal() {
        this.state.isCashMoveModalOpen = false;
        this.state.cashMoveAmount = "";
        this.state.cashMoveNotes = "";
        this.state.cashMoveSupplier = null;
        this.state.cashMoveSupplierSearch = "";
        this.state.cashMoveSupplierResults = [];
        this.state.isSearchingSuppliers = false;
    }

    selectCashMoveType(type) {
        this.state.cashMoveType = type;
        if (type === "ingreso_seguridad") {
            if (!this.state.cashMoveAmount) this.state.cashMoveAmount = "500";
        } else if (type === "pago_proveedores") {
            if (!this.state.cashMoveSupplierResults.length && !this.state.cashMoveSupplier) {
                this.searchSuppliers("");
            }
        }
    }

    async searchSuppliers(query) {
        this.state.isSearchingSuppliers = true;
        try {
            const res = await this.env.services.rpc("/pos_gas_station/search_suppliers", { query: query || "" });
            if (res && res.status === "success") {
                this.state.cashMoveSupplierResults = res.suppliers || [];
            }
        } catch (e) {
            console.error("Error search_suppliers:", e);
        } finally {
            this.state.isSearchingSuppliers = false;
        }
    }

    onSupplierSearchFocus() {
        if (!this.state.cashMoveSupplierResults.length && !this.state.cashMoveSupplier) {
            this.searchSuppliers(this.state.cashMoveSupplierSearch || "");
        }
    }

    onSupplierSearchInput(ev) {
        const query = ev.target.value;
        this.state.cashMoveSupplierSearch = query;
        this.searchSuppliers(query);
    }

    clearSupplierSearchText() {
        this.state.cashMoveSupplierSearch = "";
        this.searchSuppliers("");
    }

    selectCashMoveSupplier(supplier) {
        this.state.cashMoveSupplier = supplier;
        this.state.cashMoveSupplierSearch = "";
        this.state.cashMoveSupplierResults = [];
    }

    clearCashMoveSupplier() {
        this.state.cashMoveSupplier = null;
        this.state.cashMoveSupplierSearch = "";
        this.searchSuppliers("");
    }

    setQuickCashMoveAmount(val) {
        this.state.cashMoveAmount = String(val);
    }

    getCashMoveNotesPlaceholder() {
        if (this.state.cashMoveType === "ingreso_seguridad") {
            return "Ej: Sobre UAAP #12 / Retirada por exceso de efectivo";
        } else if (this.state.cashMoveType === "salidas_varias") {
            return "Ej: Material de limpieza, ferretería, reparaciones...";
        } else if (this.state.cashMoveType === "pago_proveedores") {
            return "Ej: Factura F-2026/041 o Albarán";
        }
        return "Detalle u observaciones del movimiento";
    }

    async confirmCashMove() {
        const rawAmount = (this.state.cashMoveAmount || "").toString().trim().replace(",", ".");
        const amount = parseFloat(rawAmount);
        if (isNaN(amount) || amount <= 0) {
            alert("Por favor, introduzca un importe válido superior a 0 €.");
            return;
        }

        if (this.state.cashMoveType === "pago_proveedores" && !this.state.cashMoveSupplier) {
            alert("⚠️ Por favor, seleccione el proveedor al que se realiza el pago.");
            return;
        }

        let typeLabel = "Salida de efectivo";
        let reason = "Movimiento de caja";
        let supplierId = null;

        if (this.state.cashMoveType === "ingreso_seguridad") {
            typeLabel = "Ingreso de seguridad";
            reason = "Ingreso de seguridad (Caja Fuerte UAAP)";
        } else if (this.state.cashMoveType === "salidas_varias") {
            typeLabel = "Salidas varias";
            reason = "Salidas varias";
        } else if (this.state.cashMoveType === "pago_proveedores") {
            typeLabel = "Pago factura a proveedores";
            const sup = this.state.cashMoveSupplier;
            supplierId = sup.id;
            const vatStr = sup.vat ? ` (${sup.vat})` : "";
            reason = `Pago proveedor: ${sup.name}${vatStr}`;
        }

        const notes = (this.state.cashMoveNotes || "").trim();
        const fullReason = notes ? `${reason} - ${notes}` : reason;
        const formattedAmount = `${amount.toFixed(2)} €`;

        try {
            let recorded = false;
            // 1. Try via controller endpoint to link partner_id in account.bank.statement.line
            try {
                const res = await this.env.services.rpc("/pos_gas_station/cash_move", {
                    session_id: this.pos.pos_session?.id,
                    amount: amount,
                    reason: fullReason,
                    translated_type: "Salida",
                    partner_id: supplierId,
                });
                if (res && res.status === "success") {
                    recorded = true;
                }
            } catch (rpcErr) {
                console.warn("Aviso en /pos_gas_station/cash_move, usando try_cash_in_out fallback:", rpcErr);
            }

            // 2. Fallback to try_cash_in_out if needed
            if (!recorded) {
                if (this.pos.pos_session?.id && this.orm) {
                    await this.orm.call("pos.session", "try_cash_in_out", [
                        [this.pos.pos_session.id],
                        "out",
                        amount,
                        fullReason,
                        {
                            formattedAmount: formattedAmount,
                            translatedType: "Salida",
                        },
                    ]);
                } else if (typeof this.pos.create_cash_move === "function") {
                    await this.pos.create_cash_move(-amount, fullReason);
                }
            }

            const supplierInfo = this.state.cashMoveSupplier ? `\n🏢 Proveedor: ${this.state.cashMoveSupplier.name}` : "";
            alert(`✅ REGISTRADO CORRECTAMENTE\n\n📌 Tipo: ${typeLabel}${supplierInfo}\n💶 Importe: ${formattedAmount}\n${notes ? "📝 Factura/Detalle: " + notes + "\n" : ""}\nEl movimiento ha quedado registrado en el turno de caja.`);
            this.closeCashMoveModal();
        } catch (err) {
            console.error("Error registrando movimiento de caja:", err);
            try {
                if (typeof this.pos.create_cash_move === "function") {
                    await this.pos.create_cash_move(-amount, fullReason);
                    alert(`✅ REGISTRADO CORRECTAMENTE: ${typeLabel} de ${formattedAmount}.`);
                    this.closeCashMoveModal();
                    return;
                }
            } catch (fallbackErr) {
                console.error("Error fallback create_cash_move:", fallbackErr);
            }
            alert(`⚠️ Error al registrar en Odoo: ${err.message || err}`);
        }
    }

    onEmergencyStopClick() {
        if (confirm("⚠️ ¿PARADA DE EMERGENCIA TOTAL DE PISTA?\nSe bloquearán inmediatamente todos los surtidores.")) {
            alert("🚨 Parada de emergencia ejecutada. Surtidores bloqueados.");
        }
    }

    async onPumpClick(pump) {
        if (pump.amount > 0 && pump.liters > 0) {
            let currentOrder = this.pos.get_order();
            const orderLines = currentOrder && currentOrder.get_orderlines ? currentOrder.get_orderlines() : [];
            // Si el ticket actual ya contiene productos de otro cliente, abrir un nuevo ticket para este repostaje
            if (!currentOrder || orderLines.length > 0) {
                currentOrder = this.pos.add_new_order();
            }

            let product = null;
            if (pump.product_id && this.pos.db.product_by_id[pump.product_id]) {
                product = this.pos.db.product_by_id[pump.product_id];
            } else {
                const fuelSearch = pump.fuel.toLowerCase();
                const fuelCode = fuelSearch.includes("plomo") || fuelSearch.includes("95") ? "95" : "GA";
                product = this.findFuelProduct(fuelCode);
            }

            if (product) {
                const targetTotal = pump.amount;
                const targetQty = pump.liters;
                const unitPrice = this.getNetPriceForTargetTotal(product, targetTotal, targetQty, currentOrder);
                const fuelPvp = pump.price || (targetTotal / targetQty);

                const existingLine = currentOrder.get_orderlines().find(l => l.pump_id === pump.id || (l.customerNote && l.customerNote.includes(`Calle ${pump.id}`)));
                let activeLine = existingLine;
                if (existingLine) {
                    existingLine.set_quantity(targetQty);
                    existingLine.set_unit_price(unitPrice);
                    existingLine.fuel_display_price = fuelPvp;
                    existingLine.target_total = targetTotal;
                    existingLine.price_type = "manual";
                } else {
                    await currentOrder.add_product(product, {
                        quantity: targetQty,
                        price: unitPrice,
                        extras: {
                            price_manually_set: true,
                            price_type: "manual",
                            pump_id: pump.id,
                            fuel_display_price: fuelPvp,
                            target_total: targetTotal
                        }
                    });
                    activeLine = currentOrder.get_last_orderline();
                    if (activeLine) {
                        activeLine.pump_id = pump.id;
                        activeLine.fuel_display_price = fuelPvp;
                        activeLine.target_total = targetTotal;
                        activeLine.price_type = "manual";
                    }
                }

                // Blindaje milimétrico de redondeo: garantiza que el importe coincida exactamente con el surtidor
                if (activeLine && targetTotal > 0) {
                    const currentDisp = activeLine.get_display_price();
                    const diff = Math.round((targetTotal - currentDisp) * 100) / 100;
                    if (Math.abs(diff) >= 0.005) {
                        const curQty = activeLine.get_quantity() || 1;
                        const taxes = activeLine.get_taxes ? activeLine.get_taxes() : [];
                        let taxFactor = 1.0;
                        if (taxes && taxes.length > 0 && !taxes[0].price_include) {
                            const taxRate = taxes.reduce((s, t) => s + (t.amount || 0), 0);
                            taxFactor = 1.0 + (taxRate / 100.0);
                        }
                        activeLine.set_unit_price(activeLine.get_unit_price() + (diff / (curQty * taxFactor)));
                    }
                }

                currentOrder.pump_id = pump.id;
                if (activeLine && activeLine.set_customer_note) {
                    activeLine.set_customer_note(`Calle ${pump.id} - ${product.display_name} (${targetQty.toFixed(2)}L)`);
                }

                // Blindaje milimétrico de redondeo: garantiza que el importe coincida exactamente con la bomba
                if (activeLine && targetTotal > 0) {
                    const currentDisp = activeLine.get_display_price();
                    const diff = Math.round((targetTotal - currentDisp) * 100) / 100;
                    if (Math.abs(diff) >= 0.01) {
                        const curQty = activeLine.get_quantity() || 1;
                        activeLine.set_unit_price(activeLine.get_unit_price() + (diff / curQty));
                    }
                }
                const savedPlate = (this.pos && this.pos.pumpPendingPlates && this.pos.pumpPendingPlates[pump.id]) || this.state.vehiclePlate || "";
                if (savedPlate) {
                    this.state.vehiclePlate = savedPlate;
                    currentOrder.vehicle_plate = savedPlate;
                    if (currentOrder.set_note) currentOrder.set_note(`Matrícula: ${savedPlate}`);
                    if (this.pos && this.pos.pumpPendingPlates && this.pos.pumpPendingPlates[pump.id]) {
                        delete this.pos.pumpPendingPlates[pump.id];
                        this.savePumpPendingPlates();
                    }
                }

                // Si la calle tenía productos de tienda vinculados, agregarlos al ticket junto con el combustible
                if (this.pos && this.pos.pumpPendingStoreItems && this.pos.pumpPendingStoreItems[pump.id] && this.pos.pumpPendingStoreItems[pump.id].length > 0) {
                    const storeItems = this.pos.pumpPendingStoreItems[pump.id];
                    delete this.pos.pumpPendingStoreItems[pump.id];
                    this.savePumpPendingStoreItems();
                    for (const item of storeItems) {
                        const prod = this.pos.db.get_product_by_id(item.productId);
                        if (prod) {
                            await currentOrder.add_product(prod, {
                                quantity: item.qty,
                                price: item.price,
                                extras: { price_manually_set: true }
                            });
                            const lastLine = currentOrder.get_last_orderline();
                            if (lastLine && item.discount) lastLine.set_discount(item.discount);
                            if (lastLine && item.customerNote && lastLine.set_customer_note) lastLine.set_customer_note(item.customerNote);
                        }
                    }
                }

                pump.status = "idle";
                pump.statusText = "LIBRE";
                pump.amount = 0;
                pump.liters = 0;
                pump.has_prepay = false;
                pump.preset_amount = 0;
                if (this.state.pumpPresets) {
                    delete this.state.pumpPresets[pump.id];
                }
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
        const inputEl = document.querySelector(".virtus-barcode-input");
        if (inputEl) {
            inputEl.focus();
            inputEl.select();
        }
    }
}

patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);
        if (this.pos && this.pos.payment_methods) {
            for (const pm of this.pos.payment_methods) {
                if (!pm || !pm.name) continue;
                const lower = pm.name.toLowerCase();
                if (lower.includes("banco")) {
                    pm.name = "Tarjeta";
                } else if (lower.includes("efectivo")) {
                    pm.name = "Efectivo";
                } else if (lower.includes("cuenta") || lower.includes("cliente") || lower.includes("customer account") || lower.includes("crédito") || lower.includes("credito")) {
                    pm.name = "Crédito";
                }
            }
        }
    }
});

ProductScreen.components = {
    ...ProductScreen.components,
    UtrecarMainScreen,
};


patch(Order.prototype, {
    set_partner(partner) {
        // 1. Registrar el importe objetivo de cada línea de combustible antes de que Odoo aplique pricelist
        const fuelTargets = new Map();
        const lines = this.get_orderlines ? this.get_orderlines() : [];
        for (const line of lines) {
            if (line.target_total || line.pump_id || line.fuel_display_price) {
                const target = line.target_total || (this.pending_prepay && this.pending_prepay.amount > 0 ? this.pending_prepay.amount : (line.get_display_price ? line.get_display_price() : (line.price * line.quantity)));
                if (target && target > 0) {
                    fuelTargets.set(line, target);
                }
            }
        }

        super.set_partner(partner);

        // 2. Blindaje milimétrico: garantizar que el importe de combustible permanezca invariable
        for (const [line, target] of fuelTargets.entries()) {
            line.price_type = "manual";
            line.target_total = target;
            if (line.get_display_price) {
                const curDisp = line.get_display_price();
                const diff = Math.round((target - curDisp) * 100) / 100;
                if (Math.abs(diff) >= 0.005) {
                    const q = line.get_quantity() || 1;
                    const taxes = line.get_taxes ? line.get_taxes() : [];
                    let taxFactor = 1.0;
                    if (taxes && taxes.length > 0 && !taxes[0].price_include) {
                        const taxRate = taxes.reduce((s, t) => s + (t.amount || 0), 0);
                        taxFactor = 1.0 + (taxRate / 100.0);
                    }
                    line.set_unit_price(line.get_unit_price() + (diff / (q * taxFactor)));
                }
            }
        }
    },

    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.is_albaran = Boolean(this.is_albaran);
        json.vehicle_plate = this.vehicle_plate || '';
        json.vehicle_driver = this.vehicle_driver || '';

        let pumpId = this.pump_id || this.pending_pump_id || (this.pending_prepay ? this.pending_prepay.pump_id : 0) || this.extraction_pump_id || 0;
        if (!pumpId && (this.get_orderlines || this.orderlines)) {
            const linesList = this.get_orderlines ? this.get_orderlines() : this.orderlines;
            const fuelLine = (linesList || []).find(l => l.pump_id);
            if (fuelLine) pumpId = fuelLine.pump_id;
        }
        json.pump_id = parseInt(pumpId) || 0;
        return json;
    },
    export_for_printing() {
        const res = super.export_for_printing(...arguments);
        res.is_albaran = Boolean(this.is_albaran);
        res.vehicle_plate = this.vehicle_plate || '';
        res.vehicle_driver = this.vehicle_driver || '';

        let pumpId = this.pump_id || this.pending_pump_id || (this.pending_prepay ? this.pending_prepay.pump_id : 0) || this.extraction_pump_id || 0;
        if (!pumpId && (this.get_orderlines || this.orderlines)) {
            const linesList = this.get_orderlines ? this.get_orderlines() : this.orderlines;
            const fuelLine = (linesList || []).find(l => l.pump_id);
            if (fuelLine) pumpId = fuelLine.pump_id;
        }
        res.pump_id = parseInt(pumpId) || 0;

        if (res.headerData) {
            res.headerData.is_albaran = Boolean(this.is_albaran);
            res.headerData.vehicle_plate = this.vehicle_plate || '';
            res.headerData.vehicle_driver = this.vehicle_driver || '';
            res.headerData.pump_id = parseInt(pumpId) || 0;
        }
        res.cashier = null;
        if (res.headerData) {
            res.headerData.cashier = null;
            res.headerData.trackingNumber = null;
        }

        let ticketName = this.backend_name;
        if (!ticketName && this.name && (/^TT[A-Z]+/.test(this.name) || /^AV[A-Z]+/.test(this.name))) {
            ticketName = this.name;
        }
        if (!ticketName) {
            const seq = this.sequence_number || 1;
            const currentYear = new Date().getFullYear();
            const prefix = this.is_albaran ? "AVTR" : "TTTR";
            ticketName = `${prefix}${currentYear}${String(seq).padStart(5, "0")}`;
        }
        if (ticketName) {
            const m = ticketName.match(/^(TT|AV)([A-Z]+)(\d{1,5})$/);
            if (m) {
                const [_, t, st, num] = m;
                const currentYear = new Date().getFullYear();
                ticketName = `${t}${st}${currentYear}${String(num).padStart(5, "0")}`;
            }
        }
        if (this.is_albaran && ticketName && /^TT[A-Z]+/.test(ticketName)) {
            ticketName = ticketName.replace(/^TT/, "AV");
        }
        if (!this.is_albaran && ticketName && /^AV[A-Z]+/.test(ticketName)) {
            ticketName = ticketName.replace(/^AV/, "TT");
        }

        res.ticket_series_name = ticketName;
        res.pos_reference = this.get_name();
        res.name = ticketName;

        if (res.headerData) {
            res.headerData.ticket_series_name = ticketName;
            res.headerData.name = ticketName;
        }

        const partner = this.get_partner();
        if (partner) {
            const partnerData = {
                id: partner.id,
                name: partner.name,
                ref: partner.ref || (partner.id ? `CLI-${partner.id}` : ''),
                vat: partner.vat || '',
                street: partner.street || '',
                zip: partner.zip || '',
                city: partner.city || '',
                customer_type: partner.customer_type,
                customer_payment_mode: partner.customer_payment_mode,
                invoice_periodicity: partner.invoice_periodicity,
            };
            res.partner = partnerData;
            if (res.headerData) {
                res.headerData.partner = partnerData;
            }
        }

        return res;
    }
});

patch(PaymentScreenStatus.prototype, {
    get markedText() {
        const line = this.props.order ? this.props.order.selected_paymentline : null;
        const amount = line ? line.get_amount() : 0;
        return this.env.utils.formatCurrency(amount);
    },
});

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.customInputBuffer = "";

        const normalizePm = (pm) => {
            if (!pm || !pm.name) return;
            const lower = pm.name.toLowerCase();
            if (lower.includes("banco")) {
                pm.name = "Tarjeta";
            } else if (lower.includes("efectivo")) {
                pm.name = "Efectivo";
            }
        };

        if (this.pos && this.pos.payment_methods) {
            this.pos.payment_methods.forEach(normalizePm);
        }
        if (this.payment_methods_from_config) {
            // Ocultar 'Cuenta de cliente' de la botonera de la calculadora
            this.payment_methods_from_config = this.payment_methods_from_config.filter((m) => {
                const name = (m && m.name ? m.name : '').toLowerCase();
                return m && m.type !== 'pay_later' && !name.includes('cuenta') && !name.includes('customer account');
            });
            this.payment_methods_from_config.forEach(normalizePm);
        }

        onMounted(() => {
            if (this.pos && this.pos.payment_methods) {
                this.pos.payment_methods.forEach(normalizePm);
            }
            if (this.payment_methods_from_config) {
                this.payment_methods_from_config.forEach(normalizePm);
            }
            if (this.currentOrder) {
                for (const pl of this.currentOrder.get_paymentlines()) {
                    if (pl && pl.payment_method) {
                        normalizePm(pl.payment_method);
                    }
                }
            }
            this.customInputBuffer = "";
            this.numberBuffer.reset();
            // Auto-asignar método de pago por defecto (Efectivo) si no hay ninguno
            if (this.currentOrder && this.currentOrder.get_paymentlines().length === 0 && this.payment_methods_from_config.length > 0) {
                const defaultPm = this.payment_methods_from_config.find(m => m.is_cash_count || (m.name && m.name.toLowerCase().includes("efectivo")))
                                  || this.payment_methods_from_config[0];
                if (defaultPm) {
                    normalizePm(defaultPm);
                    this.addNewPaymentLine(defaultPm);
                }
            }
            // Asegurar que el contador y todas las líneas de pago comiencen estrictamente a 0,00 € en cada nuevo cobro/suministro
            if (this.currentOrder) {
                for (const pl of this.currentOrder.get_paymentlines()) {
                    pl.set_amount(0);
                }
            }
            this.render();
        });
    },

    addNewPaymentLine(paymentMethod) {
        if (!this.currentOrder) return false;
        if (paymentMethod && paymentMethod.name) {
            const lower = paymentMethod.name.toLowerCase();
            if (lower.includes("banco")) {
                paymentMethod.name = "Tarjeta";
            } else if (lower.includes("efectivo")) {
                paymentMethod.name = "Efectivo";
            }
        }
        this.customInputBuffer = "";
        const lines = [...this.currentOrder.get_paymentlines()];
        // Si hay una única línea de pago y se pulsa otro método de pago (por ej. cambiar de Efectivo a Tarjeta o Cuenta),
        // sustituir limpiamente para no acumular líneas que bloqueen la calculadora
        if (lines.length === 1 && lines[0].payment_method.id !== paymentMethod.id) {
            for (const l of lines) {
                this.currentOrder.remove_paymentline(l);
            }
        } else if (lines.length > 1) {
            // Limpiar líneas redundantes a 0,00 €
            for (const l of lines) {
                if (l.amount === 0 && l.payment_method.id !== paymentMethod.id) {
                    this.currentOrder.remove_paymentline(l);
                }
            }
        }
        const res = super.addNewPaymentLine(paymentMethod);
        if (this.currentOrder.selected_paymentline) {
            if (this.currentOrder.selected_paymentline.payment_method) {
                const lower = (this.currentOrder.selected_paymentline.payment_method.name || "").toLowerCase();
                if (lower.includes("banco")) {
                    this.currentOrder.selected_paymentline.payment_method.name = "Tarjeta";
                } else if (lower.includes("efectivo")) {
                    this.currentOrder.selected_paymentline.payment_method.name = "Efectivo";
                }
            }
            this.numberBuffer.reset();
            // Siempre arrancar la línea a 0,00 € para que la calculadora no herede importes
            this.currentOrder.selected_paymentline.set_amount(0);
        }
        this.customInputBuffer = "";
        this.render();
        return res;
    },

    selectPaymentLine(cid) {
        super.selectPaymentLine(cid);
        this.customInputBuffer = "";
        this.numberBuffer.reset();
        this.render();
    },

    updateSelectedPaymentline(amount = false) {
        if (!this.currentOrder) return;
        let line = this.selectedPaymentLine;
        if (!line) {
            if (this.paymentLines.length > 0) {
                line = this.paymentLines[0];
                this.currentOrder.select_paymentline(line);
            } else if (this.payment_methods_from_config.length > 0) {
                const defaultPm = this.payment_methods_from_config.find(m => m.is_cash_count || (m.name && m.name.toLowerCase().includes("efectivo")))
                                  || this.payment_methods_from_config[0];
                this.addNewPaymentLine(defaultPm);
                line = this.selectedPaymentLine;
            }
        }
        if (!line) return;

        if (amount === false) {
            if (this.customInputBuffer) {
                amount = parseFloat(this.customInputBuffer.replace(",", ".")) || 0;
            } else {
                const buf = this.numberBuffer.get();
                if (buf === null || buf === "") {
                    amount = 0;
                } else {
                    amount = this.numberBuffer.getFloat() || 0;
                }
            }
        }
        if (amount === null) {
            amount = 0;
        }
        line.set_amount(amount);
        this.render();
    },

    deletePaymentLine(cid) {
        super.deletePaymentLine(cid);
        this.customInputBuffer = "";
        if (this.currentOrder) {
            const remaining = this.currentOrder.get_paymentlines();
            if (remaining.length > 0) {
                this.currentOrder.select_paymentline(remaining[0]);
            }
            this.numberBuffer.reset();
        }
        this.render();
    },

    getNumpadButtons() {
        return [
            { value: "1" },
            { value: "2" },
            { value: "3" },
            { value: "+10" },
            { value: "4" },
            { value: "5" },
            { value: "6" },
            { value: "+20" },
            { value: "7" },
            { value: "8" },
            { value: "9" },
            { value: "+50" },
            { value: "-", text: "+/-" },
            { value: "0" },
            { value: this.env?.services?.localization?.decimalPoint || "," },
            { value: "Clear", text: "C", class: "btn-numpad-clear" },
        ];
    },

    onNumpadClick(buttonValue) {
        if (!this.currentOrder) return;

        // 1. Asegurar que existe una línea de pago seleccionada
        let line = this.selectedPaymentLine;
        if (!line) {
            if (this.paymentLines.length > 0) {
                line = this.paymentLines[0];
                this.currentOrder.select_paymentline(line);
            } else if (this.payment_methods_from_config.length > 0) {
                const defaultPm = this.payment_methods_from_config.find(m => m.is_cash_count || (m.name && m.name.toLowerCase().includes("efectivo")))
                                  || this.payment_methods_from_config[0];
                this.addNewPaymentLine(defaultPm);
                line = this.selectedPaymentLine;
            }
        }
        if (!line) return;

        // 2. BOTÓN ROJO / CLEAR ("C"): DEJAR EL CONTADOR A 0 TOTALMENTE
        if (buttonValue === "Clear" || buttonValue === "Backspace" || buttonValue === "Delete" || buttonValue === "C") {
            this.customInputBuffer = "";
            this.numberBuffer.reset();
            line.set_amount(0);
            this.render();
            return;
        }

        // 3. BOTONES DE INCREMENTO RÁPIDO (+10, +20, +50)
        if (typeof buttonValue === "string" && buttonValue.startsWith("+") && !isNaN(parseFloat(buttonValue.slice(1)))) {
            const inc = parseFloat(buttonValue.slice(1));
            let baseAmt = line.amount || 0;
            // Si el cajero acaba de entrar y la línea tiene el total por defecto (y no ha tocado números)
            if (!this.customInputBuffer && baseAmt === this.currentOrder.get_total_with_tax()) {
                baseAmt = 0;
            }
            const newAmt = Math.round((baseAmt + inc) * 100) / 100;
            this.customInputBuffer = String(newAmt);
            this.numberBuffer.set(String(newAmt));
            line.set_amount(newAmt);
            this.render();
            return;
        }

        // 4. CAMBIO DE SIGNO (+/-)
        if (buttonValue === "-" || buttonValue === "+/-") {
            const currentAmt = line.amount || 0;
            const newAmt = -currentAmt;
            this.customInputBuffer = String(newAmt);
            this.numberBuffer.set(String(newAmt));
            line.set_amount(newAmt);
            this.render();
            return;
        }

        // 5. SEPARADOR DECIMAL (, o .)
        const decPoint = this.env?.services?.localization?.decimalPoint || ",";
        if (buttonValue === "." || buttonValue === ",") {
            if (!this.customInputBuffer || this.customInputBuffer === "0" || line.amount === 0) {
                this.customInputBuffer = "0" + decPoint;
            } else if (!this.customInputBuffer.includes(decPoint) && !this.customInputBuffer.includes(".")) {
                this.customInputBuffer += decPoint;
            }
            this.numberBuffer.set(this.customInputBuffer);
            const parsed = parseFloat(this.customInputBuffer.replace(",", ".")) || 0;
            line.set_amount(parsed);
            this.render();
            return;
        }

        // 6. DÍGITOS NUMÉRICOS (0-9)
        if (!isNaN(parseInt(buttonValue, 10))) {
            // Si el buffer estaba vacío, o era "0", o la línea tenía 0: arrancar nuevo número
            if (!this.customInputBuffer || this.customInputBuffer === "0" || line.amount === 0) {
                this.customInputBuffer = buttonValue;
            } else {
                if (this.customInputBuffer.length < 10) {
                    this.customInputBuffer += buttonValue;
                }
            }
            this.numberBuffer.set(this.customInputBuffer);
            const parsed = parseFloat(this.customInputBuffer.replace(",", ".")) || 0;
            line.set_amount(parsed);
            this.render();
            return;
        }
    },

    // NOTA: no definir aquí un getter `payment_methods_from_config`. El setup()
    // del núcleo asigna esa propiedad y un getter sin setter lanza TypeError,
    // dejando la pantalla de cobro en blanco. El filtro de 'Cuenta de cliente'
    // se aplica en setup().

    get nextScreen() {
        return "ProductScreen";
    },

    get currentPartner() {
        return this.currentOrder ? this.currentOrder.get_partner() : null;
    },

    get isCreditCustomer() {
        const partner = this.currentPartner;
        if (!partner) return false;
        if (partner.customer_type === 'credit') return !partner.credit_blocked;
        if (partner.customer_type === 'monthly') return false;
        return (partner.customer_payment_mode === 'credit') && !partner.credit_blocked;
    },

    get isMonthlyCustomer() {
        const partner = this.currentPartner;
        if (!partner) return false;
        if (partner.customer_type === 'monthly') return true;
        if (partner.customer_type === 'credit') return false;
        return partner.invoice_periodicity === 'monthly';
    },

    get isOrdinaryCustomer() {
        const partner = this.currentPartner;
        if (!partner) return false;
        return !this.isCreditCustomer && !this.isMonthlyCustomer;
    },

    async validateVirtusAlbaran() {
        if (!this.currentOrder.get_partner()) {
            await this.selectPartner();
            if (!this.currentOrder.get_partner()) {
                return;
            }
        }
        const partner = this.currentOrder.get_partner();
        if (!this.isCreditCustomer) {
            if (partner.credit_blocked) {
                alert(`⚠️ El cliente "${partner.name}" tiene el crédito BLOQUEADO por riesgo o impago.`);
            } else {
                alert(`⚠️ El cliente "${partner.name}" está configurado como cliente de CONTADO.\nSolo se permite Albarán a crédito para clientes con modalidad de Crédito autorizada.`);
            }
            return;
        }

        const creditPm = (this.pos.payment_methods || []).find(m => 
            (m.type === 'pay_later') || 
            (m.name && (m.name.toLowerCase().includes('cuenta') || m.name.toLowerCase().includes('crédito') || m.name.toLowerCase().includes('customer account')))
        ) || (this.payment_methods_from_config || []).find(m => 
            (m.type === 'pay_later') || 
            (m.name && (m.name.toLowerCase().includes('cuenta') || m.name.toLowerCase().includes('crédito') || m.name.toLowerCase().includes('customer account')))
        );

        if (creditPm) {
            const paymentlines = [...this.currentOrder.get_paymentlines()];
            for (const pl of paymentlines) {
                this.currentOrder.remove_paymentline(pl);
            }
            this.addNewPaymentLine(creditPm);
        } else {
            this.ensureOrderPaid();
        }

        this.currentOrder.is_albaran = true;
        if (this.currentOrder.name && /^TT[A-Z]+/.test(this.currentOrder.name)) {
            this.currentOrder.name = this.currentOrder.name.replace(/^TT/, "AV");
        }
        if (this.currentOrder.backend_name && /^TT[A-Z]+/.test(this.currentOrder.backend_name)) {
            this.currentOrder.backend_name = this.currentOrder.backend_name.replace(/^TT/, "AV");
        }
        this.currentOrder.set_to_invoice(false);
        this._virtusPrintTicket = true;
        await this.validateOrder(false);
    },

    ensureOrderPaid() {
        if (!this.currentOrder) return false;
        if (this.currentOrder.is_paid()) return true;

        const due = this.currentOrder.get_due();
        if (Math.abs(due) > 0.001) {
            const defaultPm = this.payment_methods_from_config.find(m => m.is_cash_count || (m.name && m.name.toLowerCase().includes("efectivo")))
                              || this.payment_methods_from_config[0];
            const existingLine = this.selectedPaymentLine || this.currentOrder.get_paymentlines()[0];
            if (existingLine) {
                existingLine.set_amount(existingLine.get_amount() + due);
            } else if (defaultPm) {
                this.addNewPaymentLine(defaultPm);
                if (this.selectedPaymentLine) {
                    this.selectedPaymentLine.set_amount(due);
                }
            }
        }
        return this.currentOrder.is_paid();
    },

    async _finalizeValidation() {
        if (this.currentOrder.is_paid_with_cash() || this.currentOrder.get_change()) {
            this.hardwareProxy.openCashbox();
        }

        this.currentOrder.date_order = luxon.DateTime.now();
        for (const line of this.paymentLines) {
            if (!line.amount === 0) {
                this.currentOrder.remove_paymentline(line);
            }
        }
        this.currentOrder.finalized = true;

        this.env.services.ui.block();
        let syncOrderResult;
        try {
            // 1. Guardar en servidor para obtener la serie y correlativo oficial TTTR
            syncOrderResult = await this.pos.push_single_order(this.currentOrder);
            if (!syncOrderResult) {
                return;
            }
            if (syncOrderResult && syncOrderResult.length > 0 && syncOrderResult[0]?.name) {
                this.currentOrder.backend_name = syncOrderResult[0].name;
                this.currentOrder.name = syncOrderResult[0].name;
                this.currentOrder.server_id = syncOrderResult[0].id;
            }

            // 2. Factura oficial si aplica
            if (this.shouldDownloadInvoice() && this.currentOrder.is_to_invoice()) {
                if (syncOrderResult[0]?.account_move) {
                    await this.report.doAction("account.account_invoices", [
                        syncOrderResult[0].account_move,
                    ]);
                } else {
                    throw {
                        code: 401,
                        message: "Backend Invoice",
                        data: { order: this.currentOrder },
                    };
                }
            }
        } catch (error) {
            if (error instanceof ConnectionLostError) {
                this.pos.showScreen(this.nextScreen);
                Promise.reject(error);
                return error;
            } else {
                throw error;
            }
        } finally {
            this.env.services.ui.unblock();
        }

        // 3. Si se pulsó TICKET (imprimir), imprimir ahora con la serie TTTR oficial ya asignada
        if (this._virtusPrintTicket) {
            this._virtusPrintTicket = false;
            try {
                await this.printer.print(
                    OrderReceipt,
                    {
                        data: this.currentOrder.export_for_printing(),
                        formatCurrency: this.env.utils.formatCurrency,
                    },
                    { webPrintFallback: true }
                );
                this.currentOrder._printed = true;
            } catch (e) {
                console.debug("Error imprimiendo ticket:", e);
            }
        }

        // 4. Post process
        if (
            syncOrderResult &&
            syncOrderResult.length > 0 &&
            this.currentOrder.wait_for_push_order()
        ) {
            await this.postPushOrderResolve(syncOrderResult.map((res) => res.id));
        }

        await this.afterOrderValidation(!!syncOrderResult && syncOrderResult.length > 0);
    },

    async validateVirtusTicket() {
        // Si es cliente mensual con cuenta de crédito y no se seleccionó pago manual, asignar cuenta de cliente
        if (this.isMonthlyCustomer && this.currentPartner && (this.currentPartner.customer_payment_mode === 'credit' || this.currentPartner.customer_type === 'monthly')) {
            const currentLines = this.currentOrder.get_paymentlines();
            const isManualNonCash = currentLines.some(l => !l.payment_method.is_cash_count && !l.payment_method.name?.toLowerCase().includes('efectivo'));
            if (!isManualNonCash) {
                const creditPm = (this.pos.payment_methods || []).find(m => 
                    (m.type === 'pay_later') || 
                    (m.name && (m.name.toLowerCase().includes('cuenta') || m.name.toLowerCase().includes('crédito') || m.name.toLowerCase().includes('customer account')))
                ) || (this.payment_methods_from_config || []).find(m => 
                    (m.type === 'pay_later') || 
                    (m.name && (m.name.toLowerCase().includes('cuenta') || m.name.toLowerCase().includes('crédito') || m.name.toLowerCase().includes('customer account')))
                );
                if (creditPm) {
                    for (const pl of [...currentLines]) {
                        this.currentOrder.remove_paymentline(pl);
                    }
                    this.addNewPaymentLine(creditPm);
                }
            }
        }

        this.ensureOrderPaid();
        this.currentOrder.is_albaran = false;
        this.currentOrder.set_to_invoice(false);
        this._virtusPrintTicket = true;
        await this.validateOrder(false);
    },

    async validateVirtusInvoice() {
        this.ensureOrderPaid();
        if (!this.currentOrder.get_partner()) {
            await this.selectPartner();
            if (!this.currentOrder.get_partner()) {
                return;
            }
        }
        const partner = this.currentOrder.get_partner();
        const clientEmail = (partner.email || "").trim();

        let deliveryMethod = "both";
        let invoiceEmail = clientEmail;

        try {
            const { confirmed, payload } = await this.popup.add(SelectionPopup, {
                title: `Factura: ${partner.name}`,
                list: [
                    { id: 1, label: `🖨️📧 Imprimir y Enviar por Email ${clientEmail ? '(' + clientEmail + ')' : ''}`, item: "both" },
                    { id: 2, label: `📧 Enviar por Email ${clientEmail ? '(' + clientEmail + ')' : ''}`, item: "email" },
                    { id: 3, label: "🖨️ Imprimir en Papel", item: "paper" },
                ],
            });
            if (!confirmed || !payload) {
                return;
            }
            deliveryMethod = payload;
        } catch (e) {
            console.debug("Aviso con SelectionPopup, usando both:", e);
            deliveryMethod = "both";
        }

        if (deliveryMethod === "email" || deliveryMethod === "both") {
            if (!invoiceEmail || !invoiceEmail.includes("@")) {
                const asked = prompt("Introduzca el correo electrónico del cliente para el envío de la factura:", "");
                if (asked && asked.includes("@")) {
                    invoiceEmail = asked.trim();
                } else if (deliveryMethod === "email") {
                    alert("⚠️ No se indicó un correo válido. Se imprimirá en papel.");
                    deliveryMethod = "paper";
                }
            }
        }

        this._virtusInvoiceDelivery = deliveryMethod;
        this._virtusInvoiceEmail = invoiceEmail;
        this._virtusPrintTicket = false;
        this.currentOrder.set_to_invoice(true);
        await this.validateOrder(false);
    },

    get nextScreen() {
        return "ProductScreen";
    },

    async validateVirtusNoPrint() {
        this.ensureOrderPaid();
        this.currentOrder.is_albaran = false;
        this.currentOrder.set_to_invoice(false);
        this._virtusPrintTicket = false;
        if (this.currentOrder) {
            this.currentOrder._printed = true;
        }
        await this.validateOrder(false);
    },

    async validateOrder(isForceValidate) {
        this.ensureOrderPaid();
        await super.validateOrder(...arguments);
    },

    async afterOrderValidation(suggestToSync = true) {
        const order = this.currentOrder;
        if (order) {
            const lines = order.get_orderlines ? order.get_orderlines() : [];

            // 1. SI LA ORDEN ERA UN PRE-PAGO: AHORA QUE HA SIDO PAGADA, ABRIR LA CALLE EN PISTA PARA EL SUMINISTRO
            if (order.pending_prepay) {
                const prepay = order.pending_prepay;
                const pumpId = prepay.pump_id;
                const fuelCode = prepay.fuel;
                const amt = prepay.amount;
                const lts = prepay.liters;

                try {
                    await jsonrpc("/pos_gas_station/authorize", {
                        config_id: this.pos.config.id,
                        pump_id: pumpId,
                        fuel: fuelCode,
                        amount: amt,
                        liters: lts,
                        has_prepay: true
                    });
                } catch (e) {
                    console.error("Error al autorizar surtidor tras cobro de prepago:", e);
                }

                if (!this.pos.pumpPresets) {
                    this.pos.pumpPresets = {};
                }
                const firstFuelLine = lines.find(l => l.pump_id === pumpId || (l.product && (l.product.default_code || '').includes('GAS') || (l.product.default_code || '').includes('SP95')));
                const unitPrice = firstFuelLine ? (firstFuelLine.fuel_display_price || (firstFuelLine.get_unit_price ? firstFuelLine.get_unit_price() : 1.45)) : (prepay.unitPrice || 1.45);
                const prodId = firstFuelLine && firstFuelLine.product ? firstFuelLine.product.id : prepay.productId;

                this.pos.pumpPresets[pumpId] = {
                    amount: prepay.presetVal,
                    liters: prepay.liters || (unitPrice > 0 ? prepay.presetVal / unitPrice : 0),
                    fuel: prepay.fuelName,
                    code: fuelCode,
                    productId: prodId,
                    unitPrice: unitPrice,
                    isMoney: prepay.isMoney,
                    hasPrepay: true,
                    isLleno: false,
                    isAlbaran: Boolean(order.is_albaran),
                    isInvoice: Boolean(order.is_to_invoice && order.is_to_invoice()),
                    orderRef: order.name,
                    orderPosRef: order.get_name ? order.get_name() : (order.pos_reference || order.name),
                    orderTicketName: order.backend_name || order.ticket_series_name || order.name,
                    pos_reference: order.pos_reference || (order.get_name ? order.get_name() : order.name),
                    orderBackendId: order.server_id || order.id || null,
                    partner: order.get_partner ? order.get_partner() : null,
                    vehiclePlate: (prepay && prepay.vehiclePlate) || (this.state && this.state.vehiclePlate) || "",
                    timestamp: Date.now()
                };
                if (this.state && this.state.pumpPresets) {
                    this.state.pumpPresets[pumpId] = Object.assign({}, this.pos.pumpPresets[pumpId]);
                }
                if (typeof this.savePumpPresets === 'function') {
                    this.savePumpPresets();
                } else {
                    try {
                        localStorage.setItem(`pos_gas_station_pump_presets_${this.pos.config.id}`, JSON.stringify(this.pos.pumpPresets || {}));
                    } catch (e) {
                        console.debug("Error guardando pumpPresets:", e);
                    }
                }
            }

            // 2. Limpiar bombas de líneas que NO sean de este prepago recién autorizado
            const prepayPumpId = order.pending_prepay ? String(order.pending_prepay.pump_id) : null;
            for (const l of lines) {
                const linePumpId = l.pump_id ? String(l.pump_id) : null;
                // Si la orden actual es un prepago para esta calle, NO llamar a clear_pump bajo ningún concepto
                if (linePumpId && (!prepayPumpId || linePumpId !== prepayPumpId)) {
                    try {
                        await jsonrpc("/pos_gas_station/clear_pump", {
                            config_id: this.pos.config.id,
                            pump_id: l.pump_id
                        });
                    } catch (e) {
                        console.debug("Aviso al limpiar bomba tras validar orden:", e);
                    }
                }
            }

            // Si este pedido correspondía a un cobro pendiente de la monedita de la calle, restarlo/eliminarlo
            if (order.pending_sale_id && order.pending_pump_id && this.pos.pendingSales) {
                const pid = order.pending_pump_id;
                if (this.pos.pendingSales[pid]) {
                    this.pos.pendingSales[pid] = this.pos.pendingSales[pid].filter(s => s.id !== order.pending_sale_id);
                    if (this.pos.pendingSales[pid].length === 0) {
                        delete this.pos.pendingSales[pid];
                    }
                    try {
                        localStorage.setItem(`pos_gas_station_pending_sales_${this.pos.config.id}`, JSON.stringify(this.pos.pendingSales));
                    } catch (e) {}
                    jsonrpc("/pos_gas_station/pending_sales/set", {
                        config_id: this.pos.config.id,
                        pending_sales: this.pos.pendingSales || {},
                    }).catch(e => console.warn("No se pudieron guardar las moneditas en servidor:", e));
                }
                const targetPump = this.state && this.state.pumps && this.state.pumps.find(p => String(p.id) === String(pid));
                if (targetPump && targetPump.status !== "dispensing") {
                    const remaining = (this.pos.pendingSales[pid] && this.pos.pendingSales[pid].length) || 0;
                    if (remaining === 0) {
                        targetPump.status = "blocked";
                        targetPump.statusText = "PREPAGO";
                        targetPump.amount = 0;
                        targetPump.liters = 0;
                    } else {
                        targetPump.status = "ready";
                        targetPump.statusText = remaining === 1 ? "COBRAR" : `COBROS (${remaining})`;
                    }
                }
            }
        }

        // Si se solicitó envío por email de factura en cobro directo
        if (order && order.is_to_invoice && order.is_to_invoice() && this._virtusInvoiceDelivery && ['email', 'both'].includes(this._virtusInvoiceDelivery)) {
            const emailToSend = this._virtusInvoiceEmail;
            const orderRef = order.name;
            if (emailToSend) {
                setTimeout(async () => {
                    try {
                        await this.env.services.rpc("/pos_gas_station/send_invoice_email", {
                            order_ref: orderRef,
                            email: emailToSend
                        });
                    } catch (mailErr) {
                        console.warn("Aviso enviando factura por email tras validación:", mailErr);
                    }
                }, 1000);
            }
        }

        // Limpiar orden de la BD local y redirigir de inmediato al TPV principal sin pasar por ReceiptScreen
        if (order) {
            this.pos.db.remove_unpaid_order(order);
            this.pos.removeOrder(order);
            this.pos.add_new_order();
            if (this.pos.resetProductScreenSearch) {
                this.pos.resetProductScreenSearch();
            }
        }
        this.pos.showScreen("ProductScreen");
    }
});

patch(ClosePosPopup.prototype, {
    async downloadSalesReport() {
        const sessionId = (this.pos && this.pos.pos_session) ? this.pos.pos_session.id : null;
        if (sessionId) {
            window.open(`/pos_gas_station/shift_report_print/${sessionId}?preview=1`, '_blank');
        }
    },
    async printShiftReport() {
        const sessionId = (this.pos && this.pos.pos_session) ? this.pos.pos_session.id : null;
        if (sessionId) {
            window.open(`/pos_gas_station/shift_report_print/${sessionId}?preview=1`, '_blank');
        }
    }
});

patch(PosStore.prototype, {
    redirectToBackend() {
        const configId = this.config ? this.config.id : null;
        const targetUrl = configId ? `/pos_gas_station/select_employee?station_id=${configId}` : '/pos_gas_station/select_employee';
        window.location.href = targetUrl;
    }
});
