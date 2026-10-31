/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { useService } from "@web/core/utils/hooks";

export class EmployeeCompanyRolesView extends Component {
    static template = "pos_gas_station.EmployeeCompanyRolesView";

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            users: [],
            companies: [],
            roles: [],
            stats: {
                total_users: 0,
                trieste_count: 0,
                utrecar_count: 0,
                multi_count: 0,
            },
            searchTerm: "",
            filterCompany: "all",
            filterRole: "all",
            updatingKey: null
        });

        onMounted(() => {
            this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const data = await jsonrpc("/pos_gas_station/employee_company_roles/data", {});
            if (data.status === "success") {
                this.state.users = data.users || [];
                this.state.companies = data.companies || [];
                this.state.roles = data.roles || [];
                this.state.stats = data.stats || this.state.stats;
            } else {
                this.notification.add("Error al cargar datos de personal", { type: "danger" });
            }
        } catch (e) {
            console.error("Error loading employee company roles:", e);
            this.notification.add("Error de conexión al cargar personal y roles", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    get filteredUsers() {
        let list = this.state.users || [];

        // Filtro por empresa
        if (this.state.filterCompany === "trieste") {
            list = list.filter(u => u.company_access && u.company_access[4] && u.company_access[4].active);
        } else if (this.state.filterCompany === "utrecar") {
            list = list.filter(u => u.company_access && u.company_access[1] && u.company_access[1].active);
        } else if (this.state.filterCompany === "multi") {
            list = list.filter(u => u.active_company_count > 1);
        } else if (this.state.filterCompany === "none") {
            list = list.filter(u => u.active_company_count === 0);
        }

        // Filtro por rol
        if (this.state.filterRole !== "all") {
            const targetRoleCode = this.state.filterRole.toLowerCase();
            list = list.filter(u => {
                if (!u.company_access) return false;
                return Object.values(u.company_access).some(acc => 
                    acc.active && (acc.role_code || "").toLowerCase() === targetRoleCode
                );
            });
        }

        // Búsqueda en tiempo real
        if (this.state.searchTerm) {
            const q = this.state.searchTerm.trim().toLowerCase();
            list = list.filter(u => {
                const nameMatch = (u.name || "").toLowerCase().includes(q);
                const emailMatch = (u.email || "").toLowerCase().includes(q);
                const dniMatch = (u.dni || "").toLowerCase().includes(q);
                const codeMatch = String(u.code || "").toLowerCase().includes(q);
                return nameMatch || emailMatch || dniMatch || codeMatch;
            });
        }

        return list;
    }

    async toggleCompanyAccess(user, companyId, currentActive) {
        const key = `${user.odoo_user_id}_${companyId}`;
        this.state.updatingKey = key;
        const nextActive = !currentActive;

        try {
            const res = await jsonrpc("/pos_gas_station/employee_company_roles/update", {
                user_id: user.odoo_user_id,
                company_id: companyId,
                active: nextActive
            });

            if (res.status === "success") {
                if (!user.company_access[companyId]) {
                    user.company_access[companyId] = {};
                }
                user.company_access[companyId].active = res.active;
                user.company_access[companyId].role_name = res.role_name;
                user.company_access[companyId].role_code = res.role_code;
                user.company_access[companyId].role_color = res.role_color;

                // Recalcular contador activo
                user.active_company_count = Object.values(user.company_access).filter(a => a.active).length;
                this.notification.add(res.message, { type: "success" });
            } else if (res.status === "warning") {
                this.notification.add(res.message, { type: "warning" });
            } else {
                this.notification.add(res.message || "Error al actualizar acceso", { type: "danger" });
            }
        } catch (e) {
            console.error("Error toggling access:", e);
            this.notification.add("Error de conexión al actualizar acceso", { type: "danger" });
        } finally {
            this.state.updatingKey = null;
        }
    }

    async changeCompanyRole(user, companyId, newRoleId) {
        const key = `${user.odoo_user_id}_${companyId}`;
        this.state.updatingKey = key;

        try {
            const res = await jsonrpc("/pos_gas_station/employee_company_roles/update", {
                user_id: user.odoo_user_id,
                company_id: companyId,
                role_id: newRoleId ? parseInt(newRoleId) : false
            });

            if (res.status === "success") {
                if (!user.company_access[companyId]) {
                    user.company_access[companyId] = {};
                }
                user.company_access[companyId].role_id = res.role_id;
                user.company_access[companyId].role_name = res.role_name;
                user.company_access[companyId].role_code = res.role_code;
                user.company_access[companyId].role_color = res.role_color;
                this.notification.add(
                    `Rol en ${res.company_id === 4 ? 'A.R. Trieste' : 'Utrecar'} actualizado a ${res.role_name} para ${user.name}`,
                    { type: "success" }
                );
            } else {
                this.notification.add(res.message || "Error al actualizar rol", { type: "danger" });
            }
        } catch (e) {
            console.error("Error changing company role:", e);
            this.notification.add("Error de conexión al actualizar rol", { type: "danger" });
        } finally {
            this.state.updatingKey = null;
        }
    }

    setCompanyFilter(filterVal) {
        this.state.filterCompany = filterVal;
    }

    setRoleFilter(roleVal) {
        this.state.filterRole = roleVal;
    }

    openDashboard() {
        this.actionService.doAction("pos_gas_station.action_gas_station_dashboard");
    }

    openMatrix() {
        this.actionService.doAction("pos_gas_station.action_utrecar_permission_matrix");
    }
}

registry.category("actions").add("employee_company_roles", EmployeeCompanyRolesView);
