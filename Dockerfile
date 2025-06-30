FROM python:3.9-slim-bullseye
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ALL files (including inventory)
COPY . .

# Verify files were copied (debugging)
RUN ls -la /app/inventory/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]