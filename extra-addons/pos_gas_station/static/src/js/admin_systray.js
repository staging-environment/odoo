/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { jsonrpc } from "@web/core/network/rpc_service";

export class AdminSystrayMenu extends Component {
    static template = "pos_gas_station.AdminSystrayMenu";

    setup() {
        this.user = useService("user");
        this.state = useState({
            adminName: "",
            vpnIp: "",
            companyName: "",
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
                this.state.companyName = data.company_name || "";
            } else {
                this.state.adminName = this.user.name;
            }
        } catch (e) {
            this.state.adminName = this.user.name;
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

registry.category("systray").add("pos_gas_station.admin_systray", adminSystrayItem, { sequence: 10 });
