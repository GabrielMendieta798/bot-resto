# Change: Add menu and customer repositories

## Why

Los modelos `Customer` y `MenuItem` existen y están migrados, pero nadie los
puede usar sin tocar la `Session` a mano: no hay repositorio, servicio ni
schemas. UC-03 (ver el menú por categorías), UC-17 (marcar un item agotado o
disponible) y UC-18 (editar nombre, descripción, precio y tiempo estimado)
necesitan esa capa, y todo flujo de WhatsApp necesita identificar al cliente
por su número. Este change construye la capa de datos y de servicios que las
pantallas del panel y el guion de WhatsApp van a consumir.

El negocio impone tres cosas que esta capa tiene que garantizar y no dejar en
manos de quien llame:

- Sacar un plato de la carta en segundos sin borrarlo, porque mañana vuelve
  (`DAT-5`), y que el staff vea los agotados para rehabilitarlos.
- Actualizar precios seguido por inflación sin alterar el monto de un pedido
  ya confirmado (`DAT-4`).
- Que un mismo número de WhatsApp nunca produzca dos customers, ni escribiendo
  dos veces ni con dos mensajes simultáneos.

Los dos modelos se escribieron sin spec. Este change los absorbe y los evalúa
contra las reglas como si fueran código nuevo (`SDD-7`); el resultado está en
design.md, sección "Evaluación de los modelos existentes".

### Orden del plan (`SDD-6`)

Respecto del plan de `AI_WORKFLOW.md`, el alcance coincide con
`01-cimientos-datos` ("repos base + MenuItem") más la porción `Customer` de
`02-pedidos-core`. El change `00-walking-skeleton` todavía no se hizo.

Lautaro aprobó explícitamente adelantar este change el 10/10/2026. El orden
de los changes está registrado en PENDIENTES, como tarea inmediata de
Lautaro.

## What Changes

- **Módulo `menu`**: servicio y schemas en `backend/app/domain/menu/`, y
  repositorio en `backend/app/db/repositories/menu.py`. Sirven para listar categorías con al menos un item disponible, listar los
  items disponibles de una categoría (cliente), listar todos los items
  incluidos los agotados (staff), obtener un item por id, fijar la
  disponibilidad de forma explícita e idempotente, y editar de forma parcial
  nombre, descripción, precio y tiempo estimado.
- **Módulo `customers`**: servicio y schemas en
  `backend/app/domain/customers/`, y repositorio en
  `backend/app/db/repositories/customers.py`. Sirven para obtener o crear un customer por su teléfono en forma
  canónica (solo dígitos, de 8 a 15). La unicidad la garantiza el índice único
  de `customers.phone`, no un chequeo previo.
- **Frontera de datos del dominio**: los repositorios son el único código que
  toca la `Session`. Pueden hacer flush, pero nunca commit ni rollback: quien
  llama es dueño de la transacción (`CONV-10`). Los repositorios viven fuera
  del dominio, en `backend/app/db/repositories/`. Nada bajo
  `backend/app/domain/` importa SQLAlchemy, `app.models` ni `app.db` (lectura
  estricta de `GEN-1`). Los servicios reciben el repositorio como `Protocol`.
  Un test de AST recorre todo el paquete `domain` y lo verifica.
- **Validación en dos capas** (`VAL-1`, `VAL-3`):
  - **La forma la valida `MenuItemUpdate` (Pydantic):** tipos, largos, campos
    requeridos, nulidad y campos desconocidos. Un `null` explícito en
    nombre, precio o tiempo estimado es error de forma, así el tiempo nunca
    vuelve a `NULL`. Sus errores siguen el camino de `ValidationError` del
    contrato de errores.
  - **Las reglas las valida el servicio, con `InvalidInputError`:** precio no
    negativo, a lo sumo dos decimales y dentro de `Numeric(12,2)`, y tiempo
    estimado no negativo y dentro de rango.
  - **El teléfono canónico lo valida el servicio de customers, con
    `InvalidInputError`.**
  - **Ningún error repite el valor rechazado.** Los importes son siempre
    `Decimal` y los timestamps siempre tienen zona horaria.
