# autoscriber-app-backend

## Development

1. Install all packages in _requirements.txt_

```
pip3 install -r requirements.txt
```

2. Make sure sql is configured in `main.py` and add `sql_pass` 

3. Running the server
```
uvicorn main:app --reload
```