# AUTO-GENERATED FROM example_pipeline.ipynb

IS_DEVELOPMENT = False

PIPELINE_NAME = "example_pipeline"

import os
import sys
import json
from pathlib import Path

if not IS_DEVELOPMENT:
    RUN_ID = sys.argv[1]
    params_raw = sys.argv[2]
    PARAMS = json.loads(params_raw)
else:
    PARAMS = {}

if IS_DEVELOPMENT:
    module_path = os.path.abspath(os.path.join('..'))
    if module_path not in sys.path:
        sys.path.append(module_path)
else:
    script_dir = Path(__file__).resolve().parent
    module_path = script_dir.parent
    if str(module_path) not in sys.path:
        sys.path.append(str(module_path))

import time
import polars as pl
from scrapers_utils import BaseScraper
from pipeline_utils import RunManager
from pipeline_utils.cleaning_utils import strip_all_str
from selenium.webdriver.common.by import By

# Development options
if IS_DEVELOPMENT:
    headless = False
    run = RunManager.start_run(
        instance_id="8be90d9f-633b-4231-887c-5b1c80249543"
    )
else:
    run = RunManager(RUN_ID)
    headless = True

# Scraper initializiation
scraper = BaseScraper.create_with_decodo(port=20001, timeout=30, headless=headless)
scraper.driver.get("https://www.scrapethissite.com/")

SANDBOX_BUTTON = (By.XPATH, "//a[contains(text(), 'Explore Sandbox')]")

try:
    sandbox_button = scraper.wait_for_clickable(SANDBOX_BUTTON)
    sandbox_button.click()
except Exception as e:
    scraper.quit()
    run.set_run_fail(f"SANDBOX_BUTTON: {e}")

scraper.human_jitter()

HOCKEY_TEAMS_BUTTON = (By.XPATH, "//a[contains(text(), 'Hockey Teams')]")

try:
    hockey_teams_button = scraper.wait_for_clickable(HOCKEY_TEAMS_BUTTON)
    hockey_teams_button.click()
except Exception as e:
    scraper.quit()
    run.set_run_fail(f"HOCKEY_TEAMS_BUTTON: {e}")

scraper.human_jitter()

TABLE_HEADERS = (By.XPATH, "//table[@class='table']//th")
TEAMS_DATA = (By.XPATH, "//table[@class='table']//tr[@class='team']")
TEAM_ROW = (By.XPATH, ".//td")
NEXT_PAGE_BUTTON = (By.XPATH, "//a[@aria-label='Next']")


raw_data_dict = {}

# Raw data dict initialization
try:
    headers_elements_list = scraper.get_all_objects(TABLE_HEADERS)
    for header_elmt in headers_elements_list:
        raw_data_dict[header_elmt.text] = []
    headers = raw_data_dict.keys()
except Exception as e:
    scraper.quit()
    run.set_run_fail(f"TABLE_HEADERS: {e}")

def get_table_data():
    teams_table_elements = scraper.get_all_objects(TEAMS_DATA)
    for team in teams_table_elements:
        row = team.find_elements(*TEAM_ROW)
        for i, key in enumerate(headers):
            raw_data_dict[key].append(row[i].text)

# Pagination and data recollection
try:
    while True:
        next_page_button = scraper.wait_for_present(NEXT_PAGE_BUTTON)
        if next_page_button is not None:
            next_page_button.click()
            get_table_data()
            scraper.human_jitter()
        else:
            break
except Exception as e:
    scraper.quit()
    run.set_run_fail(f"NEXT_PAGE_BUTTON  or TEAMS_DATA: {e}")

# Closing scraper
scraper.quit()

run.update(step="STORING_RAW_DATA")

try:
    run.save_raw_data(raw_data_dict)
except Exception as e:
    run.set_run_fail(f"STORING_RAW_DATA: {e}")

run.update(step="CLEANING_RAW_DATA")

raw_df = pl.DataFrame(raw_data_dict)
clean_df = raw_df.clone()

# All str strip
clean_df = strip_all_str(clean_df)

# Specific Type Casting and Values Cleaning
clean_df = clean_df.with_columns([
    pl.col("Team Name").replace("","0").cast(pl.String),
    pl.col("Year").replace("","0").cast(pl.Int64),
    pl.col("Wins").replace("","0").cast(pl.Int64),
    pl.col("Losses").replace("","0").cast(pl.Int64),
    pl.col("OT Losses").replace("","0").cast(pl.Int64),
    pl.col("Win %").cast(pl.Float64),
    pl.col("Goals For (GF)").replace("","0").cast(pl.Int64),
    pl.col("Goals Against (GA)").replace("","0").cast(pl.Int64),
    pl.col("+ / -").replace("","0").cast(pl.Int64)
])

cleaned_data_dict = clean_df.to_dict(as_series=False)

run.update(step="STORING_CLEANED_DATA")

try:
    run.save_cleaned_data(cleaned_data_dict)
except Exception as e:
    run.set_run_fail(f"STORING_CLEANED_DATA: {e}")

