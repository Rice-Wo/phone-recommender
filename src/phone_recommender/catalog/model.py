from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Phone:
    """單一手機規格強型別資料模型（對應 phones 資料表，完全不可變）"""
    slug: str
    name: str
    brand: str
    release_date: Optional[str]
    ram_gb: Optional[float]
    battery_mah: Optional[int]
    weight_g: Optional[float]
    os: Optional[str]
    storage_options_gb: tuple[int, ...]
    soc: Optional[str]
    display_resolution: Optional[str]
    display_type: Optional[str]
    display_size_inch: Optional[float]
    display_ppi: Optional[float]
    soc_raw: Optional[str]
    soc_score: Optional[float]
    normalized_soc_score: Optional[float]
