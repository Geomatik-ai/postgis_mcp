import os

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("GIS_READER_PASSWORD", "test_password")
