# AUTO-GENERATED FROM ebay_pipeline.ipynb
import asyncio

async def main():
    STEP = 'ENVIRONMENT_PREPARATION'

    # imports
    import os
    import sys
    import json
    import time
    import polars as pl
    from pathlib import Path

    
    DECODO_USERNAME = os.getenv("DECODO_USERNAME")
    DECODO_PASSWORD = os.getenv("DECODO_PASSWORD")
    DECODO_URL = os.getenv("DECODO_URL")
    SELENIUM_REMOTE_URL = os.getenv("SELENIUM_REMOTE_URL")
    PIPELINE_API_SECRET = os.getenv("PIPELINE_API_SECRET")
    
    IS_DEVELOPMENT = False
    
    PIPELINE_NAME = "example_pipeline"

    
    
    # Local utilities detection
    if IS_DEVELOPMENT:
        module_path = os.path.abspath(os.path.join('..'))
        if module_path not in sys.path:
            sys.path.append(module_path)
    else:
        script_dir = Path(__file__).resolve().parent
        module_path = script_dir.parent
        if str(module_path) not in sys.path:
            sys.path.append(str(module_path))
    
    from scrapers_utils import BaseScraper
    from pipeline_utils.exception_handler import handle_error
    from pipeline_utils import RunManager
    from pipeline_utils.cleaning_utils import strip_all_str
    
    # Parameter handling
    if not IS_DEVELOPMENT:
        RUN_ID = sys.argv[1]
        PARAMS = json.loads(sys.argv[2])
        run = RunManager(RUN_ID)
        headless = True
    else:
        PARAMS = {} 
        run = None 
        headless = False

    STEP = 'SCRAPER_INITIALIZATION'

    scraper = BaseScraper(
        headless=headless,
        use_proxy=True,
        proxy_user=DECODO_USERNAME,
        proxy_pass=DECODO_PASSWORD,
        proxy_server=DECODO_URL,
        remote_url=SELENIUM_REMOTE_URL
    )

    await scraper.start()

    STEP = 'HOME_PAGE'

    SANDBOX_BUTTON_TEXT = 'Explore Sandbox'

    try:
        await scraper.page.goto("https://www.scrapethissite.com/")
        await scraper.human_pause()
        button = scraper.page.get_by_text(SANDBOX_BUTTON_TEXT)
        await scraper.human_jitter_click(button)
        await scraper.wait_for_page_load()
    except Exception as e:
        await scraper.stop()
        handle_error(PIPELINE_NAME, run, "DATA_RECOLLECTION", e)

    HOCKEY_TEAMS_BUTTON_TEXT = 'Hockey Teams'

    try:
        await scraper.human_pause()
        button = scraper.page.get_by_text(HOCKEY_TEAMS_BUTTON_TEXT)
        await scraper.human_jitter_click(button)
        await scraper.wait_for_page_load()
    except Exception as e:
        await scraper.stop()
        handle_error(PIPELINE_NAME, run, "DATA_RECOLLECTION", e)

    STEP = 'HOCKEY_TEAMS_PAGE'

    DATA_TABLE = '//table' 
    TABLE_HEADERS = 'th'
    TEAM_ROW = '//tr[@class="team"]'
    ROW_COLUMN = 'td'

    try:
        data_dict = {}
        
        await scraper.wait_for_page_load()
        data_table = scraper.page.locator(DATA_TABLE) 
        headers =  await data_table.locator(TABLE_HEADERS).all_inner_texts()
        
        for header in headers:
            data_dict[header] = []
        
        while True:
            next_button = scraper.page.get_by_label('Next')
        
            await scraper.human_jitter_click(next_button)
        
            await scraper.wait_for_page_load()
            
            data_table = scraper.page.locator(DATA_TABLE) 
            
            teams = await data_table.locator(TEAM_ROW).all()
            for team in teams:
                team_data = await team.locator(ROW_COLUMN).all_inner_texts()
                for i, key in enumerate(data_dict.keys()):
                    data_dict[key].append(team_data[i])
        
            if await next_button.count() == 0 or await next_button.is_disabled():
                break
            
            await scraper.human_pause()
    except Exception as e:
        await scraper.stop()
        handle_error(PIPELINE_NAME, run, "DATA_RECOLLECTION", e)

    STEP = 'STORING_RAW_DATA'

    if run: run.update(step="STORING_RAW_DATA")
    try:
        if not data_dict:
            raise ValueError("Zero items collected.")
        
        if run: run.save_raw_data(data_dict)
    except Exception as e:
        handle_error(PIPELINE_NAME, run, "STORING_RAW_DATA", e)

    if run: run.update(step="CLEANING_RAW_DATA")
    try:
        df = pl.DataFrame(data_dict)
        df = strip_all_str(df)
        
        # Standard cleaning/casting
        df = df.with_columns([
            pl.col("Team Name").fill_null("Unknown").cast(pl.String),
            pl.col("Year").replace("","0").cast(pl.Int64),
            pl.col("Wins").replace("","0").cast(pl.Int64),
            pl.col("Losses").replace("","0").cast(pl.Int64),
            pl.col("OT Losses").replace("","0").cast(pl.Int64),
            pl.col("Win %").cast(pl.Float64),
            pl.col("Goals For (GF)").replace("","0").cast(pl.Int64),
            pl.col("Goals Against (GA)").replace("","0").cast(pl.Int64),
            pl.col("+ / -").replace("","0").cast(pl.Int64)
        ])
        
        cleaned_data = df.to_dict(as_series=False)
    except Exception as e:
        handle_error(PIPELINE_NAME, run, "CLEANING_RAW_DATA", e)

    if run: run.update(step="STORING_CLEANED_DATA")
    try:
        if run: run.save_cleaned_data(cleaned_data)
        print("Done.")
    except Exception as e:
        handle_error(PIPELINE_NAME, run, "STORING_CLEANED_DATA", e)

    await scraper.stop()


if __name__ == "__main__":
    asyncio.run(main())
