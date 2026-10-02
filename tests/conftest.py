"""Configuración común de pytest.

Cada test recibe el marker de la carpeta donde vive (`unit` o `integration`),
así ninguno queda sin clasificar y `-m` filtra de forma confiable.
"""

from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).resolve().parent

MARKER_BY_FOLDER = {
    "unit": pytest.mark.unit,
    "integration": pytest.mark.integration,
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        folder = item.path.relative_to(TESTS_ROOT).parts[0]
        marker = MARKER_BY_FOLDER.get(folder)
        if marker is not None:
            item.add_marker(marker)
