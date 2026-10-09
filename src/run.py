"""Command-line entry point for the complete case study."""
import argparse
from .analysis import load_data, fit_analysis
from .reporting import export_results

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True, help='Path to original annual SingStat CSV')
    parser.add_argument('--output', default='outputs', help='Generated tables and figures directory')
    args = parser.parse_args()
    result = fit_analysis(load_data(args.data))
    export_results(result, args.output)
    print(result['metrics'].round(4).to_string(index=False))
    print(f'Outputs written to {args.output}')

if __name__ == '__main__':
    main()
