# AUTO-GENERATED FROM example_pipeline.ipynb
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

    
    EXAMPLE_INSTANCE_ID = '8be90d9f-633b-4231-887c-5b1c80249543'
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
        run = RunManager.start_run(instance_id=EXAMPLE_INSTANCE_ID) 
        headless = False

    run_state = run.refresh()
    STEP = run_state.get('step', 'DATA_RECOLLECTION')
    run_data = run_state.get('run_data', {})

    if STEP == 'DATA_RECOLLECTION':
        scraper = BaseScraper(
            headless=headless,
            use_proxy=True,
            proxy_user=DECODO_USERNAME,
            proxy_pass=DECODO_PASSWORD,
            proxy_server=DECODO_URL,
            remote_url=SELENIUM_REMOTE_URL
        )
        await scraper.start()

    SANDBOX_BUTTON_TEXT = 'Explore Sandbox'
    HOCKEY_TEAMS_BUTTON_TEXT = 'Hockey Teams: Forms, Searching and Pagination'
    TABLE_HEADERS = '//th'
    DATA_TABLE =  '//table'
    TEAM_ROW = '//tr[@class="team"]'
    ROW_COLUMN = '//td'

    try:
        try:
            if STEP == 'DATA_RECOLLECTION':
                await scraper.page.goto("https://www.scrapethissite.com/")
                await scraper.human_pause()
                button = scraper.page.get_by_text(SANDBOX_BUTTON_TEXT)
                await scraper.human_jitter_click(button)
                await scraper.wait_for_page_load()
        
                # ... Transition to next page section ...
                # ... Lists Page ...
                await scraper.human_pause()
                button = scraper.page.get_by_text(HOCKEY_TEAMS_BUTTON_TEXT)
                await scraper.human_jitter_click(button)
                await scraper.wait_for_page_load()
        
                # ... Hockey Teams Page extraction ...
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
            elif STEP in ['STORING_RAW_DATA', 'CLEANING_RAW_DATA']:
                data_dict = run.get_raw_data()
        finally:
            if STEP == 'DATA_RECOLLECTION' and 'scraper' in locals():
                await scraper.stop()
    except Exception as e:
        await scraper.stop()
        handle_error(PIPELINE_NAME, run, "DATA_RECOLLECTION", e)

    if STEP == 'DATA_RECOLLECTION':
        STEP = 'STORING_RAW_DATA'
        run.update(step = STEP)

    if STEP == 'STORING_RAW_DATA':
        try:
            if not data_dict:
                raise ValueError("Zero items collected.")
            
            if run: run.save_raw_data(data_dict)
        except Exception as e:
            handle_error(PIPELINE_NAME, run, "STORING_RAW_DATA", e)

    if STEP == 'STORING_RAW_DATA':
        STEP = 'CLEANING_RAW_DATA'
        run.update(step = STEP)

    if STEP == 'CLEANING_RAW_DATA':
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

    if STEP == 'CLEANING_RAW_DATA':
        STEP = 'STORING_CLEANED_DATA'
        run.update(step = STEP)

    if STEP == 'STORING_CLEANED_DATA':
        try:
            if run: run.save_cleaned_data(cleaned_data)
            print("Done.")
        except Exception as e:
            handle_error(PIPELINE_NAME, run, "STORING_CLEANED_DATA", e)


if __name__ == "__main__":
    asyncio.run(main())
