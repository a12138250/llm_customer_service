# llm_customer_service

基于大语言模型的多轮电商客服对话系统。项目内核为 `ec_as_ai`，提供对话系统框架；`ecs_demo` 是一个电商客服示例工程，覆盖订单查询、修改收货信息、取消订单、物流、售后以及知识库检索等场景。

## 项目简介

`ec_as_ai` 通过 LLM 将用户输入解析为对话命令，再结合 Flow、Domain、Slot、Action 和策略模块完成多轮对话管理。系统支持命令行调试、FastAPI 服务、Inspect 可视化调试页面，以及基于 Neo4j 知识图谱的 GraphRAG 检索降级。

核心能力：

- LLM 驱动的对话理解：通过 `LLMCommandGenerator` 将自然语言转为系统命令。
- Flow 流程编排：使用 YAML 定义业务流程和条件跳转。
- Slot 状态管理：支持 LLM 填槽、受控填槽和流程结束后的持久槽位。
- 自定义 Action：自动加载用户工程 `actions/` 下继承 `Action` 的动作类。
- 策略集成：内置 `FlowPolicy` 和 `EnterpriseSearchPolicy`。
- RAG 检索：可通过 `InformationRetrieval` 扩展自定义检索器，示例中提供 Neo4j GraphRAG。
- 服务接口：提供 REST API、WebSocket、Swagger 文档和 Inspect 调试页面。

## 目录结构

```text
.
├── ec_as_ai/                  # 对话系统框架源码
│   ├── agent/                 # Agent、消息处理图、Action 基类
│   ├── api/                   # FastAPI 服务与 Inspect 页面
│   ├── channels/              # REST、SocketIO、Console 通道
│   ├── cli/                   # ec_as 命令行工具
│   ├── core/                  # Domain、Slot、Tracker、Store
│   ├── dialogue_understanding/# 命令生成、命令解析、Flow 执行
│   ├── nlg/                   # 模板回复与回复重述
│   ├── policies/              # FlowPolicy、EnterpriseSearchPolicy
│   ├── retrieval/             # 检索器抽象与扩展入口
│   ├── shared/                # 配置、常量、LLM 客户端等公共工具
│   └── training/              # 训练、校验与模型打包
├── ecs_demo/                  # 电商客服 Demo 工程
│   ├── actions/               # 订单、物流、售后等业务动作
│   ├── addons/                # GraphRAG 检索与索引构建脚本
│   ├── data/flows/            # 业务流程定义
│   ├── domain/                # 领域配置、槽位、响应、动作声明
│   ├── config.yml             # Pipeline 与策略配置
│   └── endpoints.yml          # LLM、向量库、数据库、Tracker 配置
├── requirements-ec_as.txt     # 依赖列表
└── setup.py                   # 包安装配置，注册 ec_as 命令
```

## 环境要求

- Python 3.10+
- 可用的 LLM API Key，例如 DashScope 或 OpenAI
- 运行 `ecs_demo` 的 GraphRAG 检索时，需要 Neo4j
- 运行订单、物流、售后等数据库 Action 时，需要 MySQL，并按本地环境调整数据库连接
- 运行本地中文嵌入模型时，需要准备 `bge-base-zh-v1.5` 等 embedding 模型目录

## 安装

在项目根目录执行：

```bash
python -m pip install -r requirements-ec_as.txt
python -m pip install -e .
```

安装后会注册命令行工具：

```bash
ec_as --version
ec_as --help
```

也可以通过模块方式运行：

```bash
python -m ec_as_ai --help
```

## 环境变量

命令入口会自动加载当前工作目录下的 `.env` 文件。建议在运行 Demo 的目录中创建 `.env`：

```env
DASHSCOPE_API_KEY=your_dashscope_api_key
OPENAI_API_KEY=your_openai_api_key
NEO4J_PASSWORD=your_neo4j_password
MYSQL_PASSWORD=your_mysql_password
EMBEDDING_MODEL=./models/bge-base-zh-v1.5
```

说明：

- `ecs_demo/endpoints.yml` 默认使用 `qwen-plus` 和 `${DASHSCOPE_API_KEY}`。
- GraphRAG 示例会读取 Neo4j 连接信息和本地嵌入模型路径。
- `.env`、缓存目录和模型权重已在 `.gitignore` 中排除，不应提交真实凭据或大模型文件。

