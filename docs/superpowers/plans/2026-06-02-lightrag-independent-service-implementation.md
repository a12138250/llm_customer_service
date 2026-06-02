# LightRAG Independent Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a LightRAG Server backed retriever adapter and switch the demo knowledge retrieval path from the current Neo4j GraphRAG demo to the new independent LightRAG service integration.

**Architecture:** Keep the existing `InformationRetrieval` and `EnterpriseSearchPolicy` boundary unchanged. Add `ecs_demo.addons.lightrag_retrieval.LightRAGRetriever`, which calls LightRAG Server over HTTP, maps returned reference chunks into `SearchResult`, and lets the existing policy generate the final customer service answer.

**Tech Stack:** Python 3.10+, `httpx.AsyncClient`, existing `ec_as_ai.retrieval.base_retriever.SearchResult`, existing `ec_as_ai.shared.timing`, pytest.

---

## File Structure

- Create `ecs_demo/addons/lightrag_retrieval.py`: LightRAG HTTP adapter implementing `InformationRetrieval`.
- Modify `ecs_demo/addons/__init__.py`: export `LightRAGRetriever` while keeping `GraphRAG`.
- Modify `ecs_demo/config.yml`: point `EnterpriseSearchPolicy.vector_store` to `addons.lightrag_retrieval.LightRAGRetriever`.
- Modify `ecs_demo/endpoints.yml`: replace Neo4j connection values under `vector_store` with LightRAG Server values.
- Create `tests/test_lightrag_retrieval.py`: focused unit tests for adapter config, payload, result mapping, error behavior, and tracker history conversion.
- Modify `README.md`: document LightRAG service mode and keep the GraphRAG demo as a legacy note.

## Task 1: Adapter Tests

**Files:**
- Create: `tests/test_lightrag_retrieval.py`

- [ ] **Step 1: Write failing tests for the new adapter**

Create `tests/test_lightrag_retrieval.py` with this content:

```python
import pytest

from ec_as_ai.retrieval.base_retriever import SearchResult
from ecs_demo.addons.lightrag_retrieval import LightRAGRetriever


class FakeLightRAGRetriever(LightRAGRetriever):
    def __init__(self, response=None, error=None):
        super().__init__()
        self.response = response or {}
        self.error = error
        self.calls = []

    async def _post_query(self, payload, headers):
        self.calls.append({"payload": payload, "headers": headers})
        if self.error:
            raise self.error
        return self.response


def test_connect_normalizes_config():
    retriever = LightRAGRetriever()

    retriever.connect(
        {
            "base_url": "http://127.0.0.1:9621/",
            "api_key": "secret",
            "mode": "hybrid",
            "include_references": False,
            "include_chunk_content": False,
            "timeout": 30,
        }
    )

    assert retriever.base_url == "http://127.0.0.1:9621"
    assert retriever.api_key == "secret"
    assert retriever.mode == "hybrid"
    assert retriever.include_references is False
    assert retriever.include_chunk_content is False
    assert retriever.timeout == 30.0


@pytest.mark.asyncio
async def test_search_sends_payload_and_api_key_header():
    retriever = FakeLightRAGRetriever(
        response={
            "response": "LightRAG generated answer",
            "references": [
                {
                    "reference_id": "1",
                    "file_path": "docs/return-policy.md",
                    "content": ["7天无理由退货需要商品保持完好。"],
                }
            ],
        }
    )
    retriever.connect(
        {
            "base_url": "http://localhost:9621",
            "api_key": "secret",
            "mode": "mix",
        }
    )

    results = await retriever.search(
        "退货规则是什么？",
        top_k=3,
        tracker_state={
            "events": [
                {"event": "user", "text": "我想退货"},
                {"event": "bot", "text": "请问是什么商品？"},
                {"event": "user", "text": "手机"},
            ]
        },
    )

    assert len(results) == 1
    assert retriever.calls == [
        {
            "payload": {
                "query": "退货规则是什么？",
                "mode": "mix",
                "top_k": 3,
                "include_references": True,
                "include_chunk_content": True,
                "stream": False,
                "conversation_history": [
                    {"role": "user", "content": "我想退货"},
                    {"role": "assistant", "content": "请问是什么商品？"},
                    {"role": "user", "content": "手机"},
                ],
            },
            "headers": {"X-API-Key": "secret"},
        }
    ]


@pytest.mark.asyncio
async def test_search_maps_reference_chunks_to_search_results():
    retriever = FakeLightRAGRetriever(
        response={
            "references": [
                {
                    "reference_id": "1",
                    "file_path": "docs/a.md",
                    "content": ["第一段", "第二段"],
                },
                {
                    "reference_id": "2",
                    "file_path": "docs/b.md",
                    "content": ["第三段"],
                },
            ]
        }
    )
    retriever.connect({"base_url": "http://localhost:9621"})

    results = await retriever.search("查规则", top_k=2)

    assert [result.text for result in results] == ["第一段", "第二段"]
    assert all(isinstance(result, SearchResult) for result in results)
    assert results[0].score == 1.0
    assert results[0].metadata["source"] == "docs/a.md"
    assert results[0].metadata["reference_id"] == "1"
    assert results[0].metadata["file_path"] == "docs/a.md"
    assert "retrieval_timing" in results[0].metadata


@pytest.mark.asyncio
async def test_search_uses_reference_fallback_when_content_missing():
    retriever = FakeLightRAGRetriever(
        response={
            "references": [
                {"reference_id": "sku-policy", "file_path": "docs/sku.md"}
            ]
        }
    )
    retriever.connect({"base_url": "http://localhost:9621"})

    results = await retriever.search("库存规则", top_k=3)

    assert len(results) == 1
    assert results[0].text == "LightRAG reference sku-policy from docs/sku.md"
    assert results[0].metadata["source"] == "docs/sku.md"


@pytest.mark.asyncio
async def test_search_returns_empty_list_for_empty_query():
    retriever = FakeLightRAGRetriever()
    retriever.connect({"base_url": "http://localhost:9621"})

    results = await retriever.search("   ")

    assert results == []
    assert retriever.calls == []
    assert retriever.last_timing["empty_query"] is True


@pytest.mark.asyncio
async def test_search_returns_empty_list_for_http_error():
    retriever = FakeLightRAGRetriever(error=RuntimeError("server down"))
    retriever.connect({"base_url": "http://localhost:9621"})

    results = await retriever.search("查规则")

    assert results == []
    assert retriever.last_timing["error"] == "server down"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_lightrag_retrieval.py -v
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'ecs_demo.addons.lightrag_retrieval'`.

