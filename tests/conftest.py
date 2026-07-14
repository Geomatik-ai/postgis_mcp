import os

from dotenv import load_dotenv

os.environ.setdefault("GIS_READER_PASSWORD", "test_password")

load_dotenv()