## 运行电商客服 Demo

进入 Demo 目录：

```bash
cd ecs_demo
```

先校验配置和流程：

```bash
ec_as train --data data --config config.yml --domain domain --output models --dry-run
```

生成模型包：

```bash
ec_as train --data data --config config.yml --domain domain --output models
```

启动命令行对话：

```bash
ec_as shell --model .
```

启动 HTTP 服务：

```bash
ec_as run --model . --host 0.0.0.0 --port 5005
```

启动 Inspect 调试页面：

```bash
ec_as inspect --model . --port 5005
```

访问：

- API 文档：`http://localhost:5005/docs`
- Inspect 页面：`http://localhost:5005/inspect`
- 健康检查：`http://localhost:5005/health`

## REST API

发送用户消息：

```bash
curl -X POST http://localhost:5005/api/messages \
  -H "Content-Type: application/json" \
  -d "{\"sender\":\"user_001\",\"message\":\"帮我查询一下订单\"}"
```

常用接口：

- `GET /`：服务健康检查
- `GET /health`：服务健康检查
- `POST /api/messages`：发送用户消息
- `GET /api/sessions/{session_id}`：查看会话槽位和最新消息
- `POST /api/sessions/{session_id}/reset`：重置会话
- `GET /api/domain`：查看当前 Domain 配置
- `GET /api/flows`：查看当前 Flow 配置
- `GET /api/tracker/{session_id}/full`：查看完整 Tracker 状态
- `WS /api/stream`：WebSocket 实时消息流

## 配置文件说明

`config.yml` 定义对话理解组件和策略：

```yaml
pipeline:
  - name: LLMCommandGenerator
    llm: default

policies:
  - name: FlowPolicy
  - name: EnterpriseSearchPolicy
    llm: default
    vector_store: addons.information_retrieval.GraphRAG
```

`endpoints.yml` 定义模型、向量库、数据库和 Tracker 存储：

```yaml
models:
  default:
    type: qwen
    model: qwen-plus
    api_key: ${DASHSCOPE_API_KEY}
    temperature: 0.1

vector_store:
  uri: bolt://localhost:7687
  user: neo4j
  password: ${NEO4J_PASSWORD}

tracker_store:
  type: memory
```

`domain/` 定义槽位、响应模板和动作声明；`data/flows/` 定义订单、物流、售后等业务流程；`actions/` 中实现业务动作。

## GraphRAG 知识库检索

Demo 中的 `addons.information_retrieval.GraphRAG` 继承自 `ec_as_ai.retrieval.InformationRetrieval`，工作流程包括：

1. 使用 LLM 识别问题涉及的入口节点标签和实体。
2. 通过 Neo4j Hybrid Retriever 做向量检索和全文检索。
3. 使用 LLM 生成、验证并修正 Cypher 查询。
4. 执行 Cypher 查询并将结果交给 `EnterpriseSearchPolicy` 生成客服回答。

构建 Neo4j 索引可参考：

```bash
cd ecs_demo/addons
python create_indexing.py
```

运行前请确认：

- Neo4j 已导入业务图谱数据。
- 已配置 `NEO4J_PASSWORD`。
- `EMBEDDING_MODEL` 指向本地 embedding 模型目录。
- Neo4j 中已创建对应标签的向量索引和全文索引。

## 新建自己的对话项目

使用内置模板初始化：

```bash
ec_as init --path my_bot
cd my_bot
```

然后按顺序调整：

1. `endpoints.yml`：配置 LLM、embedding、Tracker Store 和外部服务。
2. `config.yml`：配置 Pipeline、Policy 和自定义检索器。
3. `domain.yml` 或 `domain/`：定义槽位、响应和 Action。
4. `data/flows.yml` 或 `data/flows/`：定义业务流程。
5. `actions/actions.py`：实现自定义业务动作。

## 开发提示

- `ec_as train --dry-run` 可用于快速校验配置、Domain 和 Flow。
- `ec_as shell` 适合命令行调试多轮对话。
- `ec_as inspect` 适合观察 Tracker、槽位和 Flow 执行状态。
- 大模型权重、索引文件、`.env` 和本地数据库凭据不要提交到 Git。
- 如果只想验证 Flow 行为，可先关闭或替换 `EnterpriseSearchPolicy.vector_store`，避免启动时依赖 Neo4j。
