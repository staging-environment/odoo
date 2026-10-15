/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { useService } from "@web/core/utils/hooks";

export class GasStationDashboard extends Component {
    static template = "pos_gas_station.GasStationDashboard";

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            isManager: false,
            userName: "",
            companies: [],
            stats: {
                total_companies: 0,
                total_stations: 0,
                total_open_sessions: 0
            }
        });

        onMounted(() => {
            this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        this.state.loading = true;
        try {
            const data = await jsonrpc("/pos_gas_station/dashboard_data", {});
            if (data.status === "success") {
                this.state.companies = data.companies;
                this.state.isManager = data.is_manager;
                this.state.userName = data.user_name;
                this.state.stats = data.stats;
            }
        } catch (e) {
            console.error("Error loading gas station dashboard:", e);
            this.notification.add("Error al cargar estaciones y empresas", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    openStation(stationId) {
        window.location.href = `/pos/ui?config_id=${stationId}`;
    }

    openCompany(companyId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "res.company",
            res_id: companyId,
            views: [[false, "form"]],
            target: "current"
        });
    }

    openNewCompany() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "res.company",
            views: [[false, "form"]],
            target: "new"
        });
    }

    openMatrix() {
        this.actionService.doAction("pos_gas_station.action_utrecar_permission_matrix");
    }

    openOrders(stationId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Pedidos del TPV",
            res_model: "pos.order",
            domain: [["config_id", "=", stationId]],
            views: [[false, "tree"], [false, "form"]],
            target: "current"
        });
    }

    openConfig(stationId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Ajustes del Punto de Venta",
            res_model: "pos.config",
            res_id: stationId,
            views: [[false, "form"]],
            target: "current"
        });
    }
}

registry.category("actions").add("gas_station_dashboard", GasStationDashboard);