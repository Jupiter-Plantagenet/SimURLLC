# run_experiments.py
import yaml
import copy
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from sim_urllc import main as run_simulation

def load_base_config():
    """Load the base configuration from config.yaml"""
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

def define_scenarios(base_config):
    """Define different simulation scenarios"""
    scenarios = {}
    
    # Baseline scenario
    scenarios['baseline'] = copy.deepcopy(base_config)
    
    # High load scenario
    high_load = copy.deepcopy(base_config)
    high_load['arrival_rate'] = 80
    scenarios['high_load'] = high_load
    
    # Mixed priority scenario
    mixed_priority = copy.deepcopy(base_config)
    mixed_priority['device_configs'] = [
        # High priority devices
        {
            'count': base_config['num_devices'] // 2,
            'arrival_rate': base_config['arrival_rate'] * 2,
            'packet_size': base_config['packet_size'] / 2,
            'priority': 1
        },
        # Low priority devices
        {
            'count': base_config['num_devices'] // 2,
            'arrival_rate': base_config['arrival_rate'] / 4,
            'packet_size': base_config['packet_size'] * 2,
            'priority': 3
        }
    ]
    scenarios['mixed_priority'] = mixed_priority
    
    # Deadline sensitive scenario (same as mixed priority but with different deadlines)
    deadline_sensitive = copy.deepcopy(mixed_priority)
    deadline_sensitive['device_configs'][0]['max_latency'] = base_config['max_latency'] * 0.5
    deadline_sensitive['device_configs'][1]['max_latency'] = base_config['max_latency'] * 2
    scenarios['deadline_sensitive'] = deadline_sensitive
    
    # Channel variation scenario
    channel_variation = copy.deepcopy(base_config)
    channel_variation['interference_rate'] = 2
    channel_variation['path_loss_exponent'] = 4.0
    scenarios['channel_variation'] = channel_variation
    
    return scenarios

def run_experiments(scenarios):
    """Run experiments for all scenarios and schedulers"""
    schedulers = [
        'preemptive', 'non-preemptive', 'round-robin',
        'edf', 'fiveg-fixed', 'hybrid-edf'
    ]
    
    # Create results directory
    Path('results').mkdir(exist_ok=True)
    
    # Initialize results storage
    device_results = []
    aggregate_results = []
    
    for scenario_name, config in scenarios.items():
        print(f"\nRunning scenario: {scenario_name}")
        
        for scheduler in schedulers:
            print(f"  Running scheduler: {scheduler}")
            config['scheduling_policy'] = scheduler
            
            for seed in config['random_seeds']:
                print(f"    Running seed: {seed}")
                
                # Run simulation
                results = run_simulation(config, seed)
                
                # Store device-level results
                for device_stat in results['device_stats']:
                    device_results.append({
                        'scheduler': scheduler,
                        'scenario': scenario_name,
                        'seed': seed,
                        'device_id': device_stat['device_id'],
                        'priority': device_stat.get('priority', 2),  # Default priority if not specified
                        'avg_latency': device_stat['avg_latency'],
                        'percentile_99': device_stat['percentile_99'],
                        'throughput': device_stat['throughput'],
                        'reliability': device_stat['reliability'],
                        'aoi': device_stat['aoi']
                    })
                
                # Store aggregate results
                aggregate_results.append({
                    'scheduler': scheduler,
                    'scenario': scenario_name,
                    'seed': seed,
                    'avg_latency': results['avg_latency'],
                    'percentile_99': results['percentile_99'],
                    'throughput': results['throughput'],
                    'reliability': results['reliability'],
                    'aoi': results['aoi'],
                    'fairness': results['fairness']
                })
    
    # Convert to DataFrames and save
    device_df = pd.DataFrame(device_results)
    aggregate_df = pd.DataFrame(aggregate_results)
    
    device_df.to_csv('results/all_device_metrics.csv', index=False)
    aggregate_df.to_csv('results/all_aggregate_metrics.csv', index=False)
    
    return device_df, aggregate_df

def plot_fairness(aggregate_df):
    """Plot fairness comparison across scenarios and schedulers"""
    plt.figure(figsize=(12, 6))
    sns.boxplot(data=aggregate_df, x='scenario', y='fairness', hue='scheduler')
    plt.title('Fairness Comparison Across Scenarios')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('results/fairness_comparison.png')
    plt.close()

def plot_throughput_by_priority(device_df):
    """Plot throughput against priority levels"""
    plt.figure(figsize=(12, 6))
    sns.boxplot(data=device_df, x='priority', y='throughput', hue='scheduler')
    plt.title('Throughput vs Priority Levels')
    plt.tight_layout()
    plt.savefig('results/throughput_by_priority.png')
    plt.close()

def plot_latency_by_priority(device_df):
    """Plot average latency against priority levels"""
    plt.figure(figsize=(12, 6))
    sns.boxplot(data=device_df, x='priority', y='avg_latency', hue='scheduler')
    plt.title('Average Latency vs Priority Levels')
    plt.tight_layout()
    plt.savefig('results/latency_by_priority.png')
    plt.close()

def plot_reliability_heatmap(device_df):
    """Plot reliability heatmap"""
    pivot_table = pd.pivot_table(
        device_df,
        values='reliability',
        index='scheduler',
        columns='scenario',
        aggfunc='mean'
    )
    
    plt.figure(figsize=(10, 6))
    sns.heatmap(pivot_table, annot=True, cmap='YlOrRd', fmt='.3f')
    plt.title('Reliability Heatmap: Schedulers vs Scenarios')
    plt.tight_layout()
    plt.savefig('results/reliability_heatmap.png')
    plt.close()

def plot_latency_heatmap(device_df):
    """Plot latency heatmap"""
    pivot_table = pd.pivot_table(
        device_df,
        values='avg_latency',
        index='scheduler',
        columns='scenario',
        aggfunc='mean'
    )
    
    plt.figure(figsize=(10, 6))
    sns.heatmap(pivot_table, annot=True, cmap='YlOrRd', fmt='.3e')
    plt.title('Average Latency Heatmap: Schedulers vs Scenarios')
    plt.tight_layout()
    plt.savefig('results/latency_heatmap.png')
    plt.close()

def generate_plots(device_df, aggregate_df):
    """Generate all plots"""
    print("\nGenerating plots...")
    plot_fairness(aggregate_df)
    plot_throughput_by_priority(device_df)
    plot_latency_by_priority(device_df)
    plot_reliability_heatmap(device_df)
    plot_latency_heatmap(device_df)
    print("Plots generated and saved in the 'results' directory.")

def main():
    print("Starting experiments...")
    
    # Load base configuration
    base_config = load_base_config()
    
    # Define scenarios
    scenarios = define_scenarios(base_config)
    
    # Run experiments
    device_df, aggregate_df = run_experiments(scenarios)
    
    # Generate plots
    generate_plots(device_df, aggregate_df)
    
    print("\nExperiments completed. Results saved in the 'results' directory.")

if __name__ == "__main__":
    main() 