## Task 2: LightRAG Retriever Adapter

**Files:**
- Create: `ecs_demo/addons/lightrag_retrieval.py`
- Modify: `ecs_demo/addons/__init__.py`
- Test: `tests/test_lightrag_retrieval.py`

- [ ] **Step 1: Add the LightRAG retriever implementation**

Create `ecs_demo/addons/lightrag_retrieval.py` with this content:

```python
# -*- coding: utf-8 -*-
"""LightRAG Server retriever adapter for the ecommerce demo."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from ec_as_ai.retrieval.base_retriever import InformationRetrieval, SearchResult
from ec_as_ai.shared.timing import elapsed_ms, perf_counter

logger = logging.getLogger("retrieval")


class LightRAGRetriever(InformationRetrieval):
    """Retrieve knowledge chunks from a standalone LightRAG Server."""

    def __init__(self, embeddings=None):
        super().__init__(embeddings)
        self.base_url = "http://127.0.0.1:9621"
        self.api_key: Optional[str] = None
        self.mode = "mix"
        self.include_references = True
        self.include_chunk_content = True
        self.timeout = 120.0
        self.history_limit = 6
        self.last_timing: Dict[str, Any] = {}

    def connect(self, config: Optional[Dict[str, Any]] = None) -> None:
        config = config or {}

        base_url = config.get("base_url") or config.get("url") or self.base_url
        self.base_url = str(base_url).rstrip("/")

        api_key = config.get("api_key") or config.get("key")
        self.api_key = str(api_key) if api_key else None

        self.mode = str(config.get("mode", self.mode))
        self.include_references = bool(
            config.get("include_references", self.include_references)
        )
        self.include_chunk_content = bool(
            config.get("include_chunk_content", self.include_chunk_content)
        )
        self.timeout = float(config.get("timeout", self.timeout))
        self.history_limit = int(config.get("history_limit", self.history_limit))

        logger.info("LightRAG retriever configured for %s", self.base_url)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        tracker_state: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        total_start = perf_counter()
        query = (query or "").strip()
        if not query:
            self.last_timing = {
                "total_ms": elapsed_ms(total_start),
                "empty_query": True,
            }
            return []

        payload = self._build_payload(query, top_k, tracker_state)
        headers = self._build_headers()

        try:
            response_data = await self._post_query(payload, headers)
        except Exception as exc:
            self.last_timing = {
                "total_ms": elapsed_ms(total_start),
                "error": str(exc),
            }
            logger.warning("LightRAG query failed: %s", exc)
            return []

        retrieval_timing = {
            "total_ms": elapsed_ms(total_start),
        }
        results = self._results_from_response(response_data, top_k, retrieval_timing)
        retrieval_timing["result_count"] = len(results)
        self.last_timing = retrieval_timing

        for result in results:
            result.metadata["retrieval_timing"] = retrieval_timing

        return results

    def _build_payload(
        self,
        query: str,
        top_k: int,
        tracker_state: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "query": query,
            "mode": self.mode,
            "top_k": top_k,
            "include_references": self.include_references,
            "include_chunk_content": self.include_chunk_content,
            "stream": False,
        }

        history = self._conversation_history_from_tracker(tracker_state)
        if history:
            payload["conversation_history"] = history

        return payload

    def _build_headers(self) -> Dict[str, str]:
        if not self.api_key:
            return {}
        return {"X-API-Key": self.api_key}

    async def _post_query(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/query",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    def _results_from_response(
        self,
        data: Dict[str, Any],
        top_k: int,
        retrieval_timing: Dict[str, Any],
    ) -> List[SearchResult]:
        references = data.get("references") or []
        if not isinstance(references, list):
            return []

        results: List[SearchResult] = []
        for reference in references:
            if not isinstance(reference, dict):
                continue

            reference_id = str(reference.get("reference_id") or "")
            file_path = str(reference.get("file_path") or "")
            source = file_path or "LightRAG"
            contents = self._normalize_reference_content(reference)

            for chunk_index, content in enumerate(contents, 1):
                text = str(content).strip()
                if not text:
                    continue

                results.append(
                    SearchResult(
                        text=text,
                        metadata={
                            "source": source,
                            "reference_id": reference_id,
                            "file_path": file_path,
                            "chunk_index": chunk_index,
                            "retrieval_timing": retrieval_timing,
                        },
                        score=1.0,
                    )
                )
                if len(results) >= top_k:
                    return results

        return results

    def _normalize_reference_content(self, reference: Dict[str, Any]) -> List[str]:
        content = reference.get("content")
        if isinstance(content, list):
            return [str(item) for item in content if str(item).strip()]
        if isinstance(content, str) and content.strip():
            return [content]

        reference_id = str(reference.get("reference_id") or "").strip()
        file_path = str(reference.get("file_path") or "").strip()
        if reference_id or file_path:
            return [f"LightRAG reference {reference_id} from {file_path}".strip()]
        return []

    def _conversation_history_from_tracker(
        self,
        tracker_state: Optional[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        if not isinstance(tracker_state, dict):
            return []

        events = tracker_state.get("events")
        if not isinstance(events, list):
            return []

        history: List[Dict[str, str]] = []
        for event in events:
            if not isinstance(event, dict):
                continue

            event_type = event.get("event")
            text = event.get("text")
            if not isinstance(text, str) or not text.strip():
                continue

            if event_type == "user":
                history.append({"role": "user", "content": text.strip()})
            elif event_type == "bot":
                history.append({"role": "assistant", "content": text.strip()})

        return history[-self.history_limit :]
```

