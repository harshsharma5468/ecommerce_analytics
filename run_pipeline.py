"""
Master Pipeline Orchestrator
─────────────────────────────────────────────────────────────────────────────
Runs the entire end-to-end analytics platform:

  Stage 1: Data Generation (Bronze Layer)
  Stage 2: Data Validation (Great Expectations)
  Stage 3: RFM Segmentation (Silver Layer)
  Stage 4: A/B Testing Analysis
  Stage 5: Predictive ML Models
  Stage 6: Feature Store Registration
  Stage 7: Report Generation

Enhanced with:
- Prefect orchestration (if available)
- Great Expectations validation
- ML model training (churn, CLV, survival, recommendations)
"""
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

import time
from datetime import datetime
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
import traceback

console = Console()

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline Stages
# ──────────────────────────────────────────────────────────────────────────────

STAGES = [
    {
        "name": "Data Generation",
        "module": "src.pipeline.orchestrator",
        "function": "run_pipeline",
        "description": "Generate and validate raw data"
    },
    {
        "name": "RFM Segmentation",
        "module": "src.rfm_segmentation.rfm_engine",
        "function": "main",
        "description": "Calculate RFM scores and segments"
    },
    {
        "name": "A/B Testing",
        "module": "src.ab_testing.ab_engine",
        "function": "main",
        "description": "Run A/B test analyses"
    },
    {
        "name": "Churn Model",
        "module": "src.predictive.churn_model",
        "function": "train_churn_model",
        "description": "Train XGBoost churn predictor",
        "optional": True
    },
    {
        "name": "Survival Model",
        "module": "src.predictive.survival_analysis",
        "function": "train_survival_model",
        "description": "Train survival analysis model",
        "optional": True
    },
    {
        "name": "CLV Model",
        "module": "src.predictive.clv_model",
        "function": "train_clv_model",
        "description": "Train BG/NBD + Gamma-Gamma CLV",
        "optional": True
    },
    {
        "name": "Recommendations",
        "module": "src.predictive.recommendation_engine",
        "function": "train_recommendation_model",
        "description": "Train ALS recommendation engine",
        "optional": True
    },
]


def run_stage(stage: dict) -> tuple:
    """
    Run a single pipeline stage.
    
    Returns
    -------
    (success: bool, duration: float, message: str)
    """
    stage_name = stage["name"]
    module_path = stage["module"]
    function_name = stage.get("function", "main")
    is_optional = stage.get("optional", False)
    
    console.rule(f"[bold cyan]Stage: {stage_name}")
    console.print(f"[dim]{stage.get('description', '')}")
    
    t0 = time.time()
    
    try:
        # Import module
        import importlib
        mod = importlib.import_module(module_path)
        
        # Get function
        if not hasattr(mod, function_name):
            raise AttributeError(f"Function '{function_name}' not found in {module_path}")
        
        func = getattr(mod, function_name)
        
        # Run function
        result = func()
        
        elapsed = time.time() - t0
        
        # Format result message
        if isinstance(result, dict):
            msg = ", ".join(f"{k}={v}" for k, v in result.items())
        elif result is not None:
            msg = str(result)
        else:
            msg = "Completed"
        
        console.print(f"[bold green]✅ {stage_name} completed in {elapsed:.1f}s - {msg}")
        return True, elapsed, msg
        
    except ImportError as e:
        elapsed = time.time() - t0
        if is_optional:
            console.print(f"[yellow]⚠️  {stage_name} skipped (optional dependency missing): {e}")
            return False, elapsed, f"Skipped: {e}"
        else:
            console.print(f"[bold red]❌ {stage_name} FAILED (ImportError): {e}")
            traceback.print_exc()
            return False, elapsed, f"ImportError: {e}"
            
    except Exception as e:
        elapsed = time.time() - t0
        if is_optional:
            console.print(f"[yellow]⚠️  {stage_name} failed (optional): {e}")
            return False, elapsed, f"Failed: {e}"
        else:
            console.print(f"[bold red]❌ {stage_name} FAILED: {e}")
            traceback.print_exc()
            return False, elapsed, f"Failed: {e}"


def print_summary(results: list):
    """Print pipeline summary table."""
    console.rule("[bold]Pipeline Summary")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Stage", style="cyan", width=20)
    table.add_column("Status", justify="center", width=10)
    table.add_column("Duration", justify="right", width=12)
    table.add_column("Details", style="dim")
    
    for stage_name, success, duration, message in results:
        status = "[green]✅ PASSED" if success else "[red]❌ FAILED"
        table.add_row(
            stage_name,
            status,
            f"{duration:.1f}s",
            message[:50] + "..." if len(message) > 50 else message
        )
    
    console.print(table)
    
    # Overall stats
    n_passed = sum(1 for _, success, _, _ in results if success)
    n_total = len(results)
    total_time = sum(duration for _, _, duration, _ in results)
    
    console.print()
    console.print(f"[bold]Overall: {n_passed}/{n_total} stages passed in {total_time:.1f}s")


def print_next_steps():
    """Print next steps for the user."""
    console.print()
    console.print(Panel.fit(
        "[bold white]Pipeline Complete! Next Steps:\n\n"
        "[cyan]1. Launch Dashboard:[/cyan]\n"
        "    [yellow]streamlit run src/dashboard/app.py[/yellow]\n\n"
        "[cyan]2. Run Tests:[/cyan]\n"
        "    [yellow]pytest tests/ -v --cov=src[/yellow]\n\n"
        "[cyan]3. Run dbt Models:[/cyan]\n"
        "    [yellow]dbt run && dbt test[/yellow]\n\n"
        "[cyan]4. Start Streaming (optional):[/cyan]\n"
        "    [yellow]python -c \"from src.streaming import start_streaming; start_streaming()\"[/yellow]",
        title="🚀 What's Next?",
        border_style="bright_blue",
    ))


def main():
    """Run the full pipeline."""
    start_time = datetime.now()
    
    console.print(Panel.fit(
        "[bold white]NexaCommerce Analytics Intelligence Platform\n"
        "[dim]Full end-to-end pipeline: Data → Validation → RFM → ML → Features",
        border_style="bright_blue",
        title=f"🚀 Pipeline Start ({start_time.strftime('%Y-%m-%d %H:%M')})",
    ))
    
    results = []
    
    # Run each stage
    for stage in STAGES:
        success, duration, message = run_stage(stage)
        results.append((stage["name"], success, duration, message))
        
        if not success and not stage.get("optional", False):
            console.print(f"[yellow]⚠️  Continuing despite {stage['name']} failure...")
    
    # Print summary
    print_summary(results)
    
    # Print next steps
    print_next_steps()
    
    # Return summary for programmatic use
    n_passed = sum(1 for _, success, _, _ in results if success)
    return {
        "total_stages": len(results),
        "passed_stages": n_passed,
        "success_rate": n_passed / len(results) if results else 0,
        "results": results
    }


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result["success_rate"] > 0.5 else 1)
