# Change: Migrate internal identifiers to BIGINT

## Why

La migración inicial crea las claves primarias y foráneas internas como
`INTEGER`. Ese tipo alcanza aproximadamente 2.147 millones de valores
positivos, pero cambiarlo cuando las tablas ya contienen muchos pedidos,
conversaciones, historiales o notificaciones puede requerir locks prolongados
y una migración operativamente costosa.

El proyecto todavía está en una etapa temprana. Este es el momento de alinear
el esquema con el crecimiento esperado y evitar que una limitación conocida se
convierta más adelante en una migración de emergencia.

## What changes

- Cambiar a `BIGINT` todas las claves primarias internas existentes.
- Cambiar a `BIGINT` todas las claves foráneas que las referencian.
- Declarar el tipo explícitamente como `BigInteger` en SQLAlchemy.
- Mantener `int` como tipo Python de los atributos ORM.
- Crear una revisión Alembic nueva sin modificar la migración inicial.
- Preservar claves primarias, claves foráneas, índices, unicidad y generación
  automática de identificadores.
- Proteger el downgrade para que no intente convertir a `INTEGER` valores que
  estén fuera de su rango.

## Impact

El cambio afecta:

- los modelos `Customer`, `MenuItem`, `Order`, `OrderItem`, `Reservation` y
  `Conversation`;
- las PK y FK existentes en PostgreSQL;
- una nueva migración Alembic;
- tests de upgrade, integridad referencial, autoincremento y downgrade contra
  PostgreSQL real.

No cambia contratos HTTP, reglas de negocio, estados ni el tipo Python usado
por la aplicación.

## Dependencies

- `DAT-6`: todo cambio de esquema se versiona mediante Alembic.
- `GEN-6`: cualquier timestamp tocado por cambios posteriores seguirá usando
  `TIMESTAMPTZ`; este change no modifica timestamps.
- `VER-4`: la migración debe probarse en upgrade y downgrade contra
  PostgreSQL.

Este change se completa antes de agregar nuevas tablas con identificadores
internos. La tabla de idempotencia de WhatsApp queda fuera porque usa
`message_id TEXT` como clave natural.

## Non-goals

- Agregar `processed_whatsapp_messages` o implementar idempotencia.
- Cambiar cantidades como `quantity`, `people` o `estimated_time_min`.
- Reemplazar identificadores internos por UUID.
- Agregar identificadores públicos.
- Corregir estados, importes, índices operativos u otros hallazgos del feedback.
- Aplicar automáticamente la migración sobre una base compartida o de
  producción.
