# Design: Allow additions to an active order

## Context

BOT-RESTO se despliega como una instancia y una base por restaurante. El
objetivo es resolver un caso operativo frecuente sin introducir múltiples
pedidos activos ni infraestructura distribuida.

Un Order confirmado deja de ser completamente inmutable durante una ventana
acotada: se pueden anexar líneas mientras permanezca en `RECEIVED` o
`PREPARING`. Sus líneas anteriores nunca se reescriben ni se eliminan.

## Goals

- Representar el pedido del cliente como una sola operación de cocina y una
  sola entrega.
- Evitar cambios parciales si el cliente abandona la ampliación.
- Informar precio y demora antes de confirmar.
- Resolver correctamente carreras entre una ampliación y un cambio de estado.
- Conservar evidencia del precio y momento de cada incorporación.

## Non-goals

- Modelar pedidos encadenados o subpedidos.
- Replanificar capacidad global de cocina.
- Garantizar una hora exacta de preparación.
- Resolver entrega exactamente una vez de mensajes externos.
- Implementar la interfaz completa del panel dentro de este change.

## Decisions

### One active order

Se conserva el índice único parcial exigido por `DAT-9`. Si el cliente tiene
un Order no terminal, el sistema no crea otro: ofrece ampliar el existente
solo si su estado lo permite.

### Conversational draft

Las líneas nuevas se guardan temporalmente en `Conversation.cart`, asociadas al
`current_order_id`. Elegir productos no modifica el Order. Cancelar el flujo o
alcanzar el timeout descarta solamente ese borrador.

### Explicit confirmation

Antes de confirmar se muestran:

- líneas y cantidades nuevas;
- importe adicional;
- subtotal y total resultantes;
- demora estimada resultante;
- aviso de incorporación inmediata a cocina cuando el estado sea `PREPARING`.

### Append-only confirmed lines

La confirmación inserta líneas nuevas. No combina físicamente una línea nueva
con una anterior del mismo MenuItem, porque podrían tener diferente precio y
momento de incorporación. La presentación puede agruparlas sin perder los
snapshots persistidos.

Cada línea conserva `unit_price_snapshot` y `added_at`.

### ETA as an absolute kitchen deadline

`Order.estimated_kitchen_ready_at` representa una hora absoluta en UTC.

Confirmación inicial:

```text
estimated_kitchen_ready_at =
    confirmed_at + max(initial_item.estimated_time_min)
```

Ampliación:

```text
addition_candidate =
    addition_confirmed_at + max(added_item.estimated_time_min)

new_estimated_kitchen_ready_at = max(
    current_estimated_kitchen_ready_at,
    addition_candidate,
)
```

Para informar la demora se toma el tiempo restante hasta esa hora. En delivery
se suma una sola vez el tiempo de la zona. Los tiempos de los productos no se
suman porque el modelo supone preparación en paralelo.

### Money

Las líneas nuevas capturan sus precios vigentes al confirmar. Se recalculan
`subtotal` y `total` usando `Decimal`. `delivery_fee` no cambia.

### Concurrency boundary

La confirmación respeta el orden normativo de locks:

1. insert de idempotencia del mensaje;
2. `FOR UPDATE` de Conversation;
3. `FOR UPDATE` de Order;
4. revalidación de estado, disponibilidad y precios;
5. inserción de líneas y actualización de importes y ETA;
6. commit;
7. respuesta de WhatsApp y `OrderItemsAdded`.

Si el staff mueve el Order a `READY` antes de que la ampliación obtenga el
lock, la ampliación se rechaza sin cambios parciales. Si la ampliación obtiene
el lock primero, el cambio se confirma completamente antes de que continúe la
transición del staff.

### Notification

Después del commit se emite `OrderItemsAdded`. El panel debe distinguir la
ampliación del aviso original del pedido y mostrar las líneas nuevas.

El evento y los logs no contienen nombre, teléfono ni dirección.

### Accepted consistency gap

El MVP no implementa outbox. Se acepta y documenta la ventana entre el commit
y el envío externo: una caída del proceso puede dejar confirmada la ampliación
sin entregar la respuesta o alerta.

El panel continúa leyendo el Order desde PostgreSQL, los fallos explícitos se
reintentan según config y el riesgo se reevaluará si aparecen pérdidas reales,
reinicios frecuentes, múltiples workers o una exigencia de entrega garantizada.

## Trade-offs

### Benefits

- Una sola identidad de pedido, entrega y tarifa.
- Menor complejidad conversacional que varios Orders activos.
- El carrito abandonado no contamina datos comerciales.
- Historial de precios e incorporaciones preservado.

### Costs

- El total y la estimación de un Order confirmado pueden aumentar.
- Cocina necesita una alerta claramente visible para no omitir líneas nuevas.
- Una ampliación confirmada en `PREPARING` no tiene cancelación individual.
- El ETA sigue siendo una estimación nominal y no modela capacidad global.
- Sin outbox permanece una ventana pequeña de pérdida de mensajes externos.

## Observability

Una ampliación confirmada debería registrar, sin PII:

- `order_id`;
- cantidad de líneas agregadas;
- total anterior y nuevo;
- `estimated_kitchen_ready_at` anterior y nuevo;
- duración del caso de uso.

Errores relevantes:

- estado concurrente incompatible;
- producto agotado durante la confirmación;
- fallo de notificación posterior al commit.

