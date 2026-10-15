/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { useService } from "@web/core/utils/hooks";

const MATRIX_STYLES = 
/* ULTRA-COMPACT STYLES AND FORCED SCROLL */
.o_content:has(.utrecar-matrix-wrapper),
.o_client_action:has(.utrecar-matrix-wrapper),
.o_action_manager:has(.utrecar-matrix-wrapper) {
    height: 100% !important;
    max-height: 100% !important;
    overflow: hidden !important;
    display: flex !important;
    flex-direction: column !important;
}

.utrecar-matrix-wrapper {
    background: #f8fafc !important;
    height: 100% !important;
    max-height: 100% !important;
    min-height: 0 !important;
    width: 100% !important;
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
    position: relative !important;
    box-sizing: border-box !important;
}

.matrix-topbar {
    flex: 0 0 auto !important;
    background: #ffffff !important;
    padding: 6px 16px !important;
    border-bottom: 1px solid #e2e8f0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
    z-index: 20 !important;
}

.matrix-main-title {
    margin: 0 !important;
    font-size: 14px !important;
    font-weight: 800 !important;
    color: #0f172a !important;
    line-height: 1.1 !important;
}

.matrix-subtitle {
    font-size: 10px !important;
    color: #64748b !important;
}

.matrix-search-input {
    padding: 2px 20px 2px 24px !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 4px !important;
    font-size: 11px !important;
    width: 190px !important;
    height: 26px !important;
}

.btn-matrix-action {
    background: #0f172a !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 4px !important;
    padding: 3px 9px !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    height: 26px !important;
    cursor: pointer !important;
}

.matrix-table-container {
    flex: 1 1 auto !important;
    min-height: 0 !important;
    height: calc(100vh - 86px) !important;
    max-height: calc(100vh - 86px) !important;
    overflow-y: scroll !important;
    overflow-x: auto !important;
    padding: 4px 10px 50px 10px !important;
    -webkit-overflow-scrolling: touch !important;
    box-sizing: border-box !important;
}

.matrix-table-container::-webkit-scrollbar {
    width: 8px !important;
    height: 8px !important;
}
.matrix-table-container::-webkit-scrollbar-track {
    background: #f1f5f9 !important;
}
.matrix-table-container::-webkit-scrollbar-thumb {
    background: #cbd5e1 !important;
    border-radius: 4px !important;
}

.utrecar-matrix-table {
    width: 100% !important;
    background: #ffffff !important;
    border-collapse: separate !important;
    border-spacing: 0 !important;
    border-radius: 5px !important;
    border: 1px solid #e2e8f0 !important;
    table-layout: fixed !important;
}

.header-roles-row th {
    background: #f8fafc !important;
    padding: 4px 6px !important;
    font-size: 10.5px !important;
    font-weight: 800 !important;
    color: #1e293b !important;
    border-bottom: 2px solid #cbd5e1 !important;
    text-align: center !important;
    position: sticky !important;
    top: 0 !important;
    z-index: 10 !important;
}

.category-header-row td,
.category-header-cell {
    background: #f1f5f9 !important;
    border-top: 1.5px solid #e2e8f0 !important;
    border-bottom: 1px solid #e2e8f0 !important;
    padding: 2px 10px !important;
    height: 20px !important;
    line-height: 1 !important;
}

.category-name {
    font-size: 10px !important;
    font-weight: 800 !important;
    color: #1e3a8a !important;
    text-transform: uppercase !important;
    line-height: 1 !important;
}

.permission-item-row {
    border-bottom: 1px solid #f1f5f9 !important;
    height: 22px !important;
    min-height: 22px !important;
    max-height: 24px !important;
}

.permission-name-cell {
    padding: 1px 10px !important;
    vertical-align: middle !important;
    height: 22px !important;
    border-bottom: 1px solid #f1f5f9 !important;
}

.perm-name-text {
    font-size: 10.5px !important;
    font-weight: 600 !important;
    color: #1e293b !important;
    line-height: 1.1 !important;
}

.perm-code-tag {
    font-family: monospace !important;
    font-size: 8px !important;
    background: #f1f5f9 !important;
    color: #64748b !important;
    padding: 0px 3px !important;
}

.checkbox-cell {
    text-align: center !important;
    vertical-align: middle !important;
    cursor: pointer !important;
    padding: 1px 0 !important;
    height: 22px !important;
    border-bottom: 1px solid #f1f5f9 !important;
}

.matrix-checkbox {
    width: 15px !important;
    height: 15px !important;
    margin: 0 auto !important;
    border-radius: 3px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}

.matrix-checkbox.is-checked {
    background: #ea580c !important;
    border: 1.5px solid #c2410c !important;
    color: #ffffff !important;
}

.matrix-checkbox.is-unchecked {
    background: #ffffff !important;
    border: 1.5px solid #cbd5e1 !important;
}

.check-icon {
    display: block !important;
    width: 10px !important;
    height: 10px !important;
}
;

function injectMatrixStyles() {
    const id =  utrecar-permission-matrix-dynamic-styles;
    let el = document.getElementById(id);
    if (!el) {
        el = document.createElement(style);
        el.id = id;
        document.head.appendChild(el);
    }
    el.textContent = MATRIX_STYLES;
}

export class UtrecarPermissionMatrix extends Component {
    static template = "pos_gas_station.UtrecarPermissionMatrix";

    setup() {
        injectMatrixStyles();
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            roles: [],
            categories: [],
            matrix: {},
            users: [],
            searchTerm: "",
            selectedCategoryFilter: "all",
            showUserAssignModal: false,
            assignModalRole: null,
            savingCell: null
        });

        onMounted(() => {
            injectMatrixStyles();
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

    get filteredCategories() {
        const query = (this.state.searchTerm || "").toLowerCase().trim();
        const catFilter = this.state.selectedCategoryFilter;

        return this.state.categories
            .filter(cat => catFilter === "all" || cat.id === parseInt(catFilter))
            .map(cat => {
                const perms = cat.permissions.filter(p => {
                    if (!query) return true;
                    return p.name.toLowerCase().includes(query) || (p.code && p.code.toLowerCase().includes(query));
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
}

registry.category("actions").add("utrecar_permission_matrix", UtrecarPermissionMatrix);
