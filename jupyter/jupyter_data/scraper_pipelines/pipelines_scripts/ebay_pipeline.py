# AUTO-GENERATED FROM ebay_pipeline.ipynb
import asyncio

async def main():
    STEP = 'ENVIRONMENT_PREPARATION'

    import os
    import sys
    import json
    import time
    import random
    import polars as pl
    from datetime import datetime
    from pathlib import Path

    EXAMPLE_INSTANCE_ID = '8be90d9f-633b-4231-887c-5b1c80249543'
    DECODO_USERNAME = os.getenv("DECODO_USERNAME")
    DECODO_PASSWORD = os.getenv("DECODO_PASSWORD")
    DECODO_URL = os.getenv("DECODO_URL")
    SELENIUM_REMOTE_URL = os.getenv("SELENIUM_REMOTE_URL")
    PIPELINE_API_SECRET = os.getenv("PIPELINE_API_SECRET")
    
    IS_DEVELOPMENT = False
    PIPELINE_NAME = "ebay_pipeline"
    MAX_RUNTIME_MINUTES = 45 # Self-pause before the 1-hour Celery timeout

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
    
    if not IS_DEVELOPMENT:
        RUN_ID = sys.argv[1]
        PARAMS = json.loads(sys.argv[2])
        run = RunManager(RUN_ID)
        headless = True
    else:
        # EXAMPLE PARAMS: Targeting one Brand per instance
        PARAMS = {
            "brand": "HP",
            "category": "Laptops-Netbooks",
            "cat_id": "175672",
            "bn_id": "2780154",
            "initial_ranges": [
                {"low": 0, "high": 5000},
                {"low": 5000, "high": 10000}
            ]
        } 
        run = RunManager.start_run(instance_id=EXAMPLE_INSTANCE_ID) 
        headless = False

    run_state = run.refresh()
    STEP = run_state.get('step', 'DATA_RECOLLECTION')
    run_data = run_state.get('run_data', {})
    
    # 1. Initialize logic for first-time runs
    if not run_data.get('pending_ranges'):
        run_data['pending_ranges'] = PARAMS.get('initial_ranges', [{"low": 0, "high": 100000}])
        run_data['scraped_count'] = 0
        run.update(run_data=run_data)
    
    start_timestamp = time.time()

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

    try:
        try:
            if STEP == 'DATA_RECOLLECTION':
                # Recover items from RawData if resuming from PAUSED
                existing_payload = run.get_raw_data() or {}
                all_items = existing_payload.get('items', [])
                
                brand = PARAMS.get('brand')
                category = PARAMS.get('category')
                cat_id = PARAMS.get('cat_id')
                bn_id = PARAMS.get('bn_id')
        
                while run_data.get('pending_ranges'):
                    # CHECK FOR TIMEOUT (Self-Pausing)
                    elapsed_minutes = (time.time() - start_timestamp) / 60
                    if elapsed_minutes > MAX_RUNTIME_MINUTES:
                        run.log(f"Execution time exceeded {MAX_RUNTIME_MINUTES}m. Pausing for auto-resume.")
                        run.save_raw_data({"items": all_items})
                        run.set_run_pause("Timed out, pending ranges saved.", run_data=run_data)
                        sys.exit(0)
        
                    current_range = run_data['pending_ranges'][0]
                    low, high = current_range['low'], current_range['high']
                    
                    # 1. INITIAL NAVIGATION & COUNT CHECK
                    url = f"https://mx.ebay.com/b/{brand}-{category}/{cat_id}/bn_{bn_id}?LH_BIN=1&_pgn=1&_sop=15&_udhi={high}&_udlo={low}&mag=1&rt=nc"
                    await scraper.page.goto(url)
                    await scraper.wait_for_page_load()
                    
                    # Extract result count (using generic eBay browse header selector)
                    count_text = await scraper.page.locator('.srp-controls__count-heading, .b-pageheader__copy').first.inner_text() if await scraper.page.locator('.srp-controls__count-heading, .b-pageheader__copy').count() > 0 else "0"
                    
                    # Clean count text (e.g., "1,234 resultados" -> 1234)
                    import re
                    total_results = int("".join(re.findall(r'\d+', count_text.replace(',', '').replace('.', ''))) or 0)
                    
                    # 2. RECURSIVE SPLITTING LOGIC
                    if total_results > 2000 and (high - low) > 10:
                        mid = (low + high) // 2
                        run.log(f"Range ${low}-${high} has {total_results} items. Splitting into ${low}-${mid} and ${mid}-${high}.")
                        
                        # Replace current range with two smaller ones
                        run_data['pending_ranges'].pop(0)
                        run_data['pending_ranges'] = [{"low": low, "high": mid}, {"low": mid, "high": high}] + run_data['pending_ranges']
                        run.update(run_data=run_data)
                        continue # Restart loop with the new split ranges
                    
                    # 3. SCRAPE THE RANGE
                    current_page = run_data.get('current_page', 1)
                    run.log(f"Processing Range ${low}-${high} ({total_results} results)")
                    
                    for page in range(current_page, 101):
                        if page > 1: # We are already on page 1
                            page_url = f"https://mx.ebay.com/b/{brand}-{category}/{cat_id}/bn_{bn_id}?LH_BIN=1&_pgn={page}&_sop=15&_udhi={high}&_udlo={low}&mag=1&rt=nc"
                            await scraper.page.goto(page_url)
                            await scraper.wait_for_page_load()
                        
                        items = await scraper.page.locator('li.s-item').all()
                        if not items or await scraper.page.locator('.s-error-page').count() > 0:
                            break
                        
                        for item in items:
                            title_el = item.locator('h3.s-item__title')
                            if await title_el.count() > 0:
                                all_items.append({
                                    "brand": brand, "range": f"{low}-{high}",
                                    "title": await title_el.inner_text(),
                                    "price": await item.locator('.s-item__price').inner_text() if await item.locator('.s-item__price').count() > 0 else "0",
                                    "url": await item.locator('.s-item__link').get_attribute('href')
                                })
                        
                        # Page Checkpoint
                        run_data['current_page'] = page + 1
                        run.update(run_data=run_data)
                        await scraper.human_pause()
        
                        # Re-check time during pagination
                        if (time.time() - start_timestamp) / 60 > MAX_RUNTIME_MINUTES:
                            break 
                    
                    # Range Completed or Paused mid-range
                    if (time.time() - start_timestamp) / 60 > MAX_RUNTIME_MINUTES:
                         continue # Will be caught by the time check at start of while loop
                    
                    run_data['pending_ranges'].pop(0)
                    run_data['current_page'] = 1
                    run.update(run_data=run_data)
                    
                data_dict = {k: [i[k] for i in all_items] for k in all_items[0].keys()} if all_items else {}
                
            elif STEP in ['STORING_RAW_DATA', 'CLEANING_RAW_DATA']:
                raw_payload = run.get_raw_data() or {}
                data_dict = raw_payload.get('items', {})
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
            run.save_raw_data({"items": data_dict})
        except Exception as e:
            handle_error(PIPELINE_NAME, run, "STORING_RAW_DATA", e)

    if STEP == 'STORING_RAW_DATA':
        STEP = 'CLEANING_RAW_DATA'
        run.update(step = STEP)

    if STEP == 'CLEANING_RAW_DATA':
        try:
            # The payload format is slightly different now (wrapped in 'items' dict)
            df = pl.DataFrame(data_dict)
            df = strip_all_str(df)
            
            df = df.with_columns([
                pl.col("price").str.replace_all(r"[^0-9.]", "").cast(pl.Float64, strict=False).fill_null(0.0)
            ])
            
            cleaned_data = df.to_dict(as_series=False)
        except Exception as e:
            handle_error(PIPELINE_NAME, run, "CLEANING_RAW_DATA", e)

    if STEP == 'CLEANING_RAW_DATA':
        STEP = 'STORING_CLEANED_DATA'
        run.update(step = STEP)

    if STEP == 'STORING_CLEANED_DATA':
        try:
            run.save_cleaned_data(cleaned_data)
            print("Done.")
        except Exception as e:
            handle_error(PIPELINE_NAME, run, "STORING_CLEANED_DATA", e)


if __name__ == "__main__":
    asyncio.run(main())
