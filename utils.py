# utils.py
import csv
import yaml
from datetime import datetime
import os

class Logger:
    def __init__(self, filename="sim_urllc_log.csv"):
        # Create a logs directory if it doesn't exist
        if not os.path.exists("logs"):
            os.makedirs("logs")
        
        # Create timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = os.path.join("logs", f"{filename.rsplit('.', 1)[0]}_{timestamp}.csv")
        
        # Open file and initialize CSV writer
        self.file = open(self.filename, 'w', newline='')
        self.writer = csv.writer(self.file)
        
        # Write header
        self.writer.writerow([
            "time", "device_id", "packet_id", "event",
            "latency", "percentile_latency", "throughput",
            "reliability", "aoi", "sinr", "fairness"
        ])

    def log(self, time, device_id, packet_id, event, latency=None, 
            percentile_latency=None, throughput=None, reliability=None, 
            aoi=None, sinr=None, fairness=None):
        """
        Log an event with associated metrics.
        """
        row = [
            f"{time:.6f}" if time is not None else "",
            device_id,
            packet_id,
            event,
            f"{latency:.6f}" if latency is not None else "",
            f"{percentile_latency:.6f}" if percentile_latency is not None else "",
            f"{throughput:.6f}" if throughput is not None else "",
            f"{reliability:.6f}" if reliability is not None else "",
            f"{aoi:.6f}" if aoi is not None else "",
            f"{sinr:.6f}" if sinr is not None else "",
            f"{fairness:.6f}" if fairness is not None else ""
        ]
        self.writer.writerow(row)
        self.file.flush()  # Ensure data is written immediately

    def close(self):
        """
        Close the log file.
        """
        self.file.close()

def load_config(config_file="config.yaml"):
    """
    Load configuration from YAML file.
    """
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)

# Global logger instance
_logger = None

def init_logger(filename="sim_urllc_log.csv"):
    """
    Initialize the global logger instance.
    """
    global _logger
    _logger = Logger(filename)

def get_logger():
    """
    Get the global logger instance. Initialize if not exists.
    """
    global _logger
    if _logger is None:
        init_logger()
    return _logger 