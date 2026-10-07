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
            trackMode: localStorage.getItem("utrecar_track_mode") || "atendido", // 'atendido' o 'prepago'
            mode: "money", // 'money' o 'liters'
            presetValue: 0,
            selectedFuel: "GA",
            availableFuels: [
                { code: "GA", name: "Gasóleo A", class: "ga" },
                { code: "95", name: "Sin Plomo 95", class: "sp95" }
            ],
            isStoreModalOpen: false,
            isClientModalOpen: false,
            isPageDropdownOpen: false,
            currentStorePage: 1,
            selectedModalCategory: null,
            clientSearch: "",
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

        this.onGlobalClick = (ev) => {
            if (this.state.isPageDropdownOpen) {
                const dropdownEl = document.querySelector(".btn-dropdown-wrapper");
                if (dropdownEl && !dropdownEl.contains(ev.target)) {
                    this.state.isPageDropdownOpen = false;
                }
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

    handleBarcodeScan(code) {
        if (!code) return;
        const all = Object.values(this.pos.db.product_by_id || {});
        const prod = all.find(p => p.barcode === code || p.default_code === code || (p.barcode && p.barcode.endsWith(code)));
        if (prod) {
            this.addStoreProductToOrder(prod);
        } else {
            console.debug("Código de barras no encontrado:", code);
        }
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

    get popularStoreProducts() {
        const page = this.state.currentStorePage || 1;

        // PÁGINA 1: ARTÍCULOS PRINCIPALES Y FAVORITOS (VIRTUSTPV)
        const page1Items = [
            { id: "v_hielo", display_name: "HIELO EN BOLSA", lst_price: 1.90, bg_image: "/pos_gas_station/static/src/img/products/prod_341005.png", default_code: "341005" },
            { id: "v_chupa", display_name: "CHUPA CHUPS", lst_price: 0.40, bg_image: "/pos_gas_station/static/src/img/products/prod_312006.png", default_code: "312006" },
            { id: "v_kinder", display_name: "KINDER BUENO", lst_price: 1.50, bg_image: "/pos_gas_station/static/src/img/products/prod_311001.png", default_code: "311001" },
            { id: "v_mechero", display_name: "MECHERO CLIPPER", lst_price: 1.00, bg_image: "/pos_gas_station/static/src/img/products/prod_323003.png", default_code: "323003" },

            { id: "v_butano", display_name: "BOMBONA BUTANO", lst_price: 23.00, bg_image: "/pos_gas_station/static/src/img/products/prod_360014.png", default_code: "360014" },
            { id: "v_dulces", display_name: "DULCES DULCESOL", lst_price: 1.00, bg_image: "/pos_gas_station/static/src/img/products/prod_315006.png", default_code: "315006" },
            { id: "v_coca", display_name: "LATA COCA-COLA", lst_price: 1.50, bg_image: "/pos_gas_station/static/src/img/products/prod_342001.png", default_code: "342001" },
            { id: "v_cocazero", display_name: "COCA-COLA ZERO", lst_price: 1.50, bg_image: "/pos_gas_station/static/src/img/products/prod_342003.png", default_code: "342003" },

            { id: "v_aceite2t", display_name: "ACEITE 2T NIPOMIX", lst_price: 1.40, bg_image: "/pos_gas_station/static/src/img/products/prod_331002.png", default_code: "331002" },
            { id: "v_castrol", display_name: "ACEITE 2T CASTROL", lst_price: 2.00, bg_image: "/pos_gas_station/static/src/img/products/prod_331001.png", default_code: "331001" },
            { id: "v_vaper", display_name: "VAPER SABORES", lst_price: 6.50, bg_image: "/pos_gas_station/static/src/img/products/prod_323006.png", default_code: "323006" },
            { id: "v_papel", display_name: "PAPEL DE LIAR", lst_price: 1.00, bg_image: "/pos_gas_station/static/src/img/products/prod_323001.png", default_code: "323001" },

            { id: "v_cafe", display_name: "CAFE", lst_price: 1.00, bg_image: "/pos_gas_station/static/src/img/products/prod_382001.png", default_code: "382001" },
            { id: "v_zumo", display_name: "ZUMO DE BOTE", lst_price: 1.30, bg_image: "/pos_gas_station/static/src/img/products/prod_382006.png", default_code: "382006" },
            { id: "v_bifrutas", display_name: "BI FRUTAS", lst_price: 1.20, bg_image: "/pos_gas_station/static/src/img/products/prod_382008.png", default_code: "382008" },
            { id: "v_cubata", display_name: "CUBATAS", lst_price: 4.00, bg_image: "/pos_gas_station/static/src/img/products/prod_383003.png", default_code: "383003" },

            { id: "v_boc", display_name: "BOC", text_only: true, full_name: "TOSTADA / BOCADILLO", lst_price: 1.70, default_code: "381001" },
            { id: "v_cocatxt", display_name: "COCA COLA LATA", text_only: true, full_name: "LATA COCA-COLA", lst_price: 1.50, default_code: "342001" },
            { id: "v_pan", display_name: "PAN DE TORRIJA", text_only: true, full_name: "PAN PARA LLEVAR", lst_price: 0.60, default_code: "381003" },
            { id: "v_tostada", display_name: "MEDIA TOSTADA", text_only: true, full_name: "MEDIA TOSTADA", lst_price: 1.30, default_code: "381002" }
        ];

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
        const currentName = this.pos.user ? this.pos.user.name : "";
        const newName = prompt("👤 CAMBIAR NOMBRE DE CAJERO / OPERADOR:\nIntroduzca el nombre del operador que atiende en este turno:", currentName);
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
                    const samplePump = data.pumps.find(p => p.status === "atendido" || p.status === "postpago" || p.status === "blocked" || p.status === "prepago");
                    if (samplePump) {
                        this.state.trackMode = (samplePump.status === "atendido" || samplePump.status === "postpago") ? "atendido" : "prepago";
                    }
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
        setTimeout(() => {
            const input = document.querySelector(".client-search-input");
            if (input) input.focus();
        }, 100);
    }

    closeClientModal() {
        this.state.isClientModalOpen = false;
        this.state.clientSearch = "";
    }

    onClientSearchInput(ev) {
        this.state.clientSearch = ev.target.value;
    }

    get filteredClients() {
        const search = (this.state.clientSearch || "").toLowerCase().trim();
        const allPartners = Object.values(this.pos.db.partner_by_id || {});
        if (!search) {
            return allPartners.slice(0, 30);
        }
        return allPartners.filter(p => {
            const name = (p.name || "").toLowerCase();
            const vat = (p.vat || "").toLowerCase();
            const phone = (p.phone || p.mobile || "").toLowerCase();
            const email = (p.email || "").toLowerCase();
            const barcode = (p.barcode || "").toLowerCase();
            return name.includes(search) || vat.includes(search) || phone.includes(search) || email.includes(search) || barcode.includes(search);
        }).slice(0, 40);
    }

    selectClient(partner) {
        const order = this.pos.get_order();
        if (order) {
            order.set_partner(partner);
            this.state.orderVersion = Date.now();
        }
        this.closeClientModal();
    }

    removeClient() {
        const order = this.pos.get_order();
        if (order) {
            order.set_partner(null);
            this.state.orderVersion = Date.now();
        }
        this.closeClientModal();
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
            const barcode = (virtusItem.barcode || "").toLowerCase();
            const name = (virtusItem.display_name || virtusItem.full_name || "").toLowerCase();

            realProduct = (barcode ? all.find(p => (p.barcode || "").toLowerCase() === barcode) : null) ||
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

    
    toggleTrackMode() {
        const nextMode = this.state.trackMode === "atendido" ? "prepago" : "atendido";
        this.state.trackMode = nextMode;
        localStorage.setItem("utrecar_track_mode", nextMode);
        
        // Update idle pumps instantly
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
        await this.validateOrder(false);
    }
});
