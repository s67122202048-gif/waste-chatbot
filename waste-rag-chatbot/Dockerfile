FROM python:3.11-slim
# docker build --build-arg LOCAL_EMBEDDINGS=1 . = รวมโมเดลค้นหาในเครื่อง (ภาพใหญ่ ใช้ RAM >= 2 GB)
ARG LOCAL_EMBEDDINGS=0
WORKDIR /app
COPY requirements.txt requirements-local.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && if [ "$LOCAL_EMBEDDINGS" = "1" ]; then \
      pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
      && pip install --no-cache-dir -r requirements-local.txt; \
    fi
COPY . .
ENV APP_STORAGE=/data PYTHONUNBUFFERED=1
EXPOSE 8501
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true"]
