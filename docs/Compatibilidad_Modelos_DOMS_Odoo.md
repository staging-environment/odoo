# Guía Técnica: Compatibilidad de Modelos DOMS con Odoo ERP / POS

**Ámbito:** Automatización de Estaciones de Servicio y Control de Pista  
**Versión:** 1.0  
**Fecha:** Septiembre 2026  
**Documento:** Especificación Técnica de Compatibilidad de Hardware  

---

## 1. Introducción: El Rol de DOMS como Forecourt Controller (FCC)

En el sector de las estaciones de servicio, **DOMS** (desarrollado por **DOMS ApS / Gilbarco Veeder-Root**) es el controlador de pista (**Forecourt Controller - FCC**) líder y estándar a nivel internacional.

Su propósito fundamental es actuar como puente físico y lógico:
- **Hacia la pista:** Habla los protocolos propietarios y circuitos serie específicos de cada fabricante de surtidores (Gilbarco Two-Wire, Tokheim Ka-Loop, Wayne DART, Cetil RS-485, etc.), sondas de nivel de tanques (Veeder-Root TLS, OPW) y monolitos de precios.
- **Hacia el sistema de caja / ERP:** Expone una interfaz unificada y normalizada a través de redes Ethernet locales (TCP/IP).

> **Principio de Compatibilidad con Odoo:**  
> La compatibilidad entre DOMS y Odoo **no depende de las marcas de los surtidores de la pista**, sino de la **capacidad del controlador DOMS para comunicarse por TCP/IP mediante interfaces de host estándar (DOMS PSS Direct Protocol o IFSF TCP/IP)**.

---

## 2. Matriz de Compatibilidad: Modelos y Placas CPU (CPUB)

La plataforma hardware por excelencia de DOMS es la serie **DOMS PSS 5000**. Dentro de este equipo, el componente determinante para la integración con Odoo es la placa procesadora (**CPUB**):

| Modelo / Placa CPU | Nivel de Compatibilidad | Conectividad Física | Protocolos Soportados | Recomendación Técnica |
| :--- | :---: | :--- | :--- | :--- |
| **DOMS PSS 5000 (CPUB 520)** | **100% Nativa (Recomendado)** | Multi-LAN (2-3 puertos Ethernet independientes), USB, SSL/TLS por hardware, RS-232. | • PSS Direct Protocol (TCP Socket)<br/>• IFSF TCP/IP<br/>• DOMS REST API / WebServices | **Hardware de generación actual**. Máxima seguridad, alto rendimiento y separación de redes (LAN Pista vs LAN TPV). |
| **DOMS PSS 5000 (CPUB 510 / 511)** | **100% Compatible** | 1 puerto Ethernet 10/100 BASE-T, USB, RS-232 / RS-485. | • PSS Direct Protocol (TCP Socket)<br/>• IFSF TCP/IP | **El modelo más extendido** en gasolineras operativas. Perfecta integración mediante socket TCP directo o IFSF. |
| **DOMS PSS 5000 (CPUB 500 / 501 / 502 / 503 / 505)** *(Legacy)* | **Condicional (Requiere módulo LAN)** | Puertos serie nativos. Opcionalmente tarjeta Ethernet LAN auxiliar según subversión. | • PSS Serial Protocol<br/>• IFSF Serial (LonWorks / HDLC)<br/>• PSS TCP (solo con tarjeta de red y firmware reciente) | Si dispone de tarjeta LAN y firmware con soporte TCP/IP, es integrable. Si solo cuenta con puertos serie, se recomienda sustituir la placa CPU por una CPUB 510 o 520. |
| **DOMS Compact** | **100% Compatible** | 1 puerto Ethernet 10/100 BASE-T, puertos serie integrados. | • PSS Direct Protocol (TCP Socket)<br/>• IFSF TCP/IP | Variante reducida de PSS 5000 para postes desatendidos o gasolineras pequeñas. Totalmente compatible vía Ethernet. |

---

## 3. Factores de Forma y Chasis (Enclosures)

El chasis exterior alberga la fuente de alimentación, la placa CPU y las tarjetas de conexión a surtidores (DSB). El formato de la caja **no restringe la compatibilidad con Odoo**, siempre que cuente con una CPU con puerto Ethernet:

1. **PSS 5000 19 Pulgadas Rack Mount (16 ranuras):**
   - Bastidor para armario rack normalizado de comunicaciones.
   - Diseñado para estaciones medianas y grandes con gran cantidad de mangueras, sondas y postes de pago.
2. **PSS 5000 Wall-Mount Box (4 u 8 ranuras):**
   - Chasis mural metálico de alta resistencia con cerradura.
   - El formato más habitual en casetas de cobro de estaciones estándar.
3. **DOMS Compact Enclosure:**
   - Formato miniaturizado de bajo consumo para integración dentro del propio cabezal del surtidor o en terminales de pago desatendidos (OPT).

---

## 4. Módulos de Interfaz de Pista (DSB - Device Specific Boards)

Para que el DOMS gobierne los elementos de pista y traslade sus estados a Odoo, el rack debe disponer de las tarjetas de interfaz específicas para los equipos de la estación:

