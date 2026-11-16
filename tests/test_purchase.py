import tempfile
import unittest
from pathlib import Path

import app as miniboard


class PurchaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db = miniboard.DB
        miniboard.DB = Path(self.temp_dir.name) / "test.db"
        miniboard.app.config["TESTING"] = True
        miniboard.init_db()
        self.client = miniboard.app.test_client()

        with miniboard.connect() as con:
            cur = con.execute(
                """INSERT INTO products
                (name, price, description, image, created_at)
                VALUES (?, ?, ?, ?, ?)""",
                ("テスト商品", 1200, "説明", "/test.png", "2026-01-01")
            )
            self.product_id = cur.lastrowid

    def tearDown(self):
        miniboard.DB = self.original_db
        self.temp_dir.cleanup()

    def test_purchase_records_order_and_marks_product_sold(self):
        response = self.client.post(
            f"/api/products/{self.product_id}/purchase",
            json={"buyer_name": "購入者"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["buyer_name"], "購入者")
        self.assertEqual(response.json["price"], 1200)
        products = self.client.get("/api/products").json
        self.assertTrue(products[0]["sold"])

    def test_cannot_purchase_product_twice(self):
        url = f"/api/products/{self.product_id}/purchase"
        self.assertEqual(
            self.client.post(url, json={"buyer_name": "購入者"}).status_code,
            201,
        )

        response = self.client.post(url, json={"buyer_name": "別の購入者"})

        self.assertEqual(response.status_code, 409)

    def test_purchase_history_is_filtered_by_buyer_name(self):
        self.client.post(
            f"/api/products/{self.product_id}/purchase",
            json={"buyer_name": "購入者"},
        )

        own_history = self.client.get(
            "/api/orders?buyer_name=%E8%B3%BC%E5%85%A5%E8%80%85"
        )
        other_history = self.client.get("/api/orders?buyer_name=%E5%88%A5%E4%BA%BA")
        missing_name = self.client.get("/api/orders")

        self.assertEqual(own_history.status_code, 200)
        self.assertEqual(len(own_history.json), 1)
        self.assertEqual(own_history.json[0]["product_name"], "テスト商品")
        self.assertEqual(other_history.json, [])
        self.assertEqual(missing_name.status_code, 400)

    def test_requires_buyer_name_and_existing_product(self):
        missing_name = self.client.post(
            f"/api/products/{self.product_id}/purchase",
            json={"buyer_name": "  "},
        )
        invalid_body = self.client.post(
            f"/api/products/{self.product_id}/purchase",
            json=["購入者"],
        )
        missing_product = self.client.post(
            "/api/products/999/purchase",
            json={"buyer_name": "購入者"},
        )

        self.assertEqual(missing_name.status_code, 400)
        self.assertEqual(invalid_body.status_code, 400)
        self.assertEqual(missing_product.status_code, 404)

    def test_product_comments_are_saved_and_scoped_to_product(self):
        response = self.client.post(
            f"/api/products/{self.product_id}/comments",
            json={"name": "コメント者", "comment": "気になります"},
        )

        with miniboard.connect() as con:
            cur = con.execute(
                """INSERT INTO products
                (name, price, description, image, created_at)
                VALUES (?, ?, ?, ?, ?)""",
                ("別の商品", 500, "別の商品説明", "/other.png", "2026-01-02")
            )
            other_product_id = cur.lastrowid

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["comment"], "気になります")
        comments = self.client.get(
            f"/api/products/{self.product_id}/comments"
        )
        other_comments = self.client.get(
            f"/api/products/{other_product_id}/comments"
        )
        self.assertEqual(len(comments.json), 1)
        self.assertEqual(comments.json[0]["name"], "コメント者")
        self.assertEqual(other_comments.json, [])

    def test_product_comments_require_content_and_existing_product(self):
        missing_content = self.client.post(
            f"/api/products/{self.product_id}/comments",
            json={"name": "", "comment": "  "},
        )
        missing_product = self.client.post(
            "/api/products/999/comments",
            json={"name": "コメント者", "comment": "コメント"},
        )

        self.assertEqual(missing_content.status_code, 400)
        self.assertEqual(missing_product.status_code, 404)

    def test_cancel_listing_removes_product_and_its_comments(self):
        self.client.post(
            f"/api/products/{self.product_id}/comments",
            json={"name": "コメント者", "comment": "確認コメント"},
        )

        response = self.client.delete(f"/api/products/{self.product_id}")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get("/api/products").json, [])
        self.assertEqual(
            self.client.get(
                f"/api/products/{self.product_id}/comments"
            ).status_code,
            404,
        )

    def test_cannot_cancel_purchased_or_missing_product(self):
        self.client.post(
            f"/api/products/{self.product_id}/purchase",
            json={"buyer_name": "購入者"},
        )

        purchased = self.client.delete(f"/api/products/{self.product_id}")
        missing = self.client.delete("/api/products/999")

        self.assertEqual(purchased.status_code, 409)
        self.assertEqual(missing.status_code, 404)
        products = self.client.get("/api/products").json
        self.assertEqual(len(products), 1)
        self.assertTrue(products[0]["sold"])


if __name__ == "__main__":
    unittest.main()
