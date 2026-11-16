# MiniBoard Starter — 情報科学演習III

## Local / Codespaces
```bash
pip install -r requirements.txt
python app.py
```

## Docker
```bash
docker build -t miniboard .
docker run --rm -p 5000:5000 miniboard
```

## API
- GET `/api/messages`
- POST `/api/messages`
- PUT `/api/messages/<id>`
- DELETE `/api/messages/<id>`

> 授業用。Public URLに個人情報・秘密情報を入力しないこと。
