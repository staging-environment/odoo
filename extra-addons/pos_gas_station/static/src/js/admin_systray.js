/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { jsonrpc } from "@web/core/network/rpc_service";

const systrayRegistry = registry.category("systray");

// Eliminar sistemáticamente los elementos no deseados de la barra superior (Chat, Actividades, Menús por defecto)
const itemsToRemove = [
    "mail.messaging_menu",
    "mail.activity_menu",
    "discuss.CallMenu",
    "SwitchCompanyMenu",
    "web.user_menu",
    "AccountSystrayItem",
];

for (const key of itemsToRemove) {
    if (systrayRegistry.contains(key)) {
        systrayRegistry.remove(key);
    }
}

export class AdminSystrayMenu extends Component {
    static template = "pos_gas_station.AdminSystrayMenu";

    setup() {
        this.user = useService("user");
        this.companyService = useService("company");
        const initialCompany = this.companyService?.currentCompany?.name || "";

        this.state = useState({
            adminName: this.user.name || "Administrador",
            vpnIp: "",
            companyName: initialCompany,
            loading: true,
        });

        onMounted(() => {
            this.loadAdminInfo();
        });
    }

    async loadAdminInfo() {
        try {
            const data = await jsonrpc("/pos_gas_station/admin_current_info", {});
            if (data && data.status === "success") {
                this.state.adminName = data.admin_name || this.user.name;
                this.state.vpnIp = data.vpn_ip || "";
                this.state.companyName = data.company_name || this.state.companyName;
            }
        } catch (e) {
            console.warn("Could not load VPN admin info for systray:", e);
        } finally {
            this.state.loading = false;
        }
    }

    onLogout() {
        window.location.href = "/pos_gas_station/admin_logout";
    }
}

export const adminSystrayItem = {
    Component: AdminSystrayMenu,
};

registry.category("systray").add("pos_gas_station.admin_systray", adminSystrayItem, { sequence: 0 });
