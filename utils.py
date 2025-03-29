# utils.py
import csv
import yaml
from datetime import datetime
import os
import logging

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
            "reliability", "aoi", "sinr", "fairness",
            "data_rate", "expected_duration", "remaining_bits",
            "actual_allocation", "is_partial", "active_time_to_deadline",
            "preempting_time_to_deadline", "adjusted_data_rate", "qci_level",
            "will_miss_deadline", "time_to_deadline"
        ])

    def log(self, time, device_id, packet_id, event, latency=None, 
            percentile_latency=None, throughput=None, reliability=None, 
            aoi=None, sinr=None, fairness=None, data_rate=None,
            expected_duration=None, remaining_bits=None, actual_allocation=None,
            is_partial=None, active_time_to_deadline=None,
            preempting_time_to_deadline=None, adjusted_data_rate=None,
            qci_level=None, will_miss_deadline=None, time_to_deadline=None,
            **kwargs):  # Accept any additional parameters
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
            f"{fairness:.6f}" if fairness is not None else "",
            f"{data_rate:.6f}" if data_rate is not None else "",
            f"{expected_duration:.6f}" if expected_duration is not None else "",
            f"{remaining_bits}" if remaining_bits is not None else "",
            f"{actual_allocation:.6f}" if actual_allocation is not None else "",
            f"{is_partial}" if is_partial is not None else "",
            f"{active_time_to_deadline:.6f}" if active_time_to_deadline is not None else "",
            f"{preempting_time_to_deadline:.6f}" if preempting_time_to_deadline is not None else "",
            f"{adjusted_data_rate:.6f}" if adjusted_data_rate is not None else "",
            f"{qci_level}" if qci_level is not None else "",
            f"{will_miss_deadline}" if will_miss_deadline is not None else "",
            f"{time_to_deadline:.6f}" if time_to_deadline is not None else ""
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
    if _logger is not None:
        _logger.close()
    _logger = Logger(filename)
    return _logger

def get_logger():
    """
    Get the global logger instance. Initialize if not exists.
    """
    global _logger
    if _logger is None:
        _logger = init_logger()
    return _logger