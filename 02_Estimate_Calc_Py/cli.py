"""
Command-Line Interface (CLI) for NSO Estimate Calculation Pipeline.
"""
import argparse
import sys
import os

# Add parent directory to path to enable package execution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.conversion_factors import ConversionFactors
from pipeline import NSOEstimatePipeline
from loaders.access_loader import AccessDataLoader
from loaders.tabular_loader import TabularDataLoader
from loaders.mock_loader import MockDataLoader

def parse_args():
    parser = argparse.ArgumentParser(
        description="NSO Crop Yield Rate (Kg/ha) and %SE Estimation Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Input data source options
    group = parser.add_argument_group("Data Source")
    group.add_argument("--db-path", type=str, default=None,
                       help="Path to Microsoft Access database (.accdb / .mdb)")
    group.add_argument("--table-name", type=str, default="total estimate",
                       help="Table name within Access database")
    group.add_argument("--experiments-csv", type=str, default=None,
                       help="Path to CSV/Excel file containing experiment records")
    group.add_argument("--areas-csv", type=str, default=None,
                       help="Path to CSV/Excel file containing district crop areas")
    group.add_argument("--mock", action="store_true",
                       help="Run on synthetic mock data for demonstration")

    # Conversion factors
    cfg_group = parser.add_argument_group("Conversion Factors")
    cfg_group.add_argument("--driage-ratio", type=float, default=1.0,
                           help="Driage ratio (dry weight / green weight)")
    cfg_group.add_argument("--recovery-ratio", type=float, default=1.0,
                           help="Recovery ratio")
    cfg_group.add_argument("--conversion-factor", type=float, default=1.0,
                           help="Plot size to hectare conversion factor (cf)")

    # Survey criteria filters
    filt_group = parser.add_argument_group("Survey Filters")
    filt_group.add_argument("--state", type=str, default=None, help="State code (e.g. 33)")
    filt_group.add_argument("--season", type=str, default=None, help="Season code (e.g. 4)")
    filt_group.add_argument("--crop", type=str, default=None, help="Crop code (e.g. 1611)")
    filt_group.add_argument("--sample", type=str, default=None, help="Sample code ('1'=Central, '2'=State)")
    filt_group.add_argument("--conversion-type", type=int, default=1, choices=[1, 2],
                            help="1 = Specific Sample, 2 = Combined Sample")

    # Output options
    out_group = parser.add_argument_group("Output Options")
    out_group.add_argument("--export-csv", type=str, default=None,
                           help="File path to save district results CSV")
    out_group.add_argument("--export-json", type=str, default=None,
                           help="File path to save state results JSON")

    return parser.parse_args()

def main():
    args = parse_args()

    factors = ConversionFactors(
        driage_ratio=args.driage_ratio,
        recovery_ratio=args.recovery_ratio,
        conversion_factor=args.conversion_factor
    )

    if args.mock:
        print("[INFO] Running on synthetic mock data...")
        loader = MockDataLoader()
    elif args.db_path:
        print(f"[INFO] Connecting to Access database: {args.db_path}")
        loader = AccessDataLoader(db_path=args.db_path, table_name=args.table_name)
    elif args.experiments_csv:
        print(f"[INFO] Loading from CSV/Excel: {args.experiments_csv}")
        loader = TabularDataLoader(experiments_source=args.experiments_csv, areas_source=args.areas_csv)
    else:
        print("[INFO] No data source specified. Defaulting to mock data for demonstration.")
        loader = MockDataLoader()

    pipeline = NSOEstimatePipeline(loader=loader, conversion_factors=factors)
    pipeline.run(
        state_code=args.state,
        season_code=args.season,
        crop_code=args.crop,
        sample_type=args.sample,
        conversion_type=args.conversion_type
    )

    pipeline.print_summary()

    if args.export_csv:
        pipeline.export_csv(args.export_csv)
        print(f"[SUCCESS] Exported district estimates to: {args.export_csv}")

    if args.export_json:
        pipeline.export_json(args.export_json)
        print(f"[SUCCESS] Exported state estimate to: {args.export_json}")

if __name__ == '__main__':
    main()
