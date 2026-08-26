# LLM Integration

The backend uses a provider abstraction so NVIDIA can be swapped later without changing the rest of the application.

## API Key Location

Set `NVIDIA_API_KEY` in the backend `.env` file or backend environment variables. The key is never exposed to the browser.

Rules:
- structured JSON output only
- retries with bounded attempts
- no secret exposure to the browser
- per-question context only, not unnecessary full-state payloads