- **Prerrequisito que se registra:** el `NOT NULL` de
  `menu_items.estimated_time_min` es prerrequisito del change de pedidos
  (`ORD-12`). Este change no migra; deja el escenario escrito y la deuda
  anotada para `ESTADO.md`.
- **Tests**: unitarios de los servicios con repositorios falsos en memoria, y
  de integración de los repositorios contra PostgreSQL real, incluida la
  creación concurrente del mismo customer en paralelo (`VER-2`).

No hay cambios de esquema ni de modelos. No hay endpoints.

## Capabilities

### New Capabilities

- `menu-catalog`: consulta del menú por categoría para el cliente y completa
  para el staff, disponibilidad explícita sin borrado, y edición parcial con
  validación de importes y tiempos.
- `customer-registry`: obtener o crear un customer por teléfono canónico, sin
  duplicados aunque haya concurrencia, y sin exponer el teléfono en errores
  ni logs.
- `domain-data-boundary`: reglas que comparten todos los módulos de dominio:
  quién es dueño de la transacción, qué ve un servicio, y los tipos de los
  importes y timestamps que devuelve un repositorio.

### Modified Capabilities

Ninguna. Este change cumple el requirement "Exception messages carry no
customer data" de `structured-logging` sin modificarlo.

## Impact

- **Código nuevo**:
  - `backend/app/domain/__init__.py`
  - `backend/app/domain/menu/{__init__,service,schemas}.py`
  - `backend/app/domain/customers/{__init__,service,schemas}.py`
  - `backend/app/db/__init__.py`
  - `backend/app/db/repositories/{__init__,menu,customers}.py`
  - sus tests en `tests/unit/` y `tests/integration/`.

  `db/` es el destino que nombra la deuda D-5. `core/database.py` se queda
  donde está; moverlo es parte de esa deuda.
- **Código que no se toca**: `backend/app/models/`, `backend/alembic/`,
  `backend/app/core/` y `backend/app/api/`. Las excepciones que se usan
  (`InvalidInputError`, `NotFoundError`) ya existen y ya están mapeadas a
  400 y 404 (`API-3`).
- **Dependencias**: ninguna nueva.
- **Tests de integración**: siguen necesitando la PostgreSQL de
  `DATABASE_URL` (contenedor `bot-resto-db`). El test de concurrencia
  commitea y limpia sus propias filas; el resto corre dentro de una
  transacción que se revierte.

## Non-goals

- Endpoints HTTP, pantallas del panel (UC-17, UC-18) y guion de WhatsApp
  (UC-03).
- `Order`, `OrderItem`, `Conversation` y `Reservation`, y cualquier tarea de
  `add-whatsapp-message-idempotency`, `allow-order-additions` o
  `migrate-identifiers-to-bigint`. Los tests insertan `Order` y `OrderItem`
  como fixture, sin tocar sus modelos.
- Migraciones y cualquier cambio en `backend/alembic/` o `backend/app/models/`.
- Mover o reestructurar los modelos, o mover `core/database.py` a `db/`
  (deuda D-5).
- La migración `NOT NULL` de `estimated_time_min`: es prerrequisito del
  change de pedidos.
- Normalizar los teléfonos que manda Meta: es del adapter de WhatsApp.
- Alta y baja de items del menú (carga inicial): otro change. El borrado
  físico queda prohibido por `DAT-5`.
- El patrón de inyección para endpoints (dependencias de FastAPI, unit of
  work): lo define el change del webhook.
- Paginación de listas: es del adapter de WhatsApp.
- Auditoría de quién editó un item (`PAN-4`): va con el panel, que es donde
  existe un "quién".
