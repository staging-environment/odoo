/** @odoo-module **/

import { Component, useState, onMounted, onPatched } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";
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

    async openStation(stationId) {
        this.state.loading = true;
        try {
            const res = await jsonrpc("/pos_gas_station/open_station", {
                config_id: stationId
            });
            if (res.status === "success" && res.url) {
                window.location.href = res.url;
            } else {
                this.state.loading = false;
                this.notification.add(res.message || "No se pudo abrir la sesión del punto de venta", { type: "danger" });
            }
        } catch (e) {
            this.state.loading = false;
            console.error("Error opening station:", e);
            this.notification.add("Error de conexión al abrir el punto de venta", { type: "danger" });
        }
    }

    selectEmployeeForStation(stationId) {
        window.location.href = `/pos_gas_station/select_employee?station_id=${stationId}`;
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
                const codeMatch = String(e.code || "").toLowerCase().includes(q);
                return nameMatch || dniMatch || codeMatch;
            });
        }
        return list;
    }

    async toggleCompanyAccess(emp, compId, assigned) {
        this.state.updatingUserId = emp.odoo_user_id;
        try {
            const res = await jsonrpc("/pos_gas_station/toggle_employee_company_access", {
                user_id: emp.odoo_user_id,
                company_id: compId,
                assigned: assigned
            });
            if (res.status === "success") {
                emp.company_ids = res.company_ids;
                this.notification.add(res.message, { type: "success" });
            } else if (res.status === "warning") {
                this.notification.add(res.message, { type: "warning" });
                emp.company_ids = res.company_ids || emp.company_ids;
            } else {
                this.notification.add(res.message || "Error al actualizar permisos", { type: "danger" });
            }
        } catch (e) {
            console.error("Error toggling company access:", e);
            this.notification.add("Error de conexión al actualizar permisos", { type: "danger" });
        } finally {
            this.state.updatingUserId = null;
        }
    }

        async changeEmployeeRole(emp, newRoleId) {
        this.state.updatingUserId = emp.odoo_user_id;
        try {
            const roleIdInt = newRoleId ? parseInt(newRoleId) : false;
            const res = await jsonrpc("/utrecar/permission_matrix/assign_user", {
                user_id: emp.odoo_user_id,
                role_id: roleIdInt
            });
            if (res.status === "success") {
                emp.role_id = roleIdInt;
                const found = (this.state.allRoles || []).find(r => r.id === roleIdInt);
                emp.role_name = found ? found.name : "Sin Rol";
                emp.is_employee = emp.role_name === "EMPLEADO";
                this.notification.add(`Rol actualizado a ${emp.role_name} para ${emp.name}`, { type: "success" });
            } else {
                this.notification.add(res.message || "Error al actualizar rol", { type: "danger" });
            }
        } catch (e) {
            console.error("Error cambiando rol de empleado:", e);
            this.notification.add("Error de conexión al cambiar rol", { type: "danger" });
        } finally {
            this.state.updatingUserId = null;
        }
    }

    openCompany(companyId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Ficha de Empresa",
            res_model: "res.company",
            res_id: companyId,
            views: [[false, "form"]],
            target: "current",
            context: { create: false }
        });
    }

    openNewCompany() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "res.company",
            views: [[false, "form"]],
            target: "new"
        });
    }

    openEmployeeCompanyRoles() {
        this.actionService.doAction("pos_gas_station.action_employee_company_roles");
    }

    openMatrix() {
        this.actionService.doAction("pos_gas_station.action_utrecar_permission_matrix");
    }

    openVpnEmployees() {
        this.actionService.doAction("pos_gas_station.action_vpn_station_employees");
    }


    openConfig(stationId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Ajustes del Punto de Venta",
            res_model: "pos.config",
            res_id: stationId,
            views: [[false, "form"]],
            target: "current"
        });
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

    openNewStation(companyId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Nueva Estación de Servicio",
            res_model: "pos.config",
            views: [[false, "form"]],
            context: { default_company_id: companyId },
            target: "current"
        });
    }
}

registry.category("actions").add("gas_station_dashboard", GasStationDashboard);

// Botón 'Nueva Empresa' inmediatamente debajo del listado de empresas
patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => {
            this._applyCompanyListViewCustom();
        });
        onPatched(() => {
            this._applyCompanyListViewCustom();
        });
    },
    _applyCompanyListViewCustom() {
        if (!this.props.list || this.props.list.resModel !== "res.company") {
            return;
        }
        const root = this.rootRef && this.rootRef.el;
        if (!root) {
            return;
        }
        const view = root.closest(".o_view_controller") || root.closest(".o_action_manager") || document.querySelector(".o_action_manager");
        if (view) {
            view.classList.add("o_company_list_view_custom");
        }
        const cp = (view && view.querySelector(".o_control_panel")) || document.querySelector(".o_control_panel");
        if (cp) {
            cp.classList.add("o_company_control_panel_custom");
        }

        // Botón Nueva Empresa debajo del listado
        let bar = root.querySelector(".o_company_list_bottom_bar");
        if (!bar) {
            bar = document.createElement("div");
            bar.className = "o_company_list_bottom_bar";
            bar.innerHTML = '<button type="button" class="btn btn-primary fw-bold px-3 py-2"><i class="fa fa-plus me-1"></i> Nueva Empresa</button>';
            const btn = bar.querySelector("button");
            btn.addEventListener("click", (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (this.props.onAdd) {
                    this.props.onAdd();
                }
            });
            root.appendChild(bar);
        }
    }
});
