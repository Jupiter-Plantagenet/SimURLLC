# run_experiments.py
import yaml
import copy
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from sim_urllc import main as run_simulation
import sys
import traceback
import time
import os

# Set global font size for all plots
plt.rcParams.update({
    'font.size': 20,
    'axes.labelsize': 22,
    'axes.titlesize': 24,
    'xtick.labelsize': 20,
    'ytick.labelsize': 20,
    'legend.fontsize': 20,
    'legend.title_fontsize': 22,
})

def load_base_config():
    """Load the base configuration from config.yaml"""
    try:
        with open('config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("Error: config.yaml file not found.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing config.yaml: {e}")
        sys.exit(1)

def define_scenarios(base_config):
    """Define different simulation scenarios"""
    scenarios = {}
    
    # Baseline scenario
    scenarios['baseline'] = copy.deepcopy(base_config)
    
    # High load scenario
    high_load = copy.deepcopy(base_config)
    high_load['arrival_rate'] = 30  # 3x the baseline arrival rate
    # Adjust device-specific arrival rates
    for device_config in high_load.get('device_configs', []):
        device_config['arrival_rate'] *= 3  # Triple the arrival rate
    scenarios['high_load'] = high_load
    
    # Mixed priority scenario with heterogeneous device configurations
    mixed_priority = copy.deepcopy(base_config)
    mixed_priority['device_configs'] = [
        # High priority devices (30% of total)
        {
            'count': int(base_config['num_devices'] * 0.3),
            'arrival_rate': base_config['arrival_rate'] * 2,  # Higher arrival rate
            'packet_size': base_config['packet_size'] / 2,    # Smaller packets
            'priority': 1,                                   # High priority
            'max_latency': base_config['max_latency']        # Standard latency
        },
        # Medium priority devices (30% of total)
        {
            'count': int(base_config['num_devices'] * 0.3),
            'arrival_rate': base_config['arrival_rate'],      # Standard arrival rate
            'packet_size': base_config['packet_size'],        # Standard packet size
            'priority': 2,                                   # Medium priority
            'max_latency': base_config['max_latency'] * 1.5  # Relaxed latency
        },
        # Low priority devices (40% of total)
        {
            'count': int(base_config['num_devices'] * 0.4),
            'arrival_rate': base_config['arrival_rate'] / 2,  # Lower arrival rate
            'packet_size': base_config['packet_size'] * 2,    # Larger packets
            'priority': 3,                                   # Low priority
            'max_latency': base_config['max_latency'] * 2    # Very relaxed latency
        }
    ]
    scenarios['mixed_priority'] = mixed_priority
    
    # Deadline sensitive scenario (different deadlines for different device types)
    deadline_sensitive = copy.deepcopy(mixed_priority)
    # Make high priority deadlines extremely tight
    deadline_sensitive['device_configs'][0]['max_latency'] = base_config['max_latency'] * 0.1  # Extremely tight deadline (0.1ms)
    # Make medium priority deadlines very tight
    deadline_sensitive['device_configs'][1]['max_latency'] = base_config['max_latency'] * 0.3  # Very tight deadline (0.3ms)
    # Make low priority deadlines standard
    deadline_sensitive['device_configs'][2]['max_latency'] = base_config['max_latency'] * 0.8  # Slightly tighter than standard (0.8ms)
    
    # Increase packet sizes to make meeting deadlines harder
    deadline_sensitive['device_configs'][0]['packet_size'] *= 1.2  # 20% larger packets for high priority
    deadline_sensitive['device_configs'][1]['packet_size'] *= 1.5  # 50% larger packets for medium priority
    deadline_sensitive['device_configs'][2]['packet_size'] *= 1.8  # 80% larger packets for low priority
    
    # Increase arrival rates to create more contention
    deadline_sensitive['device_configs'][0]['arrival_rate'] *= 1.5  # 50% more packets for high priority
    deadline_sensitive['device_configs'][1]['arrival_rate'] *= 1.3  # 30% more packets for medium priority
    deadline_sensitive['device_configs'][2]['arrival_rate'] *= 1.2  # 20% more packets for low priority
    
    # Reduce number of resource blocks to create more contention
    deadline_sensitive['num_resource_blocks'] = max(6, base_config['num_resource_blocks'] // 1.5)
    
    scenarios['deadline_sensitive'] = deadline_sensitive
    
    # Channel variation scenario (higher interference and path loss)
    channel_variation = copy.deepcopy(base_config)
    channel_variation['interference_rate'] = 15                # Very frequent interference
    channel_variation['time_varying_channel'] = True           # Enable time-varying channel
    channel_variation['channel_variation_period'] = 2.0        # Very fast variations (2 second period)
    channel_variation['channel_variation_amplitude'] = 1.5     # Larger amplitude of variation
    
    # Add SINR threshold for packet loss
    if 'channel_model' not in channel_variation:
        channel_variation['channel_model'] = {}
    channel_variation['channel_model']['sinr_threshold'] = 10.0  # Higher SINR threshold (more packet drops)
    channel_variation['channel_model']['path_loss_exponent'] = 4.5  # Higher path loss exponent
    
    # Increase arrival rate to stress the system more
    channel_variation['arrival_rate'] = base_config['arrival_rate'] * 1.5
    for device_config in channel_variation.get('device_configs', []):
        device_config['arrival_rate'] *= 1.5  # Increase arrival rate by 50%
    
    # Reduce number of resource blocks to create more contention
    channel_variation['num_resource_blocks'] = max(5, base_config['num_resource_blocks'] // 2)
    
    scenarios['channel_variation'] = channel_variation
    
    return scenarios

def run_experiments(scenarios):
    """Run experiments for all scenarios and schedulers"""
    # All available scheduling algorithms
    schedulers = [
        'preemptive',      # Preemptive priority scheduling
        'non-preemptive',  # Non-preemptive priority scheduling
        'round-robin',     # Round-robin scheduling
        'edf',             # Earliest Deadline First
        'fiveg-fixed',     # 5G-style fixed priority
        'hybrid-edf'       # Hybrid EDF with preemption
    ]
    
    # Create results directory
    Path('results').mkdir(exist_ok=True)
    
    # Create a directory for this run with timestamp
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join('results', f'run_{timestamp}')
    Path(run_dir).mkdir(exist_ok=True)
    
    # Save configuration for reproducibility
    try:
        with open(os.path.join(run_dir, 'scenarios.yaml'), 'w') as f:
            # Use safe_dump to avoid serialization issues
            yaml.safe_dump(scenarios, f, default_flow_style=False)
    except Exception as e:
        print(f"Warning: Could not save scenarios configuration: {str(e)}")
    
    # Initialize results storage
    device_results = []
    aggregate_results = []
    
    # Limit the number of seeds for faster testing if needed
    max_seeds_per_scenario = 30  # Use at least 30 seeds for statistical significance
    min_seeds_per_scenario = 30  # Ensure at least 30 seeds for statistical significance
    
    # Track progress
    total_runs = 0
    for scenario_name, config in scenarios.items():
        # Ensure minimum number of seeds
        if 'random_seeds' in config and len(config['random_seeds']) < min_seeds_per_scenario:
            print(f"Warning: {scenario_name} has fewer than {min_seeds_per_scenario} seeds. Using default seeds.")
            config['random_seeds'] = list(range(42, 42 + min_seeds_per_scenario))
        
        # Limit seeds for faster testing
        if 'random_seeds' in config and len(config['random_seeds']) > max_seeds_per_scenario:
            print(f"Limiting {scenario_name} to {max_seeds_per_scenario} seeds for faster testing")
            config['random_seeds'] = config['random_seeds'][:max_seeds_per_scenario]
        
        total_runs += len(schedulers) * len(config.get('random_seeds', [42]))  # Default to seed 42 if no seeds specified
    
    completed_runs = 0
    failed_runs = 0
    
    for scenario_name, config in scenarios.items():
        print(f"\nRunning scenario: {scenario_name}")
        
        # Create scenario directory
        scenario_dir = os.path.join(run_dir, scenario_name)
        Path(scenario_dir).mkdir(exist_ok=True)
        
        for scheduler in schedulers:
            print(f"  Running scheduler: {scheduler}")
            
            # Update configuration with current scheduler
            config['scheduling_policy'] = scheduler
            
            # Create scheduler directory
            scheduler_dir = os.path.join(scenario_dir, scheduler)
            Path(scheduler_dir).mkdir(exist_ok=True)
            
            # Get seeds from config or use default
            seeds = config.get('random_seeds', [42])
            
            for seed in seeds:
                print(f"    Running seed: {seed} (Progress: {completed_runs}/{total_runs}, Failed: {failed_runs})")
                
                try:
                    # Run simulation
                    start_time = time.time()
                    results = run_simulation(config, seed)
                    end_time = time.time()
                    
                    # Track simulation run time
                    run_time = end_time - start_time
                    print(f"      Completed in {run_time:.2f} seconds")
                    
                    # Store device-level results
                    for device_stat in results.get('device_stats', []):
                        device_results.append({
                            'scheduler': scheduler,
                            'scenario': scenario_name,
                            'seed': seed,
                            'device_id': device_stat.get('device_id', -1),
                            'priority': device_stat.get('priority', 2),  # Default priority if not specified
                            'avg_latency': device_stat.get('avg_latency', 0),
                            'percentile_99': device_stat.get('percentile_99', 0),
                            'throughput': device_stat.get('throughput', 0),
                            'reliability': device_stat.get('reliability', 0),
                            'deadline_miss_rate': device_stat.get('deadline_miss_rate', 0),
                            'aoi': device_stat.get('aoi', 0)
                        })
                    
                    # Store aggregate results
                    aggregate_results.append({
                        'scheduler': scheduler,
                        'scenario': scenario_name,
                        'seed': seed,
                        'run_time': run_time,
                        'avg_latency': results.get('avg_latency', 0),
                        'percentile_99': results.get('percentile_99', 0),
                        'throughput': results.get('throughput', 0),
                        'reliability': results.get('reliability', 0),
                        'deadline_miss_rate': results.get('deadline_miss_rate', 0),
                        'aoi': results.get('aoi', 0),
                        'fairness': results.get('fairness', 0),
                        'packets_sent': results.get('total_packets_sent', 0),
                        'packets_dropped': results.get('total_packets_dropped', 0)
                    })
                    
                    # Save per-seed data
                    try:
                        with open(os.path.join(scheduler_dir, f'seed_{seed}_results.yaml'), 'w') as f:
                            # Use safe_dump to avoid serialization issues
                            yaml.safe_dump(results, f, default_flow_style=False)
                    except Exception as e:
                        print(f"      Warning: Could not save seed results: {str(e)}")
                    
                    # Update progress
                    completed_runs += 1
                    
                except Exception as e:
                    # Log the error in detail
                    error_file = os.path.join(scheduler_dir, f'seed_{seed}_error.log')
                    with open(error_file, 'w') as f:
                        f.write(f"Error in scenario {scenario_name}, scheduler {scheduler}, seed {seed}:\n")
                        f.write(traceback.format_exc())
                    
                    print(f"      ERROR: {str(e)}")
                    print(f"      Error details saved to {error_file}")
                    traceback.print_exc()
                    failed_runs += 1
                    
                    # Continue to next configuration
                    print("      Continuing to next configuration...")
                    continue
                
                # Save intermediate results after each scenario to avoid data loss
                if len(device_results) > 0 and len(aggregate_results) > 0:
                    try:
                        device_df_intermediate = pd.DataFrame(device_results)
                        aggregate_df_intermediate = pd.DataFrame(aggregate_results)
                        
                        device_df_intermediate.to_csv(os.path.join(run_dir, 'all_device_metrics_intermediate.csv'), index=False)
                        aggregate_df_intermediate.to_csv(os.path.join(run_dir, 'all_aggregate_metrics_intermediate.csv'), index=False)
                    except Exception as e:
                        print(f"      Warning: Could not save intermediate results: {str(e)}")
    
    # Final results
    print(f"\nCompleted {completed_runs}/{total_runs} runs, Failed: {failed_runs}")
    
    # Convert to DataFrames and save
    if device_results and aggregate_results:
        try:
            device_df = pd.DataFrame(device_results)
            aggregate_df = pd.DataFrame(aggregate_results)
            
            # Save to results directory
            device_df.to_csv(os.path.join('results', 'all_device_metrics.csv'), index=False)
            aggregate_df.to_csv(os.path.join('results', 'all_aggregate_metrics.csv'), index=False)
            
            # Also save to the specific run directory
            device_df.to_csv(os.path.join(run_dir, 'all_device_metrics.csv'), index=False)
            aggregate_df.to_csv(os.path.join(run_dir, 'all_aggregate_metrics.csv'), index=False)
            
            return device_df, aggregate_df
        except Exception as e:
            print(f"Error saving final results: {str(e)}")
            return pd.DataFrame(), pd.DataFrame()
    else:
        print("No results were collected. Check for errors in the simulation.")
        return pd.DataFrame(), pd.DataFrame()

def plot_fairness(aggregate_df):
    """Plot fairness comparison across scenarios and schedulers"""
    # Fairness comparison plot
    plt.figure(figsize=(16, 10))
    ax = sns.boxplot(data=aggregate_df, x='scenario', y='fairness', hue='scheduler')
    plt.xticks(rotation=45)
    plt.ylabel('Fairness Index')
    plt.xlabel('Scenario')
    
    # Improve legend placement
    plt.legend(title='Scheduler', bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.tight_layout()
    plt.savefig('results/fairness_comparison.png', dpi=600, bbox_inches='tight')
    plt.close()

def plot_throughput_by_priority(device_df):
    """Plot throughput against priority levels"""
    # Throughput vs Priority plot
    plt.figure(figsize=(16, 10))
    ax = sns.boxplot(data=device_df, x='priority', y='throughput', hue='scheduler')
    plt.ylabel('Throughput (bps)')
    plt.xlabel('Priority Level')
    
    # Improve legend placement
    plt.legend(title='Scheduler', bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.tight_layout()
    plt.savefig('results/throughput_by_priority.png', dpi=600, bbox_inches='tight')
    plt.close()

def plot_latency_by_priority(device_df):
    """Plot average latency against priority levels"""
    # Average Latency vs Priority plot
    plt.figure(figsize=(16, 10))
    ax = sns.boxplot(data=device_df, x='priority', y='avg_latency', hue='scheduler')
    plt.ylabel('Average Latency (s)')
    plt.xlabel('Priority Level')
    
    # Improve legend placement
    plt.legend(title='Scheduler', bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.tight_layout()
    plt.savefig('results/latency_by_priority.png', dpi=600, bbox_inches='tight')
    plt.close()

def plot_reliability_heatmap(device_df):
    """Plot reliability heatmap"""
    # Reliability heatmap plot
    if device_df.empty:
        print("No data available for reliability heatmap")
        return
        
    pivot_table = pd.pivot_table(
        device_df,
        values='reliability',
        index='scheduler',
        columns='scenario',
        aggfunc='mean'
    )
    
    plt.figure(figsize=(16, 10))
    ax = sns.heatmap(pivot_table, annot=True, cmap='YlOrRd', fmt='.3f', annot_kws={"size": 20})
    plt.ylabel('Scheduler')
    plt.xlabel('Scenario')
    
    plt.tight_layout()
    plt.savefig('results/reliability_heatmap.png', dpi=600, bbox_inches='tight')
    plt.close()

def plot_latency_heatmap(device_df):
    """Plot latency heatmap"""
    # Latency heatmap plot
    if device_df.empty:
        print("No data available for latency heatmap")
        return
        
    pivot_table = pd.pivot_table(
        device_df,
        values='avg_latency',
        index='scheduler',
        columns='scenario',
        aggfunc='mean'
    )
    
    plt.figure(figsize=(16, 10))
    ax = sns.heatmap(pivot_table, annot=True, cmap='YlOrRd', fmt='.3e', annot_kws={"size": 20})
    plt.ylabel('Scheduler')
    plt.xlabel('Scenario')
    
    plt.tight_layout()
    plt.savefig('results/latency_heatmap.png', dpi=600, bbox_inches='tight')
    plt.close()

def plot_deadline_miss_rate(aggregate_df):
    """Plot deadline miss rate comparison across scenarios and schedulers"""
    plt.figure(figsize=(16, 10))
    ax = sns.boxplot(data=aggregate_df, x='scenario', y='deadline_miss_rate', hue='scheduler')
    plt.xticks(rotation=45)
    plt.ylabel('Deadline Miss Rate')
    plt.xlabel('Scenario')
    
    # Improve legend placement
    plt.legend(title='Scheduler', bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.tight_layout()
    plt.savefig('results/deadline_miss_rate_comparison.png', dpi=600, bbox_inches='tight')
    plt.close()

def plot_deadline_miss_rate_by_priority(device_df):
    """Plot deadline miss rate against priority levels"""
    plt.figure(figsize=(16, 10))
    ax = sns.boxplot(data=device_df, x='priority', y='deadline_miss_rate', hue='scheduler')
    plt.ylabel('Deadline Miss Rate')
    plt.xlabel('Priority Level')
    
    # Improve legend placement
    plt.legend(title='Scheduler', bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.tight_layout()
    plt.savefig('results/deadline_miss_rate_by_priority.png', dpi=600, bbox_inches='tight')
    plt.close()

def plot_deadline_miss_rate_heatmap(device_df):
    """Plot deadline miss rate heatmap"""
    # Deadline miss rate heatmap plot
    if device_df.empty:
        print("No data available for deadline miss rate heatmap")
        return
        
    pivot_table = pd.pivot_table(
        device_df,
        values='deadline_miss_rate',
        index='scheduler',
        columns='scenario',
        aggfunc='mean'
    )
    
    plt.figure(figsize=(16, 10))
    ax = sns.heatmap(pivot_table, annot=True, cmap='YlOrRd', fmt='.3f', annot_kws={"size": 20})
    plt.ylabel('Scheduler')
    plt.xlabel('Scenario')
    
    plt.tight_layout()
    plt.savefig('results/deadline_miss_rate_heatmap.png', dpi=600, bbox_inches='tight')
    plt.close()

def generate_plots(device_df, aggregate_df):
    """Generate all plots"""
    print("\nGenerating plots...")
    
    if device_df.empty or aggregate_df.empty:
        print("No data available for plotting")
        return
        
    plot_fairness(aggregate_df)
    plot_throughput_by_priority(device_df)
    plot_latency_by_priority(device_df)
    plot_reliability_heatmap(device_df)
    plot_latency_heatmap(device_df)
    
    # Add new plots for deadline miss rate
    plot_deadline_miss_rate(aggregate_df)
    plot_deadline_miss_rate_by_priority(device_df)
    plot_deadline_miss_rate_heatmap(device_df)
    
    print("Plots generated and saved in the 'results' directory.")

def main():
    start_time = time.time()
    print("Starting experiments...")
    
    # Load base configuration
    base_config = load_base_config()
    
    # Define scenarios
    scenarios = define_scenarios(base_config)
    
    # Run experiments
    device_df, aggregate_df = run_experiments(scenarios)
    
    # Generate plots
    generate_plots(device_df, aggregate_df)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\nExperiments completed in {total_time:.2f} seconds.")
    print("Results saved in the 'results' directory.")

if __name__ == "__main__":
    main() 