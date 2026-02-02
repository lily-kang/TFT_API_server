# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Text Processing Pipeline API** for automated quality assessment and revision of educational English reading passages. The system analyzes and modifies text based on syntactic complexity and lexical difficulty metrics, using external text analyzers and LLMs (GPT-4, Claude Sonnet 4, Gemini 2.0 Flash).

**Primary Purpose**: Generate and validate educational reading passages that meet specific syntactic and vocabulary difficulty targets for language learners.

## Core Architecture

### Pipeline Flow

The system processes passages through a multi-stage pipeline:

1. **Initial Analysis** → External text analyzer evaluates 3 key metrics
2. **Metrics Evaluation** → Judge determines Pass/Fail for syntax and lexical metrics
3. **Case Classification** → Routes to appropriate revision module
4. **Syntax Revision** (if needed) → LLM generates 4 candidates, analyzer selects best
5. **Lexical Revision** (if needed) → LLM generates sentence-level vocabulary alternatives
6. **Final Status** → Returns either FINAL (success) or DISCARD (failed revision)

### Key Metrics

The system measures and adjusts three critical metrics:

- **AVG_SENTENCE_LENGTH**: Average sentence length (words) - uses absolute tolerance
- **All_Embedded_Clauses_Ratio**: Embedded clause ratio (syntactic complexity) - uses ratio tolerance
- **CEFR_NVJD_A1A2_lemma_ratio**: A1/A2 level vocabulary ratio - uses ratio tolerance

### Module Separation

**Syntax vs Lexical Processing**:
- **Syntax revision** (`core/llm/syntax_fixer.py`): Fully automated - generates candidates, analyzes them, selects best match
- **Lexical revision** (`core/llm/lexical_fixer.py`): Semi-automated - generates multiple vocabulary alternatives per sentence, requires human selection from sheet_data

**Why separated?**: Syntax changes affect sentence structure (can be objectively measured), while lexical changes involve semantic nuance (requires human judgment).

### Critical Components

**Pipeline Orchestration** (`core/pipeline.py`):
- `PipelineProcessor.run_pipeline()`: Main orchestrator for single passage
- `BatchProcessor.process_batch()`: Parallel processing using asyncio.gather()
- State machine logic determines: initial analysis → syntax fix (if needed) → lexical fix (if needed) → final/discard

**LLM Temperature Strategy** (`config/settings.py`):
- Syntax revision uses multiple temperatures `[0.2, 0.3]` with 2 candidates per temperature = 4 total candidates
- Generates diversity while maintaining consistency
- Each candidate is sequentially analyzed until one passes all metrics

**External Analyzer Integration** (`core/analyzer.py`):
- Calls `https://ils.jp.ngrok.io/api/enhanced_analyze`
- Returns raw analysis data including all 3 metrics
- Synchronous dependency: pipeline cannot proceed without analyzer response

**Metrics Judge** (`core/judge.py`):
- Compares current metrics against master targets with tolerance ranges
- Returns `syntax_pass` and `lexical_pass` as "PASS" or "FAIL"
- Used at multiple pipeline stages: initial analysis, post-syntax revision, post-lexical revision

## Development Commands

### Running the Server

```bash
# Development mode with auto-reload (default port 8080)
python main.py

# Or using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Production mode (from .env: DEBUG=False)
uvicorn main:app --host 0.0.0.0 --port 8080

# Custom port via environment variable
PORT=9000 python main.py
```

### Docker

```bash
# Build image
docker build -t tft-api-server .

# Run container (Cloud Run compatible)
docker run -p 8080:8080 -e OPENAI_API_KEY=<key> tft-api-server
```

### Testing

```bash
# Run specific test files
python test_api_call.py
python test_fix_revise_single.py
python test_full_syntax_pipeline.py

# Note: No pytest configuration found - tests appear to be manual execution scripts
```

### Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Required environment variables (.env file)
OPENAI_API_KEY=sk-...                              # Required for LLM calls
EXTERNAL_ANALYZER_API_URL=https://ils.jp.ngrok.io/api/enhanced_analyze
OPENAI_MODEL=gpt-4.1                               # LLM model to use
DEBUG=True                                         # Enable auto-reload
LOG_LEVEL=INFO
```

## API Endpoints

### Text Revision

**POST /syntax-fix** - Single passage syntax revision only
**POST /batch-syntax-fix** - Batch syntax revision
**POST /revise** - Combined syntax + lexical revision (recommended)
**POST /batch-revise** - Batch combined revision

### Semantic Analysis

**POST /semantic-profile** - Generate semantic profile for passage
**POST /semantic-profile:batch** - Batch semantic profile generation
**POST /topic-closeness** - Compare topic similarity between passages
**POST /topic-closeness:generate-and-score** - Generate profile and score in one call

### Analysis

**POST /analyze** - Direct call to external text analyzer
**GET /health** - Service health check with configuration status

### API Documentation

Interactive docs available when server is running:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Code Organization

```
TFT_API_server/
├── main.py                          # FastAPI app entry point
├── api/
│   └── router.py                    # All API endpoints (revision, semantic, topic closeness)
├── core/
│   ├── pipeline.py                  # Main pipeline orchestration (PipelineProcessor, BatchProcessor)
│   ├── analyzer.py                  # External analyzer API client
│   ├── metrics.py                   # Metric extraction from analyzer responses
│   ├── judge.py                     # Pass/Fail evaluation logic
│   ├── llm/
│   │   ├── client.py                # OpenAI API wrapper with lazy initialization
│   │   ├── syntax_fixer.py          # Syntax revision with candidate generation
│   │   ├── lexical_fixer.py         # Lexical revision with sheet_data output
│   │   ├── selector.py              # Best candidate selection logic
│   │   └── prompt_builder.py        # Dynamic prompt construction
│   └── services/
│       ├── text_processing_service_v2.py  # High-level revision service
│       ├── semantic_profile.py      # Semantic profile generation (2-phase)
│       └── topic_closeness.py       # Topic similarity scoring
├── models/
│   ├── request.py                   # API request models (Pydantic)
│   ├── response.py                  # API response models
│   └── internal.py                  # Internal data models
├── config/
│   ├── settings.py                  # Application configuration (Pydantic Settings)
│   ├── syntax_revision_prompt.py    # LLM prompts for syntax revision
│   ├── lexical_revision_prompt.py   # LLM prompts for lexical revision
│   ├── profile_gen_prompt.py        # Semantic profile prompts
│   ├── labeling_prompt.py           # Topic closeness scoring prompts
│   └── ar_category_structured.yaml  # AR category taxonomy for subtopic classification
└── utils/
    ├── logging.py                   # Logging configuration
    ├── exceptions.py                # Custom exception classes
    └── helpers.py                   # Utility functions
