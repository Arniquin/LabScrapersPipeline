import sys
import time
import traceback

def handle_error(PIPELINE_NAME, run, step_name, exception, scraper=None):
    error_trace = traceback.format_exc()
    short_msg = f"{step_name}: {str(exception)}"
    full_msg = f"{short_msg}\n{error_trace}"
    
    print(f"CRITICAL ERROR: {full_msg}")
    
    if run:
        if scraper:
            try:
                ss_name = f"fail_{PIPELINE_NAME}_{int(time.time())}.png"
                path = scraper.save_screenshot(ss_name)
                full_msg += f"\nScreenshot saved to: {path}"
            except:
                full_msg += "\nFailed to capture screenshot."
        run.set_run_fail(full_msg)
        
    if scraper: scraper.quit()
    sys.exit(1)