# Project Architecture

## Current layout

- `backend/`
  FastAPI application, Pydantic schemas, SQLAlchemy models, routers, and services.
- `floorplan-ui/`
  React client for plan editing, pipeline steps, and fire-alarm placement.
- `tests/`
  Integration and API tests for the backend-first flow.
- `floorplan/`
  Legacy or parallel Python package with its own requirements and tests.
- project root `.py` files
  Older desktop/PDF-generation scripts and supporting modules.
- generated artifacts
  `uploads/`, `outputs/`, `debug_output/`, `floor_plans.db`, build outputs.

## What is already good

- Backend logic is separated into `routers/` and `services/`, which is a solid base.
- API contracts are centralized in `backend/schemas.py`.
- Frontend API access is isolated under `floorplan-ui/src/api/`.
- Integration tests already exist and cover critical pipeline behavior.

## Main structural risks

- `floorplan-ui/src/pages/FloorPlanEditor.jsx` is too large and combines rendering, geometry, persistence, state orchestration, and UI logic in one file.
- The repository mixes active app code and legacy scripts at the root, which makes ownership boundaries unclear.
- Generated artifacts and working files live close to source code, increasing noise in git and reviews.
- Tooling is only partially standardized: Python has Ruff config, while frontend formatting rules were not explicitly documented before.

## Recommended target boundaries

- `backend/routers/`
  Keep thin: validation, request/response wiring, dependency injection only.
- `backend/services/`
  Keep business rules, pipeline transitions, geometry normalization, and side effects here.
- `backend/models.py` and `backend/schemas.py`
  Keep as domain contracts, but split by area if they continue to grow.
- `floorplan-ui/src/pages/`
  Keep page orchestration only.
- `floorplan-ui/src/components/floor-plan-editor/`
  Extract canvas layers, sidebars, hover panels, and toolbars from `FloorPlanEditor.jsx`.
- `floorplan-ui/src/hooks/`
  Extract editor state, drag logic, zoom/pan, and step-specific save handlers.
- `floorplan-ui/src/utils/`
  Keep geometry and pure helpers only.

## Next refactor to prioritize

1. Split `FloorPlanEditor.jsx` into:
   - `EditorCanvas`
   - `EditorSidebar`
   - `EditorToolbar`
   - `HoverPanel`
   - step-specific hooks such as `useWallEditing`, `useOpeningEditing`, `useFireAlarmEditing`
2. Move fire-alarm label and metadata helpers into `src/utils/fireAlarmLabels.js`.
3. Move room/stair derived-state logic into memoized selectors or hooks.
4. Separate legacy root scripts from the active web app path:
   - keep web app in `backend/` + `floorplan-ui/`
   - move older PDF/desktop entrypoints into `legacy/` or `tools/`

## Team conventions introduced in this repository

- `.editorconfig` defines line endings, encodings, and indentation defaults.
- `.prettierrc.json` and `.prettierignore` define frontend formatting expectations.
- `pyproject.toml` now documents Ruff lint/format scope more clearly.
- `floorplan-ui/package.json` now includes `lint`, `lint:fix`, and `test:ci` scripts.

## Practical command set

- Backend tests: `pytest`
- Frontend build: `npm run build`
- Frontend lint: `npm run lint`
- Frontend CI-style tests: `npm run test:ci`
