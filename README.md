# autoscriber-app-backend

## Development

1. Install all packages in _requirements.txt_

```
pip3 install -r requirements.txt
```

2. Make sure sql is configured in `main.py` and create `sql_pass` 

3. Running the server
```
uvicorn main:app --reload
```
  - Requests can be made at be at [localhost:8000](http://localhost:8000/)/{endpoint}
  - Swagger UI interactive API documentation found at [localhost:8000/docs](http://localhost:8000/docs)
  - Testing can be done using pytest
```
pip install -U pytest
pytest test_main.py
```
