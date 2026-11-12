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

function updateNavActiveState(actionService = null) {
    let activeSection = "";

    // 1. Chequeo por controlador activo en actionService de Odoo
    if (actionService?.currentController?.action) {
        const tag = actionService.currentController.action.tag;
        if (tag === "employee_company_roles") {
            activeSection = "expendedores";
        } else if (tag === "vpn_company_admins") {
            activeSection = "administracion";
        } else if (tag === "gas_station_dashboard") {
            activeSection = "dashboard";
        }
    }

    // 2. Chequeo por elementos presentes en el DOM
    if (!activeSection) {
        if (document.querySelector(".emp-roles-page, .employee-company-roles-view, [data-page='employee_company_roles']")) {
            activeSection = "expendedores";
        } else if (document.querySelector(".vpn-admins-page, .vpn-admins-view, [data-page='vpn_company_admins']")) {
            activeSection = "administracion";
        } else if (document.querySelector(".gas-station-dashboard-wrapper, .gas-station-dashboard-page, [data-page='gas_station_dashboard']")) {
            activeSection = "dashboard";
        }
    }

    // 3. Chequeo por hash en URL de Odoo
    if (!activeSection) {
        const hash = window.location.hash || "";
        if (hash.includes("action_employee_company_roles") || hash.includes("employee_company_roles")) {
            activeSection = "expendedores";
        } else if (hash.includes("action_vpn_company_admins") || hash.includes("vpn_company_admins")) {
            activeSection = "administracion";
        } else {
            activeSection = "dashboard";
        }
    }

    if (document.body.dataset.activeNavSection !== activeSection) {
        document.body.dataset.activeNavSection = activeSection;
    }

    const brand = document.querySelector(".o_main_navbar .o_menu_brand");
    const parentToggle = document.querySelector('.o_main_navbar [data-menu-xmlid="pos_gas_station.menu_gas_station_staff_parent"]');
    const subExp = document.querySelector('[data-menu-xmlid="pos_gas_station.menu_gas_station_sub_employee_roles"]');
    const subAdm = document.querySelector('[data-menu-xmlid="pos_gas_station.menu_gas_station_sub_company_admins"]');

    if (brand) {
        brand.classList.toggle("o_nav_active", activeSection === "dashboard");
    }
    if (parentToggle) {
        parentToggle.classList.toggle("o_nav_active", activeSection === "expendedores" || activeSection === "administracion");
    }
    if (subExp) {
        subExp.classList.toggle("o_submenu_item_active", activeSection === "expendedores");
    }
    if (subAdm) {
        subAdm.classList.toggle("o_submenu_item_active", activeSection === "administracion");
    }
}

export class AdminSystrayMenu extends Component {
    static template = "pos_gas_station.AdminSystrayMenu";

    setup() {
        this.user = useService("user");
        this.companyService = useService("company");
        this.actionService = useService("action");
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

        this.handleNavUpdate = () => updateNavActiveState(this.actionService);
        this.navCheckInterval = setInterval(this.handleNavUpdate, 200);
        window.addEventListener("hashchange", this.handleNavUpdate);
        window.addEventListener("popstate", this.handleNavUpdate);
        if (this.env?.bus) {
            this.env.bus.addEventListener("ACTION_MANAGER:UPDATE", this.handleNavUpdate);
            this.env.bus.addEventListener("MENUS:APP-CHANGED", this.handleNavUpdate);
        }

        // Actualizar al hacer clic en cualquier parte del navbar o desplegables
        this.handleDocClick = () => {
            setTimeout(this.handleNavUpdate, 40);
        };
        document.addEventListener("click", this.handleDocClick);

        onMounted(() => {
            this.loadAdminInfo();
            updateNavActiveState(this.actionService);
        });

        onWillUnmount(() => {
            window.removeEventListener("admin-company-changed", this.handleCompanyChange);
            window.removeEventListener("hashchange", this.handleNavUpdate);
            window.removeEventListener("popstate", this.handleNavUpdate);
            document.removeEventListener("click", this.handleDocClick);
            if (this.env?.bus) {
                this.env.bus.removeEventListener("ACTION_MANAGER:UPDATE", this.handleNavUpdate);
                this.env.bus.removeEventListener("MENUS:APP-CHANGED", this.handleNavUpdate);
            }
            if (this.navCheckInterval) {
                clearInterval(this.navCheckInterval);
            }
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
