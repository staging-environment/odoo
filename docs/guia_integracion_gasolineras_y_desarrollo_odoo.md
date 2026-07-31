# Guía Técnica: Integración de Gasolineras y Desarrollo de Módulos Custom en Odoo 17

---

## ⛽ 1. Arquitectura de Integración de Surtidores de Gasolinera

Para integrar estaciones de servicio con Odoo 17 se utiliza una arquitectura en 3 capas que conecta el hardware físico de la pista de servicio con el módulo **Point of Sale (POS)** e **Inventario** de Odoo.

```
┌────────────────────────────────────────────────────────┐
│             SURTIDORES DE COMBUSTIBLE                  │
│       (Gilbarco / Tokheim / Wayne / Cetil)             │
└──────────────────────────┬─────────────────────────────┘
                           │ Protocolo RS-485 / IFSF / Loop
                           ▼
┌────────────────────────────────────────────────────────┐
│     CONTROLADOR DE PISTA / FORECOURT CONTROLLER        │
│        (Ej: DOMS PSS 5000 / Alvesa / Concentrador)     │
└──────────────────────────┬─────────────────────────────┘
                           │ TCP/IP / API Local (Serial/Ethernet)
                           ▼
┌────────────────────────────────────────────────────────┐
│          AGENTE EDGE / ODOO IOT BOX (PYTHON)           │
│    - Servicio Daemon local en la estación              │
│    - Escucha eventos de manguera (Descolgada/Servida) │
│    - Envía autorizaciones de suministro                │
└──────────────────────────┬─────────────────────────────┘
                           │ WebSockets / JSON-RPC (HTTPS)
                           ▼
┌────────────────────────────────────────────────────────┐
│                    ODOO 17 ERP                         │
│  - Módulo pos_gas_station (TPV)                        │
│  - Módulo stock_tank_management (Control Tanques)     │
└────────────────────────────────────────────────────────┘
```

### 1.1 Flujos de Operación en Pista

#### A. Post-Pago (Servicio Atendido)
1. El cliente llena el depósito en el surtidor.
2. El **Controlador de Pista (FCC)** registra los litros, tipo de manguera (Gasolina 95, Diesel, etc.) e importe total.
3. El **Agente Edge** recibe el evento final de suministro del FCC y envía un mensaje WebSocket a Odoo.
4. El **TPV de Odoo (POS)** muestra la manguera activada con la venta pendiente.
5. El cajero pulsa sobre la venta en pantalla, se carga en el ticket de compra y se cobra (Efectivo, Tarjeta, Flotas/Crédito).
6. Odoo descuenta los litros del tanque correspondiente en el módulo de Inventario.

#### B. Pre-Pago (Autoservicio / Desatendido)
1. El cliente acude a la caja o terminal de pago y abona un importe (ej. 50€).
2. Odoo envía una orden de autorización al Agente Edge: **"Autorizar Manguera N por máximo 50€"**.
3. El Agente Edge transmite el comando al Controlador de Pista (FCC).
4. El surtidor se activa y corta automáticamente al llegar a los 50€ (o al colgar la manguera).
5. Si el cliente sirvió menos (ej. 43.50€), el surtidor notifica el importe real y Odoo ajusta la devolución o factura por el total consumido.

### 1.2 Modelos de Datos en Odoo para Gasolineras

Para gestionar estaciones de servicio se definen 3 modelos custom principales:
- `gas.station.tank`: Control de tanques de almacenamiento (capacidad, stock actual, sonda de temperatura, varillaje).
- `gas.station.dispenser`: Identificación física de surtidores en pista.
- `gas.station.nozzle`: Asociación entre manguera del surtidor, tipo de combustible (Producto Odoo) y tanque de origen.

---

## 🧩 2. Mecanismo para Activar / Desactivar Módulos en Odoo 17

### 2.1 Vía Interfaz Web (UI)

1. **Activar el Modo Desarrollador (Developer Mode):**
   - Ve a **Ajustes (Settings)** -> desplázate al final de la página -> Haz clic en **Activar modo desarrollador** (o añade `?debug=1` en la URL: `https://odoo.ddev.site/web?debug=1`).

2. **Actualizar Lista de Aplicaciones:**
   - Ve al menú principal **Aplicaciones (Apps)**.
   - En la barra superior, haz clic en **Actualizar lista de aplicaciones (Update Apps List)** y confirma.

3. **Instalar / Activar un Módulo:**
   - En la barra de búsqueda de Aplicaciones, **elimina el filtro por defecto "Aplicaciones"** (crucecita 'x'). Esto es fundamental para ver módulos técnicos o custom.
   - Escribe el nombre técnico de tu módulo (ej. `pos_gas_station`).
   - Haz clic en **Instalar**.

4. **Desactivar / Desinstalar un Módulo:**
   - Entra al detalle del módulo en la sección Aplicaciones.
   - Haz clic en los tres puntos o en la pestaña superior -> **Desinstalar**.

---

### 2.2 Vía Línea de Comandos (CLI / DDEV)

Con DDEV en tu entorno local o en producción:

