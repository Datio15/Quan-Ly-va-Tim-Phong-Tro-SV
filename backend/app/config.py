"""Đọc cấu hình từ biến môi trường (SPEC mục 15). Không có giá trị bí mật mặc định."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def _is_set(value: str | None) -> bool:
    """Giá trị giữ chỗ trong .env.example (CHANGE_ME, SUFFIX) coi như chưa cấu hình."""
    return bool(value) and value != "CHANGE_ME" and "SUFFIX" not in value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # PostgreSQL
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "phongtro_db"
    db_user: str = "phongtro_user"
    db_password: str = ""

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_root_user: str = ""
    minio_root_password: str = ""
    minio_bucket_private: str = "private"
    minio_bucket_public_src: str = "public-src"
    minio_secure: bool = False

    # Xác thực
    jwt_secret: str = ""
    jwt_expire_minutes: int = 720
    seed_demo_password: str = ""

    # Chi phí ước tính mặc định (mục 9.5, đã chốt ở mục 23)
    est_kwh_per_month: float = 100
    est_water_m3_per_month: float = 4
    est_people: int = 1
    est_vehicles: int = 1

    # Tìm kiếm
    search_timeout_ms: int = 3000
    azure_search_endpoint: str = ""
    azure_search_index: str = "rooms-public"
    azure_search_query_key: str = ""

    # Khác
    azure_maps_key: str = ""
    azure_blob_public_base_url: str = ""
    applicationinsights_connection_string: str = ""
    telegram_bot_name: str = ""

    # Đề xuất bổ sung SPEC (xem backend/README.md)
    cors_origins: str = ""                  # danh sách nguồn, phân tách bằng dấu phẩy
    review_skip_booking_check: bool = False  # bật để demo đánh giá không cần lịch 'done'

    @property
    def database_url(self) -> str:
        from urllib.parse import quote_plus

        return (
            f"postgresql+psycopg://{quote_plus(self.db_user)}:{quote_plus(self.db_password)}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def azure_search_enabled(self) -> bool:
        return _is_set(self.azure_search_endpoint) and _is_set(self.azure_search_query_key)

    @property
    def appinsights_enabled(self) -> bool:
        return _is_set(self.applicationinsights_connection_string)

    @property
    def maps_key_public(self) -> str:
        return self.azure_maps_key if _is_set(self.azure_maps_key) else ""

    @property
    def blob_base_url(self) -> str:
        return self.azure_blob_public_base_url.rstrip("/") if _is_set(self.azure_blob_public_base_url) else ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
