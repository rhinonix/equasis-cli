#!/usr/bin/env python3
"""
Equasis CLI Tool - Main CLI application
Command-line interface for accessing Equasis maritime data
"""

import argparse
import os
import logging

from .client import EquasisClient
from .formatter import OutputFormatter
from .banner import display_banner, display_compact_info, display_error_banner, display_success_summary, check_credentials
from .credentials import get_credential_manager
from ._version import __version__

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Main CLI entry point - supports both interactive and traditional modes"""
    import sys

    # Check if no arguments provided - start interactive mode
    if len(sys.argv) == 1:
        # No arguments - start interactive mode
        try:
            from .interactive import InteractiveShell
            shell = InteractiveShell()
            shell.start()
            return
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            return
        except ImportError as e:
            print(f"Error starting interactive mode: {e}")
            print("Falling back to traditional CLI mode...")
        except Exception as e:
            print(f"Unexpected error in interactive mode: {e}")
            print("Falling back to traditional CLI mode...")

    # Traditional CLI mode
    traditional_main()


def traditional_main():
    """Traditional CLI mode with argparse"""
    parser = argparse.ArgumentParser(description='Equasis CLI Tool for Maritime Data')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('--username', help='Equasis username (or set EQUASIS_USERNAME env var)')
    parser.add_argument('--password', help='Equasis password (or set EQUASIS_PASSWORD env var)')
    parser.add_argument('--output', choices=['table', 'json', 'csv'], default='table', help='Output format')
    parser.add_argument('--output-file', help='Output file path (optional)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging and save HTML responses')
    parser.add_argument('--no-banner', action='store_true', help='Skip startup banner display')
    parser.add_argument('--quiet', action='store_true', help='Minimal output mode')
    parser.add_argument('--interactive', action='store_true', help='Start interactive mode')
    parser.add_argument('--batch', action='store_true', help='Enable batch processing mode')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Configure command
    configure_parser = subparsers.add_parser('configure', help='Set up credentials and configuration')
    configure_group = configure_parser.add_mutually_exclusive_group()
    configure_group.add_argument('--setup', action='store_true', help='Interactively set up credentials')
    configure_group.add_argument('--clear', action='store_true', help='Clear stored credentials')
    configure_group.add_argument('--show', action='store_true', help='Show credential sources (for debugging)')

    # Vessel command
    vessel_parser = subparsers.add_parser('vessel', help='Get vessel information')
    vessel_parser.add_argument('--imo', nargs='+', help='IMO number(s) - can specify multiple')
    vessel_parser.add_argument('--imo-file', help='File containing IMO numbers (one per line)')
    vessel_parser.add_argument('--continue-on-error', action='store_true',
                              help='Continue processing on errors (batch mode)')
    vessel_parser.add_argument('--progress', action='store_true',
                              help='Show progress indicators (batch mode)')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search vessels by name')
    search_parser.add_argument('--name', required=True, help='Vessel name')

    # Fleet command
    fleet_parser = subparsers.add_parser('fleet', help='Get fleet information')
    fleet_parser.add_argument('--company', nargs='+', help='Company name(s) or identifier(s) - can specify multiple')
    fleet_parser.add_argument('--company-file', help='File containing company names (one per line)')
    fleet_parser.add_argument('--continue-on-error', action='store_true',
                              help='Continue processing on errors (batch mode)')
    fleet_parser.add_argument('--progress', action='store_true',
                              help='Show progress indicators (batch mode)')

    args = parser.parse_args()

    # Check for interactive flag
    if args.interactive:
        try:
            from .interactive import InteractiveShell
            shell = InteractiveShell()
            shell.start()
            return
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            return
        except Exception as e:
            print(f"Error starting interactive mode: {e}")
            return

    # Set logging level based on debug flag
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logger.info("Debug mode enabled")
    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Handle help display first
    if not args.command:
        # Show banner for help display
        if not args.no_banner and not args.quiet:
            display_banner()
        parser.print_help()
        return

    # Handle configure command
    if args.command == 'configure':
        credential_manager = get_credential_manager()

        if args.setup:
            success = credential_manager.interactive_setup()
            return
        elif args.clear:
            success = credential_manager.clear_credentials()
            if success:
                print("✓ Stored credentials cleared successfully")
            else:
                print("✗ Failed to clear credentials")
            return
        elif args.show:
            sources = credential_manager.get_credential_sources()
            print("\n=== Credential Sources ===")
            print(f"Environment Variables:")
            print(f"  EQUASIS_USERNAME: {'✓ set' if sources['environment_variables']['username'] else '✗ not set'}")
            print(f"  EQUASIS_PASSWORD: {'✓ set' if sources['environment_variables']['password'] else '✗ not set'}")
            print(f"\nConfig File: {sources['config_file']['path']}")
            print(f"  File exists: {'✓' if sources['config_file']['exists'] else '✗'}")
            print(f"  Has credentials: {'✓' if sources['config_file']['has_credentials'] else '✗'}")
            print(f"\nConfig Directory: {sources['config_directory']['path']}")
            print(f"  Directory exists: {'✓' if sources['config_directory']['exists'] else '✗'}")
            return
        else:
            # No specific action, show help
            configure_parser.print_help()
            return

    # Get credentials using new credential manager
    credential_manager = get_credential_manager()
    username, password = credential_manager.get_credentials(args.username, args.password)

    if not username or not password:
        print()
        display_error_banner("Authentication",
                           "No valid credentials found")
        print("Available credential methods:")
        print("  1. Run 'equasis configure --setup' to store credentials securely")
        print("  2. Set environment variables: EQUASIS_USERNAME and EQUASIS_PASSWORD")
        print("  3. Use command line flags: --username and --password")
        print()
        print("For more information: equasis configure --show")
        return

    # Display banner after credential validation (for actual commands)
    if not args.no_banner and not args.quiet:
        display_banner()
    elif not args.quiet:
        display_compact_info()

    # Initialize client
    client = EquasisClient(username, password)
    formatter = OutputFormatter()

    try:
        if args.command == 'vessel':
            # Check if batch mode (multiple IMOs or file input)
            imo_list = []

            # Handle IMO file input
            if hasattr(args, 'imo_file') and args.imo_file:
                try:
                    with open(args.imo_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            # Skip empty lines and comments
                            if line and not line.startswith('#'):
                                imo_list.append(line)
                except FileNotFoundError:
                    display_error_banner("File Error", f"File not found: {args.imo_file}")
                    return
                except Exception as e:
                    display_error_banner("File Error", f"Error reading file: {e}")
                    return
            # Handle direct IMO input
            elif hasattr(args, 'imo') and args.imo:
                imo_list = args.imo if isinstance(args.imo, list) else [args.imo]
            else:
                display_error_banner("Input Error", "Either --imo or --imo-file is required")
                return

            # Check if batch mode (multiple IMOs)
            if len(imo_list) > 1:
                # Batch processing
                if not args.quiet:
                    print(f"Processing {len(imo_list)} vessels...\n")

                # Progress callback for batch mode
                def progress_callback(current, total, imo, status):
                    if args.progress and not args.quiet:
                        if status == "processing":
                            print(f"[{current}/{total}] Processing IMO {imo}...")
                        elif status == "success":
                            print(f"[{current}/{total}] ✓ IMO {imo} retrieved")
                        elif status == "not_found":
                            print(f"[{current}/{total}] ⚠ IMO {imo} not found")
                        elif status == "error":
                            print(f"[{current}/{total}] ✗ IMO {imo} error")

                # Process batch
                results = client.search_vessels_by_imo_batch(
                    imo_list,
                    progress_callback=progress_callback if args.progress else None,
                    stop_on_error=not getattr(args, 'continue_on_error', True)
                )

                # Format and output results
                output = formatter.format_batch_vessel_info(results, args.output)
                if args.output_file:
                    with open(args.output_file, 'w') as f:
                        f.write(output)
                    if not args.quiet:
                        successful = sum(1 for r in results if r.success)
                        display_success_summary("Batch Processing",
                            f"Processed {len(results)} vessels ({successful} successful), saved to {args.output_file}")
                else:
                    print(output)
                    if not args.quiet:
                        successful = sum(1 for r in results if r.success)
                        display_success_summary("Batch Processing",
                            f"Processed {len(results)} vessels ({successful} successful)")
            else:
                # Single vessel processing (existing logic)
                vessel = client.search_vessel_by_imo(imo_list[0])
                if vessel:
                    output = formatter.format_vessel_info(vessel, args.output)
                    if args.output_file:
                        with open(args.output_file, 'w') as f:
                            f.write(output)
                        if not args.quiet:
                            display_success_summary("Vessel Lookup", f"Data saved to {args.output_file}")
                    else:
                        print(output)
                        if not args.quiet:
                            display_success_summary("Vessel Lookup", f"Comprehensive data retrieved for IMO {imo_list[0]}")
                else:
                    display_error_banner("Vessel Not Found", f"No vessel found with IMO: {imo_list[0]}")

        elif args.command == 'search':
            vessels = client.search_vessel_by_name(args.name)
            if vessels:
                output = formatter.format_simple_vessel_list(vessels, args.output)
                if args.output_file:
                    with open(args.output_file, 'w') as f:
                        f.write(output)
                    if not args.quiet:
                        display_success_summary("Vessel Search", f"Results saved to {args.output_file}")
                else:
                    print(output)
                    if not args.quiet:
                        display_success_summary("Vessel Search", f"Found {len(vessels)} vessel(s) matching '{args.name}'")
            else:
                display_error_banner("Search Results", f"No vessels found with name: {args.name}")

        elif args.command == 'fleet':
            # Check if batch mode (multiple companies or file input)
            company_list = []

            # Handle company file input
            if hasattr(args, 'company_file') and args.company_file:
                try:
                    with open(args.company_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            # Skip empty lines and comments
                            if line and not line.startswith('#'):
                                company_list.append(line)
                except FileNotFoundError:
                    display_error_banner("File Error", f"File not found: {args.company_file}")
                    return
                except Exception as e:
                    display_error_banner("File Error", f"Error reading file: {e}")
                    return
            # Handle direct company input
            elif hasattr(args, 'company') and args.company:
                company_list = args.company if isinstance(args.company, list) else [args.company]
            else:
                display_error_banner("Input Error", "Either --company or --company-file is required")
                return

            # Check if batch mode (multiple companies)
            if len(company_list) > 1:
                # Batch processing
                if not args.quiet:
                    print(f"Processing {len(company_list)} companies...\n")

                # Progress callback for batch mode
                def progress_callback(current, total, company, status):
                    if args.progress and not args.quiet:
                        if status == "processing":
                            print(f"[{current}/{total}] Processing company {company}...")
                        elif status == "success":
                            print(f"[{current}/{total}] ✓ Company {company} retrieved")
                        elif status == "not_found":
                            print(f"[{current}/{total}] ⚠ Company {company} not found")
                        elif status == "error":
                            print(f"[{current}/{total}] ✗ Company {company} error")

                # Process batch
                results = client.search_companies_batch(
                    company_list,
                    progress_callback=progress_callback if args.progress else None,
                    stop_on_error=not getattr(args, 'continue_on_error', True)
                )

                # Format and output results
                output = formatter.format_batch_fleet_info(results, args.output)
                if args.output_file:
                    with open(args.output_file, 'w') as f:
                        f.write(output)
                    if not args.quiet:
                        successful = sum(1 for r in results if r.success)
                        total_vessels = sum(r.fleet_data.total_vessels for r in results if r.success and r.fleet_data)
                        display_success_summary("Company Batch Processing",
                            f"Processed {len(results)} companies ({successful} successful, {total_vessels} vessels), saved to {args.output_file}")
                else:
                    print(output)
                    if not args.quiet:
                        successful = sum(1 for r in results if r.success)
                        total_vessels = sum(r.fleet_data.total_vessels for r in results if r.success and r.fleet_data)
                        display_success_summary("Company Batch Processing",
                            f"Processed {len(results)} companies ({successful} successful, {total_vessels} vessels)")
            else:
                # Single company processing (existing logic)
                fleet = client.get_fleet_info(company_list[0])
                if fleet:
                    output = formatter.format_fleet_info(fleet, args.output)
                    if args.output_file:
                        with open(args.output_file, 'w') as f:
                            f.write(output)
                        if not args.quiet:
                            display_success_summary("Fleet Lookup", f"Fleet data saved to {args.output_file}")
                    else:
                        print(output)
                        if not args.quiet:
                            display_success_summary("Fleet Lookup", f"Fleet data retrieved for {company_list[0]}")
                else:
                    display_error_banner("Fleet Not Found", f"No fleet found for company: {company_list[0]}")

    except KeyboardInterrupt:
        if not args.quiet:
            print("\nOperation cancelled by user")
        else:
            print("\nCancelled")
    except Exception as e:
        display_error_banner("Unexpected Error", f"An unexpected error occurred: {str(e)}")
        if args.debug:
            import traceback
            print("Debug traceback:")
            traceback.print_exc()


if __name__ == '__main__':
    main()
