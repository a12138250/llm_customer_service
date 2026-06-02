# -*- coding: utf-8 -*-
"""
LLM微调模块

提供微调数据生成和句子改写功能。
"""

from ec_as_ai.training.finetune.data_generator import (
    FinetuneDataGenerator,
    FinetuneConfig,
    FinetuneExample,
)
from ec_as_ai.training.finetune.paraphraser import (
    Paraphraser,
    ParaphraserConfig,
)

__all__ = [
    "FinetuneDataGenerator",
    "FinetuneConfig",
    "FinetuneExample",
    "Paraphraser",
    "ParaphraserConfig",
]
