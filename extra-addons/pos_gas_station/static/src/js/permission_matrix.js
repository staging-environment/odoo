/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { useService } from "@web/core/utils/hooks";

export class UtrecarPermissionMatrix extends Component {
    static template = "pos_gas_station.UtrecarPermissionMatrix";

    setup() {
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            roles: [],
            categories: [],
            matrix: {},
            users: [],
            companies: [],
            stations: [],
            selectedCompanyId: "all",
            selectedStationId: "all",
            searchTerm: "",
            selectedCategoryFilter: "all",
            showUserAssignModal: false,
            assignModalSearch: "",
            assignModalRole: null,
            savingCell: null
        });

        onMounted(() => {
            this.loadMatrixData();
        });
    }

    async loadMatrixData() {
        this.state.loading = true;
        try {
            const compParam = this.state.selectedCompanyId !== "all" ? parseInt(this.state.selectedCompanyId) : null;
            const data = await jsonrpc("/utrecar/permission_matrix/data", {
                company_id: compParam
            });
            if (data.status === "success") {
                this.state.roles = data.roles;
                this.state.categories = data.categories;
                this.state.matrix = data.matrix;
                this.state.users = data.users;
                this.state.companies = data.companies || [];
                this.state.stations = data.stations || [];
            }
        } catch (e) {
            console.error("Error cargando matriz de permisos:", e);
            this.notification.add("Error al conectar con la matriz de permisos", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async onCompanyChange() {
        await this.loadMatrixData();
        const comp = this.state.companies.find(c => String(c.id) === String(this.state.selectedCompanyId));
        const compName = comp ? comp.name : "Todas las Empresas (Base)";
        this.notification.add(`Cargando permisos para: ${compName}`, { type: "info" });
    }

    isPermissionGranted(permId, roleId) {
        if (!this.state.matrix[permId]) return false;
        return Boolean(this.state.matrix[permId][roleId]);
    }

    async togglePermission(permId, roleId) {
        const current = this.isPermissionGranted(permId, roleId);
        const nextVal = !current;

        // Optimistic UI update
        if (!this.state.matrix[permId]) {
            this.state.matrix[permId] = {};
        }
        this.state.matrix[permId][roleId] = nextVal;
        this.state.savingCell = `${permId}_${roleId}`;

        const compParam = this.state.selectedCompanyId !== "all" ? parseInt(this.state.selectedCompanyId) : null;

        try {
            const res = await jsonrpc("/utrecar/permission_matrix/toggle", {
                role_id: roleId,
                permission_id: permId,
                granted: nextVal,
                company_id: compParam
            });
            if (res.status !== "success") {
                this.state.matrix[permId][roleId] = current;
                this.notification.add("No se pudo guardar el cambio", { type: "danger" });
            } else {
                const comp = this.state.companies.find(c => String(c.id) === String(this.state.selectedCompanyId));
                if (comp) {
                    this.notification.add(`Permiso actualizado para la empresa: ${comp.name}`, { type: "success" });
                }
            }
        } catch (e) {
            this.state.matrix[permId][roleId] = current;
            console.error("Error al actualizar permiso:", e);
            this.notification.add("Error de conexión al guardar", { type: "danger" });
        } finally {
            this.state.savingCell = null;
        }
    }

    get filteredStations() {
        if (this.state.selectedCompanyId === "all") {
            return this.state.stations;
        }
        const compId = parseInt(this.state.selectedCompanyId);
        return this.state.stations.filter(st => {
            return !st.company_id || st.company_id[0] === compId;
        });
    }

    get filteredCategories() {
        const query = (this.state.searchTerm || "").toLowerCase().trim();
        const catFilter = this.state.selectedCategoryFilter;

        return this.state.categories
            .filter(cat => catFilter === "all" || cat.id === parseInt(catFilter))
            .map(cat => {
                const perms = cat.permissions.filter(p => {
                    if (!query) return true;
                    return p.name.toLowerCase().includes(query);
                });
                return { ...cat, permissions: perms };
            })
            .filter(cat => cat.permissions.length > 0);
    }

    get filteredAssignUsers() {
        if (!this.state.assignModalSearch) {
            return this.state.users;
        }
        const term = this.state.assignModalSearch.toLowerCase().trim();
        return this.state.users.filter(u => 
            (u.name || "").toLowerCase().includes(term) || 
            (u.login || "").toLowerCase().includes(term)
        );
    }

    userHasModalRole(user) {
        if (!this.state.assignModalRole) return false;
        const targetId = this.state.assignModalRole.id;
        const roleIds = Array.isArray(user.role_ids) ? user.role_ids : (user.role_id ? [user.role_id] : []);
        return roleIds.includes(targetId);
    }

    openUserAssign(role) {
        this.state.assignModalRole = role;
        this.state.assignModalSearch = "";
        this.state.showUserAssignModal = true;
    }

    closeUserAssign() {
        this.state.showUserAssignModal = false;
        this.state.assignModalRole = null;
        this.state.assignModalSearch = "";
    }

    async toggleUserRole(user, roleId) {
        const hasRole = this.userHasModalRole(user);
        const action = hasRole ? "remove" : "add";

        try {
            const res = await jsonrpc("/utrecar/permission_matrix/assign_user", {
                user_id: user.id,
                role_id: roleId,
                action: action
            });
            if (res.status === "success") {
                user.role_ids = res.role_ids;
                user.role_names = res.role_names;
                await this.loadMatrixData();
                const roleName = this.state.roles.find(r => r.id === roleId)?.name || "Rol";
                this.notification.add(
                    action === "add" ? `Rol ${roleName} añadido a ${user.name}` : `Rol ${roleName} retirado de ${user.name}`,
                    { type: "success" }
                );
            }
        } catch (e) {
            console.error("Error asignando rol:", e);
            this.notification.add("Error al modificar rol del usuario", { type: "danger" });
        }
    }
}

registry.category("actions").add("utrecar_permission_matrix", UtrecarPermissionMatrix);
