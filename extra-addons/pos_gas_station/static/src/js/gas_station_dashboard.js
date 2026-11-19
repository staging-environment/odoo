/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

export class GasStationDashboard extends Component {
    static template = "pos_gas_station.GasStationDashboard";

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.state = useState({
            loading: true,
            isManager: false,
            userName: "",
            adminName: "",
            vpnIp: "",
            companies: [],
            stats: {
                total_companies: 0,
                total_stations: 0,
                total_open_sessions: 0
            },
            // Vista Detalle de Empresa
            viewMode: "dashboard", // 'dashboard' | 'company_detail'
            selectedDetailCompany: null,
            detailTab: "stations", // 'stations' | 'customers' | 'inventory'
            companyDetailData: null,
            detailLoading: false,
            customerSearchTerm: "",
            customerCodeSearchTerm: "",
            customerFilterType: "all",
            customerPage: 1,
            customerPageSize: 30,
            customerTotalCount: 0,
            customerSortField: "name",
            customerSortDir: "asc",
            customerLoading: false,
            // Pestaña de Productos
            productSearchTerm: "",
            productCategoryFilter: "all", // 'all' | 'fuel' | 'store'
            productPage: 1,
            productPageSize: 30,
            productTotalCount: 0,
            productSortField: "code",
            productSortDir: "asc",
            productLoading: false,
            editingProductId: null,
            editingProductPrice: "",
            isSavingPrice: false,
            // Modales inline de productos y stock
            isEditProductModalOpen: false,
            editingProduct: null,
            editProdName: "",
            editProdCode: "",
            editProdBarcodes: [],
            editProdNewBarcode: "",
            editProdCategId: "",
            editProdType: "consu",
            editProdPrice: "",
            editProdCost: "",
            editProdTaxId: "",
            editProdSupplierId: "",
            editProdSupplierSearch: "",
            isSupplierDropdownOpen: false,
            editProdImageBase64: "",
            editProdImagePreview: "",
            editProdHasExistingImage: false,
            editProdInPos: true,
            isSavingProductForm: false,
            productCategoriesTree: [],
            productTaxesList: [],
            productSuppliersList: [],
            // Administración y Configuración de Parámetros (Landing por Cajitas)
            isAdminMenuOpen: false,
            adminParamSection: "menu", // 'menu' | 'taxes' | 'categories'
            taxTypesList: [],
            taxTypesLoading: false,
            isTaxTypeModalOpen: false,
            editingTaxType: null,
            taxTypeCode: "",
            taxTypeName: "",
            taxTypePercentage: "21",
            taxTypeIsExempt: false,
            isSavingTaxType: false,
            // Modal flotante de nuevo proveedor
            isNewSupplierModalOpen: false,
            newSupplierName: "",
            newSupplierVat: "",
            newSupplierPhone: "",
            newSupplierEmail: "",
            isSavingNewSupplier: false,
            isStockAdjustModalOpen: false,
            stockAdjustProduct: null,
            stockAdjustCurrentQty: 0.0,
            stockAdjustNewQty: 0.0,
            stockAdjustReason: "Recuento físico periódico",
            isSavingStockAdjust: false,
            isCategoriesModalOpen: false,
            categoriesList: [],
            categoriesTree: [],
            allParentsList: [],
            nextParentCode: "",
            categoriesLoading: false,
            newCategoryName: "",
            newCategoryParentId: "",
            newCategoryCode: "",
            isSavingCategory: false,
            isCategoryModalOpen: false,
            editingCategory: null,
            categoryModalLevel: "parent", // 'parent' | 'child'
            categoryParentId: "",
            categoryCode: "",
            categoryName: "",
            // Pestaña de Tanques y Ajustes
            isAdjustTankModalOpen: false,
            selectedAdjustTank: null,
            adjustTankLiters: 0,
            adjustTankReason: "Aforo físico periódico",
            isSavingTankAdjust: false,
            isNewTankModalOpen: false,
            newTankName: "",
            newTankFuelCode: "GA",
            newTankCapacity: 30000,
            newTankInitialLiters: 0,
            newTankWarehouseId: null,
            isSavingNewTank: false,
            canManageStaff: false,
            allAuthorizedCompanies: [],
            selectedCompanyId: null,

            // Modales inline de gestión
            showCreateCompanyModal: false,
            showCreateStationModal: false,
            showRenameCompanyModal: false,
            showEditCompanyModal: false,
            showRenameStationModal: false,
            newCompanyName: "",
            newCompanyVat: "",
            newCompanyStreet: "",
            newCompanyZip: "",
            newCompanyCity: "",
            newCompanyPhone: "",
            newCompanyEmail: "",
            newStationCompanyId: null,
            newStationCompanyName: "",
            newStationName: "",
            newStationVpnIp: "",
            companyCreateError: null,
            companyEditError: null,
            renameCompanyId: null,
            renameCompanyName: "",
            editCompanyId: null,
            editCompanyName: "",
            editCompanyVat: "",
            editCompanyStreet: "",
            editCompanyZip: "",
            editCompanyCity: "",
            editCompanyPhone: "",
            editCompanyEmail: "",
            editCompanyWebsite: "",
            renameStationId: null,
            renameStationName: "",
            showEditStationModal: false,
            editStationId: null,
            editStationName: "",
            editStationVpnIp: "",
            editStationAdminPlatformCode: "",
            editStationCompanyId: null,
            editStationStreet: "",
            editStationZip: "",
            editStationCity: "",
            editStationPhone: "",
            editStationEmail: "",
            stationEditError: null,
            selectedDetailStation: null,
            actionLoading: false,

            // Modal de asignación de empleados por empresa
            showEmployeesModal: false,
            selectedCompany: null,
            companyEmployees: [],
            allCompanies: [],
            allRoles: [],
            searchTerm: "",
            filterAssignedOnly: false,
            updatingUserId: null,
            modalLoading: false,
        });

