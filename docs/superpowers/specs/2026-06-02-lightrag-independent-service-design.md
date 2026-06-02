# LightRAG Independent Service Integration Design

## Goal

Replace the demo project's Neo4j-based GraphRAG fallback with a real LightRAG-backed knowledge retrieval path while keeping the existing `ec_as_ai` policy and dialogue architecture intact.

LightRAG will run as an independent service. The customer service project will call it through HTTP from a new retriever adapter that implements the existing `InformationRetrieval` interface.

## Current Project Context

The project already has a narrow retriever abstraction:

- `ec_as_ai.retrieval.base_retriever.InformationRetrieval` defines `connect(config)` and `search(query, top_k, tracker_state)`.
- `ec_as_ai.agent.agent.Agent` reads `policies.EnterpriseSearchPolicy.vector_store` from `config.yml`, reads `vector_store` connection values from `endpoints.yml`, and builds the retriever through `create_retriever`.
- `ec_as_ai.policies.enterprise_search_policy.EnterpriseSearchPolicy` calls `retriever.search(...)`, filters by score, then generates the final customer service answer from returned `SearchResult` context.
- `ecs_demo.addons.information_retrieval.GraphRAG` is the current demo retriever. It depends on Neo4j, local embeddings, label routing, hybrid node lookup, Cypher generation, Cypher validation, and Cypher execution.

This boundary is suitable for replacing only the retriever without changing flow policy, command generation, stack frames, or action execution.

## Selected Approach

Use LightRAG Server as an external knowledge service and add a project-local adapter named `LightRAGRetriever`.

The adapter will call LightRAG Server's non-streaming `/query` endpoint with:

- `mode`, defaulting to `mix`
- `top_k`, forwarded from `EnterpriseSearchPolicy`
- `include_references=true`
- `include_chunk_content=true`
- optional `conversation_history` derived from `tracker_state`

The adapter will map returned reference chunks into `SearchResult` objects. The existing `EnterpriseSearchPolicy` will then generate the final user-facing answer using the project's current RAG prompt.

## Alternatives Considered

### Return LightRAG's Final Answer Directly

The adapter could return LightRAG's generated `response` as a single `SearchResult`.

This is simpler, but it would make the current project generate an answer from another generated answer unless `EnterpriseSearchPolicy` is changed. That double-generation path weakens citation fidelity and makes the final tone harder to control.

### Embed LightRAG Core In-Process

The project could instantiate `LightRAG` directly and call `aquery`.

This makes deployment smaller on paper, but LightRAG Core requires explicit async storage initialization, has its own lifecycle, and brings storage configuration into the customer service process. That does not fit the current synchronous `connect()` retriever boundary as cleanly as HTTP does.

## Architecture

### Components

`LightRAG Server`

- Owns document ingestion, indexing, graph/vector storage, workspace isolation, and retrieval.
- Runs separately, normally on `http://127.0.0.1:9621`.
- Is configured through its own `.env` and command-line flags.

`ecs_demo.addons.lightrag_retrieval.LightRAGRetriever`

- Implements `InformationRetrieval`.
- Reads `base_url`, `api_key`, `mode`, `timeout`, and reference flags from `endpoints.yml`.
- Sends async HTTP requests with `httpx.AsyncClient`.
- Converts LightRAG references and chunk content into `SearchResult`.
- Records simple retriever timing in `last_timing` and in each result's metadata.

`EnterpriseSearchPolicy`

- Remains unchanged.
- Receives factual context as `SearchResult` objects.
- Applies existing similarity filtering and final answer generation.

### Configuration

`ecs_demo/config.yml` will change the retriever class path:

```yaml
policies:
  - name: FlowPolicy
  - name: EnterpriseSearchPolicy
    llm: default
    vector_store: addons.lightrag_retrieval.LightRAGRetriever
```

`ecs_demo/endpoints.yml` will use LightRAG connection settings:

```yaml
vector_store:
  base_url: http://127.0.0.1:9621
  api_key: ${LIGHTRAG_API_KEY}
  mode: mix
  include_references: true
  include_chunk_content: true
  timeout: 120
```

If `api_key` is empty, the adapter will not send `X-API-Key`.

## Data Flow

1. The user asks a knowledge question.
2. Command generation or fallback pushes a `SearchStackFrame`.
3. `EnterpriseSearchPolicy` calls `LightRAGRetriever.search(query, top_k, tracker_state)`.
4. The retriever sends a POST request to LightRAG `/query`.
5. LightRAG returns a generated response and optional references.
6. The retriever ignores the generated response by default and extracts reference chunk text.
7. Each chunk becomes a `SearchResult` with source metadata and score `1.0`.
8. `EnterpriseSearchPolicy` builds the final prompt from the returned chunks and generates the final customer service answer.

## Reference Mapping

Each LightRAG reference will map to one or more `SearchResult` entries.

For each reference:

- `text`: chunk text if available; otherwise a fallback text built from `file_path` and `reference_id`
- `metadata.source`: `file_path` if present, else `LightRAG`
- `metadata.reference_id`: LightRAG `reference_id`
- `metadata.file_path`: LightRAG `file_path`
- `metadata.retrieval_timing`: adapter timing
- `score`: `1.0`

The adapter will cap returned results to `top_k` after flattening chunks.

## Conversation History

The adapter may pass recent tracker events as LightRAG `conversation_history`.

Only user and bot text events will be included. This history is for answer context, not retrieval control. If tracker data is missing or malformed, the adapter will omit history rather than failing the request.

## Error Handling

The adapter will return an empty list when:

- The query is empty.
- LightRAG Server is unreachable.
- LightRAG returns a non-2xx response.
- The response shape does not contain usable references or chunk content.

Failures will be logged. `EnterpriseSearchPolicy` already handles empty retrieval results through its existing chitchat/default fallback path.

## Dependencies

The project already depends on `httpx`, so the adapter does not need a new runtime dependency.

LightRAG Server itself is installed and run outside this project, for example with `lightrag-hku[api]` or Docker.

## Testing

Add focused adapter tests with a fake async HTTP client or monkeypatched request method:

- `connect()` normalizes `base_url`, auth, mode, timeout, and reference flags.
- `search()` sends expected payload and `X-API-Key` header when configured.
- `search()` converts references with chunk content into `SearchResult`.
- `search()` returns an empty list for empty query, HTTP failure, and malformed response.
- tracker events are converted into LightRAG-compatible conversation history.

No live LightRAG service is required for unit tests.

## Rollout

1. Add `LightRAGRetriever`.
2. Export it from `ecs_demo.addons` for convenience.
3. Update demo configuration to use the new retriever.
4. Document how to start LightRAG Server and index documents.
5. Run unit tests.
6. Optionally run one manual query against a local LightRAG Server after it is available.

## Non-Goals

- Do not modify `EnterpriseSearchPolicy` unless adapter-only integration proves insufficient.
- Do not migrate order/user transactional data into LightRAG.
- Do not remove the existing GraphRAG demo in the first pass; keep it available as a historical example unless the user explicitly asks to delete it.
- Do not add LightRAG Server process management into this project.
