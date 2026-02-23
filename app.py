import time
import os
import threading
import requests
import random
import string
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# --- FLASK AND SOCKETIO SETUP ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_key_change_this')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# --- EMBEDDED HTML FOR FRONTEND ---
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Roblox Automation Web App</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background-color: #f0f2f5; color: #1c1e21; margin: 0; padding: 20px; }
        .container { max-width: 800px; margin: auto; background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        h1 { text-align: center; color: #1b74e4; margin-bottom: 25px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; font-weight: 600; }
        input[type="text"], textarea { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; box-sizing: border-box; font-size: 16px; }
        textarea { height: 150px; resize: vertical; font-family: 'Courier New', Courier, monospace; }
        button { display: block; width: 100%; padding: 12px; background-color: #1b74e4; color: white; border: none; border-radius: 6px; font-size: 18px; font-weight: bold; cursor: pointer; transition: background-color 0.2s; }
        button:hover { background-color: #1678e3; }
        button:disabled { background-color: #cfe2ff; cursor: not-allowed; }
        #log-container { margin-top: 25px; border: 1px solid #ddd; padding: 15px; height: 350px; overflow-y: scroll; background-color: #f7f8fa; border-radius: 6px; font-family: 'Courier New', Courier, monospace; font-size: 14px; }
        .log-entry { padding: 6px; border-bottom: 1px solid #e9ebee; }
        .log-entry:last-child { border-bottom: none; }
        .log-success { color: #28a745; }
        .log-failure { color: #dc3545; }
        .log-info { color: #007bff; }
        .warning-banner { background-color: #fff3cd; border: 1px solid #ffeeba; color: #856404; padding: 15px; border-radius: 6px; margin-bottom: 20px; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <div class="warning-banner">
            <strong>WARNING:</strong> This tool is for educational purposes only. Using it violates Roblox's ToS and will result in account bans. Use at your own risk.
        </div>
        <h1>Roblox Account Creator Control Panel</h1>
        <form id="automation-form">
            <div class="form-group">
                <label for="target-username">Target Roblox Username (Optional - for auto-follow):</label>
                <input type="text" id="target-username" placeholder="Enter user to follow after creation">
            </div>
            <div class="form-group">
                <label for="accounts-data">Base Names (one per line, optional - for username prefixes):</label>
                <textarea id="accounts-data" placeholder="botbase1\nbotbase2"></textarea>
            </div>
            <div class="form-group">
                <label for="num-accounts">Number of accounts to create:</label>
                <input type="number" id="num-accounts" min="1" max="20" value="5">
            </div>
            <button type="submit" id="run-button">Create Accounts</button>
        </form>
        <div id="log-container"></div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const form = document.getElementById('automation-form');
            const runButton = document.getElementById('run-button');
            const logContainer = document.getElementById('log-container');
            
            const socket = io({
                transports: ['websocket', 'polling'],
                reconnection: true
            });

            function addLog(message, type = 'info') {
                const logEntry = document.createElement('div');
                logEntry.className = `log-entry log-${type}`;
                logEntry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
                logContainer.appendChild(logEntry);
                logContainer.scrollTop = logContainer.scrollHeight;
            }

            socket.on('connect', () => {
                addLog('Connected to server', 'success');
            });

            socket.on('status_update', (data) => {
                const message = data.message;
                let type = 'info';
                if (message.startsWith('SUCCESS')) type = 'success';
                else if (message.startsWith('FAILURE') || message.startsWith('CRITICAL')) type = 'failure';
                addLog(message, type);
            });

            form.addEventListener('submit', (e) => {
                e.preventDefault();
                
                const targetUsername = document.getElementById('target-username').value;
                const accountsData = document.getElementById('accounts-data').value;
                const numAccounts = document.getElementById('num-accounts').value;

                logContainer.innerHTML = '';
                runButton.disabled = true;
                runButton.textContent = 'Running...';
                addLog('Starting automation...', 'info');

                socket.emit('run_script', {
                    target_username: targetUsername,
                    accounts: accountsData,
                    num_accounts: parseInt(numAccounts)
                });
            });

            socket.on('disconnect', () => {
                addLog('Disconnected from server', 'failure');
                runButton.disabled = false;
                runButton.textContent = 'Create Accounts';
            });

            socket.on('connect_error', (error) => {
                addLog('Connection error: ' + error, 'failure');
            });
        });
    </script>
</body>
</html>
"""

# --- CAPTCHA SOLVER ---
CAPSOLVER_API_KEY = os.environ.get('CAPSOLVER_API_KEY', '')
if not CAPSOLVER_API_KEY:
    print("WARNING: CAPSOLVER_API_KEY not set in environment variables")

def solve_funcaptcha(page_url, site_key):
    """Solve FunCaptcha using Capsolver API"""
    socketio.emit('status_update', {'message': 'Solving FunCaptcha...'})
    
    if not CAPSOLVER_API_KEY:
        socketio.emit('status_update', {'message': 'CRITICAL: Capsolver API key not configured'})
        return None
        
    payload = {
        "clientKey": CAPSOLVER_API_KEY,
        "task": {
            "type": "FunCaptchaTaskProxyless",
            "websiteURL": page_url,
            "websitePublicKey": site_key,
            "funcaptchaApiJSSubdomain": "https://roblox-api.arkoselabs.com"
        }
    }
    
    try:
        # Create task
        resp = requests.post("https://api.capsolver.com/createTask", json=payload)
        if resp.status_code != 200:
            socketio.emit('status_update', {'message': f'CRITICAL: Capsolver API error - {resp.status_code}'})
            return None
            
        result = resp.json()
        task_id = result.get("taskId")
        if not task_id:
            socketio.emit('status_update', {'message': f'CRITICAL: Failed to create task - {result}'})
            return None
            
        # Wait for solution
        for i in range(30):
            time.sleep(5)
            status_resp = requests.post("https://api.capsolver.com/getTaskResult", 
                                      json={"clientKey": CAPSOLVER_API_KEY, "taskId": task_id})
            status_result = status_resp.json()
            
            if status_result.get("status") == "ready":
                token = status_result["solution"].get("token")
                if token:
                    socketio.emit('status_update', {'message': 'SUCCESS: Captcha solved'})
                    return token
                    
            elif status_result.get("status") == "processing":
                socketio.emit('status_update', {'message': f'Solving captcha... ({i+1}/30)'})
                continue
            else:
                break
                
        socketio.emit('status_update', {'message': 'CRITICAL: Captcha solving timeout'})
        return None
        
    except Exception as e:
        socketio.emit('status_update', {'message': f'CRITICAL: Captcha failed - {str(e)}'})
        return None

# --- AUTOMATION LOGIC ---
def run_automation_and_emit(target_username, accounts_data, num_accounts):
    """Main automation function"""
    successful_creates = 0
    bases = [line.strip() for line in accounts_data.splitlines() if line.strip()] if accounts_data else []
    created_accounts = []

    socketio.emit('status_update', {'message': f'Starting creation of {num_accounts} accounts...'})

    for idx in range(1, num_accounts + 1):
        driver = None
        try:
            # Generate credentials
            if bases and idx - 1 < len(bases):
                base = bases[idx - 1]
            else:
                base = "Bot"
                
            rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            username = f"{base}{rand_str}"
            password = ''.join(random.choices(string.ascii_letters + string.digits + "!@#$", k=12))
            # Use a temporary email service in production
            email = f"{username}@temp-mail.org"

            socketio.emit('status_update', {'message': f'[{idx}/{num_accounts}] Creating: {username}'})

            # Configure Chrome options for Render
            options = uc.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-setuid-sandbox")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-logging")
            options.add_argument("--log-level=3")
            options.add_argument("--silent")
            options.add_argument("--blink-settings=imagesEnabled=false")
            
            # Set Chrome binary location for Render
            chrome_paths = [
                "/usr/bin/google-chrome",
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium",
                "/opt/render/project/.render/chrome/opt/google/chrome/google-chrome"
            ]
            
            chrome_found = False
            for path in chrome_paths:
                if os.path.exists(path):
                    options.binary_location = path
                    chrome_found = True
                    break
            
            if not chrome_found:
                socketio.emit('status_update', {'message': 'CRITICAL: Chrome not found'})
                continue

            # Initialize driver
            driver = uc.Chrome(options=options, version_main=120)  # Specify Chrome version
            wait = WebDriverWait(driver, 30)

            # Navigate to Roblox
            driver.get("https://www.roblox.com/")
            socketio.emit('status_update', {'message': f'Loaded Roblox homepage'})
            time.sleep(random.uniform(3, 6))

            # Click signup button
            try:
                signup_btn = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Sign Up")))
                signup_btn.click()
            except:
                try:
                    signup_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'signup')]")))
                    signup_btn.click()
                except:
                    socketio.emit('status_update', {'message': 'FAILURE: Could not find signup button'})
                    continue

            time.sleep(random.uniform(2, 4))

            # Fill form
            try:
                # Username
                username_field = wait.until(EC.presence_of_element_located((By.NAME, "username")))
                username_field.send_keys(username)
                
                # Password
                password_field = driver.find_element(By.NAME, "password")
                password_field.send_keys(password)
                
                # Birthday (select random date for 13+)
                from selenium.webdriver.support.ui import Select
                
                # Month
                month_select = Select(driver.find_element(By.NAME, "birthdayMonth"))
                month_select.select_by_index(random.randint(1, 12))
                
                # Day
                day_select = Select(driver.find_element(By.NAME, "birthdayDay"))
                day_select.select_by_index(random.randint(1, 28))
                
                # Year (make sure user is 13+)
                year_select = Select(driver.find_element(By.NAME, "birthdayYear"))
                current_year = 2024
                year_options = [int(opt.get_attribute("value")) for opt in year_select.options if opt.get_attribute("value").isdigit()]
                valid_years = [y for y in year_options if y <= current_year - 13]
                if valid_years:
                    year_select.select_by_value(str(random.choice(valid_years)))
                
                # Gender (optional)
                try:
                    gender_male = driver.find_element(By.XPATH, "//span[text()='Male']")
                    gender_male.click()
                except:
                    pass
                    
            except Exception as e:
                socketio.emit('status_update', {'message': f'FAILURE: Form filling error - {str(e)}'})
                continue

            # Solve CAPTCHA
            site_key = "476068BF-9607-4799-B53D-966BE98E2B81"  # Roblox FunCaptcha key
            token = solve_funcaptcha(driver.current_url, site_key)
            
            if not token:
                socketio.emit('status_update', {'message': 'FAILURE: Could not solve captcha'})
                continue

            # Inject token
            try:
                driver.execute_script(f'''
                    var input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = 'fc-token';
                    input.value = '{token}';
                    document.querySelector('form').appendChild(input);
                ''')
                time.sleep(1)
            except:
                pass

            # Submit form
            try:
                submit_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
                submit_btn.click()
            except:
                try:
                    submit_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Sign Up')]")
                    submit_btn.click()
                except:
                    socketio.emit('status_update', {'message': 'FAILURE: Could not find submit button'})
                    continue

            # Wait for success (check URL or presence of home page elements)
            time.sleep(5)
            current_url = driver.current_url
            
            if "home" in current_url or "games" in current_url:
                socketio.emit('status_update', {'message': f'SUCCESS: Created account - Username: {username}, Password: {password}'})
                created_accounts.append(f"{username}:{password}")
                successful_creates += 1

                # Optional: Auto-follow target
                if target_username:
                    try:
                        # Search for user
                        driver.get(f"https://www.roblox.com/search/users?keyword={target_username}")
                        time.sleep(3)
                        
                        # Click on profile
                        profile_link = wait.until(EC.element_to_be_clickable((By.XPATH, f"//a[contains(@href, 'users') and contains(text(), '{target_username}')]")))
                        profile_link.click()
                        time.sleep(2)
                        
                        # Click follow button
                        follow_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Follow')]")))
                        follow_btn.click()
                        socketio.emit('status_update', {'message': f'SUCCESS: Followed {target_username}'})
                    except Exception as e:
                        socketio.emit('status_update', {'message': f'Could not follow target: {str(e)}'})
            else:
                socketio.emit('status_update', {'message': f'FAILURE: Account creation might have failed - check manually'})

        except Exception as e:
            socketio.emit('status_update', {'message': f'FAILURE: Account {idx} error - {str(e)[:100]}'})
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            # Random delay between accounts
            time.sleep(random.uniform(10, 20))

    # Final summary
    summary = f"FINISHED! Successfully created {successful_creates}/{num_accounts} accounts"
    if created_accounts:
        summary += f"\nAccounts: {', '.join(created_accounts)}"
    socketio.emit('status_update', {'message': summary})

# --- SOCKETIO HANDLER ---
@socketio.on('run_script')
def handle_run_script(data):
    """Handle incoming run requests"""
    target_username = data.get('target_username', '').strip()
    accounts_data = data.get('accounts', '')
    num_accounts = data.get('num_accounts', 5)
    
    # Limit maximum accounts
    if num_accounts > 20:
        num_accounts = 20
        socketio.emit('status_update', {'message': 'Limited to 20 accounts maximum'})
    
    # Run in background thread
    thread = threading.Thread(
        target=run_automation_and_emit, 
        args=(target_username, accounts_data, num_accounts),
        daemon=True
    )
    thread.start()

# --- SERVE APP ---
@app.route('/')
def index():
    return render_template_string(HTML_CONTENT)

@app.route('/health')
def health():
    return {'status': 'healthy'}, 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
