/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

export class GasStationDashboard extends Component {
    static template = "pos_gas_station.GasStationDashboard";

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
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

    async openStation(stationId) {
        this.state.loading = true;
        try {
            const res = await jsonrpc("/pos_gas_station/open_station", {
                config_id: stationId
            });
            if (res.status === "success" && res.url) {
                window.location.href = res.url;
            } else {
                this.state.loading = false;
                this.notification.add(res.message || "No se pudo abrir la sesión del punto de venta", { type: "danger" });
            }
        } catch (e) {
            this.state.loading = false;
            console.error("Error opening station:", e);
            this.notification.add("Error de conexión al abrir el punto de venta", { type: "danger" });
        }
    }

    openCompany(companyId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Ficha de Empresa",
            res_model: "res.company",
            res_id: companyId,
            views: [[false, "form"]],
            target: "current",
            context: { create: false }
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

    async deleteStation(st) {
        this.dialog.add(ConfirmationDialog, {
            title: "Eliminar Estación de Servicio",
            body: `¿Está seguro de que desea eliminar la estación "${st.name}"? Esta acción no se puede deshacer.`,
            confirm: async () => {
                this.state.loading = true;
                try {
                    const res = await jsonrpc("/pos_gas_station/delete_station", { config_id: st.id });
                    if (res.status === "success") {
                        this.notification.add(res.message, { type: "success" });
                        await this.loadDashboardData();
                    } else {
                        this.state.loading = false;
                        this.dialog.add(ConfirmationDialog, {
                            title: "No se puede eliminar la estación",
                            body: res.message || "No se puede eliminar la estación porque contiene registros de ventas o facturación.",
                            confirmLabel: "Entendido",
                            cancel: () => {},
                        });
                    }
                } catch (e) {
                    this.state.loading = false;
                    console.error("Error deleting station:", e);
                    this.notification.add("Error al comunicarse con el servidor al eliminar la estación.", { type: "danger" });
                }
            },
            cancel: () => {},
        });
    }

    async deleteCompany(comp) {
        this.dialog.add(ConfirmationDialog, {
            title: "Eliminar Empresa",
            body: `¿Está seguro de que desea eliminar la empresa "${comp.name}"? Esta acción no se puede deshacer.`,
            confirm: async () => {
                this.state.loading = true;
                try {
                    const res = await jsonrpc("/pos_gas_station/delete_company", { company_id: comp.id });
                    if (res.status === "success") {
                        this.notification.add(res.message, { type: "success" });
                        await this.loadDashboardData();
                    } else {
                        this.state.loading = false;
                        this.dialog.add(ConfirmationDialog, {
                            title: "No se puede eliminar la empresa",
                            body: res.message || "No se puede eliminar la empresa.",
                            confirmLabel: "Entendido",
                            cancel: () => {},
                        });
                    }
                } catch (e) {
                    this.state.loading = false;
                    console.error("Error deleting company:", e);
                    this.notification.add("Error al comunicarse con el servidor al eliminar la empresa.", { type: "danger" });
                }
            },
            cancel: () => {},
        });
    }

    openNewStation(companyId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Nueva Estación de Servicio",
            res_model: "pos.config",
            views: [[false, "form"]],
            context: { default_company_id: companyId },
            target: "current"
        });
    }
}

registry.category("actions").add("gas_station_dashboard", GasStationDashboard);
