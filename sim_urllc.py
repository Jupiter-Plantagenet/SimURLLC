# sim_urllc.py
# This is the main file that runs the SimURLLC simulator. It sets up everything,
# runs the simulation multiple times with different seeds, and analyzes the results.

import simpy  # SimPy library for discrete-event simulation
import yaml   # Library to read the config.yaml file
import random # For setting random seeds and generating random values
from entities import BaseStation, URLLCDevice  # Import our entity classes
from utils import init_logger, get_logger  # Import logging utilities
import numpy as np  # For calculating percentiles and fairness index

def main():
    # Print a startup message so we know the simulation is beginning
    print("Starting SimURLLC simulation...")

    # Open and read the config.yaml file to get all our simulation parameters
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)  # Load YAML into a Python dictionary

    # Define a list of seeds for multiple runs (improves statistical validity)
    seeds = config["random_seeds"]  # Get seeds from config (e.g., [42, 43, 44, 45, 46])

    # Create a list to store results from all simulation runs
    all_results = []

    # Loop through each seed to run the simulation multiple times
    for seed in seeds:
        # Announce which seed we're using for this run
        print(f"Running simulation with seed {seed}...")

        # Initialize the logger for this run, using a unique filename with the seed
        init_logger(f"sim_urllc_log_seed_{seed}.csv")

        # Set the random seed so results are reproducible for this run
        random.seed(seed)

        # Create a new SimPy environment for this simulation run
        env = simpy.Environment()

        # Create the BaseStation object with parameters from config
        base_station = BaseStation(
            env=env,  # The simulation environment
            num_rbs=config["num_resource_blocks"],  # Number of resource blocks
            scheduling_policy=config.get("scheduling_policy", "hybrid-edf-preemptive")  # Default policy if not in config
        )

        # Create a list to hold all URLLCDevice objects
        devices = []

        # Create each device based on the number specified in config
        for i in range(config["num_devices"]):
            device = URLLCDevice(
                env=env,  # The simulation environment
                id=i,  # Unique ID for this device (0 to num_devices-1)
                location=random.uniform(10, 100),  # Random distance between 10 and 100 meters
                arrival_rate=config["arrival_rate"],  # Packet arrival rate from config
                packet_size=config["packet_size"],  # Packet size in bits
                base_station=base_station,  # Reference to the base station
                priority=random.choice(config["priority_levels"]),  # Random priority (e.g., 1, 2, 3)
                max_latency=config["max_latency"]  # Max allowed latency (e.g., 1 ms)
            )
            devices.append(device)  # Add the device to our list

        # Run the simulation until the duration specified in config (e.g., 10 seconds)
        env.run(until=config["sim_duration"])

        # Get the logger instance to log results and close it later
        logger = get_logger()

        # Store per-device stats for this run
        device_stats = []

        # Analyze results for each device
        for device in devices:
            # Calculate average latency; use 0 if no packets were sent
            avg_latency = sum(device.latencies) / len(device.latencies) if device.latencies else 0

            # Calculate 99th percentile latency using NumPy; 0 if too few samples
            percentile_99 = np.percentile(device.latencies, 99) if len(device.latencies) >= 10 else 0

            # Calculate throughput: total bits sent divided by simulation duration
            throughput = (device.packets_sent * config["packet_size"]) / config["sim_duration"]

            # Calculate reliability: fraction of packets with latency <= max_latency
            reliable_packets = sum(1 for lat in device.latencies if lat <= config["max_latency"])
            reliability = reliable_packets / device.packets_sent if device.packets_sent > 0 else 0

            # Get the final Age of Information (AoI) for this device
            aoi = device.aoi

            # Log a summary for this device
            logger.log(
                time=env.now,  # Current simulation time (end of run)
                device_id=device.id,
                packet_id=-1,  # No specific packet for summary
                event="device_summary",
                latency=avg_latency,
                percentile_latency=percentile_99,
                throughput=throughput,
                reliability=reliability,
                aoi=aoi
            )

            # Store stats for this device
            device_stats.append({
                "avg_latency": avg_latency,
                "percentile_99": percentile_99,
                "throughput": throughput,
                "reliability": reliability,
                "aoi": aoi
            })

        # Calculate Jain’s Fairness Index across all devices’ throughputs
        throughputs = [stat["throughput"] for stat in device_stats]
        fairness = (sum(throughputs) ** 2) / (len(throughputs) * sum(t ** 2 for t in throughputs)) if throughputs else 0

        # Calculate run-wide averages
        avg_latency_run = sum(stat["avg_latency"] for stat in device_stats) / len(device_stats)
        percentile_99_run = np.percentile([stat["percentile_99"] for stat in device_stats], 99) if device_stats else 0
        total_throughput_run = sum(stat["throughput"] for stat in device_stats)
        avg_reliability_run = sum(stat["reliability"] for stat in device_stats) / len(device_stats)
        avg_aoi_run = sum(stat["aoi"] for stat in device_stats) / len(device_stats)

        # Log a summary for the entire simulation run
        logger.log(
            time=env.now,
            device_id=-1,
            packet_id=-1,
            event="simulation_summary",
            latency=avg_latency_run,
            percentile_latency=percentile_99_run,
            throughput=total_throughput_run,
            reliability=avg_reliability_run,
            aoi=avg_aoi_run,
            fairness=fairness
        )

        # Close the logger to save the file
        logger.close()

        # Store results for this run
        all_results.append({
            "seed": seed,
            "avg_latency": avg_latency_run,
            "percentile_99": percentile_99_run,
            "throughput": total_throughput_run,
            "reliability": avg_reliability_run,
            "aoi": avg_aoi_run,
            "fairness": fairness,
            "device_stats": device_stats
        })

        # Announce completion of this run
        print(f"Completed simulation with seed {seed}.")

    # Print a message when all runs are done
    print("All simulation runs completed.")

    # Open a summary file to write overall results
    with open("sim_urllc_summary.txt", "w") as summary_file:
        # Write a header for the summary table
        summary_file.write("Seed\tAvg Latency (s)\t99th Percentile Latency (s)\tTotal Throughput (bps)\tAvg Reliability\tAvg AoI (s)\tFairness Index\n")

        # Write results for each run
        for result in all_results:
            summary_file.write(
                f"{result['seed']}\t"
                f"{result['avg_latency']:.6f}\t"
                f"{result['percentile_99']:.6f}\t"
                f"{result['throughput']:.2f}\t"
                f"{result['reliability']:.6f}\t"
                f"{result['aoi']:.6f}\t"
                f"{result['fairness']:.6f}\n"
            )

    # Print a final message to confirm results are saved
    print("Simulation Done. Results written to sim_urllc_summary.txt")

# If this file is run directly (not imported as a module), start the simulation
if __name__ == "__main__":
    main()