- [ ] **Step 2: Export the new retriever**

Modify `ecs_demo/addons/__init__.py` to:

```python
# -*- coding: utf-8 -*-
"""
电商客服Demo Addons模块
"""

from .information_retrieval import GraphRAG
from .lightrag_retrieval import LightRAGRetriever

__all__ = ["GraphRAG", "LightRAGRetriever"]
```

- [ ] **Step 3: Run adapter tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_lightrag_retrieval.py -v
```

Expected: PASS all tests in `tests/test_lightrag_retrieval.py`.

- [ ] **Step 4: Commit adapter and tests**

Run:

```powershell
git add ecs_demo\addons\lightrag_retrieval.py ecs_demo\addons\__init__.py tests\test_lightrag_retrieval.py
git commit -m "feat: add LightRAG retriever adapter"
```

Expected: commit succeeds with only these files staged.

## Task 3: Demo Configuration Switch

**Files:**
- Modify: `ecs_demo/config.yml`
- Modify: `ecs_demo/endpoints.yml`
- Test: `tests/test_lightrag_retrieval.py`

- [ ] **Step 1: Point the demo policy to LightRAGRetriever**

Modify `ecs_demo/config.yml` to:

```yaml
# -*- coding: utf-8 -*-
# 电商客服Demo配置文件

