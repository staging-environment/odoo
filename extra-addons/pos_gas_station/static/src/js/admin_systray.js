/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
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
        const initialCompanyId = this.companyService?.currentCompany?.id || null;

        this.state = useState({
            adminName: this.user.name || "Administrador",
            vpnIp: "",
            companyName: initialCompany,
            companyId: initialCompanyId,
            companies: [],
            loading: true,
        });

        this.handleCompanyChange = (ev) => {
            if (ev.detail) {
                if (ev.detail.companyName) {
                    this.state.companyName = ev.detail.companyName;
                }
                if (ev.detail.companyId) {
                    this.state.companyId = parseInt(ev.detail.companyId);
                }
            }
        };
        window.addEventListener("admin-company-changed", this.handleCompanyChange);

        onMounted(() => {
            this.loadAdminInfo();
        });

        onWillUnmount(() => {
            window.removeEventListener("admin-company-changed", this.handleCompanyChange);
        });
    }

    async loadAdminInfo() {
        try {
            const data = await jsonrpc("/pos_gas_station/admin_current_info", {});
            if (data && data.status === "success") {
                this.state.adminName = data.admin_name || this.user.name;
                this.state.vpnIp = data.vpn_ip || "";
                this.state.companyName = data.company_name || this.state.companyName;
                this.state.companyId = data.company_id || this.state.companyId;
                this.state.companies = data.companies || [];
            }
        } catch (e) {
            console.warn("Could not load VPN admin info for systray:", e);
        } finally {
            this.state.loading = false;
        }
    }

    async onSwitchCompany(newCompanyId) {
        const cid = parseInt(newCompanyId);
        if (!cid || cid === this.state.companyId) {
            return;
        }
        try {
            const res = await jsonrpc("/pos_gas_station/switch_dashboard_company", {
                company_id: cid,
            });
            if (res && res.status === "success") {
                this.state.companyId = cid;
                this.state.companyName = res.company_name || "";

                // Cambiar de empresa en toda la aplicación Odoo actualizando cids en URL
                const url = new URL(window.location.href);
                url.searchParams.set("cids", String(cid));
                if (url.hash) {
                    url.hash = url.hash.replace(/cids=[^&]*/g, `cids=${cid}`);
                    if (!url.hash.includes("cids=")) {
                        url.hash += `&cids=${cid}`;
                    }
                }
                window.location.href = url.toString();
            }
        } catch (e) {
            console.error("Error switching company from navbar:", e);
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
