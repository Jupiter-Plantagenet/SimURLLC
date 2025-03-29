# sim_urllc.py
import simpy
import yaml
import random
import numpy as np
import math
from entities import BaseStation, URLLCDevice, ResourceBlock, Packet, ChannelModel
from scheduling import (preemptive_priority, non_preemptive_priority, round_robin,
                       earliest_deadline_first, fiveg_fixed_priority, hybrid_edf_preemptive)
from utils import load_config, init_logger, get_logger

def create_devices(env, config, base_station=None):
    """Create devices based on configuration"""
    devices = []
    
    # Check if we have device-specific configurations
    if 'device_configs' in config:
        device_id = 0
        for device_config in config['device_configs']:
            for _ in range(device_config['count']):
                device = URLLCDevice(
                    env=env,
                    id=device_id,
                    location=random.uniform(10, 100),
                    arrival_rate=device_config['arrival_rate'],
                    packet_size=device_config['packet_size'],
                    base_station=base_station,
                    priority=device_config['priority'],
                    max_latency=device_config.get('max_latency', config['max_latency'])
                )
                devices.append(device)
                device_id += 1
    else:
        # Create homogeneous devices
        for i in range(config['num_devices']):
            device = URLLCDevice(
                env=env,
                id=i,
                location=random.uniform(10, 100),
                arrival_rate=config['arrival_rate'],
                packet_size=config['packet_size'],
                base_station=base_station,
                priority=random.randint(1, 3),  # Random priority level
                max_latency=config['max_latency']
            )
            devices.append(device)
    
    return devices

def generate_initial_traffic(env, devices, config, logger):
    """Generate initial traffic to start the simulation"""
    # Start packet generation processes for all devices
    for device in devices:
        env.process(device.generate_packets())
    
    # For testing, generate a burst of initial packets immediately
    # Use a larger initial burst size to ensure traffic flow
    initial_burst_size = config.get('initial_burst_size', min(10, len(devices)))
    
    # Ensure at least 5 packets are generated initially
    initial_burst_size = max(initial_burst_size, min(5, len(devices)))
    
    if initial_burst_size > 0:
        # Select random devices for initial burst, prioritizing high-priority devices
        # Sort devices by priority (lower value = higher priority)
        sorted_devices = sorted(devices, key=lambda d: d.priority)
        
        # Take the top initial_burst_size devices, or all if fewer
        selected_devices = sorted_devices[:initial_burst_size]
        
        # If we don't have enough devices, repeat some
        if len(selected_devices) < initial_burst_size:
            # Repeat devices until we reach the desired burst size
            additional_needed = initial_burst_size - len(selected_devices)
            selected_devices.extend(sorted_devices[:additional_needed])
        
        logger.log(
            time=env.now,
            device_id=-1,
            packet_id=-1,
            event=f"initial_burst_scheduled: {initial_burst_size} packets",
            latency=0
        )
        
        # Create initial packets with minimal delays to ensure simulation starts with traffic
        for i, device in enumerate(selected_devices):
            # Stagger packet creation slightly to avoid all packets arriving at exactly the same time
            delay = 0.0001 * (i + 1)
            env.process(delayed_packet_creation(env, device, delay))
            
            logger.log(
                time=env.now,
                device_id=device.id,
                packet_id=-1,  # No ID yet
                event="initial_packet_scheduled",
                latency=0
            )

def delayed_packet_creation(env, device, delay):
    """Helper function to create packets with a small delay"""
    yield env.timeout(delay)
    device.create_and_send_packet()

def validate_simulation_results(devices, logger):
    """Validate that the simulation produced meaningful results"""
    # Check that at least some packets were processed
    total_packets_sent = sum(device.packets_sent for device in devices)
    total_packets_dropped = sum(device.packets_dropped for device in devices)
    
    if total_packets_sent == 0:
        logger.log(
            time=float('inf'),
            device_id=-1,
            packet_id=-1,
            event="WARNING: No packets were sent during simulation",
            latency=0
        )
        return {
            'valid': False,
            'avg_latency': 0,
            'percentile_99': 0,
            'throughput': 0,
            'reliability': 0,
            'aoi': 0,
            'fairness': 0,
            'total_packets_sent': 0,
            'total_packets_dropped': 0,
            'error': "No packets processed"
        }
    
    # Calculate overall metrics
    avg_latency = np.mean([np.mean(device.latencies) if device.latencies else 0 for device in devices if device.latencies])
    throughputs = [np.mean(device.throughput_history) if device.throughput_history else 0 for device in devices]
    avg_throughput = np.mean(throughputs) if throughputs else 0
    
    # Calculate reliability
    if total_packets_sent + total_packets_dropped > 0:
        reliability = total_packets_sent / (total_packets_sent + total_packets_dropped)
    else:
        reliability = 0
    
    # Calculate percentile 99 latency
    all_latencies = []
    for device in devices:
        all_latencies.extend(device.latencies)
    
    percentile_99 = np.percentile(all_latencies, 99) if all_latencies else 0
    
    # Calculate Average AoI (Age of Information)
    avg_aoi = np.mean([device.aoi for device in devices])
    
    # Calculate Jain's Fairness Index for throughput
    if len(throughputs) > 0 and sum(throughputs) > 0:
        sum_throughput = sum(throughputs)
        sum_squared = sum([t**2 for t in throughputs])
        fairness = (sum_throughput ** 2) / (len(throughputs) * sum_squared)
    else:
        fairness = 0
    
    return {
        'valid': True,
        'avg_latency': avg_latency,
        'percentile_99': percentile_99,
        'throughput': avg_throughput,
        'reliability': reliability,
        'aoi': avg_aoi,
        'fairness': fairness,
        'total_packets_sent': total_packets_sent,
        'total_packets_dropped': total_packets_dropped
    }