recipe: default.v1
language: zh

# Pipeline配置
pipeline:
  - name: LLMCommandGenerator
    llm: default  # 引用endpoints.yml中的模型配置

# 策略配置
policies:
  - name: FlowPolicy
  - name: EnterpriseSearchPolicy
    llm: default
    vector_store: addons.lightrag_retrieval.LightRAGRetriever
```

- [ ] **Step 2: Replace Neo4j vector_store settings with LightRAG settings**

Modify `ecs_demo/endpoints.yml` to:

```yaml
# -*- coding: utf-8 -*-
# 端点配置文件

# LLM模型配置
models:
  default:
    type: qwen
    model: qwen-plus
    api_key: ${DASHSCOPE_API_KEY}
    temperature: 0.1

# LightRAG Server 配置
vector_store:
  base_url: http://127.0.0.1:9621
  api_key: ${LIGHTRAG_API_KEY}
  mode: mix
  include_references: true
  include_chunk_content: true
  timeout: 120

# 数据库配置 (MySQL)
database:
  url: mysql+pymysql://root:${MYSQL_PASSWORD}@localhost:3306/ecommerce

# Tracker存储配置
tracker_store:
  type: memory

# NLG配置
nlg:
  rephrase_enabled: false
```

- [ ] **Step 3: Run adapter tests after config change**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_lightrag_retrieval.py -v
```

Expected: PASS all tests.

- [ ] **Step 4: Verify retriever factory can import the configured class**

Run from `C:\code\python\llm_customer_service\ecs_demo`:

```powershell
..\.venv\Scripts\python.exe -c "from ec_as_ai.retrieval import create_retriever; r=create_retriever('addons.lightrag_retrieval.LightRAGRetriever', {'base_url':'http://127.0.0.1:9621'}); print(type(r).__name__, r.base_url)"
```

Expected output contains:

```text
LightRAGRetriever http://127.0.0.1:9621
```

- [ ] **Step 5: Commit configuration switch**

Run:

```powershell
git add ecs_demo\config.yml ecs_demo\endpoints.yml
git commit -m "chore: configure demo to use LightRAG service"
```

Expected: commit succeeds with only the two config files staged.

## Task 4: README Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update project overview references**

In `README.md`, change the sentence near the top from:

```markdown
`ec_as_ai` 通过 LLM 将用户输入解析为对话命令，再结合 Flow、Domain、Slot、Action 和策略模块完成多轮对话管理。系统支持命令行调试、FastAPI 服务、Inspect 可视化调试页面，以及基于 Neo4j 知识图谱的 GraphRAG 检索降级。
```

to:

```markdown
`ec_as_ai` 通过 LLM 将用户输入解析为对话命令，再结合 Flow、Domain、Slot、Action 和策略模块完成多轮对话管理。系统支持命令行调试、FastAPI 服务、Inspect 可视化调试页面，以及通过 `InformationRetrieval` 扩展接入 LightRAG 等知识库检索服务。
```

Change the RAG bullet from:

```markdown
- RAG 检索：可通过 `InformationRetrieval` 扩展自定义检索器，示例中提供 Neo4j GraphRAG。
```

to:

```markdown
- RAG 检索：可通过 `InformationRetrieval` 扩展自定义检索器，Demo 默认使用独立 LightRAG Server。
```

Change the environment requirement from:

```markdown
- 运行 `ecs_demo` 的 GraphRAG 检索时，需要 Neo4j
```

to:

```markdown
- 运行 `ecs_demo` 的知识库检索时，需要启动 LightRAG Server 并完成知识库索引
```

- [ ] **Step 2: Update config examples**

In the `config.yml` example, change:

```yaml
    vector_store: addons.information_retrieval.GraphRAG
```

to:

```yaml
    vector_store: addons.lightrag_retrieval.LightRAGRetriever
```

