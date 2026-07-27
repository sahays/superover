# Workspace Custom Rules for Super Over Alchemy

## Development Rules
- **Verification**: Always run `./run_tests.sh api`, `./run_tests.sh worker`, or `./run_tests.sh libs` depending on modified components after making code changes.
- **Type Annotations**: Ensure all Python functions specify return types and argument types.
- **Schema Validation**: Any changes to scene analysis payloads must maintain compatibility with `scene_analysis_schema.json`.
