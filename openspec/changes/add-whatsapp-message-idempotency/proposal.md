# Change: Add WhatsApp inbound message idempotency

## Why

WhatsApp puede entregar más de una vez el mismo mensaje. Sin una barrera
persistente, un retry del proveedor o dos entregas concurrentes podrían aplicar
dos veces el mismo efecto: crear un pedido, ampliar uno existente, cancelar una
operación o avanzar dos veces la conversación.

La regla `WA-4` exige registrar el `message_id` antes de procesar y cortar los
duplicados. `CONV-9` y `CONV-10` exigen además un orden de locks fijo y que la
marca de idempotencia comparta transacción con el efecto de dominio.

## What changes

- Agregar `processed_whatsapp_messages` con `message_id` como PK de texto y
  `received_at` como `TIMESTAMPTZ` en UTC.
- Insertar el identificador mediante `INSERT ... ON CONFLICT DO NOTHING
  RETURNING message_id`.
- Procesar solamente cuando el insert devuelve la fila nueva.
- Ejecutar el insert, el lock de Conversation y el efecto de dominio dentro de
  una única transacción.
- Hacer rollback de todo, incluida la marca, si el procesamiento falla.
- Responder 200 sin repetir efectos cuando el mensaje ya fue procesado.
- Enviar respuestas y notificaciones externas solamente después del commit.

## Impact

El cambio afectará, en etapas posteriores:

- modelo SQLAlchemy y migración Alembic;
- repositorio de idempotencia del adapter de WhatsApp;
- orquestación transaccional del webhook;
- respuesta HTTP de duplicados y errores;
- tests de integración y concurrencia contra PostgreSQL.

## Dependencies

- Verificación de firma definida por `WA-3` antes de abrir el procesamiento.
- Repositorio y lock de Conversation definidos por `CONV-2`.
- Límite transaccional y orden de locks de `CONV-9` y `CONV-10`.

El modelo y la migración pueden implementarse antes que el webhook completo,
pero el change no se considera terminado hasta probar el flujo transaccional.

## Non-goals

- Guardar el payload completo del webhook.
- Registrar texto, teléfono, dirección u otra PII en esta tabla.
- Rastrear mensajes salientes, entregados o leídos.
- Implementar un outbox.
- Garantizar entrega exactamente una vez hacia sistemas externos.
- Definir una política automática de borrado en el MVP.
- Particionar la tabla o agregar índices distintos de su PK sin una consulta
  real que los justifique.

