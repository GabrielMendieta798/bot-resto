# Design: WhatsApp inbound message idempotency

## Context

Meta usa entrega al menos una vez: puede repetir un webhook cuando no obtiene
una respuesta satisfactoria o entregar concurrentemente el mismo mensaje. La
aplicación necesita distinguir un retry del proveedor de una nueva intención
del cliente.

Una deduplicación en memoria no sirve porque se pierde al reiniciar y no se
comparte entre procesos. Una consulta seguida de insert tampoco es segura:
dos transacciones pueden consultar al mismo tiempo y ambas creer que el mensaje
es nuevo. La unicidad debe decidirla PostgreSQL.

## Goals

- Aplicar como máximo una vez el efecto de dominio de cada `message_id`.
- Permitir un retry real cuando el procesamiento anterior hizo rollback.
- Resolver correctamente dos entregas concurrentes del mismo mensaje.
- Mantener la tabla mínima y libre de PII.
- Preservar el orden de locks normativo.

## Non-goals

- Evitar duplicados de mensajes salientes.
- Resolver la brecha entre commit y envío externo.
- Almacenar webhooks para debugging o replay manual.
- Introducir un broker, cache distribuido o infraestructura adicional.

## Data model

```text
processed_whatsapp_messages
-----------------------------------------
message_id   TEXT         PRIMARY KEY
received_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
```

`message_id` es la clave de consulta real y por eso se usa directamente como
PK. Un ID numérico adicional no aportaría una identidad nueva y obligaría a
mantener otro índice único.

`TEXT` evita asumir una longitud máxima del proveedor. `received_at` permite
observar crecimiento y antigüedad, pero no necesita un índice en el MVP.

No se persisten payload, tipo, cliente ni estados salientes. La tabla indica
únicamente que ese mensaje entrante ya produjo un commit exitoso.

## Transaction ownership

La transacción pertenece al caso de uso que procesa un mensaje entrante. El
repositorio de idempotencia no hace `commit` ni abre una transacción separada.

El flujo obligatorio es:

```text
validar firma
    ↓
abrir transacción del mensaje
    ↓
INSERT idempotente del message_id
    ↓
si es duplicado: terminar sin efectos
    ↓
SELECT ... FOR UPDATE de Conversation
    ↓
efecto de dominio y otros locks necesarios
    ↓
commit
    ↓
respuesta de WhatsApp y notificaciones externas
```

La operación de claim usa conceptualmente:

```sql
INSERT INTO processed_whatsapp_messages (message_id)
VALUES (:message_id)
ON CONFLICT (message_id) DO NOTHING
RETURNING message_id;
```

Si retorna una fila, esta transacción adquirió el mensaje. Si no retorna, el
mensaje ya fue confirmado por otra transacción y no se procesa.

## Failure behavior

### Failure before commit

Una excepción revierte la marca de idempotencia junto con cualquier cambio de
dominio. El webhook responde 5xx y registra el `message_id` sin payload ni PII.
Cuando Meta reintenta, el insert vuelve a poder ganar.

### Duplicate after successful commit

El insert no retorna fila. El webhook responde 200 sin cuerpo útil y no toma el
lock de Conversation ni repite efectos o envíos.

### Crash after commit and before external send

El mensaje queda marcado como procesado y un retry se corta como duplicado. La
respuesta o notificación externa podría perderse. Esta es la brecha aceptada y
documentada al diferir el outbox; este change no intenta ocultarla.

## Concurrent delivery

Dos transacciones que insertan el mismo `message_id` se coordinan mediante la
PK de PostgreSQL. Solo una puede conservar la fila. La otra espera la resolución
del conflicto y luego continúa como duplicado o puede ganar si la primera hace
rollback.

No se hace primero un `SELECT`, porque ese patrón deja una carrera entre la
consulta y el insert.

## Batched webhooks

Si un payload contiene varios mensajes, cada `message_id` se procesa en su
propia transacción. Si uno falla, los ya confirmados permanecen confirmados y el
webhook puede responder 5xx. En el retry, los exitosos se cortan como duplicados
y solamente los que hicieron rollback vuelven a procesarse.

## Retention

El MVP no elimina filas automáticamente. Borrar una PK permite que un replay
antiguo vuelva a producir efectos. El volumen por instancia se medirá antes de
definir una retención segura.

## Security and observability

Se puede registrar:

- `message_id`;
- resultado `claimed`, `duplicate` o `rolled_back`;
- duración del procesamiento.

No se registra el payload, texto, teléfono ni dirección. El SQL logging sigue
apagado en producción según `DAT-10`.

Métricas futuras útiles:

- `whatsapp_messages_claimed_total`;
- `whatsapp_messages_duplicate_total`;
- `whatsapp_message_processing_failed_total`.

No se agrega infraestructura de métricas dentro de este change si aún no existe.

## Trade-offs

### Benefits

- Corrección frente a retries y concurrencia sin servicios adicionales.
- La misma transacción permite reintentar fallos reales.
- Modelo pequeño y fácil de consultar.

### Costs

- Crecimiento continuo hasta definir retención.
- Una PK de texto ocupa más que una PK numérica, aunque evita un índice único
  adicional y el volumen por restaurante es bajo.
- No recupera envíos externos perdidos después del commit.

