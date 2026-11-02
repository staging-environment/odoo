# Regla de Flujo de Trabajo: Commit y Despliegue Automático en Producción

## Política Obligatoria y Permanente (Instrucción Expresa del Usuario)
Cada vez que se complete o verifique cualquier cambio de código, corrección, función o mejora solicitada por el usuario en este repositorio, **SIEMPRE se debe realizar de forma proactiva y automática**:

1. **Commit y Push Local:**
   - `git add <archivos>`
   - `git commit -m "feat/fix: descripción clara del cambio"`
   - `git push origin main`

2. **Despliegue Inmediato en Servidor de Producción (164.68.101.69):**
   - Conexión SSH: `ssh root@164.68.101.69`
   - En `/home/developer/Projects/odoo`:
     - Ejecutar pull: `su - developer -c 'cd /home/developer/Projects/odoo && git pull origin main'`
     - Si hay cambios en modelos Python, vistas XML o estructura de base de datos:
       `docker exec ddev-odoo-odoo odoo -u pos_gas_station -d odoo --stop-after-init`
     - Reiniciar contenedor para recargar procesos en memoria:
       `docker restart ddev-odoo-odoo`
     - Verificar logs de arranque:
       `docker logs --tail 15 ddev-odoo-odoo`

3. **Arquitectura Multi-Rol por Empresa:**
   - La asignación de roles a usuarios soporta **múltiples roles simultáneos** (`EMPLEADO`, `GESTOR`, `CEO`, `ADMINISTRACION`) tanto a nivel global (`res.users.utrecar_role_ids`) como por empresa específica (`utrecar.employee.company.access.role_ids`).
   - En la pantalla "Personal, Empresas y Roles" (`employee_company_roles.xml` / `employee_company_roles.js`), el selector permite marcar casillas de verificación múltiples por empresa (A.R. Trieste y Utrecar S.L.).
