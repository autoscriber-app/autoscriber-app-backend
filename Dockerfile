FROM python:3.7-slim-buster

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt
RUN pip3 install uvicorn[standard]
COPY . .

CMD [ "python3", "-m" , "uvicorn", "main:app", "--host=0.0.0.0", "--port=8001"]
