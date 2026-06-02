# -*- coding: utf-8 -*-
"""
shared - 共享工具模块

提供跨模块使用的工具、常量、配置和异常类。
"""

from ec_as_ai.shared.constants import (
    DEFAULT_SERVER_PORT,
    DEFAULT_MODELS_PATH,
    DEFAULT_CONFIG_PATH,
    DEFAULT_DOMAIN_PATH,
    DEFAULT_ENDPOINTS_PATH,
    DEFAULT_DATA_PATH,
    DegradationReason,
)

from ec_as_ai.shared.exceptions import (
    EcAsException,
    ConfigurationException,
    ModelNotFound,
    InvalidConfigException,
    LLMException,
    TrackerStoreException,
)

__all__ = [
    # 常量
    "DEFAULT_SERVER_PORT",
    "DEFAULT_MODELS_PATH",
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_DOMAIN_PATH",
    "DEFAULT_ENDPOINTS_PATH",
    "DEFAULT_DATA_PATH",
    "DegradationReason",
    # 异常
    "EcAsException",
    "ConfigurationException",
    "ModelNotFound",
    "InvalidConfigException",
    "LLMException",
    "TrackerStoreException",
]
