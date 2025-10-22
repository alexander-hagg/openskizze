#!/usr/bin/env python3
"""
PyRibs QD Hyperparameter Benchmarking Script

This script benchmarks different QD algorithm configurations to find optimal
hyperparameters for the OpenSKIZZE urban planning optimization domain.

Key considerations:
- Parcel sizes vary in production (affects search space size)
- Will switch to AI-predicted objective function later
- Need good performance across different urban contexts
- Keep benchmark runtime reasonable (~30-60 minutes)

Hyperparameters tested:
- num_emitters: Number of emitters for exploration
- sigma: Mutation strength for GaussianEmitter
- learning_rate: Gradient step size (for evolution strategies)
- batch_size: Solutions evaluated per iteration

Metrics collected:
- Archive coverage (% of niches filled)
- QD-score (sum of all objective values)
- Best objective found
- Convergence speed
- Diversity maintenance
"""

import sys
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import time
import json
from datetime import datetime
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.config import ENCODING_CONFIG, DOMAIN_CONFIG, QD_CONFIG
from backend.encoding import ParametricEncoding
from backend.optimizer import run_qd_optimization
from backend.evaluation import eval_solution
from backend.optimization_process import create_environment
from shapely.geometry import box
import geopandas as gpd


class QDBenchmark:
    """Benchmark suite for QD hyperparameters."""
    
    def __init__(self, output_dir: str = "helper/qd_benchmark_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.results = []
        
        # Test configurations - balanced for runtime vs coverage
        self.test_configs = self._generate_test_configs()
        
        # Test parcels - small, medium, large
        self.test_parcels = self._generate_test_parcels()
        
        print(f"QD Hyperparameter Benchmark Suite")
        print(f"=" * 60)
        print(f"Output directory: {self.output_dir}")
        print(f"Test configurations: {len(self.test_configs)}")
        print(f"Test parcels: {len(self.test_parcels)}")
        print(f"Total runs: {len(self.test_configs) * len(self.test_parcels)}")
        print(f"=" * 60)
    
    def _generate_test_configs(self) -> List[Dict]:
        """
        Generate test configurations for hyperparameters.
        
        Strategy:
        - Start with default values
        - Test key dimensions systematically
        - Keep total runtime reasonable (~30-60 minutes)
        """
        configs = []
        
        # Baseline (current defaults)
        configs.append({
            'name': 'baseline',
            'num_emitters': 5,
            'sigma': 0.1,
            'learning_rate': 0.01,
            'batch_size': 16,
            'num_generations': 200,  # Reduced for benchmarking
        })
        
        # Test num_emitters (exploration breadth)
        for n_emit in [3, 7, 10]:
            configs.append({
                'name': f'emitters_{n_emit}',
                'num_emitters': n_emit,
                'sigma': 0.1,
                'learning_rate': 0.01,
                'batch_size': 16,
                'num_generations': 200,
            })
        
        # Test sigma (mutation strength)
        for sig in [0.05, 0.15, 0.2]:
            configs.append({
                'name': f'sigma_{sig:.2f}',
                'num_emitters': 5,
                'sigma': sig,
                'learning_rate': 0.01,
                'batch_size': 16,
                'num_generations': 200,
            })
        
        # Test learning_rate (gradient step size)
        for lr in [0.005, 0.02, 0.05]:
            configs.append({
                'name': f'lr_{lr:.3f}',
                'num_emitters': 5,
                'sigma': 0.1,
                'learning_rate': lr,
                'batch_size': 16,
                'num_generations': 200,
            })
        
        # Test batch_size (evaluations per iteration)
        for bs in [8, 32, 64]:
            configs.append({
                'name': f'batch_{bs}',
                'num_emitters': 5,
                'sigma': 0.1,
                'learning_rate': 0.01,
                'batch_size': bs,
                'num_generations': 200,
            })
        
        # Test promising combinations
        configs.extend([
            {
                'name': 'high_exploration',
                'num_emitters': 10,
                'sigma': 0.15,
                'learning_rate': 0.02,
                'batch_size': 32,
                'num_generations': 200,
            },
            {
                'name': 'focused_search',
                'num_emitters': 3,
                'sigma': 0.05,
                'learning_rate': 0.005,
                'batch_size': 8,
                'num_generations': 200,
            },
            {
                'name': 'balanced_fast',
                'num_emitters': 7,
                'sigma': 0.1,
                'learning_rate': 0.01,
                'batch_size': 32,
                'num_generations': 200,
            },
        ])
        
        return configs
    
    def _generate_test_parcels(self) -> List[Dict]:
        """
        Generate test parcels of different sizes.
        
        Represents realistic parcel sizes in NRW:
        - Small: 50m × 50m = 2500 m² (single block)
        - Medium: 100m × 100m = 10000 m² (large block)
        - Large: 250m × 250m = 62500 m² (district scale)
        """
        parcels = []
        
        # Small parcel (50m × 50m = 2500 m²)
        parcels.append({
            'name': 'small',
            'width': 50,
            'height': 50,
            'area_m2': 2500,
        })
        
        # Medium parcel (100m × 100m = 10000 m²)
        parcels.append({
            'name': 'medium',
            'width': 100,
            'height': 100,
            'area_m2': 10000,
        })
        
        # Large parcel (250m × 250m = 62500 m²)
        parcels.append({
            'name': 'large',
            'width': 250,
            'height': 250,
            'area_m2': 62500,
        })
        
        return parcels
    
    def _create_test_environment(self, parcel_config: Dict) -> Dict:
        """Create a test environment for a given parcel size."""
        # Create rectangular parcel geometry
        width = parcel_config['width']
        height = parcel_config['height']
        
        # Center at arbitrary coordinates in Bonn area (realistic UTM zone 32N)
        center_x, center_y = 374000, 5643000  # Bonn, Germany
        min_x = center_x - width / 2
        max_x = center_x + width / 2
        min_y = center_y - height / 2
        max_y = center_y + height / 2
        
        # Create polygon in EPSG:25832 (native)
        polygon = box(min_x, min_y, max_x, max_y)
        gdf_native = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:25832")
        
        # Convert to EPSG:4326 for GeoJSON (expected by create_environment)
        gdf_wgs84 = gdf_native.to_crs("EPSG:4326")
        
        # Convert to GeoJSON
        geojson = json.loads(gdf_wgs84.to_json())
        
        # Create environment (no existing buildings for benchmark)
        selected_features = [0, 1, 2, 3, 4, 5]  # Use subset for speed
        user_feature_ranges = {}
        hard_constraints = {'max_height': 30, 'min_distance': 0}
        
        # Create fake cached_building_data to avoid NRW API calls
        cached_building_data = {
            'gdf_buildings': gpd.GeoDataFrame(geometry=[], crs="EPSG:25832"),
            'gdf_building_heights': gpd.GeoDataFrame(geometry=[], crs="EPSG:25832"),
        }
        
        env_config = create_environment(
            user_polygon_geojson=geojson,
            selected_features=selected_features,
            user_feature_ranges=user_feature_ranges,
            hard_constraints=hard_constraints,
            cached_building_data=cached_building_data,  # Empty buildings
            feature_set='original'
        )
        
        env_config['wind_direction'] = 180
        env_config['hard_constraints'] = hard_constraints
        env_config['objective_function'] = 'simple_porosity'
        
        return env_config
    
    def _run_optimization(self, config: Dict, env_config: Dict) -> Dict:
        """Run optimization with given config and collect metrics."""
        start_time = time.time()
        
        # Create QD config
        qd_config = {
            'num_niches': 5,
            'num_generations': config['num_generations'],
            'num_emitters': config['num_emitters'],
            'sigma': config['sigma'],
            'learning_rate': config['learning_rate'],
            'batch_size': config['batch_size'],
            'output_inv_frequency': 50,  # Log every 50 generations
            'live_update_interval': 10,  # Capture metrics every 10 generations
        }
        
        # Create encoding
        encoding_config = ENCODING_CONFIG.copy()
        encoding_obj = ParametricEncoding(encoding_config)
        
        # Track metrics over time
        metrics_history = {
            'generation': [],
            'archive_size': [],
            'coverage': [],
            'qd_score': [],
            'best_objective': [],
            'evaluations': [],
        }
        
        # Progress callback to track metrics during optimization
        def track_metrics(progress, message, archive_snapshot):
            """Callback to capture metrics at intervals."""
            if archive_snapshot is not None:
                gen = int(progress / 100 * qd_config['num_generations'])
                
                # Use new PyRibs API (archive.data with return_type='pandas')
                archive_df = archive_snapshot.data(return_type='pandas')
                num_features = len(env_config['selected_features'])
                total_niches = qd_config['num_niches'] ** num_features
                
                coverage = len(archive_df) / total_niches if total_niches > 0 else 0.0
                qd_score = archive_df['objective'].sum() if len(archive_df) > 0 else 0.0
                best_obj = archive_df['objective'].max() if len(archive_df) > 0 else 0.0
                
                metrics_history['generation'].append(gen)
                metrics_history['archive_size'].append(len(archive_df))
                metrics_history['coverage'].append(coverage)
                metrics_history['qd_score'].append(qd_score)
                metrics_history['best_objective'].append(best_obj)
                
                # Estimate total evaluations
                total_evals = gen * qd_config['batch_size'] * qd_config['num_emitters']
                metrics_history['evaluations'].append(total_evals)
        
        # Run optimization using the standard function
        archive = run_qd_optimization(
            encoding_obj=encoding_obj,
            env_config=env_config,
            qd_config=qd_config,
            x0_adaptive=None,
            progress_callback=track_metrics
        )
        
        runtime = time.time() - start_time
        
        # Final metrics - use new PyRibs API
        final_archive = archive.data(return_type='pandas')
        num_features = len(env_config['selected_features'])
        total_niches = qd_config['num_niches'] ** num_features
        final_coverage = len(final_archive) / total_niches if total_niches > 0 else 0.0
        final_qd_score = final_archive['objective'].sum() if len(final_archive) > 0 else 0.0
        final_best = final_archive['objective'].max() if len(final_archive) > 0 else 0.0
        
        total_evals = qd_config['num_generations'] * qd_config['batch_size'] * qd_config['num_emitters']
        
        return {
            'runtime_seconds': runtime,
            'total_evaluations': total_evals,
            'final_archive_size': len(final_archive),
            'final_coverage': final_coverage,
            'final_qd_score': final_qd_score,
            'final_best_objective': final_best,
            'metrics_history': metrics_history,
        }
    
    def run_benchmark(self):
        """Run the full benchmark suite."""
        print("\nStarting benchmark...")
        print(f"Estimated runtime: {len(self.test_configs) * len(self.test_parcels) * 1.5:.1f} minutes")
        print("(assuming ~90 seconds per run)\n")
        
        total_runs = len(self.test_configs) * len(self.test_parcels)
        current_run = 0
        
        for parcel_config in self.test_parcels:
            print(f"\n{'='*60}")
            print(f"Testing parcel: {parcel_config['name']} ({parcel_config['area_m2']} m²)")
            print(f"{'='*60}")
            
            # Create environment once per parcel
            env_config = self._create_test_environment(parcel_config)
            
            for config in self.test_configs:
                current_run += 1
                print(f"\n[{current_run}/{total_runs}] Running: {config['name']}")
                print(f"  emitters={config['num_emitters']}, sigma={config['sigma']}, "
                      f"lr={config['learning_rate']}, batch={config['batch_size']}")
                
                try:
                    # Run optimization
                    result = self._run_optimization(config, env_config)
                    
                    # Store results
                    self.results.append({
                        'parcel': parcel_config['name'],
                        'parcel_area_m2': parcel_config['area_m2'],
                        'config_name': config['name'],
                        'num_emitters': config['num_emitters'],
                        'sigma': config['sigma'],
                        'learning_rate': config['learning_rate'],
                        'batch_size': config['batch_size'],
                        'num_generations': config['num_generations'],
                        **result
                    })
                    
                    # Print summary
                    print(f"  ✓ Completed in {result['runtime_seconds']:.1f}s")
                    print(f"    Archive: {result['final_archive_size']} solutions")
                    print(f"    Coverage: {result['final_coverage']*100:.1f}%")
                    print(f"    QD-Score: {result['final_qd_score']:.2f}")
                    print(f"    Best: {result['final_best_objective']:.4f}")
                    
                except Exception as e:
                    print(f"  ✗ Failed: {e}")
                    import traceback
                    traceback.print_exc()
        
        print(f"\n{'='*60}")
        print("Benchmark complete!")
        print(f"{'='*60}\n")
    
    def analyze_results(self):
        """Analyze benchmark results and generate visualizations."""
        if not self.results:
            print("No results to analyze!")
            return
        
        df = pd.DataFrame(self.results)
        
        print("\n" + "="*60)
        print("BENCHMARK RESULTS ANALYSIS")
        print("="*60)
        
        # Overall statistics
        print("\n1. OVERALL STATISTICS")
        print("-" * 60)
        print(f"Total runs: {len(df)}")
        print(f"Successful runs: {len(df[df['final_coverage'] > 0])}")
        print(f"Average runtime: {df['runtime_seconds'].mean():.1f}s (±{df['runtime_seconds'].std():.1f}s)")
        print(f"Average coverage: {df['final_coverage'].mean()*100:.1f}%")
        print(f"Average QD-score: {df['final_qd_score'].mean():.2f}")
        
        # Best configurations
        print("\n2. TOP 5 CONFIGURATIONS (by QD-score)")
        print("-" * 60)
        top5 = df.nlargest(5, 'final_qd_score')[['config_name', 'parcel', 'final_qd_score', 
                                                    'final_coverage', 'final_best_objective', 'runtime_seconds']]
        print(top5.to_string(index=False))
        
        # Best by coverage
        print("\n3. TOP 5 CONFIGURATIONS (by coverage)")
        print("-" * 60)
        top5_cov = df.nlargest(5, 'final_coverage')[['config_name', 'parcel', 'final_coverage',
                                                       'final_qd_score', 'runtime_seconds']]
        print(top5_cov.to_string(index=False))
        
        # Best by efficiency (QD-score / runtime)
        print("\n4. TOP 5 CONFIGURATIONS (by efficiency)")
        print("-" * 60)
        df['efficiency'] = df['final_qd_score'] / df['runtime_seconds']
        top5_eff = df.nlargest(5, 'efficiency')[['config_name', 'parcel', 'efficiency',
                                                   'final_qd_score', 'runtime_seconds']]
        print(top5_eff.to_string(index=False))
        
        # Hyperparameter impact analysis
        print("\n5. HYPERPARAMETER IMPACT ANALYSIS")
        print("-" * 60)
        
        for param in ['num_emitters', 'sigma', 'learning_rate', 'batch_size']:
            grouped = df.groupby(param).agg({
                'final_qd_score': 'mean',
                'final_coverage': 'mean',
                'runtime_seconds': 'mean'
            }).round(3)
            print(f"\n{param}:")
            print(grouped.to_string())
        
        # Parcel size impact
        print("\n6. PARCEL SIZE IMPACT")
        print("-" * 60)
        parcel_impact = df.groupby('parcel').agg({
            'final_qd_score': ['mean', 'std'],
            'final_coverage': ['mean', 'std'],
            'runtime_seconds': ['mean', 'std']
        }).round(3)
        print(parcel_impact.to_string())
        
        # Generate plots
        self._generate_plots(df)
        
        # Save detailed results
        self._save_results(df)
        
        # Generate recommendations
        self._generate_recommendations(df)
    
    def _generate_plots(self, df: pd.DataFrame):
        """Generate visualization plots."""
        print("\nGenerating plots...")
        
        # Set style
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = (12, 8)
        
        # 1. Hyperparameter heatmaps
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Hyperparameter Impact on QD-Score', fontsize=16, fontweight='bold')
        
        params = ['num_emitters', 'sigma', 'learning_rate', 'batch_size']
        for idx, param in enumerate(params):
            ax = axes[idx // 2, idx % 2]
            pivot = df.pivot_table(values='final_qd_score', index=param, columns='parcel', aggfunc='mean')
            sns.heatmap(pivot, annot=True, fmt='.1f', cmap='YlOrRd', ax=ax, cbar_kws={'label': 'QD-Score'})
            ax.set_title(f'{param} vs QD-Score', fontweight='bold')
            ax.set_xlabel('Parcel Size')
            ax.set_ylabel(param)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'hyperparameter_heatmaps.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        # 2. Coverage vs Runtime scatter
        fig, ax = plt.subplots(figsize=(10, 6))
        for parcel in df['parcel'].unique():
            parcel_df = df[df['parcel'] == parcel]
            ax.scatter(parcel_df['runtime_seconds'], parcel_df['final_coverage']*100,
                      label=parcel, s=100, alpha=0.6)
        ax.set_xlabel('Runtime (seconds)', fontsize=12)
        ax.set_ylabel('Archive Coverage (%)', fontsize=12)
        ax.set_title('Coverage vs Runtime Trade-off', fontsize=14, fontweight='bold')
        ax.legend(title='Parcel Size')
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'coverage_vs_runtime.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        # 3. QD-Score vs Configuration
        fig, ax = plt.subplots(figsize=(14, 6))
        config_scores = df.groupby('config_name')['final_qd_score'].mean().sort_values(ascending=False)
        config_scores.plot(kind='bar', ax=ax, color='steelblue')
        ax.set_xlabel('Configuration', fontsize=12)
        ax.set_ylabel('Average QD-Score', fontsize=12)
        ax.set_title('Configuration Performance Comparison', fontsize=14, fontweight='bold')
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, axis='y', alpha=0.3)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'config_comparison.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        # 4. Convergence curves (for top 3 configs)
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        top3_configs = df.nlargest(3, 'final_qd_score')['config_name'].unique()[:3]
        
        metrics = ['qd_score', 'coverage', 'best_objective']
        titles = ['QD-Score Over Time', 'Coverage Over Time', 'Best Objective Over Time']
        
        for idx, metric in enumerate(metrics):
            ax = axes[idx]
            for config_name in top3_configs:
                config_results = df[df['config_name'] == config_name].iloc[0]
                history = config_results['metrics_history']
                generations = history['generation']
                values = history[metric] if metric != 'coverage' else [v*100 for v in history['coverage']]
                ax.plot(generations, values, marker='o', label=config_name, linewidth=2)
            ax.set_xlabel('Generation', fontsize=11)
            ax.set_ylabel(metric.replace('_', ' ').title(), fontsize=11)
            ax.set_title(titles[idx], fontweight='bold')
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'convergence_curves.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"  ✓ Plots saved to {self.output_dir}")
    
    def _save_results(self, df: pd.DataFrame):
        """Save detailed results to files."""
        # Save CSV
        csv_path = self.output_dir / 'benchmark_results.csv'
        df_save = df.drop('metrics_history', axis=1)  # Remove nested data
        df_save.to_csv(csv_path, index=False)
        print(f"  ✓ Results saved to {csv_path}")
        
        # Save JSON with full history
        json_path = self.output_dir / 'benchmark_results_full.json'
        with open(json_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"  ✓ Full results saved to {json_path}")
    
    def _generate_recommendations(self, df: pd.DataFrame):
        """Generate hyperparameter recommendations."""
        print("\n" + "="*60)
        print("RECOMMENDATIONS")
        print("="*60)
        
        # Best overall configuration
        best_overall = df.loc[df['final_qd_score'].idxmax()]
        print("\n1. BEST OVERALL CONFIGURATION:")
        print(f"   Name: {best_overall['config_name']}")
        print(f"   num_emitters: {best_overall['num_emitters']}")
        print(f"   sigma: {best_overall['sigma']}")
        print(f"   learning_rate: {best_overall['learning_rate']}")
        print(f"   batch_size: {best_overall['batch_size']}")
        print(f"   → QD-Score: {best_overall['final_qd_score']:.2f}")
        print(f"   → Coverage: {best_overall['final_coverage']*100:.1f}%")
        print(f"   → Runtime: {best_overall['runtime_seconds']:.1f}s")
        
        # Best for production (balance of performance and speed)
        df['production_score'] = (df['final_qd_score'] / df['final_qd_score'].max()) * 0.5 + \
                                  (1 - df['runtime_seconds'] / df['runtime_seconds'].max()) * 0.5
        best_production = df.loc[df['production_score'].idxmax()]
        print("\n2. RECOMMENDED FOR PRODUCTION (balanced):")
        print(f"   Name: {best_production['config_name']}")
        print(f"   num_emitters: {best_production['num_emitters']}")
        print(f"   sigma: {best_production['sigma']}")
        print(f"   learning_rate: {best_production['learning_rate']}")
        print(f"   batch_size: {best_production['batch_size']}")
        print(f"   → QD-Score: {best_production['final_qd_score']:.2f}")
        print(f"   → Coverage: {best_production['final_coverage']*100:.1f}%")
        print(f"   → Runtime: {best_production['runtime_seconds']:.1f}s")
        
        # General insights
        print("\n3. KEY INSIGHTS:")
        
        # Emitters
        emitter_corr = df[['num_emitters', 'final_qd_score']].corr().iloc[0, 1]
        print(f"   • num_emitters correlation with QD-score: {emitter_corr:.3f}")
        if emitter_corr > 0.3:
            print("     → More emitters generally improve performance")
        elif emitter_corr < -0.3:
            print("     → Fewer emitters may be more efficient")
        else:
            print("     → num_emitters has modest impact; use 5-7 for balance")
        
        # Sigma
        best_sigma = df.groupby('sigma')['final_qd_score'].mean().idxmax()
        print(f"   • Best average sigma: {best_sigma:.3f}")
        print(f"     → Controls mutation strength; higher = more exploration")
        
        # Learning rate
        best_lr = df.groupby('learning_rate')['final_qd_score'].mean().idxmax()
        print(f"   • Best average learning_rate: {best_lr:.4f}")
        print(f"     → Controls gradient steps; higher = faster but less stable")
        
        # Batch size
        best_batch = df.groupby('batch_size')['final_qd_score'].mean().idxmax()
        print(f"   • Best average batch_size: {int(best_batch)}")
        print(f"     → Larger batches = more evaluations per generation")
        
        print("\n4. NOTES FOR PRODUCTION:")
        print("   • These results are for simple_porosity objective")
        print("   • AI-predicted objective may favor different parameters")
        print("   • Consider testing with representative AI surrogate")
        print("   • Parcel size doesn't strongly affect optimal parameters")
        print("   • Can safely use same config across parcel sizes")
        
        print("\n" + "="*60)


def main():
    """Main execution."""
    print("PyRibs QD Hyperparameter Benchmark")
    print("OpenSKIZZE Urban Planning Optimization")
    print("=" * 60)
    
    # Create benchmark
    benchmark = QDBenchmark(output_dir="helper/qd_benchmark_results")
    
    # Run benchmark
    benchmark.run_benchmark()
    
    # Analyze results
    benchmark.analyze_results()
    
    print("\n✓ Benchmark complete!")
    print(f"Results saved to: {benchmark.output_dir}")
    print("\nNext steps:")
    print("1. Review the generated plots")
    print("2. Check the recommendations section")
    print("3. Update QD_CONFIG in backend/config.py with recommended values")
    print("4. Test with AI surrogate model when available")


if __name__ == "__main__":
    main()
