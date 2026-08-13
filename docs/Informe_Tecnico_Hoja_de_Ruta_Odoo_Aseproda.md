# Informe Técnico y Hoja de Ruta: Transición de Aseproda a Odoo 17 ERP

---

## 📄 1. Resumen Ejecutivo y Visión Estratégica

El presente informe técnico establece la **hoja de ruta integral** para la migración y evolución del sistema de gestión actual (**Aseproda**) hacia la plataforma **Odoo 17 (Enterprise/Community + Módulos Especializados en Estaciones de Servicio)**.

Aseproda ha actuado como una solución vertical funcional para el sector de estaciones de servicio en España, cubriendo la facturación de pista, el control de surtidores y la gestión básica de flotas. Sin embargo, su arquitectura monolítica y cerrada limita la automatización, la visión 360° del negocio, la integración con otros canales comerciales y la escalabilidad.

### Principio Director de la Migración
> **Evolución sin Pérdida Operativa:** La estrategia no consiste en limitar el nuevo ERP a replicar mímicamente las pantallas de Aseproda, sino en **absorber y perfeccionar todas sus capacidades críticas de pista (TPV, control de surtidores, crédito de flotas y normativa española)** mientras se desbloquea el vasto ecosistema modular de Odoo (CRM, Contabilidad Española avanzada, Inventario valorado FIFO/PMP, Portal de Clientes web, RRHH y Business Intelligence).

---

## 📊 2. Análisis Comparativo: Aseproda vs. Odoo 17

| Área Funcional | Funcionalidad en Aseproda | Solución en Odoo 17 (Estándar + Extra-Addons) | Ventaja Estratégica en Odoo |
| :--- | :--- | :--- | :--- |
| **TPV / POS Pista** | Aplicación TPV de escritorio clásica. Pantalla de cobro rápida orientada a mangueras. | Módulo **pos_gas_station** en Odoo POS. Interfaz táctil web reactiva con integración WebSockets a pista. | Flexibilidad multidispositivo (PC, Tablet, Terminales Móviles Android/iOS), actualización centralizada instantánea. |
| **Control Surtidores** | Conexión directa mediante tarjetas serie o concentrador Aseproda. | **Agente Edge / Odoo IoT Box** comunicando con controlador de pista (DOMS PSS 5000, Cetil, Aseproda FCC) vía IFSF / TCP IP. | Independencia de hardware. Compatibilidad multi-marca de surtidores sin depender de licencias cerradas. |
| **Gestión de Tanques** | Control básico de volúmenes y entradas de cisternas. | Módulo **stock_tank_management** integrado con Inventario Odoo. Lecturas automáticas de sondas ATG (Veeder-Root). | Ajustes automáticos de mermas por temperatura y densidad, valorización contable exacta del stock en tiempo real. |
| **Crédito de Flotas** | Tarjetas físicas de flota con saldo, pin y matrículas. Facturación fin de mes. | Módulo **leet_credit_cards** + Portal del Cliente en Sitio Web. | Autogestión de clientes: descarga directa de facturas, control de tarjetas, límites configurables en tiempo real sin llamar a la gasolinera. |
| **Cambio de Precios** | Envío manual o programado a surtidores y monopolos. | Módulo de Tarifas Odoo + integración automática con monolitos de precios y surtidores en tiempo real. | Automatización por reglas de margen sobre coste del barril o precios de la competencia. |
| **Cumplimiento Fiscal** | Módulos adicionales para SII y ficheros de impuestos. | **Contabilidad Española Odoo (l10n_es)** + módulos SII y **VeriFactu / TicketBAI**. | Declaración directa sin intermediarios, conciliación bancaria automatizada con IA y generación inmediata de libros fiscales. |
| **MITECO (Geoportal)** | Exportación o envío de ficheros de precios a Ministerio. | Módulo **uel_pricing_minetur**: Envío automático por API/REST de cambios de precio al Ministerio para Transición Ecológica. | Cumplimiento legal automático 100% garantizado sin intervención humana. |
| **ERP Global** | Limitado o nulo en CRM, RRHH, Compras avanzadas y Analítica. | **Ecosistema Odoo 17 completo:** CRM, Compras, Proyectos, RRHH, Partes de Horas, Marketing, BI Dashboard. | Visión unificada de todo el grupo empresarial en una sola base de datos. |

---

## 🔌 3. Arquitectura del TPV / POS y Control de Pista

