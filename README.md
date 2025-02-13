# Nebular

Nebular is a Python-based AI assistant experimental platform that integrates various modern AI tools and frameworks for exploring and developing intelligent assistant applications.

## 🌟 Key Features

| Category         | Capabilities                          | Technology Stack        |
|-------------------|---------------------------------------|-------------------------|
| Task Orchestration| Intelligent routing, Load balancing  | CrewAI, Custom Heuristics|
| API Management    | Retry logic, Rate limiting           | FastAPI, Backoff        |
| Service Discovery | Dynamic resource binding, UUID-based addressing, Dependency resolution | Custom Heuristics, SignalR |
| Code Generation   | Multi-file coordination, Dependency analysis, Structural pattern recognition | CrewAI, AST Parsing  |

## 🚀 Architectural Highlights

### Core Innovation
**Intelligent Task Routing Engine**  
- Implements multi-dimensional CR selection strategy combining:
  - Framework expertise matching (React/Python/Java specialists)
  - Real-time workload monitoring
  - Historical performance metrics
  - Contextual awareness of resource dependencies

**Unified Processing Pipeline**  
- End-to-end request lifecycle management:
  1. Intent Recognition (NLU-based classification)
  2. Contextual Analysis (Dependency graph construction)
  3. Resource Binding (File/Service discovery)
  4. Expert Routing (QoS-based agent selection)
  5. Execution Monitoring (Real-time tracing)

### Engineering Excellence
**Observability Stack**  
- Trace_ID propagation across distributed services
- Structured logging with OpenTelemetry compatibility
- Performance metrics aggregation (Prometheus/Grafana)

**Configuration Framework**  
- YAML-driven agent/task definitions which leverage CrewAI's [Hierachical Process](https://docs.crewai.com/how-to/hierarchical-process), [Flows](https://docs.crewai.com/concepts/flows)
- Dynamic workflow composition via declarative templates

**Modular Architecture**  
- Pluggable tool components with standardized interfaces:
  - API Toolkits (REST/gRPC connectors)
  - Data Processors (ETL pipelines)
  - Monitoring Adapters
- Service isolation through process boundaries

## Roadmap

- [ ] Init Prompt Template by CrewManager Spawning
- [ ] Recurring summon opera
- [x] Leverage CrewAI [Hierachical Process](https://docs.crewai.com/how-to/hierarchical-process), [Flows](https://docs.crewai.com/concepts/flows)
- [ ] CrewRunner more Tools
