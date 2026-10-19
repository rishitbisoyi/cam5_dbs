import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "cinebook-fallback-secret-key-39182371")
    
    # MySQL Database Configuration
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "qwerty")
    DB_NAME = os.getenv("DB_NAME", "CineBookDB")
    DB_PORT = int(os.getenv("DB_PORT", 3306))
    
    # Admin Credentials
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD_HASH = os.getenv(
        "ADMIN_PASSWORD_HASH",
        "scrypt:32768:8:1$zOLXdvIeZuqpUCxd$fd365302b3d52c1a8d050585e3b88970c464eb2d7c05661741c59f82b0f3264f8d4416bbb8401506dd97b920cb5dbe85e63cc734800b4968266e43f9c56a0d1f"
    )
    ADMIN_DEFAULT_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD", "admin123")

    @classmethod
    def get_db_config(cls):
        return {
            "host": cls.DB_HOST,
            "user": cls.DB_USER,
            "password": cls.DB_PASSWORD,
            "database": cls.DB_NAME,
            "port": cls.DB_PORT,
            "charset": "utf8mb4",
            "autocommit": False
        }
