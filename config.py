from pathlib import Path

API_ID=37071915
API_HASH = '813aa290bbc1be070ff00f6ca8eb8a19'
OWNER_ID = 940460718
COMMAND_PATTERNS = [
    r'^\.startrp(?:\s+.*)?$',
    r'^\.unrp(?:\s+.*)?$',
    r'^\.list$',
    r'^\.clearrp$',
    r'^\.chatid$',
    r'^\.pickmeon$',
    r'^\.pickmeoff$',
    r'^\.photo(?:\s+.*)?$',
    r'^\.menu$',
    r'^\.id$',
]
BASE_DIR = Path(__file__).resolve().parent
PHRASES_FILE = BASE_DIR / "phrases.txt"
PHOTOS_DIR = BASE_DIR / "photos"

