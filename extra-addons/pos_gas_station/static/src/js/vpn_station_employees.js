/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { useService } from "@web/core/utils/hooks";

export class VpnStationEmployeesView extends Component {
    static template = "pos_gas_station.VpnStationEmployeesView";

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            stations: [],
            stats: {
                total_stations: 0,
                total_employees: 0,
                active_controllers: 0
            },
            searchTerm: "",
            selectedStationId: "all"
        });

        onMounted(() => {
            this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const res = await jsonrpc("/pos_gas_station/vpn_employees_data", {});
            if (res.status === "success") {
                this.state.stations = res.stations;
                this.state.stats = res.stats;
            } else {
                this.notification.add("Error al cargar datos de empleados y estaciones", { type: "danger" });
            }
        } catch (e) {
            console.error("Error loading VPN station employees:", e);
            this.notification.add("Error de conexión al cargar empleados por VPN", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    get filteredStations() {
        let stations = this.state.stations;
        if (this.state.selectedStationId !== "all") {
            const targetId = parseInt(this.state.selectedStationId);
            stations = stations.filter(st => st.id === targetId);
        }

        const term = this.state.searchTerm.toLowerCase().trim();
        if (!term) {
            return stations;
        }

        return stations.map(st => {
            const stationMatches = st.name.toLowerCase().includes(term) ||
                                  st.vpn_ips_str.toLowerCase().includes(term) ||
                                  st.company_name.toLowerCase().includes(term);

            const filteredEmps = st.employees.filter(emp => {
                return (emp.full_name && emp.full_name.toLowerCase().includes(term)) ||
                       (emp.dni && emp.dni.toLowerCase().includes(term)) ||
                       (emp.email && emp.email.toLowerCase().includes(term)) ||
                       (emp.puesto && emp.puesto.toLowerCase().includes(term));
            });

            if (stationMatches) {
                return st;
            }

            return {
                ...st,
                employees: filteredEmps,
                employees_count: filteredEmps.length
            };
        }).filter(st => st.employees.length > 0 || st.name.toLowerCase().includes(term) || st.vpn_ips_str.toLowerCase().includes(term));
    }

    openStationConfig(stationId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "pos.config",
            res_id: stationId,
            views: [[false, "form"]],
            target: "current"
        });
    }

    openDashboard() {
        this.actionService.doAction("pos_gas_station.action_gas_station_dashboard");
    }
}

registry.category("actions").add("vpn_station_employees", VpnStationEmployeesView);
