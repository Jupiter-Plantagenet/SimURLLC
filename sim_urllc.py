# sim_urllc.py
import simpy
import yaml
import random
import numpy as np
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
                priority=2,  # Default priority
                max_latency=config['max_latency']
            )
            devices.append(device)
    
    return devices

def main(config=None, seed=None):
    """Run a single simulation with given configuration and seed"""
    if config is None:
        config = load_config()
    
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    
    # Initialize logger
    init_logger(f"sim_urllc_log_seed_{seed}.csv" if seed else "sim_urllc_log.csv")
    
    # Create SimPy environment
    env = simpy.Environment()
    
    # Create devices (initially without base station)
    devices = create_devices(env, config)
    
    # Create base station
    base_station = BaseStation(
        env=env,
        num_rbs=config['num_resource_blocks'],
        scheduling_policy=config['scheduling_policy'],
        devices=devices
    )
    
    # Set base station reference in devices and start packet generation
    for device in devices:
        device.base_station = base_station
        env.process(device.generate_packets())
    
    # Run simulation
    env.run(until=config['sim_duration'])
    
    # Collect and analyze results
    logger = get_logger()
    device_stats = []
    
    for device in devices:
        # Calculate per-device statistics
        avg_latency = np.mean(device.latencies) if device.latencies else 0
        percentile_99 = np.percentile(device.latencies, 99) if device.latencies else 0
        throughput = (device.packets_sent * device.packet_size) / config['sim_duration']
        reliability = sum(1 for lat in device.latencies if lat <= config['max_latency'])
        reliability = reliability / device.packets_sent if device.packets_sent > 0 else 0
        
        # Store device statistics
        device_stats.append({
            'device_id': device.id,
            'priority': device.priority,
            'avg_latency': avg_latency,
            'percentile_99': percentile_99,
            'throughput': throughput,
            'reliability': reliability,
            'aoi': device.aoi,
            'packets_sent': device.packets_sent,
            'packets_dropped': device.packets_dropped
        })
    
    # Calculate aggregate metrics
    throughputs = [stat['throughput'] for stat in device_stats]
    if throughputs:
        sum_squared = sum(t**2 for t in throughputs)
        fairness = (sum(throughputs)**2) / (len(throughputs) * sum_squared) if sum_squared != 0 else 0
    else:
        fairness = 0
    
    # Calculate aggregate statistics
    results = {
        'avg_latency': np.mean([stat['avg_latency'] for stat in device_stats]),
        'percentile_99': np.percentile([stat['percentile_99'] for stat in device_stats], 99),
        'throughput': sum(stat['throughput'] for stat in device_stats),
        'reliability': np.mean([stat['reliability'] for stat in device_stats]),
        'aoi': np.mean([stat['aoi'] for stat in device_stats]),
        'fairness': fairness,
        'device_stats': device_stats
    }
    
    logger.close()
    return results

if __name__ == "__main__":
    main() 