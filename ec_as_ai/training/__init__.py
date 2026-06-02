# -*- coding: utf-8 -*-
"""
训练模块

提供模型训练和打包功能。
"""

from ec_as_ai.training.trainer import Trainer, TrainerConfig
from ec_as_ai.training.model_storage import (
    ModelMetadata,
    create_model_package,
    extract_model_archive,
    get_latest_model,
    get_model_path,
    load_metadata_from_archive,
)
from ec_as_ai.training.finetune import (
    FinetuneDataGenerator,
    FinetuneConfig,
    FinetuneExample,
    Paraphraser,
    ParaphraserConfig,
)

__all__ = [
    "Trainer",
    "TrainerConfig",
    # Model Storage
    "ModelMetadata",
    "create_model_package",
    "extract_model_archive",
    "get_latest_model",
    "get_model_path",
    "load_metadata_from_archive",
    # Finetune
    "FinetuneDataGenerator",
    "FinetuneConfig",
    "FinetuneExample",
    "Paraphraser",
    "ParaphraserConfig",
]
