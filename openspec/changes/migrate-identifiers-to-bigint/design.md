# Design: BIGINT internal identifiers

## Context

La migración inicial declara todas las PK y FK como `sa.Integer()`. Los modelos
SQLAlchemy omiten el tipo explícito en las PK y lo infieren desde
`Mapped[int]`, lo que también produce `INTEGER`.

Python no diferencia entre un entero de 32 y 64 bits para estos atributos. La
diferencia relevante está en PostgreSQL y debe expresarse con `BigInteger` en
el mapping para que el modelo represente la intención real del esquema.

## Goals

- Dejar todas las PK y FK internas existentes en `BIGINT`.
- Mantener exactamente el mismo tipo en cada PK y sus FK dependientes.
- Preservar integridad referencial, índices y autogeneración de IDs.
- Introducir el cambio mediante una migración separada y reversible.
- Detectar de forma explícita un downgrade que perdería rango.

## Non-goals

- Cambiar la identidad pública de las entidades.
- Crear tablas nuevas.
- Modificar reglas del dominio o relaciones ORM.
- Optimizar índices o consultas no relacionadas.
- Diseñar todavía las tablas append-only futuras.

## Affected columns

```text
customers.id
menu_items.id
orders.id
orders.customer_id
order_items.id
order_items.order_id
order_items.menu_item_id
reservations.id
reservations.customer_id
conversations.id
conversations.customer_id
conversations.current_order_id
```

Todas esas columnas terminarán como `BIGINT`. `Mapped[int]` se conserva porque
el tipo de aplicación sigue siendo un entero Python.

## Model mapping

Las PK se declararán explícitamente:

```python
id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
```

Las FK también declararán `BigInteger` antes de `ForeignKey`. No se confía en
la inferencia para una decisión física de esquema que debe permanecer visible
en el modelo.

## Migration strategy

La migración inicial no se edita porque puede haber sido aplicada en algún
entorno. Una revisión posterior convierte las columnas existentes.

El `upgrade()` debe:

1. preservar o recrear temporalmente las FK según lo que requiera PostgreSQL;
2. convertir cada PK y sus FK dependientes a `BIGINT`;
3. restaurar las FK con sus acciones actuales de borrado;
4. conservar PK, índices, unicidad y generación automática de IDs;
5. no modificar datos ni relaciones existentes.

La revisión no se acepta únicamente porque Alembic la autogenere. Se revisarán
manualmente tipos, nombres de constraints, secuencias y orden de operaciones.

## Downgrade safety

Convertir `BIGINT` a `INTEGER` es seguro solamente si todos los valores caben
en el rango de PostgreSQL `INTEGER`. Antes de alterar columnas, el downgrade
debe comprobar las PK relevantes y abortar con un error claro si encuentra un
valor fuera de rango.

Si todos los valores son representables, el downgrade restaura PK y FK a
`INTEGER` sin perder filas ni relaciones. PostgreSQL ejecuta la migración de
forma transaccional para evitar un esquema parcialmente convertido ante un
fallo.

## Deployment and operational risk

Alterar tipos puede adquirir locks y, según la versión y la operación elegida,
requerir trabajo proporcional al tamaño de las tablas e índices. Por eso este
cambio se hace temprano y no se aplicará automáticamente sobre producción.

Antes de una ejecución real se debe conocer:

- cantidad de filas y tamaño de las tablas;
- versión de PostgreSQL;
- ventana de mantenimiento disponible;
- existencia de conexiones o transacciones largas.

En el estado actual, con tablas pequeñas o vacías, una migración directa es la
opción de menor complejidad. No se justifica una migración online por etapas.

## Trade-offs

### Benefits

- Mucho mayor rango antes del agotamiento de IDs.
- Evita una conversión más riesgosa con tablas grandes.
- Mantiene PK compactas y ordenables frente a usar UUID aleatorio.

### Costs

- Cada valor e índice de identificador usa más espacio que `INTEGER`.
- El upgrade puede bloquear temporalmente las tablas afectadas.
- El downgrade deja de ser posible después de superar el rango de `INTEGER`.

## Observability

La migración debe registrar su éxito o error mediante el mecanismo habitual de
Alembic, sin imprimir datos de filas. En producción interesan especialmente la
duración, espera por locks y espacio adicional consumido.
