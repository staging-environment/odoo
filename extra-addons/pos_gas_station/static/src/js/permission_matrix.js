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
            const data = await jsonrpc("/utrecar/permission_matrix/data", {});
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

        try {
            const res = await jsonrpc("/utrecar/permission_matrix/toggle", {
                role_id: roleId,
                permission_id: permId,
                granted: nextVal
            });
            if (res.status !== "success") {
                this.state.matrix[permId][roleId] = current;
                this.notification.add("No se pudo guardar el cambio", { type: "danger" });
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

    openUserAssign(role) {
        this.state.assignModalRole = role;
        this.state.showUserAssignModal = true;
    }

    closeUserAssign() {
        this.state.showUserAssignModal = false;
        this.state.assignModalRole = null;
    }

    async toggleUserRole(user, roleId) {
        const newRoleId = user.role_id === roleId ? false : roleId;
        try {
            await jsonrpc("/utrecar/permission_matrix/assign_user", {
                user_id: user.id,
                role_id: newRoleId
            });
            user.role_id = newRoleId;
            user.role_name = newRoleId ? this.state.roles.find(r => r.id === newRoleId)?.name : "Sin Rol";
            await this.loadMatrixData();
            this.notification.add(`Rol actualizado para ${user.name}`, { type: "success" });
        } catch (e) {
            console.error("Error asignando rol:", e);
            this.notification.add("Error al asignar rol", { type: "danger" });
        }
    }

    async toggleUserStation(user, stationId, ev) {
        if (ev) ev.stopPropagation();
        const currentList = Array.isArray(user.pos_config_ids) ? [...user.pos_config_ids] : [];
        const idx = currentList.indexOf(stationId);
        if (idx >= 0) {
            currentList.splice(idx, 1);
        } else {
            currentList.push(stationId);
        }

        try {
            await jsonrpc("/utrecar/permission_matrix/assign_user", {
                user_id: user.id,
                pos_config_ids: currentList
            });
            user.pos_config_ids = currentList;
            await this.loadMatrixData();
            this.notification.add(`Tiendas actualizadas para ${user.name}`, { type: "success" });
        } catch (e) {
            console.error("Error asignando tienda a usuario:", e);
            this.notification.add("Error al actualizar tiendas del usuario", { type: "danger" });
        }
    }
}

registry.category("actions").add("utrecar_permission_matrix", UtrecarPermissionMatrix);