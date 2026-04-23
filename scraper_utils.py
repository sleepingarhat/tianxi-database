"""Shared utilities for all HKJC scrapers (Traditional Chinese pages)."""
import os
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

CHROMIUM_PATH = os.environ.get(
    "CHROMIUM_PATH",
    "/nix/store/qa9cnw4v5xkxyip6mb9kxqfq1z4x2dx1-chromium-138.0.7204.100/bin/chromium",
)
CHROMEDRIVER_PATH = os.environ.get(
    "CHROMEDRIVER_PATH",
    "/nix/store/8zj50jw4w0hby47167kqqsaqw4mm5bkd-chromedriver-unwrapped-138.0.7204.100/bin/chromedriver",
)

MAX_RETRIES = 3
PAGE_TIMEOUT = 30


def make_driver():
    opts = webdriver.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.binary_location = CHROMIUM_PATH
    from selenium.webdriver.chrome.service import Service as ChromeService
    return webdriver.Chrome(
        service=ChromeService(executable_path=CHROMEDRIVER_PATH),
        options=opts
    )


def load_page(driver, url, timeout=PAGE_TIMEOUT, retries=MAX_RETRIES):
    for attempt in range(1, retries + 1):
        try:
            driver.get(url)
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            return True
        except Exception as e:
            print(f"  Load failed attempt {attempt}/{retries} for {url}: {type(e).__name__}: {e}")
            if attempt < retries:
                time.sleep(3)
    return False


def safe_cell(cells, index, default=""):
    try:
        return cells[index].text.strip()
    except (IndexError, Exception):
        return default


def log_failed(logfile, entity_id, reason=""):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(logfile, "a") as f:
        f.write(f"{entity_id}  # {reason}  [{ts}]\n")


def parse_zh_location(raw):
    """
    Parse a Traditional Chinese location string into (racecourse, track, course).

    Examples:
      '沙田草地"A"'        -> ('沙田', '草地', 'A')
      '跑馬地草地"A"'      -> ('跑馬地', '草地', 'A')
      '沙田全天候跑道'      -> ('沙田', '全天候跑道', '')
      '草地"C"'            -> ('', '草地', 'C')
      '沙地跑道'           -> ('', '沙地跑道', '')
    """
    raw = raw.strip()
    m = re.match(
        r'^(沙田|跑馬地)?(草地|全天候跑道|沙地跑道|沙地|泥地)"?([^"]*)"?$',
        raw
    )
    if m:
        racecourse = m.group(1) or ""
        track = m.group(2) or ""
        course = m.group(3).strip('"').strip() if m.group(3) else ""
        return racecourse, track, course
    return raw, "", ""