        onMounted(() => {
            this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        this.state.loading = true;
        try {
            const data = await jsonrpc("/pos_gas_station/dashboard_data", {});
            if (data.status === "success") {
                this.state.companies = data.companies;
                this.state.isManager = data.is_manager;
                this.state.canManageStaff = Boolean(data.can_manage_staff);
                this.state.userName = data.user_name;
                this.state.adminName = data.admin_name || data.user_name;
                this.state.vpnIp = data.vpn_ip || "";
                this.state.stats = data.stats;
                this.state.allAuthorizedCompanies = data.all_authorized_companies || [];
                this.state.selectedCompanyId = data.selected_company_id;
            }
        } catch (e) {
            console.error("Error loading gas station dashboard:", e);
            this.notification.add("Error al cargar estaciones y empresas", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    // ==================== GESTIÓN INLINE DE EMPRESAS ====================
    openNewCompany() {
        this.state.newCompanyName = "";
        this.state.newCompanyVat = "";
        this.state.newCompanyStreet = "";
        this.state.newCompanyZip = "";
        this.state.newCompanyCity = "";
        this.state.newCompanyPhone = "";
        this.state.newCompanyEmail = "";
        this.state.companyCreateError = null;
        this.state.showCreateCompanyModal = true;
    }

    closeCreateCompanyModal() {
        this.state.companyCreateError = null;
        this.state.showCreateCompanyModal = false;
    }

    async submitCreateCompany() {
        this.state.companyCreateError = null;
        const name = (this.state.newCompanyName || "").trim();
        if (!name) {
            this.state.companyCreateError = "Por favor, introduzca el Nombre o Razón Social de la empresa.";
            this.notification.add("El nombre de la empresa es obligatorio.", { type: "warning" });
            return;
        }
        this.state.actionLoading = true;
        try {
            const res = await jsonrpc("/pos_gas_station/create_company", {
                name: name,
                vat: this.state.newCompanyVat,
                street: this.state.newCompanyStreet,
                zip: this.state.newCompanyZip,
                city: this.state.newCompanyCity,
                phone: this.state.newCompanyPhone,
                email: this.state.newCompanyEmail,
            });
            if (res.status === "success") {
                this.notification.add(res.message, { type: "success" });
                this.closeCreateCompanyModal();
                await this.loadDashboardData();
            } else {
                this.state.companyCreateError = res.message || "Error al crear empresa";
                this.notification.add(res.message || "Error al crear empresa", { type: "danger" });
            }
        } catch (e) {
            console.error("Error creating company:", e);
            this.state.companyCreateError = "Error de conexión con el servidor al crear la empresa.";
            this.notification.add("Error de conexión al crear empresa", { type: "danger" });
        } finally {
            this.state.actionLoading = false;
        }
    }

    promptEditCompany(comp) {
        this.state.editCompanyId = comp.id;
        this.state.editCompanyName = comp.name || "";
        this.state.editCompanyVat = comp.vat || "";
        this.state.editCompanyStreet = comp.street || "";
        this.state.editCompanyZip = comp.zip || "";
        this.state.editCompanyCity = comp.city || "";
        this.state.editCompanyPhone = comp.phone || "";
        this.state.editCompanyEmail = comp.email || "";
        this.state.editCompanyWebsite = comp.website || "";
        this.state.companyEditError = null;
        this.state.showEditCompanyModal = true;
    }

    promptRenameCompany(comp) {
        this.promptEditCompany(comp);
    }

    closeEditCompanyModal() {
        this.state.companyEditError = null;
        this.state.showEditCompanyModal = false;
    }

    closeRenameCompanyModal() {
        this.closeEditCompanyModal();
    }

    openFullCompanyForm(companyId) {
        this.closeEditCompanyModal();
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "res.company",
            res_id: companyId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async submitEditCompany() {
        this.state.companyEditError = null;
        const name = (this.state.editCompanyName || "").trim();
        if (!name) {
            this.state.companyEditError = "El nombre de la empresa no puede estar vacío.";
            this.notification.add("El nombre de la empresa no puede estar vacío.", { type: "warning" });
            return;
        }
        this.state.actionLoading = true;
        try {
            const res = await jsonrpc("/pos_gas_station/update_company", {
                company_id: this.state.editCompanyId,
                name: name,
                vat: this.state.editCompanyVat,
                street: this.state.editCompanyStreet,
                zip: this.state.editCompanyZip,
                city: this.state.editCompanyCity,
                phone: this.state.editCompanyPhone,
                email: this.state.editCompanyEmail,
                website: this.state.editCompanyWebsite,
            });
            if (res.status === "success") {
                this.notification.add(res.message, { type: "success" });
                this.closeEditCompanyModal();
                if (this.state.viewMode === "company_detail" && this.state.selectedDetailCompany) {
                    await this.loadCompanyDetailData(this.state.editCompanyId);
                }
                await this.loadDashboardData();
            } else {
                this.state.companyEditError = res.message || "Error al actualizar empresa";
                this.notification.add(res.message || "Error al actualizar empresa", { type: "danger" });
            }
        } catch (e) {
            console.error("Error updating company:", e);
            this.state.companyEditError = "Error de conexión con el servidor al actualizar la empresa.";
            this.notification.add("Error de conexión al actualizar empresa", { type: "danger" });
        } finally {
            this.state.actionLoading = false;
        }
    }

    async submitRenameCompany() {
        return this.submitEditCompany();
    }

    async deleteCompany(comp) {
        this.dialog.add(ConfirmationDialog, {
            title: "Eliminar Empresa",
            body: `¿Está seguro de que desea eliminar la empresa "${comp.name}"? Esta acción no se puede deshacer.`,
            confirm: async () => {
                this.state.loading = true;
                try {
                    const res = await jsonrpc("/pos_gas_station/delete_company", { company_id: comp.id });
                    if (res.status === "success") {
                        this.notification.add(res.message, { type: "success" });
                        await this.loadDashboardData();
                    } else {
                        this.state.loading = false;
                        this.dialog.add(ConfirmationDialog, {
                            title: "No se puede eliminar la empresa",
                            body: res.message || "No se puede eliminar la empresa.",
                            confirmLabel: "Entendido",
                            cancel: () => {},
                        });
                    }
                } catch (e) {
                    this.state.loading = false;
                    console.error("Error deleting company:", e);
                    this.notification.add("Error al comunicarse con el servidor al eliminar la empresa.", { type: "danger" });
                }
            },
            cancel: () => {},
        });
    }

    // ==================== GESTIÓN INLINE DE ESTACIONES ====================
    openNewStation(companyId, companyName) {
        this.state.newStationCompanyId = companyId;
        this.state.newStationCompanyName = companyName || "";
        this.state.newStationName = "";
        this.state.newStationVpnIp = "";
        this.state.showCreateStationModal = true;
    }

    closeCreateStationModal() {
        this.state.showCreateStationModal = false;
    }

    async submitCreateStation() {
        const name = (this.state.newStationName || "").trim();
        if (!name) {
            this.notification.add("El nombre de la estación es obligatorio.", { type: "warning" });
            return;
        }
        this.state.actionLoading = true;
        try {
            const res = await jsonrpc("/pos_gas_station/create_station", {
                company_id: this.state.newStationCompanyId,
                name: name,
                vpn_ip: this.state.newStationVpnIp
            });
            if (res.status === "success") {
                this.notification.add(res.message, { type: "success" });
                this.closeCreateStationModal();
                await this.loadDashboardData();
            } else {
                this.notification.add(res.message || "Error al crear estación", { type: "danger" });
            }
        } catch (e) {
            console.error("Error creating station:", e);
            this.notification.add("Error de conexión al crear estación", { type: "danger" });
        } finally {
            this.state.actionLoading = false;
        }
    }

    promptEditStation(st) {
        this.state.editStationId = st.id;
        this.state.editStationName = st.name || "";
        this.state.editStationVpnIp = st.vpn_ip || "";
        this.state.editStationAdminPlatformCode = st.admin_platform_code || "";
        this.state.editStationCompanyId = st.company_id || (this.state.companies[0] ? this.state.companies[0].id : null);
        this.state.editStationStreet = st.street || "";
        this.state.editStationZip = st.zip || "";
        this.state.editStationCity = st.city || "";
        this.state.editStationPhone = st.phone || "";
        this.state.editStationEmail = st.email || "";
        this.state.renameStationId = st.id;
        this.state.renameStationName = st.name || "";
        this.state.stationEditError = null;
        this.state.showEditStationModal = true;
    }

    openStationDetail(st) {
        this.state.selectedDetailStation = Object.assign({}, st);
        this.state.editStationId = st.id;
        this.state.editStationName = st.name || "";
        this.state.editStationVpnIp = st.vpn_ip || "";
        this.state.editStationAdminPlatformCode = st.admin_platform_code || "";
        this.state.editStationCompanyId = st.company_id || (this.state.companies[0] ? this.state.companies[0].id : null);
        this.state.editStationStreet = st.street || "";
        this.state.editStationZip = st.zip || "";
        this.state.editStationCity = st.city || "";
        this.state.editStationPhone = st.phone || "";
        this.state.editStationEmail = st.email || "";
        this.state.stationEditError = null;
        this.state.viewMode = "station_detail";
    }

    backFromStationDetail() {
        this.state.selectedDetailStation = null;
        if (this.state.selectedDetailCompany) {
            this.state.viewMode = "company_detail";
        } else {
            this.state.viewMode = "dashboard";
        }
    }

    promptRenameStation(st) {
        this.promptEditStation(st);
    }

    closeEditStationModal() {
        this.state.stationEditError = null;
        this.state.showEditStationModal = false;
        this.state.showRenameStationModal = false;
    }

    closeRenameStationModal() {
        this.closeEditStationModal();
    }

    openFullStationForm(stationId) {
        this.closeEditStationModal();
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "pos.config",
            res_id: stationId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async submitEditStation() {
        this.state.stationEditError = null;
        const name = (this.state.editStationName || this.state.renameStationName || "").trim();
        if (!name) {
            this.state.stationEditError = "El nombre de la estación no puede estar vacío.";
            this.notification.add("El nombre de la estación no puede estar vacío.", { type: "warning" });
            return;
        }
        this.state.actionLoading = true;
        try {
            const res = await jsonrpc("/pos_gas_station/update_station", {
                config_id: this.state.editStationId || this.state.renameStationId,
                name: name,
                vpn_ip: this.state.editStationVpnIp,
                admin_platform_code: this.state.editStationAdminPlatformCode,
                company_id: this.state.editStationCompanyId,
                street: this.state.editStationStreet,
                zip: this.state.editStationZip,
                city: this.state.editStationCity,
                phone: this.state.editStationPhone,
                email: this.state.editStationEmail,
            });
            if (res.status === "success") {
                this.notification.add(res.message, { type: "success" });
                this.closeEditStationModal();
                if (this.state.selectedDetailStation && this.state.selectedDetailStation.id === (this.state.editStationId || this.state.renameStationId)) {
                    this.state.selectedDetailStation.name = name;
                    this.state.selectedDetailStation.company_id = this.state.editStationCompanyId;
                    this.state.selectedDetailStation.vpn_ip = this.state.editStationVpnIp;
                    this.state.selectedDetailStation.admin_platform_code = this.state.editStationAdminPlatformCode;
                    this.state.selectedDetailStation.street = this.state.editStationStreet;
                    this.state.selectedDetailStation.zip = this.state.editStationZip;
                    this.state.selectedDetailStation.city = this.state.editStationCity;
                    this.state.selectedDetailStation.phone = this.state.editStationPhone;
                    this.state.selectedDetailStation.email = this.state.editStationEmail;
                    const matchedComp = this.state.allAuthorizedCompanies.find(c => c.id == this.state.editStationCompanyId);
                    if (matchedComp) {
                        this.state.selectedDetailStation.company_name = matchedComp.name;
                    }
                }
                if (this.state.viewMode === "company_detail" && this.state.selectedDetailCompany) {
                    await this.loadCompanyDetailData(this.state.selectedDetailCompany.id);
                }
                await this.loadDashboardData();
            } else {
                this.state.stationEditError = res.message || "Error al actualizar estación";
                this.notification.add(res.message || "Error al actualizar estación", { type: "danger" });
            }
        } catch (e) {
            console.error("Error updating station:", e);
            this.state.stationEditError = "Error de conexión con el servidor al actualizar la estación.";
            this.notification.add("Error de conexión al actualizar estación", { type: "danger" });
        } finally {
            this.state.actionLoading = false;
        }
    }

    async submitRenameStation() {
        return this.submitEditStation();
    }

    async deleteStation(st) {
        this.dialog.add(ConfirmationDialog, {
            title: "Eliminar Estación de Servicio",
            body: `¿Está seguro de que desea eliminar la estación "${st.name}"? Esta acción no se puede deshacer.`,
            confirm: async () => {
                this.state.loading = true;
                try {
                    const res = await jsonrpc("/pos_gas_station/delete_station", { config_id: st.id });
                    if (res.status === "success") {
                        this.notification.add(res.message, { type: "success" });
                        await this.loadDashboardData();
                    } else {
                        this.state.loading = false;
                        this.dialog.add(ConfirmationDialog, {
                            title: "No se puede eliminar la estación",
                            body: res.message || "No se puede eliminar la estación porque contiene registros de ventas o facturación.",
                            confirmLabel: "Entendido",
                            cancel: () => {},
                        });
                    }
                } catch (e) {
                    this.state.loading = false;
                    console.error("Error deleting station:", e);
                    this.notification.add("Error al comunicarse con el servidor al eliminar la estación.", { type: "danger" });
                }
            },
            cancel: () => {},
        });
    }

    // ==================== EMPLEADOS Y PERSONAL ====================
    openEmployeeCompanyRoles() {
        this.actionService.doAction("pos_gas_station.action_employee_company_roles");
    }

    async openCompanyEmployees(comp) {
        this.state.selectedCompany = comp;
        this.state.showEmployeesModal = true;
        this.state.modalLoading = true;
        this.state.searchTerm = "";
        this.state.filterAssignedOnly = false;
        try {
            const data = await jsonrpc("/pos_gas_station/company_employees_data", {
                company_id: comp.id
            });
            if (data.status === "success") {
                this.state.allCompanies = data.companies;
                this.state.companyEmployees = data.employees;
            }
        } catch (e) {
            console.error("Error loading company employees:", e);
            this.notification.add("Error al cargar listado de empleados", { type: "danger" });
        } finally {
            this.state.modalLoading = false;
        }
    }

    closeEmployeesModal() {
        this.state.showEmployeesModal = false;
        this.loadDashboardData();
    }

    onSearchInput(ev) {
        this.state.searchTerm = (ev.target.value || "").toLowerCase();
    }

    clearSearch() {
        this.state.searchTerm = "";
    }

    setFilter(assignedOnly) {
        this.state.filterAssignedOnly = assignedOnly;
    }

    getAssignedCount() {
        if (!this.state.selectedCompany) return 0;
        const compId = this.state.selectedCompany.id;
        return (this.state.companyEmployees || []).filter(e => e.company_ids.includes(compId)).length;
    }

    getFilteredEmployees() {
        let list = this.state.companyEmployees || [];
        if (this.state.filterAssignedOnly && this.state.selectedCompany) {
            const compId = this.state.selectedCompany.id;
            list = list.filter(e => e.company_ids.includes(compId));
        }
        if (this.state.searchTerm) {
            const q = this.state.searchTerm.trim().toLowerCase();
            list = list.filter(e => {
                const nameMatch = (e.name || "").toLowerCase().includes(q);
                const dniMatch = (e.dni || "").toLowerCase().includes(q);
                const emailMatch = (e.email || "").toLowerCase().includes(q);
                const codeMatch = String(e.code || "").toLowerCase().includes(q);
                return nameMatch || dniMatch || emailMatch || codeMatch;
            });
        }
        return list;
    }

    async toggleCompanyAccess(emp, compId, enable) {
        this.state.updatingUserId = emp.odoo_user_id;
        try {
            const res = await jsonrpc("/pos_gas_station/toggle_employee_company_access", {
                user_id: emp.odoo_user_id,
                company_id: compId,
                enable: enable
            });
            if (res.status === "success") {
                emp.company_ids = res.company_ids;
                const comp = this.state.companies.find(c => c.id === compId);
                if (comp) {
                    comp.employees_count = res.company_employees_count;
                }
                this.notification.add(
                    enable
                        ? `Acceso concedido a ${emp.name} en ${res.company_name}`
                        : `Acceso retirado a ${emp.name} de ${res.company_name}`,
                    { type: "success" }
                );
            } else {
                this.notification.add(res.message || "Error al actualizar asignación", { type: "danger" });
            }
        } catch (e) {
            console.error("Error toggling employee access:", e);
            this.notification.add("Error de conexión al actualizar permisos", { type: "danger" });
        } finally {
            this.state.updatingUserId = null;
        }
    }

    // ==================== PÁGINA DE DETALLE DE EMPRESA ====================
    async openCompanyDetail(comp) {
        this.state.selectedDetailCompany = comp;
        this.state.viewMode = "company_detail";
        this.state.detailTab = "stations";
        this.state.customerSearchTerm = "";
        this.state.customerCodeSearchTerm = "";
        this.state.customerFilterType = "all";
        this.state.customerPage = 1;
        this.state.customerTotalCount = 0;
        this.state.customerSortField = "name";
        this.state.customerSortDir = "asc";
        this.state.productSearchTerm = "";
        this.state.productCategoryFilter = "all";
        this.state.productPage = 1;
        this.state.productTotalCount = 0;
        this.state.editingProductId = null;
        this.state.editingProductPrice = "";
        await this.loadCompanyDetailData(comp.id);
    }

    async loadCompanyDetailData(companyId) {
        this.state.detailLoading = true;
        try {
            const data = await jsonrpc("/pos_gas_station/company_detail_data", {
                company_id: companyId
            });
            if (data.status === "success") {
                this.state.companyDetailData = data;
                this.state.customerTotalCount = (data.customer_stats && typeof data.customer_stats.total === "number")
                    ? data.customer_stats.total
                    : (data.customers ? data.customers.length : 0);
                this.state.productTotalCount = (data.product_stats && typeof data.product_stats.total === "number")
                    ? data.product_stats.total
                    : (data.products ? data.products.length : 0);
                if (data.product_form_metadata) {
                    this.state.productCategoriesTree = data.product_form_metadata.categories_tree || [];
                    this.state.productTaxesList = data.product_form_metadata.taxes || [];
                    this.state.productSuppliersList = data.product_form_metadata.suppliers || [];
                }
            } else {
                this.notification.add(data.message || "Error al cargar detalle de empresa", { type: "danger" });
            }
        } catch (e) {
            console.error("Error loading company detail:", e);
            this.notification.add("Error de conexión al cargar detalle de empresa", { type: "danger" });
        } finally {
            this.state.detailLoading = false;
        }
    }

    backToDashboard() {
        this.state.viewMode = "dashboard";
        this.state.selectedDetailCompany = null;
        this.state.selectedDetailStation = null;
        this.state.companyDetailData = null;
        this.state.isAdminMenuOpen = false;
        this.loadDashboardData();
    }

    setDetailTab(tab) {
        this.state.detailTab = tab;
        this.state.isAdminMenuOpen = false;
    }

    toggleAdminMenu() {
        this.state.isAdminMenuOpen = !this.state.isAdminMenuOpen;
    }

    async selectAdminOption(optionTab) {
        this.state.isAdminMenuOpen = false;
        this.state.detailTab = optionTab;
        if (optionTab === "admin_params") {
            this.state.adminParamSection = "menu";
            await Promise.all([
                this.loadTaxTypes(),
                this.loadCategoriesList()
            ]);
        }
    }

    setAdminParamSection(section) {
        this.state.adminParamSection = section;
        if (section === "taxes") {
            this.loadTaxTypes();
        } else if (section === "categories") {
            this.loadCategoriesList();
        }
    }

    async loadTaxTypes() {
        const companyId = this.state.selectedDetailCompany ? this.state.selectedDetailCompany.id : null;
        this.state.taxTypesLoading = true;
        try {
            const res = await jsonrpc("/pos_gas_station/get_tax_types", {
                company_id: companyId,
            });
            if (res && res.status === "success") {
                this.state.taxTypesList = res.tax_types || [];
            } else {
                this.notification.add((res && res.message) || "Error al cargar tipos de IVA", { type: "danger" });
            }
        } catch (e) {
            console.error("Error loading tax types:", e);
            this.notification.add("Error de conexión al cargar tipos de IVA", { type: "danger" });
        } finally {
            this.state.taxTypesLoading = false;
        }
    }

    openTaxTypeModal(taxRow = null) {
        this.state.editingTaxType = taxRow || null;
        this.state.taxTypeCode = taxRow ? String(taxRow.code || "") : "";
        this.state.taxTypeName = taxRow ? (taxRow.name || "") : "";
        this.state.taxTypePercentage = taxRow ? String(taxRow.percentage ?? 0) : "21";
        this.state.taxTypeIsExempt = taxRow ? Boolean(taxRow.is_exempt) : false;
        this.state.isTaxTypeModalOpen = true;
    }

    closeTaxTypeModal() {
        this.state.isTaxTypeModalOpen = false;
        this.state.editingTaxType = null;
    }

    async saveTaxTypeModal() {
        if (!this.state.taxTypeCode || !this.state.taxTypeCode.trim()) {
            this.notification.add("El código del tipo de IVA es obligatorio.", { type: "warning" });
            return;
        }
        if (!this.state.taxTypeName || !this.state.taxTypeName.trim()) {
            this.notification.add("El nombre del tipo de IVA es obligatorio.", { type: "warning" });
            return;
        }
        const companyId = this.state.selectedDetailCompany ? this.state.selectedDetailCompany.id : null;
        this.state.isSavingTaxType = true;
        try {
            const res = await jsonrpc("/pos_gas_station/save_tax_type", {
                tax_type_id: this.state.editingTaxType ? this.state.editingTaxType.id : null,
                company_id: companyId,
                code: this.state.taxTypeCode.trim(),
                name: this.state.taxTypeName.trim(),
                percentage: this.state.taxTypeIsExempt ? 0 : (parseFloat(this.state.taxTypePercentage) || 0),
                is_exempt: this.state.taxTypeIsExempt,
            });
            if (res && res.status === "success") {
                this.notification.add(res.message, { type: "success" });
                this.closeTaxTypeModal();
                await this.loadTaxTypes();
                await this.loadProductFormMetadata();
            } else {
                this.notification.add((res && res.message) || "Error al guardar tipo de IVA", { type: "danger" });
            }
        } catch (e) {
            console.error("Error saving tax type:", e);
            this.notification.add("Error de conexión al guardar tipo de IVA", { type: "danger" });
        } finally {
            this.state.isSavingTaxType = false;
        }
    }

    async deleteTaxType(taxRow) {
        if (!taxRow) return;
        this.dialog.add(ConfirmationDialog, {
            title: "Eliminar Tipo de IVA",
            body: `¿Seguro que desea eliminar el tipo de IVA "${taxRow.code} · ${taxRow.name}"?`,
            confirm: async () => {
                try {
                    const res = await jsonrpc("/pos_gas_station/delete_tax_type", {
                        tax_type_id: taxRow.id,
                    });
                    if (res && res.status === "success") {
                        this.notification.add(res.message, { type: "success" });
                        await this.loadTaxTypes();
                        await this.loadProductFormMetadata();
                    } else {
                        this.notification.add((res && res.message) || "Error al eliminar tipo de IVA", { type: "danger" });
                    }
                } catch (e) {
                    console.error("Error deleting tax type:", e);
                    this.notification.add("Error de conexión al eliminar tipo de IVA", { type: "danger" });
                }
            },
            cancel: () => {},
        });
    }

    async setCustomerFilter(type) {
        this.state.customerFilterType = type;
        this.state.customerPage = 1;
        await this.searchCompanyCustomers();
    }

    onCustomerSearchInput(ev) {
        this.state.customerSearchTerm = ev.target.value;
        if (this.customerSearchDebounceTimer) {
            clearTimeout(this.customerSearchDebounceTimer);
        }
        this.customerSearchDebounceTimer = setTimeout(() => {
            this.state.customerPage = 1;
            this.searchCompanyCustomers();
        }, 300);
    }

    onCustomerCodeSearchInput(ev) {
        this.state.customerCodeSearchTerm = ev.target.value;
        if (this.customerCodeSearchDebounceTimer) {
            clearTimeout(this.customerCodeSearchDebounceTimer);
        }
        this.customerCodeSearchDebounceTimer = setTimeout(() => {
            this.state.customerPage = 1;
            this.searchCompanyCustomers();
        }, 300);
    }

    async sortCompanyCustomers(field) {
        if (this.state.customerSortField === field) {
            this.state.customerSortDir = this.state.customerSortDir === "asc" ? "desc" : "asc";
        } else {
            this.state.customerSortField = field;
            this.state.customerSortDir = "asc";
        }
        this.state.customerPage = 1;
        await this.searchCompanyCustomers();
    }

    async goToCustomerPage(page) {
        const target = Math.max(1, Math.min(page, this.customerTotalPages));
        if (target === this.state.customerPage) return;
        this.state.customerPage = target;
        await this.searchCompanyCustomers();
    }

    async searchCompanyCustomers() {
        if (!this.state.selectedDetailCompany) return;
        this.state.customerLoading = true;
        try {
            const offset = (this.state.customerPage - 1) * this.state.customerPageSize;
            const res = await jsonrpc("/pos_gas_station/company_customers", {
                company_id: this.state.selectedDetailCompany.id,
                search_term: this.state.customerSearchTerm,
                code_term: this.state.customerCodeSearchTerm,
                customer_type: this.state.customerFilterType,
                limit: this.state.customerPageSize,
                offset: offset,
                sort_field: this.state.customerSortField,
                sort_dir: this.state.customerSortDir,
            });
            if (res && res.status === "success" && this.state.companyDetailData) {
                this.state.companyDetailData.customers = res.customers || [];
                this.state.customerTotalCount = typeof res.total === "number"
                    ? res.total
                    : (res.customers || []).length;
            }
        } catch (e) {
            console.error("Error searching company customers:", e);
        } finally {
            this.state.customerLoading = false;
        }
    }

    get customerTotalPages() {
        return Math.max(1, Math.ceil((this.state.customerTotalCount || 0) / this.state.customerPageSize));
    }

    get customerRangeStart() {
        if (!this.state.customerTotalCount) return 0;
        return (this.state.customerPage - 1) * this.state.customerPageSize + 1;
    }

    get customerRangeEnd() {
        if (!this.state.customerTotalCount) return 0;
        return Math.min(this.state.customerPage * this.state.customerPageSize, this.state.customerTotalCount);
    }

    get customerPaginationPages() {
        const total = this.customerTotalPages;
        const current = this.state.customerPage;
        if (total <= 7) {
            return Array.from({ length: total }, (_, idx) => ({ key: `p-${idx + 1}`, type: "page", page: idx + 1 }));
        }
        const pages = [{ key: "p-1", type: "page", page: 1 }];
        if (current > 3) {
            pages.push({ key: "e-left", type: "ellipsis" });
        }
        const start = Math.max(2, current - 1);
        const end = Math.min(total - 1, current + 1);
        for (let p = start; p <= end; p++) {
            pages.push({ key: `p-${p}`, type: "page", page: p });
        }
        if (current < total - 2) {
            pages.push({ key: "e-right", type: "ellipsis" });
        }
        pages.push({ key: `p-${total}`, type: "page", page: total });
        return pages;
    }

    get filteredCompanyCustomers() {
        if (!this.state.companyDetailData || !this.state.companyDetailData.customers) {
            return [];
        }
        return this.state.companyDetailData.customers;
    }

    openPartnerForm(partnerId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: partnerId,
            views: [[false, "form"]],
            target: "current"
        });
    }

    openCreatePartner() {
        const compId = this.state.selectedDetailCompany ? this.state.selectedDetailCompany.id : false;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            views: [[false, "form"]],
            context: {
                default_company_id: compId,
                default_customer_rank: 1,
            },
            target: "current"
        });
    }

    openOdooCustomersView() {
        const compId = this.state.selectedDetailCompany ? this.state.selectedDetailCompany.id : false;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: `Clientes - ${this.state.selectedDetailCompany ? this.state.selectedDetailCompany.name : ''}`,
            res_model: "res.partner",
            views: [[false, "list"], [false, "form"]],
            domain: [["company_id", "=", compId], ["type", "!=", "private"]],
            context: {
                default_company_id: compId,
                search_default_filter_customer: 1,
            },
            target: "current"
        });
    }

