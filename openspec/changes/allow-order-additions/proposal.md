# Change: Allow additions to an active order

## Why

En la operación real del restaurante es frecuente que un cliente quiera agregar
productos pocos minutos después de confirmar su pedido. Crear otro pedido
duplicaría la operación de cocina, la tarifa de envío y los flujos de consulta
y cancelación.

El comportamiento vigente en `ORD-7` solo contemplaba modificar el carrito
anterior a la confirmación. Las reglas normativas ya fueron actualizadas para
permitir ampliaciones controladas del mismo Order mientras esté en `RECEIVED`
o `PREPARING`.

## What changes

- Mantener como máximo un Order no terminal por cliente.
- Permitir preparar una ampliación en el carrito conversacional sin modificar
  todavía el Order confirmado.
- Mostrar importe adicional, nuevo total y nueva demora antes de solicitar una
  segunda confirmación explícita.
- Agregar líneas nuevas sin alterar ni eliminar las líneas ya confirmadas.
- Conservar una sola `delivery_fee`.
- Recalcular `estimated_kitchen_ready_at` tomando el máximo entre la estimación
  existente y la estimación de las líneas nuevas.
- Revalidar estado, disponibilidad y precios bajo lock al confirmar.
- Emitir `OrderItemsAdded` después del commit para avisar al panel.

## Impact

El cambio afectará, en etapas posteriores:

- modelo y migración de `Order` y `OrderItem`;
- estado conversacional y carrito JSONB;
- caso de uso de ampliación de pedido;
- repositorios de Orders, MenuItems y Conversation;
- intención de respuesta y adapter de WhatsApp;
- notificación persistente del panel;
- tests de dominio, integración, concurrencia e idempotencia.

## Dependencies

- `WA-4`, `CONV-9` y `CONV-10`: idempotencia y límite transaccional.
- Estados canónicos de Order y restricciones definidas en `ORD-1` a `ORD-5`.
- `DAT-7`: separación de `subtotal`, `delivery_fee` y `total`.
- `CONV-8`: carrito persistido en la fila bloqueada de Conversation.
- `NOT-2` y `NOT-7`: notificaciones persistentes del panel.

Estas dependencias se implementarán en sus changes correspondientes. Este
change no autoriza a adelantarlas de manera silenciosa.

## Non-goals

- Permitir más de un Order no terminal por cliente.
- Agregar productos cuando el Order está `READY`, `ON_THE_WAY` o terminal.
- Restar cantidades o eliminar líneas después de la confirmación inicial.
- Cancelar individualmente una línea confirmada.
- Cobrar una segunda tarifa de envío.
- Incorporar pagos en línea.
- Implementar un outbox.
- Agregar interpretación de lenguaje libre o IA.

