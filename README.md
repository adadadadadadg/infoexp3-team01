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
- POST `/api/messages/<id>/reactions`
- PUT `/api/messages/<id>`
- DELETE `/api/messages/<id>`
- GET `/api/products` — 商品一覧（購入済み商品には `sold: true`）
- GET `/api/products/<id>/comments` — 商品のコメント一覧
- POST `/api/products/<id>/comments` — 商品にコメントを投稿（`name`, `comment`）
- POST `/api/products/<id>/reactions` — 商品へのリアクション追加・取り消し
- GET `/api/orders?buyer_name=<name>` — 購入者名に一致する注文履歴
- GET `/api/orders?participant_name=<name>` — 購入者または出品者名に一致する注文履歴
- GET `/api/orders/<id>/messages?participant_name=<name>` — 注文の会話を取得
- POST `/api/orders/<id>/messages` — 注文の会話に投稿（`participant_name`, `message`）
- POST `/api/products` — 商品を出品
- POST `/api/products/<id>/purchase` — 購入者名を指定して注文を記録
- DELETE `/api/products/<id>` — 未購入商品の出品を取り消し

購入処理は注文を記録し、同じ商品が重複購入されないようにします。購入後は購入履歴から注文ごとの会話を開始できます。出品者も出品時の出品者名で購入履歴を表示できます。購入済み商品は出品を取り消せません。外部決済は行いません。

> 授業用。会話の参加者確認は名前の一致のみで、ログイン認証はありません。個人情報・秘密情報や、秘匿が必要な内容を入力しないでください。
