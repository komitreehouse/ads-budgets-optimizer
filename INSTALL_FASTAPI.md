# Installing FastAPI - Manual Instructions

Due to network restrictions in the sandbox, you'll need to install FastAPI manually.

## Option 1: Install from requirements.txt (Recommended)

```bash
pip3 install -r requirements.txt
```

This will install all dependencies including FastAPI.

## Option 2: Install FastAPI packages directly

```bash
pip3 install fastapi uvicorn python-multipart
```

For better performance (optional):
```bash
pip3 install "uvicorn[standard]"
```

## Option 3: Use a Virtual Environment (Best Practice)

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

## Verify Installation

After installing, verify it works:

```bash
python3 -c "import fastapi; import uvicorn; print('FastAPI:', fastapi.__version__); print('Uvicorn:', uvicorn.__version__)"
```

You should see version numbers printed.

## Troubleshooting

### Permission Errors

If you get permission errors, try:
- Using `pip3 install --user` to install for your user only
- Using a virtual environment (recommended)
- Using `sudo pip3 install` (not recommended, but works)

### SSL Errors

If you get SSL errors, you may need to:
- Update your certificates
- Use `pip3 install --trusted-host pypi.org --trusted-host files.pythonhosted.org`

### Python Version

Make sure you're using Python 3.7+:
```bash
python3 --version
```

FastAPI requires Python 3.7+.

## After Installation

Once FastAPI is installed:

1. **Test the API:**
   ```bash
   python3 scripts/test_api.py
   ```

2. **Start the API server:**
   ```bash
   python3 scripts/run_api.py
   ```

3. **In another terminal, start the frontend:**
   ```bash
   streamlit run frontend/app.py
   ```
