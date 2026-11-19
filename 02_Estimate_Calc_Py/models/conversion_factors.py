"""
Conversion Factors Model for NSO Crop Estimation.
"""
from dataclasses import dataclass

@dataclass
class ConversionFactors:
    """
    Encapsulates driage ratio, recovery ratio, and plot-to-hectare conversion factor.
    
    Attributes:
        driage_ratio (float): Ratio of dry weight to green weight (d <= 1.0).
        recovery_ratio (float): Processing / recovery ratio (r <= 1.0).
        conversion_factor (float): Factor to convert experimental plot weight (g)
                                   to hectare yield (kg/ha).
    """
    driage_ratio: float = 1.0
    recovery_ratio: float = 1.0
    conversion_factor: float = 1.0

    @property
    def ccf(self) -> float:
        """
        Composite Conversion Factor (CCF) = driage_ratio * recovery_ratio * conversion_factor.
        """
        return self.driage_ratio * self.recovery_ratio * self.conversion_factor

    def validate(self) -> None:
        """Validates that all factors are non-negative numbers."""
        if self.driage_ratio < 0:
            raise ValueError(f"Driage ratio must be non-negative, got {self.driage_ratio}")
        if self.recovery_ratio < 0:
            raise ValueError(f"Recovery ratio must be non-negative, got {self.recovery_ratio}")
        if self.conversion_factor < 0:
            raise ValueError(f"Conversion factor must be non-negative, got {self.conversion_factor}")
