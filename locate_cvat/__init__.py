"""
Locate CVAT - High Performance Universal Annotation Framework.
"""

from locate_cvat.label_registry import (
    LabelRegistry,
    LabelType,
    LabelItem,
    LabelAttribute,
    SkeletonConfig,
    SkeletonNode,
)
from locate_cvat.translators import (
    COCOTranslator,
    SkeletonCOCOTranslator,
    CuboidAndPolylineTranslator,
)

__version__ = "1.0.0"

__all__ = [
    "LabelRegistry",
    "LabelType",
    "LabelItem",
    "LabelAttribute",
    "SkeletonConfig",
    "SkeletonNode",
    "COCOTranslator",
    "SkeletonCOCOTranslator",
    "CuboidAndPolylineTranslator",
]