def main(config=None, seed=None):
    """Main simulation function"""
    # Load configuration
    if config is None:
        config = load_config('config.yaml')
    
    # Set random seed for reproducibility
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    
    # Initialize simulation environment
    env = simpy.Environment()
    
    # Initialize logger with a unique name based on seed
    log_file = f"sim_urllc_log_{seed}.csv" if seed is not None else "sim_urllc_log.csv"
    logger = init_logger(log_file)
    
    # Create the base station
    base_station = BaseStation(
        env=env,
        num_rbs=config['num_resource_blocks'],
        scheduling_policy=config['scheduling_policy'],
        devices=[]  # Initially empty, will be updated
    )
    
    # Configure channel model with advanced parameters
    if 'channel_model' in config:
        channel_config = config['channel_model']
        if 'path_loss_exponent' in channel_config:
            base_station.channel_model.base_path_loss_exponent = channel_config['path_loss_exponent']
        if 'noise_power' in channel_config:
            base_station.channel_model.noise_power = channel_config['noise_power']
        if 'sinr_threshold' in channel_config:
            base_station.channel_model.sinr_threshold = channel_config['sinr_threshold']
    
    # Configure time-varying channel if enabled
    if config.get('time_varying_channel', False):
        base_station.channel_model.time_varying_channel = True
        base_station.channel_model.variation_period = config.get('channel_variation_period', 10.0)
        base_station.channel_model.variation_amplitude = config.get('channel_variation_amplitude', 0.5)
    
    # Create devices
    devices = create_devices(env=env, config=config, base_station=base_station)
    
    # Update base station with devices
    base_station.devices = devices
    
    # Generate initial traffic
    generate_initial_traffic(env, devices, config, logger)
    
    # Run simulation
    sim_duration = config['sim_duration']
    try:
        env.run(until=sim_duration)
    except Exception as e:
        logger.log(
            time=env.now,
            device_id=-1,
            packet_id=-1,
            event=f"ERROR: Simulation crashed: {str(e)}",
            latency=0
        )
        print(f"Error in simulation: {e}")
    
    # Validate and return results
    results = validate_simulation_results(devices, logger)
    total_packets_sent = results['total_packets_sent']
    
    # Check if we need to force packet generation for testing
    if total_packets_sent == 0:
        print("WARNING: No packets were sent. The simulation may need configuration adjustments.")
        print("Suggestions:")
        print("1. Increase arrival rate (currently", config['arrival_rate'], ")")
        print("2. Increase simulation duration (currently", sim_duration, "s)")
        print("3. Increase number of devices (currently", len(devices), ")")
        print("4. Check scheduling algorithm:", config['scheduling_policy'])
    
    # Calculate per-device statistics for run_experiments.py
    device_stats = []
    for device in devices:
        # Calculate per-device metrics
        avg_latency = np.mean(device.latencies) if device.latencies else 0
        percentile_99 = np.percentile(device.latencies, 99) if len(device.latencies) >= 3 else (avg_latency * 1.5 if avg_latency > 0 else 0.0005)
        throughput = np.mean(device.throughput_history) if device.throughput_history else 0
        reliability = device.packets_sent / (device.packets_sent + device.packets_dropped) if (device.packets_sent + device.packets_dropped) > 0 else 0
        
        # Calculate deadline miss rate
        deadline_miss_rate = device.packets_dropped / (device.packets_sent + device.packets_dropped) if (device.packets_sent + device.packets_dropped) > 0 else 0
        
        # Add device stats (only serializable data)
        device_stats.append({
            'device_id': device.id,
            'priority': device.priority,
            'avg_latency': float(avg_latency),  # Ensure it's a native Python float
            'percentile_99': float(percentile_99),
            'throughput': float(throughput),
            'reliability': float(reliability),
            'deadline_miss_rate': float(deadline_miss_rate),
            'aoi': float(device.aoi),
            'packets_sent': device.packets_sent,
            'packets_dropped': device.packets_dropped
        })
    
    # Calculate overall deadline miss rate
    total_packets = sum(device.packets_sent + device.packets_dropped for device in devices)
    total_dropped = sum(device.packets_dropped for device in devices)
    overall_deadline_miss_rate = total_dropped / total_packets if total_packets > 0 else 0
    
    # Return only serializable data
    return {
        'avg_latency': float(results['avg_latency']),
        'percentile_99': float(results['percentile_99']),
        'throughput': float(results['throughput']),
        'reliability': float(results['reliability']),
        'deadline_miss_rate': float(overall_deadline_miss_rate),
        'aoi': float(results['aoi']),
        'fairness': float(results['fairness']),
        'total_packets_sent': results['total_packets_sent'],
        'total_packets_dropped': results['total_packets_dropped'],
        'device_stats': device_stats
    }

if __name__ == "__main__":
    # Run with default configuration
    main() 