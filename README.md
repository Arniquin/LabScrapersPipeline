# LabScrapersPipeline

A professional, fully-orchestrated web scraping platform. This ecosystem enables developers to prototype scrapers in Jupyter Lab and deploy them into a production-ready environment managed by Django and Celery.

---

## 🚀 Quick Start

### 1. Prerequisites
- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- A \`.env\` file (see \`docker-compose.yml\` for required variables: \`POSTGRES_DB\`, \`POSTGRES_USER\`, \`POSTGRES_PASSWORD\`, \`DECODO_USERNAME\`, \`DECODO_PASSWORD\`, etc.)

### 2. Launch the Ecosystem
\`\`\`bash
docker compose up --build
\`\`\`

### 3. Initialize the Manager
In a new terminal, create your administrative account:
\`\`\`bash
docker compose exec django python manage.py createsuperuser
\`\`\`

### 4. Access the Dashboard
Visit \`http://localhost:8000\` and log in with your superuser credentials.

---

## 🏗️ Architecture & Inner Workings

The system is built as a distributed microservice architecture:

- **Django App**: The management hub. Handles the database, provides the UI Dashboard, and exposes an internal API for scrapers.
- **Celery Worker**: The engine that executes scraping tasks in the background.
- **Redis**: The message broker that coordinates between Django and Celery.
- **Jupyter Lab**: The IDE where scrapers are born and tested.
- **Selenium Chrome**: A standalone container running Chrome for automated browsing.
- **PostgreSQL**: Robust storage for metadata, logs, and extracted data.

### Orchestration Flow
1. **Daily Planner (\`celery_worker\`)**: Every midnight, it scans all active \`PipelineInstances\` and marks those due for execution (Daily, Weekly, Monthly) as \`is_queued=True\`.
2. **Heartbeat Dispatcher (\`celery_worker\`)**: Runs every minute. It checks the global \`ScraperSettings\` (Max concurrency, Execution windows) and triggers the next available queued tasks.
3. **Subprocess Execution**: When a task starts, the Celery worker calls the Python script via \`subprocess\`. This isolation ensures that a scraper crash doesn't bring down the worker.
4. **RunManager**: The running script uses an internal API to report its status (\`DATA_RECOLLECTION\`, \`CLEANING\`, etc.) and save raw/cleaned data directly back to the Django DB.

---

## 🐍 Scraper & Pipeline Structure

All scrapers must follow a specific structure in their Jupyter notebooks to ensure they work both in the **Lab** and in **Production**.

### 1. Development Toggle
At the top of your notebook, define the environment:
\`\`\`python
IS_DEVELOPMENT = True # Automatically flipped to False during deployment
\`\`\`

### 2. Environment & Arguments
Handle imports and command-line arguments (passed by Celery in production):
\`\`\`python
import os, sys, json
from pathlib import Path

if not IS_DEVELOPMENT:
    RUN_ID = sys.argv[1]
    PARAMS = json.loads(sys.argv[2]) # JSON parameters from the Dashboard
else:
    PARAMS = {} # Manual test parameters

# Fix paths to find local utils
if IS_DEVELOPMENT:
    sys.path.append(os.path.abspath(os.path.join('..')))
else:
    sys.path.append(str(Path(__file__).resolve().parent.parent))
\`\`\`

### 3. Initialization
Initialize the \`RunManager\` and the \`BaseScraper\`:
\`\`\`python
from scrapers_utils import BaseScraper
from pipeline_utils import RunManager

if IS_DEVELOPMENT:
    run = RunManager.start_run(instance_id="YOUR_TEST_ID")
    headless = False
else:
    run = RunManager(RUN_ID)
    headless = True

scraper = BaseScraper.create_with_decodo(port=20001, headless=headless)
\`\`\`

### 4. The Scraping Loop
Use \`run.update\` to keep the dashboard informed of your progress:
\`\`\`python
try:
    scraper.driver.get("https://example.com")
    run.update(step="DATA_RECOLLECTION", last_log="Starting extraction...")
    
    # ... your scraping logic ...
    
    run.save_raw_data(my_data_dict)
except Exception as e:
    run.set_run_fail(f"Error at step X: {e}")
finally:
    scraper.quit()
\`\`\`

### 5. Data Cleaning
Use Polars for high-performance cleaning before final storage:
\`\`\`python
run.update(step="CLEANING_RAW_DATA")
df = pl.DataFrame(my_data_dict)
# ... cleaning logic ...
run.save_cleaned_data(df.to_dict(as_series=False))
\`\`\`

---

## 🛠️ User Workflow: From Lab to Production

### Step 1: Develop in the Lab
1. Open Jupyter Lab at \`http://localhost:8888\`.
2. Navigate to \`work/scraper_pipelines/pipelines/\` and create your scraper in a \`.ipynb\` notebook.
3. **Use the Boilerplate**: Inherit from \`BaseScraper\` for built-in proxy support and human-like interactions.
4. **Local Testing**: Set \`IS_DEVELOPMENT = True\` to test within the notebook.

### Step 2: Sync and Deploy
1. Go to the **Pipelines** section in the Dashboard.
2. Click **Sync Notebooks**. The system will detect your new notebook and create a Blueprint.
3. Click the **Update** button (Update icon) on your blueprint. This converts your \`.ipynb\` into a production-ready \`.py\` script and automatically flips \`IS_DEVELOPMENT\` to \`False\`.

### Step 3: Configure Clients & Instances
1. **Add a Client**: In the **Clients** section, create a record for the target entity.
2. **Link a Pipeline**: Under the client's details, add a "Pipeline Instance". 
3. **Parameterize**: You can pass specific parameters (JSON) to this instance (e.g., specific URLs, login credentials). These are injected into the script at runtime.

### Step 4: Schedule and Monitor
1. **Set Frequency**: In the **Global Scheduler**, set the instance to *Daily*, *Weekly*, or *Monthly*.
2. **Manual Run**: Click "Run Now" to trigger an execution immediately (ignoring windows).
3. **Live Monitoring**: Watch the **Runs** table. You will see real-time updates as the scraper moves through its stages (Data Recollection -> Storing Raw -> Cleaning -> Storing Cleaned).

---

## 🛡️ Key Features

- **Proxy Management**: Automatic proxy rotation and authentication using custom Chrome extensions generated on-the-fly.
- **Concurrency Guards**: Protect your hardware (e.g., Ryzen 2700x) by limiting how many scrapers run at once via \`ScraperSettings\`.
- **Time Windows**: Ensure scrapers only run during specific hours to mimic human activity or avoid server load during peak hours.
- **Data Lifecycle**: Integrated support for storing both \`RawData\` (original JSON/HTML) and \`CleanedData\` (Polars-processed results) linked to specific runs.
