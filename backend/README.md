# OMNIVEX Backend Documentation

> **Academic Research Prototype Notice:**  
> This backend is an academic research system designed for studying distribution drift, empirical performance metrics, and model reliability. It is not certified for production critical systems.

## Execution Instructions (Windows Command Prompt)

1. Activate virtual environment from project root:
   ```cmd
   cd C:\OMNIVEX
   venv\Scripts\activate
   ```
2. Run backend test suite:
   ```cmd
   python -m pytest -v
   ```
3. Start the FastAPI backend server:
   ```cmd
   uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
   ```
4. Access Swagger API documentation:
   - [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
