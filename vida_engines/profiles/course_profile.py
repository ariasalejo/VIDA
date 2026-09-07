from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Mapping


@dataclass(frozen=True)
class CourseProfile:
    """
    Contrato de configuración de un curso para VIDA.

    IMPORTANTE:
        Este objeto describe EL CURSO.
        No contiene progreso personal.

    Separaciones fundamentales:
        configuración != progreso
        progreso != evidencia
        evidencia != certificación

    El perfil debe ser:
        - determinista
        - validable
        - inmutable
        - reutilizable
        - independiente de la UI
    """

    course_id: str
    name: str
    version: str = "1.0"

    components: dict[str, bool] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    # ---------------------------------------------------------
    # COMPONENTES
    # ---------------------------------------------------------

    def has_component(self, component: str) -> bool:
        """Indica si un componente está habilitado."""
        self._validate_component_name(component)
        return bool(self.components.get(component, False))

    def enabled_components(self) -> list[str]:
        """Devuelve componentes habilitados, ordenados."""
        return sorted(
            name
            for name, enabled in self.components.items()
            if enabled
        )

    # ---------------------------------------------------------
    # PESOS
    # ---------------------------------------------------------

    def weight(self, component: str) -> float:
        """
        Obtiene el peso de un componente.

        Alias admitidos:
            video    -> videos
            activity -> activities
            mastery  -> concepts
        """
        self._validate_component_name(component)

        value = self.weights.get(component, 0.0)

        try:
            value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"El peso '{component}' no es numérico."
            ) from exc

        if not isfinite(value):
            raise ValueError(
                f"El peso '{component}' debe ser finito."
            )

        if value < 0:
            raise ValueError(
                f"El peso '{component}' no puede ser negativo."
            )

        return value

    def weighted_components(self) -> list[str]:
        """Devuelve componentes con peso positivo."""
        return sorted(
            name
            for name in self.weights
            if self.weight(name) > 0
        )

    def total_weight(self) -> float:
        """Suma todos los pesos declarados."""
        return sum(
            self.weight(name)
            for name in self.weights
        )

    # ---------------------------------------------------------
    # METADATA
    # ---------------------------------------------------------

    def metadata_value(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Obtiene metadata sin modificar el perfil.
        """
        if not isinstance(key, str):
            raise TypeError("metadata key debe ser str.")

        return self.metadata.get(key, default)

    # ---------------------------------------------------------
    # VALIDACIÓN
    # ---------------------------------------------------------

    def validate(self) -> None:
        """
        Valida la integridad completa del perfil.

        No modifica el objeto.
        """

        if not isinstance(self.course_id, str):
            raise TypeError("course_id debe ser str.")

        if not self.course_id.strip():
            raise ValueError(
                "course_id no puede estar vacío."
            )

        if not isinstance(self.name, str):
            raise TypeError("name debe ser str.")

        if not self.name.strip():
            raise ValueError(
                "name no puede estar vacío."
            )

        if not isinstance(self.version, str):
            raise TypeError("version debe ser str.")

        if not self.version.strip():
            raise ValueError(
                "version no puede estar vacío."
            )

        if not isinstance(self.components, dict):
            raise TypeError(
                "components debe ser dict."
            )

        if not isinstance(self.weights, dict):
            raise TypeError(
                "weights debe ser dict."
            )

        # -----------------------------------------------------
        # COMPONENTES
        # -----------------------------------------------------

        for component, enabled in self.components.items():
            self._validate_component_name(component)

            if not isinstance(enabled, bool):
                raise TypeError(
                    f"El componente '{component}' "
                    "debe tener valor bool."
                )

        # -----------------------------------------------------
        # PESOS
        # -----------------------------------------------------

        for component in self.weights:
            self._validate_component_name(component)

            weight = self.weight(component)

            if weight > 0 and not self.has_component(
                self._component_name(component)
            ):
                raise ValueError(
                    f"El componente '{component}' "
                    f"tiene peso {weight}, "
                    "pero no está habilitado."
                )

        total = self.total_weight()

        if total > 1.000001:
            raise ValueError(
                "La suma de pesos no puede superar 1.0: "
                f"{total}"
            )

        # -----------------------------------------------------
        # METADATA
        # -----------------------------------------------------

        if not isinstance(self.metadata, dict):
            raise TypeError(
                "metadata debe ser dict."
            )

    # ---------------------------------------------------------
    # UTILIDADES INTERNAS
    # ---------------------------------------------------------

    @staticmethod
    def _validate_component_name(component: str) -> None:
        if not isinstance(component, str):
            raise TypeError(
                "El nombre del componente debe ser str."
            )

        if not component.strip():
            raise ValueError(
                "El nombre del componente no puede estar vacío."
            )

    @staticmethod
    def _component_name(weight_name: str) -> str:
        """
        Traduce nombres de pesos a nombres de componentes.
        """
        aliases = {
            "video": "videos",
            "activity": "activities",
            "mastery": "concepts",
            "evidence": "evidence",
            "project": "projects",
        }

        return aliases.get(
            weight_name,
            weight_name,
        )