```

## Important Implementation Details

### Async Processing Patterns

All core processing is async. When adding new features:
- Use `async def` for any function that calls external APIs (analyzer, OpenAI)
- Use `await` for LLM calls, analyzer calls, and pipeline steps
- Batch operations use `asyncio.gather(*tasks)` for parallelism
- Error handling: `return_exceptions=True` in gather() to prevent one failure from stopping batch

### LLM Client Initialization

The OpenAI client uses **lazy initialization** (`core/llm/client.py`):
- Client is only created on first use (not at import time)
- Allows server to start even if OPENAI_API_KEY is missing
- Check `self._client_init_error` for initialization failures
- API key can come from settings.openai_api_key or OPENAI_API_KEY env var

### Tolerance Calculation

Two tolerance types with different calculation methods:
- **Absolute**: `target ± tolerance_abs` (used for sentence length)
- **Ratio**: `target ± tolerance_ratio` (used for clause ratio and CEFR ratio)

Example: `master.AVG_SENTENCE_LENGTH = 12.3, tolerance_abs = 1.97` → range `[10.33, 14.27]`

### Prompt Builder Strategy

`core/llm/prompt_builder.py` dynamically constructs prompts based on:
- Current metric values vs target ranges
- Direction of adjustment needed (increase/decrease)
- Problematic metric identification (which metric failed)
- Referential clauses for context preservation

**Key method**: `determine_problematic_metric()` - analyzes which metric is out of range and calculates adjustment direction

### Semantic Profile Two-Phase Generation

Semantic profiles are generated in two phases (`core/services/semantic_profile.py`):
1. **Phase 1**: LLM extracts 8 fields (discipline, subtopic_1, central_focus, key_concepts, etc.)
2. **Phase 2**: Uses `ar_category_structured.yaml` to refine subtopic_1 into more granular subtopic_2

This enables topic closeness scoring across 8 dimensions to determine if generated passages are too similar/different from originals.

### Status Codes and Result Types

**Pipeline Status** (`models/response.py`):
- `FINAL`: Successfully met all metric targets
- `SYNTAX_FAIL`: Syntax revision failed to meet targets
- `LEXICAL_FAIL`: Lexical revision failed to meet targets
- `ERROR`: System error during processing

**Pass/Fail Values**:
- `PASS`: Metric within tolerance range
- `FAIL`: Metric outside tolerance range

### Trace Logging

Pipeline results include `trace` field with step-by-step execution log:
- Each step records: step name, metrics, pass/fail status, candidates generated
- Useful for debugging why a passage was discarded
- Access via `result.trace` in API responses

## Common Development Tasks

### Adding a New Metric

1. Update `models/request.py`: Add to `MasterMetrics` and appropriate tolerance model
2. Update `core/metrics.py`: Add extraction logic in `extract()` method
3. Update `core/judge.py`: Add evaluation logic in `evaluate()` method
4. Update prompts in `config/`: Include new metric in revision prompts if needed
5. Update external analyzer (outside this codebase) to return the new metric

### Modifying LLM Behavior

- **Temperature changes**: Edit `settings.llm_temperatures` in `config/settings.py`
- **Candidate count**: Edit `syntax_candidates_per_temperature` in settings
- **Prompt changes**: Edit files in `config/*_prompt.py` - these use template strings
- **Model selection**: Change `settings.openai_model` (default: gpt-4.1)

### Adding New API Endpoints

1. Define request/response models in `models/request.py` and `models/response.py`
2. Add route handler in `api/router.py`
3. Use `@router.post()` decorator with appropriate tags
4. Import and call service layer functions from `core/services/`
5. Add error handling with HTTPException for user-facing errors

### Debugging Pipeline Failures

1. Check `step_results` in response - shows which step failed
2. Review `trace` field for metric values at each stage
3. Check `detailed_result` for human-readable metric comparison
4. Verify external analyzer is reachable: test `/analyze` endpoint directly
5. Check `error_message` field if status is ERROR

## Configuration Notes

**Default Settings** (`config/settings.py`):
- Syntax candidates: 2 per temperature × 2 temperatures = 4 total candidates
- Lexical candidates: 3 (per sentence, across 3 LLM calls = up to 9 alternatives)
- Pipeline timeout: 300 seconds
- Max output tokens: 4096
- Default port: 8080 (configurable via PORT env var)

**Cloud Run Deployment**:
- Dockerfile exposes port 8080 (configurable via $PORT env var)
- Uses Python 3.11-slim base image
- OPENAI_API_KEY should be injected as secret/env var

**Logging**:
- Configured in `utils/logging.py`
- Log level controlled by LOG_LEVEL env var (default: INFO)
- Logs include request_id for tracing across batch operations

## Reference Documents

For deeper understanding of the system architecture and workflow:
- `TFT_Passage_Pipeline_Overview.md`: Comprehensive process flow documentation
- `FP_Passage_Pipeline_prompts.md`: Detailed prompt engineering guide for passage generation
- `FP_Question_Pipeline_Prompts.md`: Prompt engineering guide for question generation
- `README.md`: User-facing documentation with API usage examples