In the `endpoints.yml` example, change:

```yaml
vector_store:
  uri: bolt://localhost:7687
  user: neo4j
  password: ${NEO4J_PASSWORD}
```

to:

```yaml
vector_store:
  base_url: http://127.0.0.1:9621
  api_key: ${LIGHTRAG_API_KEY}
  mode: mix
  include_references: true
  include_chunk_content: true
  timeout: 120
```

- [ ] **Step 3: Replace the GraphRAG section with LightRAG instructions**

Replace the `## GraphRAG 知识库检索` section with:

````markdown
## LightRAG 知识库检索

Demo 默认通过 `addons.lightrag_retrieval.LightRAGRetriever` 接入独立 LightRAG Server。该适配器继承自 `ec_as_ai.retrieval.InformationRetrieval`，工作流程包括：

1. `EnterpriseSearchPolicy` 将用户问题交给 `LightRAGRetriever.search()`。
2. `LightRAGRetriever` 调用 LightRAG Server 的 `/query` 接口，默认使用 `mix` 模式。
3. 适配器读取 LightRAG 返回的 `references` 和 chunk 内容，转换为 `SearchResult`。
4. `EnterpriseSearchPolicy` 使用这些检索上下文生成最终客服回答。

启动 LightRAG Server 可参考 LightRAG 官方文档。最小本地流程通常是：

```bash
pip install "lightrag-hku[api]"
lightrag-server --host 127.0.0.1 --port 9621
```

运行前请确认：

- LightRAG Server 已完成 LLM 和 Embedding 配置。
- LightRAG 工作区已导入并索引电商知识库文档。
- 如果 LightRAG Server 启用了 API Key，已配置 `LIGHTRAG_API_KEY`。
- `ecs_demo/endpoints.yml` 中的 `vector_store.base_url` 指向正确的 LightRAG Server 地址。

旧的 `addons.information_retrieval.GraphRAG` 和 `addons/create_indexing.py` 仍保留为 Neo4j GraphRAG 示例，但不再是 Demo 默认检索路径。
````

- [ ] **Step 4: Update development tip**

Change:

```markdown
- 如果只想验证 Flow 行为，可先关闭或替换 `EnterpriseSearchPolicy.vector_store`，避免启动时依赖 Neo4j。
```

to:

```markdown
- 如果只想验证 Flow 行为，可先关闭或替换 `EnterpriseSearchPolicy.vector_store`，避免启动时依赖 LightRAG Server。
```

- [ ] **Step 5: Check README references**

Run:

```powershell
rg -n "GraphRAG|Neo4j|LightRAG|lightrag_retrieval" README.md
```

Expected: remaining `GraphRAG` and `Neo4j` references are only in the legacy note for the old example.

- [ ] **Step 6: Commit README documentation**

Run:

```powershell
git add README.md
git commit -m "docs: document LightRAG service retrieval"
```

Expected: commit succeeds with only `README.md` staged.

## Task 5: Final Verification

**Files:**
- Verify: `ecs_demo/addons/lightrag_retrieval.py`
- Verify: `ecs_demo/config.yml`
- Verify: `ecs_demo/endpoints.yml`
- Verify: `README.md`
- Verify: `tests/test_lightrag_retrieval.py`

- [ ] **Step 1: Run the focused test suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_lightrag_retrieval.py -v
```

Expected: PASS all tests.

- [ ] **Step 2: Run all available tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -v
```

Expected: PASS all tests in `tests`.

- [ ] **Step 3: Verify working tree scope**

Run:

```powershell
git status --short
```

Expected: no uncommitted changes from this LightRAG implementation. Pre-existing unrelated local changes may still appear and should not be reverted.

- [ ] **Step 4: Optional manual LightRAG smoke test**

Only run this if a local LightRAG Server is already running and indexed:

```powershell
.\.venv\Scripts\python.exe -c "import asyncio; from ecs_demo.addons.lightrag_retrieval import LightRAGRetriever; r=LightRAGRetriever(); r.connect({'base_url':'http://127.0.0.1:9621'}); results=asyncio.run(r.search('退货规则是什么？', top_k=3)); print(len(results)); print(results[0].text[:120] if results else 'NO_RESULTS')"
```

Expected: prints a result count and either the first retrieved chunk preview or `NO_RESULTS` if the LightRAG knowledge base has no matching indexed content.
