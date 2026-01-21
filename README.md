# PSS CF MCP Server

A MCP server for hosting tools for development modernization.

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd pss_cf_mcp_tools
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your actual credentials
```
## Running the Server

### Development Mode

```bash
python -m app.main
```

Or with uvicorn directly:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Production Mode

```bash
# Set environment variables
export ENV=production
export DEBUG=false
export HOST=0.0.0.0
export PORT=8000

# Run with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```