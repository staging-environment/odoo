/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { useService } from "@web/core/utils/hooks";

export class VpnCompanyAdminsView extends Component {
    static template = "pos_gas_station.VpnCompanyAdminsView";

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            admins: [],
            companies: [],
            users: [],
            stats: {
                total_admins: 0,
                active_admins: 0,
                can_manage_staff_count: 0,
                company_counts: {},
            },
            searchTerm: "",
            filterCompany: "all",
            updatingKey: null,

            // Modal de Crear / Editar
            showModal: false,
            modalAdminId: null,
            modalName: "",
            modalVpnIp: "",
            modalUserId: "",
            modalCanManageStaff: false,
            modalActive: true,
            modalCompanyIds: [],
            modalNotes: "",
            modalLoading: false,
            modalError: null,
        });

        onMounted(() => {
            this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const data = await jsonrpc("/pos_gas_station/vpn_company_admins/data", {});
            if (data.status === "success") {
                this.state.admins = data.admins || [];
                this.state.companies = data.companies || [];
                this.state.users = data.users || [];
                this.state.stats = data.stats || this.state.stats;
            } else {
                this.notification.add(data.message || "Error al cargar administradores VPN", { type: "danger" });
            }
        } catch (e) {
            console.error("Error loading VPN company admins:", e);
            this.notification.add("Error de conexión al cargar administradores VPN", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    get filteredAdmins() {
        let list = this.state.admins || [];

        // Filtro por empresa
        if (this.state.filterCompany !== "all") {
            const cid = parseInt(this.state.filterCompany);
            if (!isNaN(cid)) {
                list = list.filter(a => a.company_ids && a.company_ids.includes(cid));
            } else if (this.state.filterCompany === "staff") {
                list = list.filter(a => a.can_manage_staff);
            }
        }

        // Búsqueda en tiempo real
        if (this.state.searchTerm) {
            const q = this.state.searchTerm.trim().toLowerCase();
            list = list.filter(a => {
                const nameMatch = (a.name || "").toLowerCase().includes(q);
                const ipMatch = (a.vpn_ip || "").toLowerCase().includes(q);
                const userMatch = (a.user_name || "").toLowerCase().includes(q) || (a.user_login || "").toLowerCase().includes(q);
                return nameMatch || ipMatch || userMatch;
            });
        }

        return list;
    }

    async toggleCompany(admin, companyId, isAssigned) {
        const key = `comp_${admin.id}_${companyId}`;
        this.state.updatingKey = key;
        const nextEnable = !isAssigned;

        try {
            const res = await jsonrpc("/pos_gas_station/vpn_company_admins/toggle_company", {
                admin_id: admin.id,
                company_id: companyId,
                enable: nextEnable
            });

            if (res.status === "success") {
                admin.company_ids = res.company_ids;
                this._recomputeStats();
                this.notification.add(res.message, { type: "success" });
            } else {
                this.notification.add(res.message || "Error al actualizar asignación", { type: "danger" });
            }
        } catch (e) {
            console.error("Error toggling company admin:", e);
            this.notification.add("Error de conexión al actualizar", { type: "danger" });
        } finally {
            this.state.updatingKey = null;
        }
    }

    async toggleField(admin, field, currentValue) {
        const key = `${field}_${admin.id}`;
        this.state.updatingKey = key;
        const nextVal = !currentValue;

        try {
            const res = await jsonrpc("/pos_gas_station/vpn_company_admins/toggle_field", {
                admin_id: admin.id,
                field: field,
                value: nextVal
            });

            if (res.status === "success") {
                admin[field] = res.value;
                this._recomputeStats();
                this.notification.add(res.message, { type: "success" });
            } else {
                this.notification.add(res.message || "Error al actualizar", { type: "danger" });
            }
        } catch (e) {
            console.error(`Error toggling ${field}:`, e);
            this.notification.add("Error de conexión al actualizar", { type: "danger" });
        } finally {
            this.state.updatingKey = null;
        }
    }

    _recomputeStats() {
        const company_counts = {};
        for (const c of this.state.companies || []) {
            company_counts[c.id] = 0;
        }
        let activeCount = 0;
        let manageStaffCount = 0;

        for (const a of this.state.admins || []) {
            if (a.active) {
                activeCount++;
                if (a.can_manage_staff) manageStaffCount++;
                for (const cid of (a.company_ids || [])) {
                    company_counts[cid] = (company_counts[cid] || 0) + 1;
                }
            }
        }

        this.state.stats = {
            total_admins: (this.state.admins || []).length,
            active_admins: activeCount,
            can_manage_staff_count: manageStaffCount,
            company_counts: company_counts,
        };
    }

    setFilter(filterVal) {
        this.state.filterCompany = filterVal;
    }

    openNewAdminModal() {
        this.state.modalAdminId = null;
        this.state.modalName = "";
        this.state.modalVpnIp = "";
        this.state.modalUserId = "";
        this.state.modalCanManageStaff = false;
        this.state.modalActive = true;
        this.state.modalCompanyIds = [];
        this.state.modalNotes = "";
        this.state.modalError = null;
        this.state.showModal = true;
    }

    editAdmin(admin) {
        this.state.modalAdminId = admin.id;
        this.state.modalName = admin.name || "";
        this.state.modalVpnIp = admin.vpn_ip || "";
        this.state.modalUserId = admin.user_id ? String(admin.user_id) : "";
        this.state.modalCanManageStaff = Boolean(admin.can_manage_staff);
        this.state.modalActive = Boolean(admin.active);
        this.state.modalCompanyIds = [...(admin.company_ids || [])];
        this.state.modalNotes = admin.notes || "";
        this.state.modalError = null;
        this.state.showModal = true;
    }

    closeModal() {
        this.state.showModal = false;
        this.state.modalError = null;
    }

    toggleModalCompany(companyId) {
        const idx = this.state.modalCompanyIds.indexOf(companyId);
        if (idx >= 0) {
            this.state.modalCompanyIds.splice(idx, 1);
        } else {
            this.state.modalCompanyIds.push(companyId);
        }
    }

    async saveModalAdmin() {
        this.state.modalError = null;
        const name = (this.state.modalName || "").trim();
        const vpnIp = (this.state.modalVpnIp || "").trim();

        if (!name) {
            this.state.modalError = "El nombre o persona física es obligatorio.";
            return;
        }
        if (!vpnIp) {
            this.state.modalError = "La IP de VPN WireGuard es obligatoria (ej: 10.8.0.2).";
            return;
        }

        this.state.modalLoading = true;
        try {
            const res = await jsonrpc("/pos_gas_station/vpn_company_admins/save_admin", {
                admin_id: this.state.modalAdminId,
                name: name,
                vpn_ip: vpnIp,
                user_id: this.state.modalUserId ? parseInt(this.state.modalUserId) : null,
                can_manage_staff: this.state.modalCanManageStaff,
                active: this.state.modalActive,
                company_ids: this.state.modalCompanyIds,
                notes: this.state.modalNotes,
            });

            if (res.status === "success") {
                this.notification.add(res.message, { type: "success" });
                this.closeModal();
                await this.loadData();
            } else {
                this.state.modalError = res.message || "Error al guardar administrador";
            }
        } catch (e) {
            console.error("Error saving VPN admin:", e);
            this.state.modalError = "Error de comunicación con el servidor.";
        } finally {
            this.state.modalLoading = false;
        }
    }

    openDashboard() {
        this.actionService.doAction("pos_gas_station.action_gas_station_dashboard");
    }

    openEmployeeCompanyRoles() {
        this.actionService.doAction("pos_gas_station.action_employee_company_roles");
    }
}

registry.category("actions").add("vpn_company_admins", VpnCompanyAdminsView);