    openOdooInventoryView() {
        const compId = this.state.selectedDetailCompany ? this.state.selectedDetailCompany.id : false;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: `Stock / Inventario - ${this.state.selectedDetailCompany ? this.state.selectedDetailCompany.name : ''}`,
            res_model: "stock.quant",
            views: [[false, "list"], [false, "form"]],
            domain: [["company_id", "=", compId]],
            context: {
                default_company_id: compId,
            },
            target: "current"
        });
    }

    // ==================== GESTIÓN DE PRODUCTOS Y TARIFAS ====================
    get productTotalPages() {
        if (!this.state.productTotalCount || this.state.productTotalCount <= 0) return 1;
        return Math.ceil(this.state.productTotalCount / this.state.productPageSize);
    }

    async setProductCategoryFilter(cat) {
        if (this.state.productCategoryFilter === cat) return;
        this.state.productCategoryFilter = cat;
        this.state.productPage = 1;
        await this.searchCompanyProducts();
    }

    async onProductSearchInput(ev) {
        this.state.productSearchTerm = ev.target.value;
        this.state.productPage = 1;
        if (this._productSearchTimeout) clearTimeout(this._productSearchTimeout);
        this._productSearchTimeout = setTimeout(() => {
            this.searchCompanyProducts();
        }, 350);
    }

    clearProductSearch() {
        this.state.productSearchTerm = "";
        this.state.productPage = 1;
        this.searchCompanyProducts();
    }

    async goToProductPage(page) {
        const target = Math.max(1, Math.min(page, this.productTotalPages));
        if (target === this.state.productPage) return;
        this.state.productPage = target;
        await this.searchCompanyProducts();
    }

    async searchCompanyProducts() {
        if (!this.state.selectedDetailCompany) return;
        this.state.productLoading = true;
        try {
            const offset = (this.state.productPage - 1) * this.state.productPageSize;
            const res = await jsonrpc("/pos_gas_station/company_products", {
                company_id: this.state.selectedDetailCompany.id,
                search_term: this.state.productSearchTerm,
                category_type: this.state.productCategoryFilter,
                limit: this.state.productPageSize,
                offset: offset,
                sort_field: this.state.productSortField,
                sort_dir: this.state.productSortDir,
            });
            if (res && res.status === "success" && this.state.companyDetailData) {
                this.state.companyDetailData.products = res.products || [];
                this.state.productTotalCount = res.total || 0;
            }
        } catch (e) {
            console.error("Error searching products:", e);
        } finally {
            this.state.productLoading = false;
        }
    }

    startEditProductPrice(prod) {
        this.state.editingProductId = prod.id;
        this.state.editingProductPrice = String(prod.list_price || "0.000");
    }

    cancelEditProductPrice() {
        this.state.editingProductId = null;
        this.state.editingProductPrice = "";
    }

    onProductPriceKeydown(ev, prod) {
        if (ev.key === "Enter") {
            this.saveProductPrice(prod);
        } else if (ev.key === "Escape") {
            this.cancelEditProductPrice();
        }
    }

    async saveProductPrice(prod) {
        if (!this.state.editingProductId || this.state.editingProductId !== prod.id) return;
        this.state.isSavingPrice = true;
        try {
            const res = await jsonrpc("/pos_gas_station/update_product_price", {
                product_id: prod.id,
                new_price: this.state.editingProductPrice,
            });
            if (res && res.status === "success") {
                prod.list_price = res.new_price;
                this.notification.add(res.message, { type: "success" });
                this.cancelEditProductPrice();
            } else {
                this.notification.add((res && res.message) || "Error al actualizar precio", { type: "danger" });
            }
        } catch (e) {
            console.error("Error updating price:", e);
            this.notification.add("Error de conexión al actualizar precio", { type: "danger" });
        } finally {
            this.state.isSavingPrice = false;
        }
    }

    async openCreateProduct() {
        await this.openEditProductModal(null);
    }

    async loadProductFormMetadata() {
        const companyId = this.state.selectedDetailCompany ? this.state.selectedDetailCompany.id : null;
        try {
            const res = await jsonrpc("/pos_gas_station/get_product_form_metadata", {
                company_id: companyId,
            });
            if (res && res.status === "success") {
                this.state.productCategoriesTree = res.categories_tree || [];
                this.state.productTaxesList = res.taxes || [];
                this.state.productSuppliersList = res.suppliers || [];
            } else if (res && res.message) {
                this.notification.add(res.message, { type: "warning" });
            }
        } catch (e) {
            console.error("Error loading product form metadata:", e);
        }
    }

    async openEditProductModal(prod) {
        if (!this.state.productCategoriesTree || !this.state.productCategoriesTree.length) {
            await this.loadProductFormMetadata();
        } else {
            this.loadProductFormMetadata();
        }
        this.state.editingProduct = prod || null;
        this.state.editProdName = prod ? prod.name : "";
        this.state.editProdCode = prod ? (prod.default_code || "") : "";
        const initialBarcodes = prod
            ? (Array.isArray(prod.all_barcodes) && prod.all_barcodes.length
                ? [...prod.all_barcodes]
                : (prod.barcode ? [prod.barcode] : []))
            : [];
        this.state.editProdBarcodes = initialBarcodes;
        this.state.editProdNewBarcode = "";
        this.state.editProdCategId = prod && prod.categ_id ? String(prod.categ_id) : "";
        this.state.editProdType = prod ? (prod.type || "consu") : "consu";
        this.state.editProdPrice = prod ? String(prod.list_price ?? "") : "";
        this.state.editProdCost = prod ? String(prod.standard_price ?? "") : "";
        let defaultTaxId = "";
        if (prod && prod.tax_id) {
            defaultTaxId = String(prod.tax_id);
        } else if (this.state.productTaxesList && this.state.productTaxesList.length) {
            const generalTax = this.state.productTaxesList.find(t => String(t.code) === "1") || this.state.productTaxesList[0];
            defaultTaxId = generalTax ? String(generalTax.id) : "";
        }
        this.state.editProdTaxId = defaultTaxId;
        this.state.editProdSupplierId = prod && prod.supplier_id ? String(prod.supplier_id) : "";
        let supplierLabel = "";
        if (prod && prod.supplier_id) {
            const foundSup = (this.state.productSuppliersList || []).find(s => String(s.id) === String(prod.supplier_id));
            if (foundSup) {
                supplierLabel = foundSup.vat ? `${foundSup.name} (${foundSup.vat})` : foundSup.name;
            } else if (prod.supplier_name) {
                supplierLabel = prod.supplier_name;
            }
        }
        this.state.editProdSupplierSearch = supplierLabel;
        this.state.isSupplierDropdownOpen = false;
        this.state.editProdImageBase64 = "";
        this.state.editProdHasExistingImage = Boolean(prod && prod.has_image);
        this.state.editProdImagePreview = (prod && prod.image_url) ? prod.image_url : "";
        this.state.editProdInPos = prod ? (prod.available_in_pos !== false) : true;
        this.state.isEditProductModalOpen = true;
    }

    get filteredProductSuppliers() {
        const list = this.state.productSuppliersList || [];
        const q = (this.state.editProdSupplierSearch || "").trim().toLowerCase();
        if (!q) {
            return list.slice(0, 35);
        }
        return list.filter(sup => {
            const name = (sup.name || "").toLowerCase();
            const vat = (sup.vat || "").toLowerCase();
            const ref = (sup.ref || "").toLowerCase();
            return name.includes(q) || vat.includes(q) || ref.includes(q);
        }).slice(0, 35);
    }

    onSupplierSearchInput(ev) {
        this.state.editProdSupplierSearch = ev.target.value;
        this.state.editProdSupplierId = "";
        this.state.isSupplierDropdownOpen = true;
    }

    onSupplierSearchFocus() {
        this.state.isSupplierDropdownOpen = true;
    }

    onSupplierSearchBlur() {
        setTimeout(() => {
            this.state.isSupplierDropdownOpen = false;
        }, 200);
    }

    selectSupplierOption(sup) {
        if (!sup) return;
        this.state.editProdSupplierId = String(sup.id);
        this.state.editProdSupplierSearch = sup.vat ? `${sup.name} (${sup.vat})` : sup.name;
        this.state.isSupplierDropdownOpen = false;
    }

    clearSelectedSupplier() {
        this.state.editProdSupplierId = "";
        this.state.editProdSupplierSearch = "";
        this.state.isSupplierDropdownOpen = true;
    }

    closeEditProductModal() {
        this.state.isEditProductModalOpen = false;
        this.state.editingProduct = null;
        this.state.isNewSupplierModalOpen = false;
        this.state.isSupplierDropdownOpen = false;
    }

    async onProductCategoryChange(ev) {
        const categId = ev.target.value;
        this.state.editProdCategId = categId;
        if (!categId) {
            if (!this.state.editingProduct) {
                this.state.editProdCode = "";
            }
            return;
        }
        try {
            const res = await jsonrpc("/pos_gas_station/next_product_code", {
                categ_id: parseInt(categId),
            });
            if (res && res.status === "success" && res.next_code) {
                this.state.editProdCode = res.next_code;
            }
        } catch (e) {
            console.error("Error fetching next product code:", e);
        }
    }

    onProductImageSelected(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) return;
        if (!file.type.startsWith("image/")) {
            this.notification.add("El archivo seleccionado debe ser una imagen.", { type: "warning" });
            return;
        }
        const reader = new FileReader();
        reader.onload = () => {
            const dataUrl = reader.result || "";
            const base64 = dataUrl.includes(",") ? dataUrl.split(",")[1] : dataUrl;
            this.state.editProdImagePreview = dataUrl;
            this.state.editProdImageBase64 = base64;
        };
        reader.readAsDataURL(file);
    }

    addProductBarcode() {
        const clean = (this.state.editProdNewBarcode || "").trim();
        if (!clean) return;
        if (this.state.editProdBarcodes.includes(clean)) {
            this.notification.add(`El código de barras "${clean}" ya está en la lista.`, { type: "warning" });
            return;
        }
        this.state.editProdBarcodes = [...this.state.editProdBarcodes, clean];
        this.state.editProdNewBarcode = "";
    }

    removeProductBarcode(item) {
        if (typeof item === "number") {
            this.state.editProdBarcodes = this.state.editProdBarcodes.filter((_, i) => i !== item);
        } else {
            this.state.editProdBarcodes = this.state.editProdBarcodes.filter(b => b !== item);
        }
    }

    onBarcodeInputKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.addProductBarcode();
        }
    }

    openNewSupplierModal() {
        this.state.newSupplierName = "";
        this.state.newSupplierVat = "";
        this.state.newSupplierPhone = "";
        this.state.newSupplierEmail = "";
        this.state.isNewSupplierModalOpen = true;
    }

    closeNewSupplierModal() {
        this.state.isNewSupplierModalOpen = false;
    }

    async saveNewSupplierModal() {
        if (!this.state.newSupplierName || !this.state.newSupplierName.trim()) {
            this.notification.add("El nombre / razón social del proveedor es obligatorio.", { type: "warning" });
            return;
        }
        this.state.isSavingNewSupplier = true;
        try {
            const res = await jsonrpc("/pos_gas_station/create_supplier", {
                name: this.state.newSupplierName.trim(),
                vat: (this.state.newSupplierVat || "").trim(),
                phone: (this.state.newSupplierPhone || "").trim(),
                email: (this.state.newSupplierEmail || "").trim(),
            });
            if (res && res.status === "success" && res.supplier) {
                this.notification.add(res.message, { type: "success" });
                this.state.productSuppliersList = [...this.state.productSuppliersList, res.supplier]
                    .sort((a, b) => a.name.localeCompare(b.name));
                this.state.editProdSupplierId = String(res.supplier.id);
                this.state.editProdSupplierSearch = res.supplier.vat
                    ? `${res.supplier.name} (${res.supplier.vat})`
                    : res.supplier.name;
                this.state.isSupplierDropdownOpen = false;
                this.closeNewSupplierModal();
            } else {
                this.notification.add((res && res.message) || "Error al crear proveedor", { type: "danger" });
            }
        } catch (e) {
            console.error("Error creating supplier:", e);
            this.notification.add("Error de conexión al crear proveedor", { type: "danger" });
        } finally {
            this.state.isSavingNewSupplier = false;
        }
    }

    async saveProductModal() {
        // Si escribió un EAN en la caja y no pulsó "+", añadirlo automáticamente
        if (this.state.editProdNewBarcode && this.state.editProdNewBarcode.trim()) {
            this.addProductBarcode();
        }

        // Si escribió exactamente el nombre de un proveedor sin hacer clic en la sugerencia
        if (!this.state.editProdSupplierId && this.state.editProdSupplierSearch && this.state.editProdSupplierSearch.trim()) {
            const q = this.state.editProdSupplierSearch.trim().toLowerCase();
            const exact = (this.state.productSuppliersList || []).find(
                s => (s.name || "").toLowerCase() === q ||
                     (s.vat && `${s.name} (${s.vat})`.toLowerCase() === q)
            );
            if (exact) {
                this.state.editProdSupplierId = String(exact.id);
            }
        }

        if (!this.state.editProdName || !this.state.editProdName.trim()) {
            this.notification.add("El nombre del artículo es obligatorio.", { type: "warning" });
            return;
        }
        if (!this.state.editProdImageBase64 && !this.state.editProdHasExistingImage) {
            this.notification.add("La imagen asociada al producto es obligatoria.", { type: "warning" });
            return;
        }
        if (!this.state.editProdCategId) {
            this.notification.add("Debe seleccionar una categoría de producto.", { type: "warning" });
            return;
        }
        if (!this.state.editProdCode || !this.state.editProdCode.trim()) {
            this.notification.add("El código interno / referencia es obligatorio.", { type: "warning" });
            return;
        }
        if (!this.state.editProdBarcodes || this.state.editProdBarcodes.length === 0) {
            this.notification.add("Debe añadir al menos un código de barras (EAN).", { type: "warning" });
            return;
        }
        if (!this.state.editProdType) {
            this.notification.add("El tipo de producto es obligatorio.", { type: "warning" });
            return;
        }
        if (!this.state.editProdTaxId) {
            this.notification.add("Debe seleccionar el tipo de IVA o Exento de IVA.", { type: "warning" });
            return;
        }
        if (this.state.editProdPrice === "" || this.state.editProdPrice === null || isNaN(parseFloat(this.state.editProdPrice))) {
            this.notification.add("El Precio de Venta al Público (PVP) es obligatorio.", { type: "warning" });
            return;
        }
        if (this.state.editProdCost === "" || this.state.editProdCost === null || isNaN(parseFloat(this.state.editProdCost))) {
            this.notification.add("El Precio de Coste es obligatorio.", { type: "warning" });
            return;
        }
        if (!this.state.editProdSupplierId) {
            this.notification.add("Debe seleccionar un proveedor para el producto.", { type: "warning" });
            return;
        }

        const companyId = this.state.selectedDetailCompany ? this.state.selectedDetailCompany.id : null;
        this.state.isSavingProductForm = true;
        try {
            const res = await jsonrpc("/pos_gas_station/save_product", {
                product_id: this.state.editingProduct ? this.state.editingProduct.id : null,
                company_id: companyId,
                name: this.state.editProdName.trim(),
                default_code: this.state.editProdCode.trim(),
                barcodes: this.state.editProdBarcodes,
                categ_id: parseInt(this.state.editProdCategId),
                prod_type: this.state.editProdType,
                list_price: parseFloat(this.state.editProdPrice),
                standard_price: parseFloat(this.state.editProdCost),
                tax_id: this.state.editProdTaxId,
                supplier_id: parseInt(this.state.editProdSupplierId),
                image_1920: this.state.editProdImageBase64 || null,
                available_in_pos: this.state.editProdInPos,
            });
            if (res && res.status === "success") {
                this.notification.add(res.message, { type: "success" });
                this.closeEditProductModal();
                await this.fetchProducts();
            } else {
                this.notification.add((res && res.message) || "Error al guardar producto", { type: "danger" });
            }
        } catch (e) {
            console.error("Error saving product:", e);
            this.notification.add("Error de conexión al guardar producto", { type: "danger" });
        } finally {
            this.state.isSavingProductForm = false;
        }
    }

    openStockAdjustModal(prod) {
        if (!prod) return;
        this.state.stockAdjustProduct = prod;
        this.state.stockAdjustCurrentQty = prod.qty_available || 0.0;
        this.state.stockAdjustNewQty = prod.qty_available || 0.0;
        this.state.stockAdjustReason = "Recuento físico periódico";
        this.state.isStockAdjustModalOpen = true;
    }

    closeStockAdjustModal() {
        this.state.isStockAdjustModalOpen = false;
        this.state.stockAdjustProduct = null;
    }

    async saveStockAdjustModal() {
        if (!this.state.stockAdjustProduct) return;
        const companyId = this.state.selectedDetailCompany ? this.state.selectedDetailCompany.id : null;
        this.state.isSavingStockAdjust = true;
        try {
            const res = await jsonrpc("/pos_gas_station/adjust_product_stock", {
                product_id: this.state.stockAdjustProduct.id,
                company_id: companyId,
                new_qty: parseFloat(this.state.stockAdjustNewQty) || 0.0,
                reason: this.state.stockAdjustReason,
            });
            if (res && res.status === "success") {
                this.notification.add(res.message, { type: "success" });
                this.state.stockAdjustProduct.qty_available = res.new_qty;
                this.closeStockAdjustModal();
            } else {
                this.notification.add((res && res.message) || "Error al ajustar stock", { type: "danger" });
            }
        } catch (e) {
            console.error("Error adjusting stock:", e);
            this.notification.add("Error de conexión al ajustar stock", { type: "danger" });
        } finally {
            this.state.isSavingStockAdjust = false;
        }
    }

    async openCategoriesModal() {
        await this.selectAdminOption("admin_params");
        this.setAdminParamSection("categories");
    }

    closeCategoriesModal() {
        this.state.isCategoriesModalOpen = false;
    }

    async loadCategoriesList() {
        this.state.categoriesLoading = true;
        try {
            const res = await jsonrpc("/pos_gas_station/get_categories_list", {});
            if (res && res.status === "success") {
                this.state.categoriesList = res.categories || [];
                this.state.categoriesTree = res.categories_tree || [];
                this.state.allParentsList = res.all_parents || [];
                this.state.nextParentCode = res.next_parent_code || "";
                if (this.state.companyDetailData) {
                    this.state.companyDetailData.all_categories = (res.categories || []).map(c => ({
                        id: c.id,
                        name: c.name,
                        parent_id: c.parent_id,
                        code: c.code,
                        full_code: c.full_code,
                    }));
                }
            } else if (res && res.message) {
                this.notification.add(res.message, { type: "warning" });
            }
        } catch (e) {
            console.error("Error loading categories:", e);
        } finally {
            this.state.categoriesLoading = false;
        }
    }

    async openCategoryFormModal(level = 'parent', parentId = null, categoryToEdit = null) {
        this.state.editingCategory = categoryToEdit || null;
        this.state.categoryModalLevel = level;
        let resolvedParentId = "";
        if (parentId) {
            resolvedParentId = String(parentId);
        } else if (categoryToEdit && categoryToEdit.parent_id) {
            resolvedParentId = String(categoryToEdit.parent_id);
        } else if (level === "child") {
            if (this.state.categoryParentId) {
                resolvedParentId = String(this.state.categoryParentId);
            } else if (this.state.allParentsList && this.state.allParentsList.length) {
                resolvedParentId = String(this.state.allParentsList[0].id);
            }
        }
        this.state.categoryParentId = resolvedParentId;
        this.state.categoryName = categoryToEdit ? categoryToEdit.name : "";

        if (categoryToEdit) {
            this.state.categoryCode = categoryToEdit.code || "";
        } else {
            // Sugerir siguiente código disponible
            try {
                const res = await jsonrpc("/pos_gas_station/get_next_category_code", {
                    parent_id: this.state.categoryParentId ? parseInt(this.state.categoryParentId) : null,
                });
                if (res && res.status === "success") {
                    this.state.categoryCode = res.code || "";
                } else {
                    this.state.categoryCode = level === "parent" ? (this.state.nextParentCode || "1") : "01";
                }
            } catch (e) {
                this.state.categoryCode = level === "parent" ? (this.state.nextParentCode || "1") : "01";
            }
        }
        this.state.isCategoryModalOpen = true;
    }

    closeCategoryModal() {
        this.state.isCategoryModalOpen = false;
        this.state.editingCategory = null;
    }

    async onCategoryModalParentChange(ev) {
        const pid = ev.target.value;
        this.state.categoryParentId = pid;
        if (this.state.categoryModalLevel === "child" && pid && !this.state.editingCategory) {
            try {
                const res = await jsonrpc("/pos_gas_station/get_next_category_code", {
                    parent_id: parseInt(pid),
                });
                if (res && res.status === "success") {
                    this.state.categoryCode = res.code || "01";
                }
            } catch (e) {
                console.error("Error getting next child code:", e);
            }
        }
    }

    async saveCategoryModal() {
        if (!this.state.categoryName || !this.state.categoryName.trim()) {
            this.notification.add("El nombre de la categoría es obligatorio.", { type: "warning" });
            return;
        }
        const isChild = this.state.categoryModalLevel === "child";
        if (isChild && !this.state.categoryParentId) {
            this.notification.add("Debe seleccionar una categoría padre para la subfamilia.", { type: "warning" });
            return;
        }
        const code = (this.state.categoryCode || "").trim();
        if (!code) {
            this.notification.add("El código de la categoría es obligatorio.", { type: "warning" });
            return;
        }
        if (isChild && (code.length !== 2 || !/^\d{2}$/.test(code))) {
            this.notification.add("El código de subfamilia debe tener exactamente 2 dígitos numéricos (ej: 01, 12).", { type: "warning" });
            return;
        }
        if (!isChild && (code.length !== 1 || !/^\d$/.test(code))) {
            this.notification.add("El código de familia padre debe tener exactamente 1 dígito numérico (1-9).", { type: "warning" });
            return;
        }

        this.state.isSavingCategory = true;
        try {
            const res = await jsonrpc("/pos_gas_station/save_category", {
                category_id: this.state.editingCategory ? this.state.editingCategory.id : null,
                name: this.state.categoryName.trim(),
                parent_id: isChild ? parseInt(this.state.categoryParentId) : null,
                code: code,
            });
            if (res && res.status === "success") {
                this.notification.add(res.message, { type: "success" });
                this.closeCategoryModal();
                await this.loadCategoriesList();
                await this.loadProductFormMetadata();
                await this.fetchProducts();
            } else {
                this.notification.add((res && res.message) || "Error al guardar categoría", { type: "danger" });
            }
        } catch (e) {
            console.error("Error saving category:", e);
            this.notification.add("Error de conexión al guardar categoría", { type: "danger" });
        } finally {
            this.state.isSavingCategory = false;
        }
    }

    async deleteCategoryItem(catItem) {
        if (!catItem) return;
        const isParent = !catItem.parent_id;
        const typeLabel = isParent ? "Familia Padre" : "Subfamilia";
        this.dialog.add(ConfirmationDialog, {
            title: `Eliminar ${typeLabel}`,
            body: `¿Está seguro de que desea eliminar ${isParent ? 'la familia' : 'la subfamilia'} "${catItem.full_code ? catItem.full_code + ' · ' : ''}${catItem.name}"? Esta acción solo se permitirá si no tiene subfamilias ni artículos asociados.`,
            confirm: async () => {
                try {
                    const res = await jsonrpc("/pos_gas_station/delete_category", {
                        category_id: catItem.id,
                    });
                    if (res && res.status === "success") {
                        this.notification.add(res.message, { type: "success" });
                        await this.loadCategoriesList();
                        await this.loadProductFormMetadata();
                        await this.fetchProducts();
                    } else {
                        this.notification.add((res && res.message) || "Error al eliminar categoría", { type: "danger" });
                    }
                } catch (e) {
                    console.error("Error deleting category:", e);
                    this.notification.add("Error de conexión al eliminar categoría", { type: "danger" });
                }
            }
        });
    }

    async saveNewCategory() {
        if (!this.state.newCategoryName || !this.state.newCategoryName.trim()) {
            this.notification.add("Introduzca el nombre de la categoría.", { type: "warning" });
            return;
        }
        this.state.isSavingCategory = true;
        try {
            const res = await jsonrpc("/pos_gas_station/save_category", {
                name: this.state.newCategoryName.trim(),
                parent_id: this.state.newCategoryParentId ? parseInt(this.state.newCategoryParentId) : null,
                code: (this.state.newCategoryCode || "").trim() || null,
            });
            if (res && res.status === "success") {
                this.notification.add(res.message, { type: "success" });
                this.state.newCategoryName = "";
                this.state.newCategoryCode = "";
                await this.loadCategoriesList();
                await this.fetchProducts();
            } else {
                this.notification.add((res && res.message) || "Error al crear categoría", { type: "danger" });
            }
        } catch (e) {
            console.error("Error creating category:", e);
            this.notification.add("Error de conexión al crear categoría", { type: "danger" });
        } finally {
            this.state.isSavingCategory = false;
        }
    }

    openOdooStockPickingView() {
        const compId = this.state.selectedDetailCompany ? this.state.selectedDetailCompany.id : false;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: `Recepciones y Descargas - ${this.state.selectedDetailCompany ? this.state.selectedDetailCompany.name : ''}`,
            res_model: "stock.picking",
            views: [[false, "list"], [false, "form"]],
            domain: compId ? [["company_id", "=", compId]] : [],
            context: {
                default_company_id: compId,
            },
            target: "current"
        });
    }

    // ==================== GESTIÓN DE TANQUES Y AFOROS ====================
    openAdjustTankModal(tank) {
        this.state.selectedAdjustTank = tank;
        this.state.adjustTankLiters = tank.current_liters || 0;
        this.state.adjustTankReason = "Aforo físico periódico";
        this.state.isAdjustTankModalOpen = true;
    }

    closeAdjustTankModal() {
        this.state.isAdjustTankModalOpen = false;
        this.state.selectedAdjustTank = null;
    }

    async saveTankAdjustment() {
        if (!this.state.selectedAdjustTank) return;
        this.state.isSavingTankAdjust = true;
        try {
            const res = await jsonrpc("/pos_gas_station/adjust_tank_stock", {
                location_id: this.state.selectedAdjustTank.id,
                new_liters: this.state.adjustTankLiters,
                reason: this.state.adjustTankReason,
            });
            if (res && res.status === "success") {
                this.notification.add(res.message, { type: "success" });
                this.state.selectedAdjustTank.current_liters = res.new_liters;
                if (this.state.selectedAdjustTank.capacity_liters > 0) {
                    this.state.selectedAdjustTank.fill_pct = Math.min(100.0, Math.max(0.0, Math.round((res.new_liters / this.state.selectedAdjustTank.capacity_liters) * 1000) / 10));
                    this.state.selectedAdjustTank.status = this.state.selectedAdjustTank.fill_pct < 15 ? 'Nivel crítico' : (this.state.selectedAdjustTank.fill_pct < 30 ? 'Nivel bajo' : 'Operativo');
                }
                this.closeAdjustTankModal();
            } else {
                this.notification.add((res && res.message) || "Error al ajustar nivel", { type: "danger" });
            }
        } catch (e) {
            console.error("Error adjusting tank:", e);
            this.notification.add("Error de conexión al ajustar nivel de tanque", { type: "danger" });
        } finally {
            this.state.isSavingTankAdjust = false;
        }
    }

    openNewTankModal() {
        const whs = (this.state.companyDetailData && this.state.companyDetailData.inventory && this.state.companyDetailData.inventory.warehouses) || [];
        this.state.newTankName = "";
        this.state.newTankFuelCode = "GA";
        this.state.newTankCapacity = 30000;
        this.state.newTankInitialLiters = 0;
        this.state.newTankWarehouseId = whs.length ? whs[0].id : null;
        this.state.isNewTankModalOpen = true;
    }

    closeNewTankModal() {
        this.state.isNewTankModalOpen = false;
        this.state.newTankName = "";
    }

    async saveNewTank() {
        if (!this.state.newTankName || !this.state.newTankName.trim()) {
            this.notification.add("Debe introducir un nombre para el tanque.", { type: "warning" });
            return;
        }
        const companyId = this.state.selectedDetailCompany ? this.state.selectedDetailCompany.id : null;
        if (!companyId) return;

        this.state.isSavingNewTank = true;
        try {
            const res = await jsonrpc("/pos_gas_station/create_tank", {
                company_id: companyId,
                warehouse_id: this.state.newTankWarehouseId,
                name: this.state.newTankName.trim(),
                fuel_code: this.state.newTankFuelCode,
                capacity_liters: parseFloat(this.state.newTankCapacity) || 30000,
                initial_liters: parseFloat(this.state.newTankInitialLiters) || 0,
            });
            if (res && res.status === "success") {
                this.notification.add(res.message, { type: "success" });
                this.closeNewTankModal();
                await this.loadCompanyDetailData(companyId);
            } else {
                this.notification.add((res && res.message) || "Error al crear tanque", { type: "danger" });
            }
        } catch (e) {
            console.error("Error creating tank:", e);
            this.notification.add("Error de conexión al crear tanque", { type: "danger" });
        } finally {
            this.state.isSavingNewTank = false;
        }
    }

    async deleteTank(tank) {
        if (!tank) return;
        if (!confirm(`¿Está seguro de que desea eliminar el tanque "${tank.name}"? Esta acción no se puede deshacer.`)) {
            return;
        }
        const companyId = this.state.selectedDetailCompany ? this.state.selectedDetailCompany.id : null;
        try {
            const res = await jsonrpc("/pos_gas_station/delete_tank", {
                tank_id: tank.id
            });
            if (res && res.status === "success") {
                this.notification.add(res.message, { type: "success" });
                if (companyId) {
                    await this.loadCompanyDetailData(companyId);
                }
            } else {
                this.notification.add((res && res.message) || "Error al eliminar tanque", { type: "danger" });
            }
        } catch (e) {
            console.error("Error deleting tank:", e);
            this.notification.add("Error de conexión al eliminar tanque", { type: "danger" });
        }
    }

    async switchDashboardCompany(companyId) {
        try {
            const res = await jsonrpc("/pos_gas_station/switch_dashboard_company", {
                company_id: companyId
            });
            if (res.status === "success") {
                this.notification.add("Empresa activa: " + (res.company_name || ""), { type: "success" });
                await this.loadDashboardData();
                window.dispatchEvent(new CustomEvent("admin-company-changed", {
                    detail: { companyId: companyId, companyName: res.company_name }
                }));
            } else {
                this.notification.add(res.message || "No se pudo cambiar de empresa", { type: "danger" });
            }
        } catch (e) {
            console.error("Error switching dashboard company:", e);
        }
    }

    openVpnCompanyAdmins() {
        this.actionService.doAction("pos_gas_station.action_vpn_company_admins");
    }
}

registry.category("actions").add("gas_station_dashboard", GasStationDashboard);
