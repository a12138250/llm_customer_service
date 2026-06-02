# -*- coding: utf-8 -*-
"""
ec_as_ai API模块

提供基于FastAPI的Web服务接口。
"""

from ec_as_ai.api.server import EcAsServer, create_app

__all__ = [
    "EcAsServer",
    "create_app",
]
