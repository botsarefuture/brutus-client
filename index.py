import time
import requests
import re
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
import subprocess
import backoff
from collections import defaultdict
from datetime import datetime, timedelta

# Configuration
API_URL = "https://security.luova.club/api/log_attack"  # Single API endpoint for reporting attacks
API_URL_BLOCK = "https://security.luova.club/api/block_list"  # API to fetch IPs to block
PUBLIC_IP_SERVICE = "https://api.ipify.org"  # Service to fetch public IP
LOG_FILE_PATH = "/var/log/auth.log"  # Modify depending on your system
BLOCK_INTERVAL = 60  # Time in seconds to check for IPs to block
BACKOFF_MAX_TRIES = 5  # Maximum retries for API calls
FAILED_LOGIN_LIMIT = 1  # Number of failed logins before blocking
FAILED_LOGIN_WINDOW = 0  # Time in seconds to consider for failed logins

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SSHLogHandler(FileSystemEventHandler):
    """Monitors SSH log files for brute-force attempts and reports them to a central API."""
    
    def __init__(self, log_file, server_ip):
        self.log_file = log_file
        self.server_ip = server_ip
        self.last_position = 0  # Track the last position read in the log file
        self.failed_attempts = defaultdict(list)  # Store failed attempts with timestamps

    def on_modified(self, event):
        """Triggered when the log file is modified."""
        if event.src_path == self.log_file:
            self.process_new_lines()

    def process_new_lines(self):
        """Read new lines added to the log file since the last read position."""
        with open(self.log_file, 'r') as f:
            f.seek(self.last_position)
            new_lines = f.readlines()
            self.last_position = f.tell()  # Update the last position read

        for line in new_lines:
            self.process_log_line(line)

    def process_log_line(self, line):
        """Extracts potential brute-force attempts from the log line."""
        failed_login_pattern = r'Failed password for (invalid user )?(\S+) from (\S+)'
        match = re.search(failed_login_pattern, line)
        if match:
            username = match.group(2)
            ip_address = match.group(3)
            logging.info(f"Brute-force attempt detected: Username={username}, IP={ip_address}")
            self.report_attack(ip_address, username)
            self.record_failed_attempt(ip_address)

    def record_failed_attempt(self, ip_address):
        """Records the failed login attempt with the current timestamp."""
        current_time = datetime.now()
        self.failed_attempts[ip_address].append(current_time)
        
        if not FAILED_LOGIN_WINDOW == 0:
            # Remove attempts that are outside the window
            self.failed_attempts[ip_address] = [timestamp for timestamp in self.failed_attempts[ip_address]
                                                if timestamp > current_time - timedelta(seconds=FAILED_LOGIN_WINDOW)]

        # Check if we exceed the failed login limit
        if len(self.failed_attempts[ip_address]) >= FAILED_LOGIN_LIMIT:
            logging.info(f"Blocking IP due to excessive failed attempts: {ip_address}")
            block_ips([ip_address])  # Block the IP immediately
            del self.failed_attempts[ip_address]  # Clear the record for the blocked IP

    @backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=BACKOFF_MAX_TRIES)
    def report_attack(self, ip_address, username):
        """Sends a brute-force attempt to the Flask API."""
        payload = {
            "server_ip": self.server_ip,
            "ip_address": ip_address,
            "username": username
        }

        try:
            response = requests.post(API_URL, json=payload)
            if response.status_code == 200:
                logging.info(f"Attack logged successfully: {payload}")
            else:
                logging.error(f"Failed to log attack: {response.text}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Error logging attack: {str(e)}")

def fetch_public_ip():
    """Fetches the public IP address of the server."""
    try:
        response = requests.get(PUBLIC_IP_SERVICE)
        response.raise_for_status()  # Raise an error for bad responses
        return response.text.strip()  # Return the public IP as a string
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching public IP: {str(e)}")
        return None

@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=BACKOFF_MAX_TRIES)
def fetch_ips_to_block():
    """Fetches the list of IP addresses that need to be blocked from the Flask API."""
    try:
        response = requests.get(API_URL_BLOCK)
        response.raise_for_status()
        ips_to_block = response.json().get('ips', [])
        return ips_to_block
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching IPs: {str(e)}")
        return []

def block_ips(ips):
    """Blocks the given IP addresses using iptables or firewall commands."""
    for ip in ips:
        try:
            # Use iptables to block the IP address
            block_command = f"ufw deny from {ip}"
            logging.info(f"Blocking IP: {ip}")
            subprocess.run(block_command, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to block IP {ip}: {str(e)}")
        except Exception as e:
            logging.error(f"Unexpected error when blocking IP {ip}: {str(e)}")

def monitor_ssh_log():
    """Starts monitoring the SSH log file for brute-force attempts."""
    log_file_path = LOG_FILE_PATH
    server_ip = fetch_public_ip()  # Fetch the public IP to use as the server IP
    if not server_ip:
        logging.error("Could not fetch public IP. Exiting...")
        return

    event_handler = SSHLogHandler(log_file_path, server_ip)
    observer = Observer()
    observer.schedule(event_handler, path=log_file_path, recursive=False)
    
    logging.info(f"Monitoring SSH log file: {log_file_path}")
    observer.start()
    
    try:
        while True:
            # Fetch the list of IPs to block every BLOCK_INTERVAL seconds
            ips_to_block = fetch_ips_to_block()
            if ips_to_block:
                block_ips(ips_to_block)

            time.sleep(BLOCK_INTERVAL)  # Check for IPs to block every minute
    except KeyboardInterrupt:
        observer.stop()
    except Exception as e:
        logging.error(f"Unexpected error in monitor loop: {str(e)}")
    finally:
        observer.join()

if __name__ == "__main__":
    monitor_ssh_log()
