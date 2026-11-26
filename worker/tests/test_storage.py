"""Kiểm thử đơn vị worker/storage.py (SAS giới hạn quyền), không cần Azure hay CSDL.

Chạy (image worker không chứa thư mục tests, nên gắn vào khi chạy):
    docker compose run --rm --no-deps -v ./worker/tests:/app/tests worker python -m unittest discover -s tests -v
"""
import os
import unittest
from unittest import mock

from worker import storage

ACCOUNT = "stphongtrotest"
IMAGES_URL = f"https://{ACCOUNT}.blob.core.windows.net/public-images"
QUEUE_URL = f"https://{ACCOUNT}.queue.core.windows.net/ops-ticks"
IMAGES_SAS = "sv=2022-11-02&si=worker-pub&sr=c&spr=https&sig=AbC%2Bdef%3D"
QUEUE_SAS = "sv=2022-11-02&si=worker-queue&spr=https&sig=XyZ%2Bghi%3D"
CONN = (f"DefaultEndpointsProtocol=https;AccountName={ACCOUNT};"
        "AccountKey=dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleQ==;EndpointSuffix=core.windows.net")

VARS = ("AZURE_PUBLIC_IMAGES_SAS", "AZURE_PUBLIC_IMAGES_URL", "AZURE_BLOB_PUBLIC_BASE_URL",
        "AZURE_QUEUE_SAS", "AZURE_QUEUE_URL", "AZURE_STORAGE_CONNECTION_STRING")


def env(**values):
    """Đặt đúng các biến Storage cho một ca kiểm thử; biến không nêu thì để trống."""
    return mock.patch.dict(os.environ, {k: values.get(k, "") for k in VARS})


class ImagesTest(unittest.TestCase):
    def test_sas_duoc_uu_tien_hon_chuoi_ket_noi(self):
        with env(AZURE_PUBLIC_IMAGES_SAS=IMAGES_SAS, AZURE_BLOB_PUBLIC_BASE_URL=IMAGES_URL,
                 AZURE_STORAGE_CONNECTION_STRING=CONN):
            self.assertEqual(storage.images_mode(), storage.SAS)
            c = storage.images_container()
        self.assertEqual(c.container_name, "public-images")
        self.assertEqual(c.account_name, ACCOUNT)
        self.assertIn("sig=", c.url)  # client mang SAS, không mang khóa tài khoản

    def test_url_cong_khai_khong_chua_chu_ky_sas(self):
        with env(AZURE_PUBLIC_IMAGES_SAS=IMAGES_SAS, AZURE_BLOB_PUBLIC_BASE_URL=IMAGES_URL):
            blob = storage.images_container().get_blob_client("rooms/r1/i1.jpg")
        self.assertIn("sig=", blob.url)
        url = storage.public_url(blob.url)
        self.assertEqual(url, f"{IMAGES_URL}/rooms/r1/i1.jpg")
        self.assertNotIn("?", url)

    def test_url_container_rieng_uu_tien_hon_base_url(self):
        with env(AZURE_PUBLIC_IMAGES_SAS=IMAGES_SAS, AZURE_PUBLIC_IMAGES_URL=IMAGES_URL,
                 AZURE_BLOB_PUBLIC_BASE_URL="https://cdn.example.com/anh"):
            self.assertEqual(storage.images_container().account_name, ACCOUNT)

    def test_bo_dau_nhay_va_dau_hoi_cua_sas(self):
        with env(AZURE_PUBLIC_IMAGES_SAS=f'"?{IMAGES_SAS}"', AZURE_BLOB_PUBLIC_BASE_URL=IMAGES_URL + "/"):
            c = storage.images_container()
        self.assertEqual(c.url.count("?"), 1)
        self.assertTrue(c.url.startswith(IMAGES_URL + "?"))

    def test_du_phong_bang_chuoi_ket_noi(self):
        with env(AZURE_STORAGE_CONNECTION_STRING=CONN):
            self.assertEqual(storage.images_mode(), storage.CONN)
            c = storage.images_container()
        self.assertEqual(c.container_name, "public-images")
        self.assertNotIn("sig=", c.url)

    def test_co_sas_ma_thieu_url_thi_khong_dung_sas(self):
        with env(AZURE_PUBLIC_IMAGES_SAS=IMAGES_SAS):
            self.assertIsNone(storage.images_mode())
        with env(AZURE_PUBLIC_IMAGES_SAS=IMAGES_SAS, AZURE_STORAGE_CONNECTION_STRING=CONN):
            self.assertEqual(storage.images_mode(), storage.CONN)

    def test_gia_tri_giu_cho_xem_nhu_chua_cau_hinh(self):
        with env(AZURE_PUBLIC_IMAGES_SAS="CHANGE_ME",
                 AZURE_BLOB_PUBLIC_BASE_URL="https://stphongtroSUFFIX.blob.core.windows.net/public-images",
                 AZURE_STORAGE_CONNECTION_STRING="CHANGE_ME"):
            self.assertIsNone(storage.images_mode())
            self.assertIsNone(storage.images_container())


class QueueTest(unittest.TestCase):
    def test_sas_hang_doi(self):
        with env(AZURE_QUEUE_SAS=QUEUE_SAS, AZURE_QUEUE_URL=QUEUE_URL, AZURE_STORAGE_CONNECTION_STRING=CONN):
            self.assertEqual(storage.queue_mode(), storage.SAS)
            q = storage.queue_client("ops-ticks")
        self.assertEqual(q.queue_name, "ops-ticks")
        self.assertIn("sig=", q.url)

    def test_du_phong_bang_chuoi_ket_noi(self):
        with env(AZURE_STORAGE_CONNECTION_STRING=CONN):
            q = storage.queue_client("ops-ticks")
        self.assertEqual(q.queue_name, "ops-ticks")
        self.assertEqual(q.account_name, ACCOUNT)

    def test_chua_cau_hinh(self):
        with env():
            self.assertIsNone(storage.queue_client("ops-ticks"))

    def test_tin_json_khong_ma_hoa_base64(self):
        with env(AZURE_QUEUE_SAS=QUEUE_SAS, AZURE_QUEUE_URL=QUEUE_URL):
            q = storage.queue_client("ops-ticks")
        # Function ghi tin JSON thuần; client mà mã hóa base64 thì worker đọc ra chuỗi rác.
        self.assertEqual(type(q._message_encode_policy).__name__, "NoEncodePolicy")
        self.assertEqual(type(q._message_decode_policy).__name__, "NoDecodePolicy")


if __name__ == "__main__":
    unittest.main()
