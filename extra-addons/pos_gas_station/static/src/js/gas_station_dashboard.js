/** @odoo-module **/

import { Component, useState, onMounted, onPatched } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";
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

// Botón 'Nueva Empresa' e icono 'Editar' en listado de empresas
patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => {
            this._setupCompanyObserver();
        });
        onPatched(() => {
            if (this.props.list && this.props.list.resModel === "res.company") {
                this._applyCompanyListViewCustom();
            }
        });
    },
    _setupCompanyObserver() {
        if (!this.props.list || this.props.list.resModel !== "res.company") {
            return;
        }
        this._applyCompanyListViewCustom();
        const root = this.rootRef && this.rootRef.el;
        if (root && !this._companyObserver) {
            this._companyObserver = new MutationObserver(() => {
                this._applyCompanyListViewCustom();
            });
            this._companyObserver.observe(root, { childList: true, subtree: true });
        }
    },
    _applyCompanyListViewCustom() {
        if (!this.props.list || this.props.list.resModel !== "res.company") {
            return;
        }
        const root = this.rootRef && this.rootRef.el;
        if (!root) {
            return;
        }
        const view = root.closest(".o_view_controller") || root.closest(".o_action_manager") || document.querySelector(".o_action_manager");
        if (view) {
            view.classList.add("o_company_list_view_custom");
        }
        const cp = (view && view.querySelector(".o_control_panel")) || document.querySelector(".o_control_panel");
        if (cp) {
            cp.classList.add("o_company_control_panel_custom");
        }

        // 1. Añadir columna e icono 'Editar' en cada fila
        const table = this.tableRef ? this.tableRef.el : root.querySelector("table");
        if (table) {
            const theadRow = table.querySelector("thead tr");
            if (theadRow && !theadRow.querySelector(".o_company_edit_th")) {
                const th = document.createElement("th");
                th.className = "o_company_edit_th text-center";
                th.style.width = "90px";
                th.innerText = "Acción";
                theadRow.appendChild(th);
            }

            const rows = table.querySelectorAll("tbody tr.o_data_row");
            rows.forEach((tr, index) => {
                if (!tr.querySelector(".o_company_edit_td")) {
                    const td = document.createElement("td");
                    td.className = "o_data_cell o_company_edit_td text-center align-middle";
                    td.innerHTML = '<button type="button" class="btn btn-sm btn-outline-primary o_company_edit_btn" title="Editar empresa"><i class="fa fa-pencil me-1"></i> Editar</button>';
                    const btn = td.querySelector("button");
                    btn.addEventListener("click", (e) => {
                        e.stopPropagation();
                        e.preventDefault();
                        const record = this.props.list.records && this.props.list.records[index];
                        if (record && this.props.openRecord) {
                            this.props.openRecord(record);
                        }
                    });
                    tr.appendChild(td);
                }
            });
        }

        // 2. Añadir botón Nueva Empresa debajo del listado
        let bar = root.querySelector(".o_company_list_bottom_bar");
        if (!bar) {
            bar = document.createElement("div");
            bar.className = "o_company_list_bottom_bar";
            bar.innerHTML = '<button type="button" class="btn btn-primary fw-bold px-3 py-2"><i class="fa fa-plus me-1"></i> Nueva Empresa</button>';
            const btn = bar.querySelector("button");
            btn.addEventListener("click", (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (this.props.onAdd) {
                    this.props.onAdd();
                }
            });
            root.appendChild(bar);
        }
    }
});