La arquitectura propuesta se divide en 3 capas de alta disponibilidad y tolerancia a fallos:



### 3.1 Flujos de Operación en TPV
1. **Post-pago (Servicio Atendido / Autoservicio estándar):**
   - El cliente descuelga manguera y reposta. El controlador (DOMS/FCC) notifica litros e importe final.
   - El Agente Edge transmite por WebSocket la venta pendiente a Odoo POS.
   - La pantalla del TPV muestra la manguera en color amarillo/activo con la venta.
   - El cajero selecciona la manguera, asigna forma de pago (Efectivo, Tarjeta, Flota/Crédito) e imprime comprobante.
   - Odoo descuenta los litros del tanque y actualiza contabilidad e inventario.

2. **Pre-pago (Pago Previas en Caja o Terminal Desatendido):**
   - El cliente abona 40€ en caja antes de servir.
   - El TPV de Odoo envía el comando AUTH_PUMP(surtidor_id, manguera_id, max_amount=40.00).
   - El surtidor permite el paso de combustible y corta automáticamente al alcanzar 40.00€.
   - Si el cliente consume menos (ej. 34.20€), el surtidor notifica el importe real y Odoo emite la devolución o ajusta la factura simplificada por 34.20€.

3. **Garantía Offline (Tolerancia Cero a Caídas):**
   - Si se interrumpe la conexión a Internet o al servidor central, el **Agente Edge local** almacena en buffer (SQLite) todas las transacciones de pista.
   - El TPV de Odoo en la LAN local continúa operando normalmente con el Agente Edge.
   - Al restablecerse la conectividad, las ventas se sincronizan automáticamente con el servidor central de Odoo sin duplicidades.

---

## 🛢️ 4. Gestión de Carburantes, Tanques e Inventario

La gestión de inventario de hidrocarburos presenta particularidades físicas que Odoo 17 resuelve mediante el módulo stock_tank_management:

1. **Estructura de Tanques y Sondas (ATG):**
   - Integración directa con sondas de nivel y temperatura (**Veeder-Root TLS-350 / TLS-450**, OPW, Colibri).
   - Lectura continua de: Nivel de producto (litros), Nivel de agua acumulada en fondo, Temperatura del combustible.
2. **Varillaje y Ajuste de Mermas:**
   - Comparación automática entre el inventario teórico de Odoo (Ventas - Compras) y el volumen real medido por la sonda.
   - Registro automático de pérdidas por evaporación o contracción térmica (mermas permitidas) mediante asientos de ajuste de stock configurables.
3. **Recepciones de Cisterna:**
   - Proceso de descarga de combustible con verificación de volumen corregido a 15°C (según albarán de la mayorista/CLH).
   - Asignación de lote por cisterna y valorización de inventario mediante PMP (Precio Medio Ponderado) o FIFO.
4. **Cambio Automático de Precios:**
   - Definición centralizada de tarifas por combustible (Gasolina 95, Diesel A, Diesel Plus, AdBlue).
   - Actualización programada o en tiempo real que transmite las nuevas tarifas tanto al monolito/tótem de precios en calle como a los procesadores del surtidor.

---

## 💳 5. Gestión Comercial, Flotas y Crédito de Clientes

Uno de los pilares clave de Aseproda es el crédito de flotas, el cual en Odoo 17 experimenta un salto cualitativo:

1. **Gestión de Tarjetas y Claves de Flota (leet_credit_cards):**
   - Tarjetas magnéticas, RFID o códigos QR asociados a empresas y vehículos específicos.
   - Parámetros de seguridad por tarjeta: Código PIN obligatorio, Matrícula verificada, Límite diario/mensual en euros o litros, Restricción por tipo de producto (ej. solo Diésel A) y horario de repostaje.
2. **Facturación Mensual Agrupada Automática:**
   - Durante el mes, las ventas de pista con tarjeta de flota generan albaranes o vales diferidos en Odoo.
   - El último día del mes (o quincenalmente), Odoo ejecuta un proceso por lotes que agrupa todos los repostajes del periodo por cliente y emite una **Factura Rectificada / Agrupada Oficial** con el desglose por vehículo, fecha, estación y litros.
3. **Portal Web de Clientes de Flota:**
   - Los clientes profesionales acceden a su área privada web en Odoo para:
     - Consultar consumos en tiempo real y repostajes realizados por sus chóferes.
     - Descargar facturas en PDF y XML/Facturae.
     - Bloquear/desbloquear tarjetas de flota de forma autónoma.
     - Solicitar nuevas tarjetas o modificar límites.

