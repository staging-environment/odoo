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
            customerFilterType: "all",
            customerPage: 1,
            customerPageSize: 30,
            customerTotalCount: 0,
            customerSortField: "name",
            customerSortDir: "asc",
            customerLoading: false,
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
        this.state.customerFilterType = "all";
        this.state.customerPage = 1;
        this.state.customerTotalCount = 0;
        this.state.customerSortField = "name";
        this.state.customerSortDir = "asc";
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
        this.loadDashboardData();
    }

    setDetailTab(tab) {
        this.state.detailTab = tab;
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
