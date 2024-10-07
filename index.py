import time
import requests
import re
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configuration
API_URL_LOG = "https://security.luova.club/api/log_attack"
API_URL_BLOCK = "https://security.luova.club/api/block_list"
PUBLIC_IP_SERVICE = "https://api.ipify.org"  # Service to fetch public IP
LOG_FILE_PATH = "/var/log/auth.log"  # Modify depending on your system (e.g., /var/log/secure on CentOS)

class SSHLogHandler(FileSystemEventHandler):
    """Monitors SSH log files for brute-force attempts and reports them to a central API."""
    
    def __init__(self, log_file, server_ip):
        self.log_file = log_file
        self.server_ip = server_ip
        self._seek_to_end()

    def _seek_to_end(self):
        """Move the file pointer to the end of the file to start tailing."""
        with open(self.log_file, 'r') as f:
            f.seek(0, 2)

    def on_modified(self, event):
        """Triggered when the log file is modified."""
        if event.src_path == self.log_file:
            with open(self.log_file, 'r') as f:
                for line in f.readlines():
                    self.process_log_line(line)

    def process_log_line(self, line):
        """Extracts potential brute-force attempts from the log line."""
        failed_login_pattern = r'Failed password for (invalid user )?(\S+) from (\S+)'
        match = re.search(failed_login_pattern, line)
        if match:
            username = match.group(2)
            ip_address = match.group(3)
            print(f"Brute-force attempt detected: Username={username}, IP={ip_address}")
            self.report_attack(ip_address)

    def report_attack(self, ip_address):
        """Sends the brute-force attempt to the Flask API."""
        payload = {
            "server_ip": self.server_ip,
            "ip_address": ip_address,
            "blocked": False
        }
        try:
            response = requests.post(API_URL_LOG, json=payload)
            if response.status_code == 200:
                print(f"Attack logged successfully for IP: {ip_address}")
            else:
                print(f"Failed to log attack: {response.text}")
        except Exception as e:
            print(f"Error logging attack: {str(e)}")

def fetch_public_ip():
    """Fetches the public IP address of the server."""
    try:
        response = requests.get(PUBLIC_IP_SERVICE)
        if response.status_code == 200:
            return response.text.strip()  # Return the public IP as a string
        else:
            print(f"Failed to fetch public IP: {response.text}")
            return None
    except Exception as e:
        print(f"Error fetching public IP: {str(e)}")
        return None

def fetch_ips_to_block():
    """Fetches the list of IP addresses that need to be blocked from the Flask API."""
    try:
        response = requests.get(API_URL_BLOCK)
        if response.status_code == 200:
            ips_to_block = response.json().get('ips', [])
            return ips_to_block
        else:
            print(f"Failed to fetch IPs to block: {response.text}")
            return []
    except Exception as e:
        print(f"Error fetching IPs: {str(e)}")
        return []

def block_ips(ips):
    """Simulate blocking the given IP addresses."""
    for ip in ips:
        print(f"Blocking IP: {ip}")
        # Here, you would add the actual blocking mechanism, e.g., iptables or firewall commands.

def monitor_ssh_log():
    """Starts monitoring the SSH log file for brute-force attempts."""
    log_file_path = LOG_FILE_PATH
    server_ip = fetch_public_ip()  # Fetch the public IP to use as the server IP
    if not server_ip:
        print("Could not fetch public IP. Exiting...")
        return

    event_handler = SSHLogHandler(log_file_path, server_ip)
    observer = Observer()
    observer.schedule(event_handler, path=log_file_path, recursive=False)
    
    print(f"Monitoring SSH log file: {log_file_path}")
    observer.start()
    
    try:
        while True:
            # Fetch the list of IPs to block every 60 seconds
            ips_to_block = fetch_ips_to_block()
            if ips_to_block:
                block_ips(ips_to_block)

            time.sleep(60)  # Check for IPs to block every minute
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    monitor_ssh_log()
