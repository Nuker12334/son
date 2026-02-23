import time
import os
import threading
import requests
import random
import string
import subprocess
import sys
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
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
                <label for="target-username">Target Roblox Username (Optional):</label>
                <input type="text" id="target-username" placeholder="Enter user to follow">
            </div>
            <div class="form-group">
                <label for="accounts-data">Base Names (one per line):</label>
                <textarea id="accounts-data" placeholder="botbase1&#10;botbase2"></textarea>
            </div>
            <div class="form-group">
                <label for="num-accounts">Number of accounts to create:</label>
                <input type="number" id="num-accounts" min="1" max="5" value="2">
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
                reconnection: true,
                reconnectionAttempts: 5
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
                addLog('Process finished - You can close this window', 'info');
                runButton.disabled = false;
                runButton.textContent = 'Create Accounts';
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
        resp = requests.post("https://api.capsolver.com/createTask", json=payload, timeout=30)
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
                                      json={"clientKey": CAPSOLVER_API_KEY, "taskId": task_id},
                                      timeout=30)
            status_result = status_resp.json()
            
            if status_result.get("status") == "ready":
                token = status_result["solution"].get("token")
                if token:
                    socketio.emit('status_update', {'message': 'SUCCESS: Captcha solved'})
                    return token
                    
            elif status_result.get("status") == "processing":
                if i % 3 == 0:  # Update every 15 seconds
                    socketio.emit('status_update', {'message': f'Solving captcha...'})
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
    bases = [line.strip() for line in accounts_data.splitlines() if line.strip()] if accounts_data else ["User"]
    created_accounts = []

    socketio.emit('status_update', {'message': f'Starting creation of {num_accounts} accounts...'})

    for idx in range(1, num_accounts + 1):
        driver = None
        try:
            # Generate credentials
            base = bases[(idx - 1) % len(bases)]
            rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
            username = f"{base}{rand_str}"
            password = ''.join(random.choices(string.ascii_letters + string.digits + "!@#$", k=12))
            # Use a temporary email service format
            email = f"{username}@tempmail.com"

            socketio.emit('status_update', {'message': f'[{idx}/{num_accounts}] Creating: {username}'})

            # Configure Chrome options for Render
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-setuid-sandbox")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-logging")
            chrome_options.add_argument("--log-level=3")
            chrome_options.add_argument("--silent")
            chrome_options.add_argument("--blink-settings=imagesEnabled=false")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Find Chrome binary
            chrome_paths = [
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium",
                "/opt/render/project/.render/chrome/opt/google/chrome/google-chrome"
            ]
            
            chrome_found = False
            for path in chrome_paths:
                if os.path.exists(path):
                    chrome_options.binary_location = path
                    socketio.emit('status_update', {'message': f'Found Chrome at: {path}'})
                    chrome_found = True
                    break
            
            if not chrome_found:
                # Try to find Chrome using which command
                try:
                    result = subprocess.run(['which', 'google-chrome'], capture_output=True, text=True)
                    if result.returncode == 0:
                        chrome_path = result.stdout.strip()
                        chrome_options.binary_location = chrome_path
                        socketio.emit('status_update', {'message': f'Found Chrome at: {chrome_path}'})
                        chrome_found = True
                except:
                    pass
            
            if not chrome_found:
                socketio.emit('status_update', {'message': 'CRITICAL: Chrome not found. Please check build script.'})
                continue

            # Initialize driver with automatic driver management
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Set page load timeout
            driver.set_page_load_timeout(30)
            
            wait = WebDriverWait(driver, 20)

            # Navigate to Roblox signup page directly
            socketio.emit('status_update', {'message': 'Loading Roblox signup page...'})
            driver.get("https://www.roblox.com/")
            time.sleep(3)

            # Click signup button or go directly to signup
            try:
                signup_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'signup')]")))
                signup_btn.click()
            except:
                # Direct navigation to signup
                driver.get("https://www.roblox.com/signup")
            
            time.sleep(2)

            # Fill the signup form
            try:
                # Wait for form to load
                wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='text' or @name='username']")))
                
                # Find and fill username field
                username_fields = driver.find_elements(By.XPATH, "//input[@type='text' or @name='username' or @placeholder*='[Uu]sername']")
                if username_fields:
                    username_fields[0].clear()
                    username_fields[0].send_keys(username)
                
                # Find and fill password field
                password_fields = driver.find_elements(By.XPATH, "//input[@type='password' or @name='password' or @placeholder*='[Pp]assword']")
                if password_fields:
                    password_fields[0].clear()
                    password_fields[0].send_keys(password)
                
                # Birthday dropdowns
                from selenium.webdriver.support.ui import Select
                
                # Month
                month_selects = driver.find_elements(By.XPATH, "//select[contains(@name, 'month') or contains(@id, 'Month')]")
                if month_selects:
                    Select(month_selects[0]).select_by_index(random.randint(1, 12))
                
                # Day
                day_selects = driver.find_elements(By.XPATH, "//select[contains(@name, 'day') or contains(@id, 'Day')]")
                if day_selects:
                    Select(day_selects[0]).select_by_index(random.randint(1, 28))
                
                # Year
                year_selects = driver.find_elements(By.XPATH, "//select[contains(@name, 'year') or contains(@id, 'Year')]")
                if year_selects:
                    # Select year for someone 13+ (before 2011)
                    Select(year_selects[0]).select_by_value(str(random.randint(1990, 2010)))
                
            except Exception as e:
                socketio.emit('status_update', {'message': f'Form filling warning: {str(e)}'})

            # Check for captcha
            try:
                if "funcaptcha" in driver.page_source.lower() or "arkose" in driver.page_source.lower():
                    socketio.emit('status_update', {'message': 'Captcha detected, solving...'})
                    site_key = "476068BF-9607-4799-B53D-966BE98E2B81"
                    token = solve_funcaptcha(driver.current_url, site_key)
                    
                    if token:
                        # Inject token
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

            # Try to submit the form
            try:
                submit_buttons = driver.find_elements(By.XPATH, "//button[@type='submit'] | //input[@type='submit'] | //button[contains(text(), 'Sign Up')]")
                if submit_buttons:
                    submit_buttons[0].click()
                    socketio.emit('status_update', {'message': 'Form submitted'})
            except Exception as e:
                socketio.emit('status_update', {'message': f'Submit warning: {str(e)}'})

            # Wait for potential success
            time.sleep(5)
            
            # Check if we're still on signup page
            current_url = driver.current_url
            if "home" in current_url or "games" in current_url or "dashboard" in current_url:
                socketio.emit('status_update', {'message': f'SUCCESS: Account created - {username}:{password}'})
                created_accounts.append(f"{username}:{password}")
                successful_creates += 1
            else:
                socketio.emit('status_update', {'message': f'Account creation attempted for {username}. Check manually.'})

        except Exception as e:
            socketio.emit('status_update', {'message': f'FAILURE: Account {idx} error - {str(e)}'})
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            # Delay between accounts
            if idx < num_accounts:
                time.sleep(random.uniform(10, 15))

    # Final summary
    summary = f"FINISHED! Created {successful_creates}/{num_accounts} accounts"
    if created_accounts:
        summary += f"\nAccounts:\n" + "\n".join(created_accounts)
    socketio.emit('status_update', {'message': summary})
    socketio.emit('disconnect')  # Signal completion

# --- SOCKETIO HANDLER ---
@socketio.on('run_script')
def handle_run_script(data):
    """Handle incoming run requests"""
    target_username = data.get('target_username', '').strip()
    accounts_data = data.get('accounts', '')
    num_accounts = min(data.get('num_accounts', 2), 5)  # Max 5 accounts
    
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
    return {'status': 'healthy', 'chrome': check_chrome()}, 200

def check_chrome():
    """Check if Chrome is installed"""
    chrome_paths = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium"
    ]
    for path in chrome_paths:
        if os.path.exists(path):
            return True
    return False

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
