"""Repositorio de customers sobre SQLAlchemy (DAT-2, DAT-3).

Recibe una `Session` abierta y no controla la transacción: no hace commit,
rollback ni begin. Quien abrió la transacción decide si sus efectos persisten
(CONV-10). Devuelve schemas del dominio, nunca objetos ORM.

Supuesto: el caller corre en `read committed` (el default de PostgreSQL). En
`repeatable read` o `serializable`, la carrera de `get_or_create` termina en un
error de serialización en lugar de devolver el customer existente (design D4).
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.customers.schemas import CustomerRead
from app.domain.customers.service import CustomerRepository
from app.models.customer import Customer

_COLUMNS = (Customer.id, Customer.phone, Customer.name, Customer.created_at)


class SqlCustomerRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create(self, phone: str) -> CustomerRead:
        """El customer de ese teléfono, insertándolo si no existe.

        Primero el `INSERT`, nunca un `SELECT` previo: el índice único de
        `customers.phone` resuelve la carrera. Si otra transacción insertó el
        mismo número y no commiteó, este `INSERT` espera a que termine. Si
        commitea, el `ON CONFLICT DO NOTHING` no devuelve fila y el `SELECT`
        siguiente (snapshot nuevo en `read committed`) la encuentra. Si hace
        rollback, el `INSERT` procede.
        """
        inserted = self._session.execute(
            insert(Customer)
            .values(phone=phone)
            .on_conflict_do_nothing(index_elements=[Customer.phone])
            .returning(*_COLUMNS)
        ).one_or_none()
        row = (
            inserted
            if inserted is not None
            else self._session.execute(
                select(*_COLUMNS).where(Customer.phone == phone)
            ).one()
        )
        return CustomerRead.model_validate(dict(row._mapping))


# Conformidad con la interfaz del dominio: mypy estricto falla acá si el
# repositorio deja de cumplir `CustomerRepository` (design D1).
_CONFORMS_TO_PROTOCOL: type[CustomerRepository] = SqlCustomerRepository
