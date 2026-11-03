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
                none_count: 0,
            },
            searchTerm: "",
            filterCompany: "all",
            updatingKey: null,
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
            this.notification.add("Error de conexión al cargar personal", { type: "danger" });
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
        } else if (typeof this.state.filterCompany === "number") {
            const cid = this.state.filterCompany;
            list = list.filter(u => u.company_access && u.company_access[cid] && u.company_access[cid].active);
        } else if (this.state.filterCompany === "multi") {
            list = list.filter(u => u.active_company_count > 1);
        } else if (this.state.filterCompany === "none") {
            list = list.filter(u => u.active_company_count === 0);
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

                // Recalcular contador activo del usuario
                user.active_company_count = Object.values(user.company_access).filter(a => a.active).length;

                // Recalcular estadísticas globales
                this._recomputeStats();

                this.notification.add(res.message, { type: "success" });
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

    _recomputeStats() {
        const company_counts = {};
        for (const c of this.state.companies || []) {
            company_counts[c.id] = 0;
        }
        let multi = 0;
        let none = 0;

        for (const u of this.state.users || []) {
            let activeCount = 0;
            for (const c of this.state.companies || []) {
                if (u.company_access && u.company_access[c.id] && u.company_access[c.id].active) {
                    company_counts[c.id] = (company_counts[c.id] || 0) + 1;
                    activeCount++;
                }
            }
            if (activeCount > 1) multi++;
            if (activeCount === 0) none++;
        }

        this.state.stats = {
            total_users: (this.state.users || []).length,
            company_counts: company_counts,
            trieste_count: company_counts[4] || 0,
            utrecar_count: company_counts[1] || 0,
            multi_count: multi,
            none_count: none,
        };
    }

    setCompanyFilter(filterVal) {
        this.state.filterCompany = filterVal;
    }

    openDashboard() {
        this.actionService.doAction("pos_gas_station.action_gas_station_dashboard");
    }
}

registry.category("actions").add("employee_company_roles", EmployeeCompanyRolesView);