| Tarjeta DSB | Función y Dispositivos Conectados | Protocolo de Surtidor / Dispositivo |
| :--- | :--- | :--- |
| **DSB 451** | Surtidores Gilbarco Veeder-Root | Two-Wire 20mA Current Loop |
| **DSB 452** | Surtidores Tokheim Quantium / Koppens | Ka-Loop / Dunclare Current Loop |
| **DSB 453** | Surtidores Wayne Dresser | Wayne DART Protocol / Current Loop |
| **DSB 454 / 455** | Surtidores Multimarca / Electrónicos | RS-485 / RS-422 (Cetil, Bennett, Salzkotten, etc.) |
| **DSB 461 / 462** | Sondas de Medición de Tanques (ATG) | Conexión serie a consolas Veeder-Root TLS-350 / 450, OPW, Colibri |
| **DSB 471** | Monolitos y Pantallas de Precios | Protocolo de monolito LED / Interfaces serie o bucle |

---

## 5. Protocolos y Licencias Software DOMS para Odoo

Para que Odoo pueda consultar y ordenar acciones sobre los surtidores, el firmware del DOMS debe tener habilitada alguna de las siguientes opciones de software:

### 5.1 Protocolo Directo DOMS (PSS Direct Protocol over TCP/IP)
- Comunicación por socket TCP bidireccional directo (por defecto puerto 7000).
- Proporciona notificación inmediata de eventos en milisegundos:
  - Manguera descolgada (*Nozzle lifted / Call*).
  - Litros e importes en tiempo real durante el despacho (*Pumping / Fueling*).
  - Fin de suministro y manguera colgada (*Stopped / Call cleared*).
  - Bloqueo y autorización por manguera (*Authorise / Suspend / Resume*).
  - Lectura de totalizadores inalterables electrónicos de cada bomba.

### 5.2 Estándar IFSF POS Protocol (over TCP/IP)
- Estándar internacional normalizado de la industria petrolífera (puerto TCP 4000/4001).
- Define la máquina de estados universal para dispensadores (Dispenser Application), cambio de precios de postes y lectura de niveles de tanques.

### 5.3 DOMS Web Services / XML REST API
- Disponible en versiones de firmware recientes de las placas CPUB 510 y CPUB 520.
- Permite integración orientada a microservicios para autorizaciones y auditorías.

---

## 6. Arquitectura de Integración con Odoo ERP / POS

Debido a que un ERP en la nube o local no debe gestionar directamente bucles serie ni tolerar caídas de latencia de red en pistas de combustible, se utiliza una **arquitectura de 3 niveles con Agente Edge Local**:

`
+-----------------------------------------------------------------------------+
|                         SURTIDORES Y TANQUES (PISTA)                        |
|         Gilbarco · Tokheim · Wayne · Cetil · Sondas Veeder-Root TLS         |
+--------------------------------------+--------------------------------------+
                                       | Cableado 20mA Loop / RS-485 / RS-422
                                       v
+-----------------------------------------------------------------------------+
|                 CONTROLADOR DE PISTA: DOMS PSS 5000                         |
|   - Placa CPU: CPUB 510 o CPUB 520                                          |
|   - Tarjetas DSB específicas de cada surtidor                               |
|   - Licencia: PSS TCP Direct Protocol o IFSF TCP/IP                         |
+--------------------------------------+--------------------------------------+
                                       | Red Local Ethernet (TCP/IP - Socket 7000 / 4000)
                                       v
+-----------------------------------------------------------------------------+
|                    AGENTE EDGE LOCAL / ODOO IOT BOX                         |
|   - Hardware: Mini PC Industrial Fanless / Raspberry Pi 4 (Linux)           |
|   - Agente Daemon Python (Servicio de Pista y Máquina de Estados)          |
|   - Base de Datos Local de Contingencia (SQLite / PostgreSQL Buffer)        |
+--------------------------------------+--------------------------------------+
                                       | WebSockets (WSS) / JSON-RPC (LAN o Cloud)
                                       v
+-----------------------------------------------------------------------------+
|                        CAJA Y TPV: ODOO 17 POS                              |
|   - Módulo pos_gas_station integrado en TPV táctil                          |
|   - Autorización de repostajes prepago y postpago                           |
|   - Carga directa del importe y litros a la cesta del ticket                |
|   - Gestión de clientes de crédito, matrículas y flotas                     |
+-----------------------------------------------------------------------------+
`

### Ventajas del Agente Edge frente a caídas de conexión:
1. **Buffer Local Offline:** Si se corta la conexión con el servidor central de Odoo en la nube, el Agente Edge sigue autorizando surtidores y registrando cada suministro localmente.
2. **Sincronización Automática:** Cuando la conectividad a internet se restablece, las ventas acumuladas se transmiten a Odoo creando las facturas y asientos contables correspondientes sin pérdida de información ni duplicados.

---

## 7. Lista de Comprobación (Checklist) para Auditoría de Campo

Antes de conectar una estación de servicio con DOMS a Odoo, verifique los siguientes puntos en el controlador físico:

1. [ ] **Modelo de CPU:** Inspeccione la placa CPU del rack PSS 5000. Debe indicar CPUB 510, CPUB 511 o CPUB 520.
2. [ ] **Puerto Ethernet Activo:** Comprobar que el conector RJ-45 de la placa CPU tiene enlace de red y se le ha asignado una IP fija en la subred local de la estación.
3. [ ] **Licencia / Protocolo Host Habilitado:** Verificar en la configuración del DOMS (mediante la herramienta *DOMS Site Configuration Tool / POS Port Config*) que el puerto TCP hacia el POS está habilitado en modo **PSS Direct Protocol** o **IFSF POS**.
4. [ ] **Tarjetas DSB y Canales:** Confirmar que todos los surtidores de la pista están online y respondiendo en los canales DSB correspondientes.
5. [ ] **Agente Edge en Red:** Asegurar que el Mini PC del Agente Edge puede realizar *ping* y abrir socket TCP hacia la dirección IP y puerto del DOMS.
