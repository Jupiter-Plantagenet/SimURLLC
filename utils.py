# utils.py
# This file contains helper functions for SimURLLC, mainly for logging simulation events
# and metrics to a CSV file. It’s like a diary for everything that happens in the sim.

import csv  # Library to write data to CSV files
from datetime import datetime  # To add timestamps to our log files

class Logger:
    # This class handles writing events to a CSV file so we can analyze them later
    def __init__(self, filename="sim_urllc_log.csv"):
        # Constructor to set up the logger with a file
        # Get the current date and time (e.g., 2025-03-01 12:34:56)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Format it as YYYYMMDD_HHMMSS
        # Create a unique filename by adding the timestamp (e.g., sim_urllc_log_20250301_123456.csv)
        self.filename = f"{filename.rsplit('.', 1)[0]}_{timestamp}.csv"
        # Open the file in write mode; 'newline=""' prevents extra blank lines on Windows
        self.file = open(self.filename, 'w', newline='')
        # Create a CSV writer object to easily write rows to the file
        self.writer = csv.writer(self.file)
        # Write the header row with all the columns we’ll use
        # These match the metrics we want to track (time, IDs, event type, and all the stats)
        self.writer.writerow(["time", "device_id", "packet_id", "event", 
                             "latency", "percentile_latency", "throughput", 
                             "reliability", "aoi", "sinr", "fairness"])

    def log(self, time, device_id, packet_id, event, latency=None, percentile_latency=None, 
            throughput=None, reliability=None, aoi=None, sinr=None, fairness=None):
        # This method writes a single event or metric to the CSV file
        # Format numbers to 6 decimal places for precision, or leave blank if not provided
        row = [
            f"{time:.6f}",  # Current simulation time (e.g., 0.123456)
            device_id,      # Device ID (e.g., 3, or -1 for global events)
            packet_id,      # Packet ID (e.g., 2519, or -1 for summaries)
            event,          # What happened (e.g., "generated", "transmission_end")
            f"{latency:.6f}" if latency is not None else "",  # Latency in seconds
            f"{percentile_latency:.6f}" if percentile_latency is not None else "",  # 99th percentile latency
            f"{throughput:.6f}" if throughput is not None else "",  # Throughput in bits/s
            f"{reliability:.6f}" if reliability is not None else "",  # Reliability fraction
            f"{aoi:.6f}" if aoi is not None else "",  # Age of Information in seconds
            f"{sinr:.6f}" if sinr is not None else "",  # SINR in dB
            f"{fairness:.6f}" if fairness is not None else ""  # Jain’s Fairness Index
        ]
        # Write this row to the CSV file
        self.writer.writerow(row)
        # Flush the file to make sure it’s saved right away (no data loss if crash)
        self.file.flush()

    def close(self):
        # This method closes the log file when we’re done
        # It’s important to call this so all data is saved properly
        self.file.close()

# Create a global variable to hold our logger; starts as None (not set up yet)
logger = None

def init_logger(filename="sim_urllc_log.csv"):
    # This function sets up the logger when we first need it
    global logger  # Use the global logger variable
    # Create a new Logger instance with the given filename (e.g., "sim_urllc_log_seed_42.csv")
    logger = Logger(filename)

def get_logger():
    # This function gets the logger, setting it up if it hasn’t been yet
    global logger  # Use the global logger variable
    # If we haven’t made a logger yet, make one with the default name
    if logger is None:
        init_logger()  # Default filename will be used
    # Return the logger so other parts of the code can use it
    return logger