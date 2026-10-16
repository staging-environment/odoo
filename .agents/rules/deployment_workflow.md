# Regla de Flujo de Trabajo: Commit y Despliegue Automático en Producción

## Política Obligatoria
Cada vez que se complete un cambio de código, corrección o mejora solicitada por el usuario en este repositorio:

1. **Commit y Push:**
   - Realizar `git add` de los archivos modificados relevantes.
   - Crear un commit descriptivo y conciso (formato convencional `feat(...)`, `fix(...)`, `refactor(...)`, etc.).
   - Hacer `git push origin main`.

2. **Despliegue Inmediato en Producción:**
   - Conectarse al servidor de producción vía SSH (`utrecar-dev` o `developer@164.68.101.69`).
   - En la ruta `/home/developer/Projects/odoo`:
     - Ejecutar `git pull origin main`.
     - Reiniciar el contenedor Odoo con `docker restart ddev-odoo-odoo` (o actualizar el módulo con `-u <modulo>` si hay cambios en modelos o vistas de base de datos).
     - Verificar que el contenedor esté activo e inicializado (`docker logs --tail 10 ddev-odoo-odoo`).
