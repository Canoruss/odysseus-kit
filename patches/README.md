# Core patches

Small, optional patches the installer applies to the stock Odysseus 1.0.2 files (copies, never the image itself):

- **Auto model** (`auto_router.py`, `llm_defaults.py`, `chat_routes`, `chat_processor`, `model_routes`): an extra "Auto" entry in the model picker that sends simple messages to a fast model and harder ones to a thinking model. Needs at least one configured model; override the picks with the `auto_route_*` settings.
- **Sampling defaults** per model type, and `top_p` support (`llm_core`, `agent_loop`).
- **Base persona** (`prompt_security`) and **memory audit in small batches** (`memory_extractor`).
- **Quieter email logs** (`email_helpers`, `email_routes`) and a clean 404 for a missing page (`app`).

All-or-nothing: if any patch does not apply cleanly (for example on another Odysseus version), the installer skips them all and continues. Disable with `KIT_PATCHES=0 ./install.sh`.
