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
            companies: [],
            stats: {
                total_companies: 0,
                total_stations: 0,
                total_open_sessions: 0
            },
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
            renameStationId: null,
            renameStationName: "",
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
                this.state.userName = data.user_name;
                this.state.stats = data.stats;
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
        this.state.showCreateCompanyModal = true;
    }

    closeCreateCompanyModal() {
        this.state.showCreateCompanyModal = false;
    }

    async submitCreateCompany() {
        const name = (this.state.newCompanyName || "").trim();
        if (!name) {
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
                this.notification.add(res.message || "Error al crear empresa", { type: "danger" });
            }
        } catch (e) {
            console.error("Error creating company:", e);
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
        this.state.showEditCompanyModal = true;
    }

    promptRenameCompany(comp) {
        this.promptEditCompany(comp);
    }

    closeEditCompanyModal() {
        this.state.showEditCompanyModal = false;
    }

    closeRenameCompanyModal() {
        this.closeEditCompanyModal();
    }

    async submitEditCompany() {
        const name = (this.state.editCompanyName || "").trim();
        if (!name) {
            this.notification.add("El nombre no puede estar vacío.", { type: "warning" });
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
            });
            if (res.status === "success") {
                this.notification.add(res.message, { type: "success" });
                this.closeEditCompanyModal();
                await this.loadDashboardData();
            } else {
                this.notification.add(res.message || "Error al actualizar empresa", { type: "danger" });
            }
        } catch (e) {
            console.error("Error updating company:", e);
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

    promptRenameStation(st) {
        this.state.renameStationId = st.id;
        this.state.renameStationName = st.name;
        this.state.showRenameStationModal = true;
    }

    closeRenameStationModal() {
        this.state.showRenameStationModal = false;
    }

    async submitRenameStation() {
        const name = (this.state.renameStationName || "").trim();
        if (!name) {
            this.notification.add("El nombre no puede estar vacío.", { type: "warning" });
            return;
        }
        this.state.actionLoading = true;
        try {
            const res = await jsonrpc("/pos_gas_station/rename_station", {
                config_id: this.state.renameStationId,
                name: name
            });
            if (res.status === "success") {
                this.notification.add(res.message, { type: "success" });
                this.closeRenameStationModal();
                await this.loadDashboardData();
            } else {
                this.notification.add(res.message || "Error al renombrar estación", { type: "danger" });
            }
        } catch (e) {
            console.error("Error renaming station:", e);
            this.notification.add("Error de conexión al renombrar estación", { type: "danger" });
        } finally {
            this.state.actionLoading = false;
        }
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
}

registry.category("actions").add("gas_station_dashboard", GasStationDashboard);