---

## ⚖️ 6. Cumplimiento Normativo y Fiscal en España

El sistema configurado en Odoo 17 garantiza el cumplimiento riguroso de la legislación española vigente:

1. **SII (Suministro Inmediato de Información de la AEAT):**
   - Envío automático en menos de 4 días de los registros de facturación (emitidas y recibidas) a la sede electrónica de la Agencia Tributaria.
2. **VeriFactu / TicketBAI:**
   - Generación de facturas simplificadas y completas con encadenamiento criptográfico Hash, código QR normativo y registro inalterable de ventas en TPV.
3. **Comunicación al MITECO (Geoportal Precios Carburantes):**
   - Conexión vía API REST con la plataforma del Ministerio para la Transición Ecológica (uel_pricing_minetur).
   - Envío automático de actualizaciones de precios de venta al público en menos de 30 minutos tras su modificación en surtidor.
4. **Ley de Hidrocarburos y Libres de Impuestos (IIEE):**
   - Control de Impuestos Especiales sobre Hidrocarburos (Gasóleo Bonificado / Agrícola B y C).
   - Generación de ficheros de ventas de gasóleo bonificado para declaración ante la AEAT.

---

## 🚀 7. Ecosistema Ampliado Odoo 17: El Valor Añadido

Al migrar a Odoo, la empresa no solo reemplaza Aseproda, sino que dota a su organización de herramientas corporativas de primer nivel:

- **Contabilidad Española Avanzada:** Conciliación bancaria automatizada con reglas inteligentes, modelos 303, 347, 390, 111 y balances oficiales en un clic.
- **Gestión de Compras y Proveedores:** Control de costes de aprovisionamiento con mayoristas de carburante (Repsol, Cepsa, BP, Exolum/CLH), cálculo automático de márgenes brutos por litro.
- **Tienda de Conveniencia y Lavadero:** Gestión integral del stock de superette/tienda (bebidas, lubricantes, snacks) y venta de vales/fichas de lavadero integrada en el mismo TPV.
- **RRHH y Gestión de Turnos:** Cuadrante de horarios para empleados de gasolinera, fichaje digital, control de ausencias y cálculo de incentivos por ventas.
- **Business Intelligence (BI):** Cuadros de mando ejecutivos con KPIs clave: litros vendidos por hora, margen medio por carburante, horas pico de pista y ventas por empleado.

---

## 🗺️ 8. Hoja de Ruta de Implementación (Roadmap por Fases)

La implementación se dividirá en **5 fases estratégicas** a lo largo de un periodo estimado de **16 a 20 semanas**:



---

## ⚠️ 9. Matriz de Riesgos y Plan de Mitigación

| Riesgo Identificado | Impacto | Probabilidad | Estrategia de Mitigación |
| :--- | :---: | :---: | :--- |
| **Pérdida de conectividad con controlador de pista en momentos de alta demanda** | Crítico | Baja | Despliegue del **Agente Edge en mini-PC industrial fanless** dedicado por estación con doble puerto de red redundante. |
| **Resistencia al cambio por parte de los cajeros/expendedores** | Medio | Media | Diseño de interfaz TPV minimalista y ergonómica. Programa intensivo de capacitación en estación piloto previa. |
| **Inconsistencias en migración de saldos de flotas desde Aseproda** | Alto | Baja | Ejecución de scripts de validación de saldos y doble auditoría de corte de caja en la fecha de cambio. |
| **Retardos en la autorización de manguera (< 200ms exigidos)** | Alto | Baja | Utilización de conexión persistente WebSockets local (LAN) entre el Agente Edge y el TPV en caja. |

---

## 🎯 10. Conclusiones y Próximos Pasos

La transición de Aseproda a **Odoo 17** representa la modernización definitiva de la infraestructura tecnológica de las estaciones de servicio. Odoo no solo cubre al 100% las necesidades operativas de pista y crédito de flotas, sino que elimina los silos de información, automatiza el cumplimiento fiscal español y dota a la directiva de un control analítico total en tiempo real.

### Próximos Pasos Recomendados:
1. Aprobar la presente hoja de ruta y constitución del equipo de proyecto.
2. Iniciar la **Fase 1 (Semana 1)** con la auditoría de hardware de pista existente (modelos de surtidores, sondas y concentradores).
3. Desplegar el entorno de Staging de Odoo 17 para validación de prototipo.