```bash
# 1. Instalar un nuevo módulo
ddev exec odoo -c /etc/odoo/odoo.conf -d db -i pos_gas_station --stop-after-init

# 2. Actualizar un módulo tras hacer cambios en el código
ddev exec odoo -c /etc/odoo/odoo.conf -d db -u pos_gas_station --stop-after-init

# 3. Desinstalar un módulo
ddev exec odoo -c /etc/odoo/odoo.conf -d db --uninstall=pos_gas_station --stop-after-init
```

---

## 🛠️ 3. Guía de Desarrollo de Módulos Custom en Odoo 17

Todos los módulos custom que desarrolles deben estar ubicados dentro del directorio `./extra-addons/` de tu repositorio.

### 3.1 Estructura Estándar de Archivos

Ejemplo de estructura para el módulo `pos_gas_station`:

```text
extra-addons/pos_gas_station/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── dispenser.py
│   └── tank.py
├── security/
│   └── ir.model.access.csv
└── views/
    ├── dispenser_views.xml
    └── tank_views.xml
```

---

### 3.2 Código Paso a Paso de un Módulo Custom

#### A. Archivo `__manifest__.py`
Define los metadatos del módulo, dependencias y archivos XML que se cargarán.

```python
# extra-addons/pos_gas_station/__manifest__.py
{
    'name': 'Gestión de Gasolineras y Surtidores',
    'version': '17.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Integración de surtidores, mangueras y tanques de combustible con Odoo 17 POS',
    'author': 'Tu Empresa / Developer',
    'depends': ['base', 'point_of_sale', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/dispenser_views.xml',
        'views/tank_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
```

#### B. Archivo `__init__.py` Raíz
```python
# extra-addons/pos_gas_station/__init__.py
from . import models
```

#### C. Modelos Python (`models/dispenser.py`)
Define los datos y la lógica de negocio usando la API de Odoo 17.

```python
# extra-addons/pos_gas_station/models/__init__.py
from . import dispenser
from . import tank
```

```python
# extra-addons/pos_gas_station/models/dispenser.py
from odoo import models, fields, api

class GasStationDispenser(models.Model):
    _name = 'gas.station.dispenser'
    _description = 'Surtidor de Gasolinera'

    name = fields.Char(string='Número / Nombre de Surtidor', required=True)
    code = fields.Char(string='Código de Pista (FCC)', required=True)
    active = fields.Boolean(string='Activo', default=True)
    nozzle_ids = fields.One2many(
        'gas.station.nozzle', 
        'dispenser_id', 
        string='Mangueras'
    )

class GasStationNozzle(models.Model):
    _name = 'gas.station.nozzle'
    _description = 'Manguera de Surtidor'

    name = fields.Char(string='Manguera', required=True)
    number = fields.Integer(string='Número de Manguera', required=True)
    dispenser_id = fields.Many2one('gas.station.dispenser', string='Surtidor', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Combustible', required=True)
    tank_id = fields.Many2one('gas.station.tank', string='Tanque Asignado')
```

#### D. Vistas XML (`views/dispenser_views.xml`)
Crea las interfaces de usuario (formularios, listas y menúes).

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Vista Lista (Tree) -->
    <record id="view_gas_dispenser_tree" model="ir.ui.view">
        <record name="name">gas.station.dispenser.tree</record>
        <record name="model">gas.station.dispenser</record>
        <record name="arch" type="xml">
            <tree string="Surtidores">
                <field name="name"/>
                <field name="code"/>
                <field name="active"/>
            </tree>
        </record>
    </record>

    <!-- Acciones de Ventana -->
    <record id="action_gas_dispenser" model="ir.actions.act_window">
        <field name="name">Surtidores</field>
        <field name="res_model">gas.station.dispenser</field>
        <field name="view_mode">tree,form</field>
    </record>

    <!-- Menú Principal -->
    <menuitem id="menu_gas_station_root" name="Gasolinera" sequence="10"/>
    <menuitem id="menu_gas_dispenser" name="Surtidores" parent="menu_gas_station_root" action="action_gas_dispenser"/>
</odoo>
```

#### E. Permisos de Seguridad (`security/ir.model.access.csv`)
Odoo 17 exige definir permisos de lectura/escritura para cada modelo custom.

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_gas_dispenser_user,access.gas.dispenser.user,model_gas_station_dispenser,base.group_user,1,1,1,1
access_gas_nozzle_user,access.gas.nozzle.user,model_gas_station_nozzle,base.group_user,1,1,1,1
```

---

## 🚀 4. Ciclo de Despliegue del Nuevo Módulo

1. **Crear el módulo** dentro de `./extra-addons/pos_gas_station/`.
2. **Reiniciar e instalar en local (DDEV):**
   ```bash
   ddev restart
   ddev exec odoo -c /etc/odoo/odoo.conf -d db -i pos_gas_station --stop-after-init
   ```
3. **Subir cambios a GitHub:**
   ```bash
   git add extra-addons/pos_gas_station/
   git commit -m "feat: modulo inicial pos_gas_station"
   git push origin main
   ```
4. **Desplegar e instalar en Producción:**
   ```bash
   ssh developer@164.68.101.69 "cd /home/developer/Projects/odoo && git pull origin main && ddev exec odoo -c /etc/odoo/odoo.conf -d db -i pos_gas_station --stop-after-init && docker restart ddev-odoo-odoo"
   ```
