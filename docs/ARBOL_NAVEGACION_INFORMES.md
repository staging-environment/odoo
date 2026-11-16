# 🧭 Árbol de Navegación: Módulo de Informes y Gestión Operativa

Este documento define la estructura y arquitectura jerárquica del menú de navegación de **Informes**, diseñado para servir de base escalable a los módulos de reporting, auditoría y análisis de pista de Odoo 17 ERP - UTRECAR.

---

## 📊 Estructura Jerárquica (Mermaid)

```mermaid
graph TD
    %% Nodo Principal
    ROOT["📊 INFORMES"]

    %% Ramas de Primer Nivel
    ALM["📦 ALMACÉN"]
    COM["🛒 COMPRAS"]
    VEN["📈 VENTAS"]
    FIC["📁 FICHEROS"]
    TUR["⏱️ TURNOS"]
    COB["💶 COBROS"]

    %% Conexiones de Primer Nivel
    ROOT --> ALM
    ROOT --> COM
    ROOT --> VEN
    ROOT --> FIC
    ROOT --> TUR
    ROOT --> COB

    %% Sub-ramas de Almacén
    ALM_DOC["📄 DOCUMENTOS"]
    ALM_SUM["⛽ SUMINISTROS"]
    ALM --> ALM_DOC
    ALM --> ALM_SUM

    %% Sub-ramas de Compras
    COM_DOC["📄 DOCUMENTOS"]
    COM --> COM_DOC

    %% Estilos de Nodos
    style ROOT fill:#1e3a8a,stroke:#1d4ed8,stroke-width:3px,color:#ffffff,font-weight:bold,font-size:15px
    style ALM fill:#0284c7,stroke:#0369a1,stroke-width:2px,color:#ffffff,font-weight:bold
    style COM fill:#0d9488,stroke:#0f766e,stroke-width:2px,color:#ffffff,font-weight:bold
    style VEN fill:#16a34a,stroke:#15803d,stroke-width:2px,color:#ffffff,font-weight:bold
    style FIC fill:#6366f1,stroke:#4f46e5,stroke-width:2px,color:#ffffff,font-weight:bold
    style TUR fill:#d97706,stroke:#b45309,stroke-width:2px,color:#ffffff,font-weight:bold
    style COB fill:#ea580c,stroke:#c2410c,stroke-width:2px,color:#ffffff,font-weight:bold

    style ALM_DOC fill:#e0f2fe,stroke:#0284c7,stroke-width:1.5px,color:#0369a1,font-weight:bold
    style ALM_SUM fill:#e0f2fe,stroke:#0284c7,stroke-width:1.5px,color:#0369a1,font-weight:bold
    style COM_DOC fill:#ccfbf1,stroke:#0d9488,stroke-width:1.5px,color:#0f766e,font-weight:bold
```

---

## 🗂️ Detalle de Secciones y Alcance Funcional

| Sección / Nivel | Submenús Directos | Descripción y Objetivos |
| :--- | :--- | :--- |
| **INFORMES** | - | Nodo raíz de navegación para reportes analíticos, operacionales y fiscales. |
| **📦 ALMACÉN** | `DOCUMENTOS`, `SUMINISTROS` | Control de stock en tanques de combustible, entradas de cisternas, calibraciones/probetas, mermas y suministros de pista por manguera y surtidor. |
| **🛒 COMPRAS** | `DOCUMENTOS` | Registro y fiscalización de albaranes de compra de carburantes (CLH/Exolum, Cepsa, Repsol) y facturas de proveedores de tienda. |
| **📈 VENTAS** | *(Ampliación futura)* | Informes de ventas por estación, empleado, forma de pago (efectivo, tarjeta, crédito, albarán), márgenes y comparativas temporales. |
| **📁 FICHEROS** | *(Ampliación futura)* | Catálogo maestro de entidades exportables (maestro de clientes de crédito, vehículos/matrículas, códigos de surtidores y tarifas). |
| **⏱️ TURNOS** | *(Ampliación futura)* | Informes oficiales de arqueo, cierre de sesión (`pos.session`), cuadre de caja, incidencias, entradas y extracciones por turno y expendedor. |
| **💶 COBROS** | *(Ampliación futura)* | Conciliación de cobros pendientes de pista, deudas por cliente de crédito, cobros diferidos y liquidaciones de cuentas. |

---

## 🚀 Hoja de Ruta para Ampliaciones Futuras
Este árbol se encuentra desacoplado en este documento para incorporar paulatinamente:
- Acciones de menú Odoo (`ir.actions.act_window` / `ir.ui.menu`).
- Filtros por Estación de Servicio (Repsol, Ronda Norte, Vistalegre, Rodalabota, Atenas).
- Permisos por rol (Expendedor vs Encargado vs Administrador).
