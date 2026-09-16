#!/usr/bin/env python3
"""
Output Formatter - Handles different output formats for vessel, fleet, and search data
"""

import json
from typing import List
from dataclasses import asdict
from datetime import datetime

from .parser import EquasisVesselData
from .client import SimpleVesselInfo, FleetInfo, BatchResult, BatchSummary, CompanyBatchResult, CompanyBatchSummary


class OutputFormatter:
    """Handle different output formats"""

    @staticmethod
    def format_vessel_info(vessel_data: EquasisVesselData, output_format: str = 'table', detail_level: str = 'summary'):
        """Format comprehensive vessel information"""
        if output_format == 'json':
            return json.dumps({
                'basic_info': asdict(vessel_data.basic_info),
                'overview': vessel_data.overview,
                'management': [asdict(c) for c in vessel_data.management],
                'classification': [asdict(c) for c in vessel_data.classification],
                'geographical': [asdict(g) for g in vessel_data.geographical],
                'inspections': [asdict(i) for i in vessel_data.inspections],
                'historical_names': [asdict(h) for h in vessel_data.historical_names],
                'historical_flags': [asdict(h) for h in vessel_data.historical_flags],
                'historical_companies': [asdict(h) for h in vessel_data.historical_companies]
            }, indent=2)
        elif output_format == 'csv':
            # Basic CSV format for compatibility
            basic = vessel_data.basic_info
            return f"{basic.imo},{basic.name},{basic.flag},{basic.vessel_type or ''},{basic.dwt or ''},{basic.gross_tonnage or ''},{basic.year_built or ''}"
        else:  # table format
            return OutputFormatter._format_comprehensive_table(vessel_data, detail_level)

    @staticmethod
    def _format_comprehensive_table(vessel_data: EquasisVesselData, detail_level: str = 'summary'):
        """Format comprehensive vessel data as a table"""
        basic = vessel_data.basic_info
        output = f"""
Vessel Information (Comprehensive):
===================================
IMO Number:    {basic.imo}
Name:          {basic.name}
Flag:          {basic.flag} ({basic.flag_code or 'N/A'})
Call Sign:     {basic.call_sign or 'N/A'}
MMSI:          {basic.mmsi or 'N/A'}
Type:          {basic.vessel_type or 'N/A'}
Gross Tonnage: {basic.gross_tonnage or 'N/A'}
DWT:           {basic.dwt or 'N/A'}
Year Built:    {basic.year_built or 'N/A'}
Status:        {basic.status or 'N/A'}
Last Update:   {basic.last_update or 'N/A'}
"""

        # Add overview section
        if vessel_data.overview:
            output += "\nOverview:\n" + "-" * 9 + "\n"
            for key, value in vessel_data.overview.items():
                formatted_key = key.replace('_', ' ').title()
                output += f"{formatted_key}: {value}\n"

        # Add management companies
        if vessel_data.management:
            output += f"\nManagement Companies ({len(vessel_data.management)}):\n" + "-" * 30 + "\n"
            for company in vessel_data.management:
                output += f"• {company.name} ({company.role})\n"
                if company.date_effect and detail_level == 'detailed':
                    output += f"  Since: {company.date_effect}\n"

        # Add classification
        if vessel_data.classification:
            output += f"\nClassification ({len(vessel_data.classification)}):\n" + "-" * 16 + "\n"
            for cls in vessel_data.classification:
                output += f"• {cls.society} - {cls.status}\n"
                if cls.date_effect and detail_level == 'detailed':
                    output += f"  {cls.date_effect}\n"

        # Add recent inspections
        if vessel_data.inspections:
            recent_count = min(3, len(vessel_data.inspections)) if detail_level == 'summary' else len(vessel_data.inspections)
            output += f"\nRecent PSC Inspections ({recent_count} of {len(vessel_data.inspections)}):\n" + "-" * 35 + "\n"
            for inspection in vessel_data.inspections[:recent_count]:
                output += f"• {inspection.date}: {inspection.psc_organization}\n"
                if inspection.detention != 'No detention':
                    output += f"  ⚠️  Detention: {inspection.detention}\n"

        # Add historical data summary
        if vessel_data.historical_names and detail_level == 'summary':
            output += f"\nHistorical Names ({len(vessel_data.historical_names)} total):\n" + "-" * 22 + "\n"
            for name in vessel_data.historical_names[:3]:
                output += f"• {name.name} ({name.date_effect})\n"
            if len(vessel_data.historical_names) > 3:
                output += f"  ... and {len(vessel_data.historical_names) - 3} more\n"

        # Detailed historical data
        elif vessel_data.historical_names and detail_level == 'detailed':
            output += f"\nHistorical Names ({len(vessel_data.historical_names)}):\n" + "-" * 18 + "\n"
            for name in vessel_data.historical_names:
                output += f"• {name.name} (since {name.date_effect})\n"

        if vessel_data.historical_flags and detail_level == 'detailed':
            output += f"\nHistorical Flags ({len(vessel_data.historical_flags)}):\n" + "-" * 18 + "\n"
            for flag in vessel_data.historical_flags:
                output += f"• {flag.flag} (since {flag.date_effect})\n"

        return output

    @staticmethod
    def format_simple_vessel_list(vessels: List[SimpleVesselInfo], output_format: str = 'table'):
        """Format simple vessel list for search results"""
        if output_format == 'json':
            return json.dumps([vessel.__dict__ for vessel in vessels], indent=2)
        elif output_format == 'csv':
            lines = ['IMO,Name,Flag,Type,DWT,GRT,YearBuilt,Status']
            for vessel in vessels:
                lines.append(f"{vessel.imo},{vessel.name},{vessel.flag},{vessel.vessel_type},{vessel.dwt or ''},{vessel.grt or ''},{vessel.year_built or ''},{vessel.status or ''}")
            return '\n'.join(lines)
        else:  # table format
            output = f"\nSearch Results ({len(vessels)} vessels found):\n" + "=" * 40 + "\n"
            for vessel in vessels:
                output += f"IMO: {vessel.imo} | Name: {vessel.name} | Flag: {vessel.flag} | Type: {vessel.vessel_type}\n"
            return output

    @staticmethod
    def format_fleet_info(fleet: FleetInfo, output_format: str = 'table'):
        """Format fleet information for output"""
        if output_format == 'json':
            return json.dumps({
                'company': fleet.company_name,
                'total_vessels': fleet.total_vessels,
                'vessels': [vessel.__dict__ for vessel in fleet.vessels]
            }, indent=2)
        elif output_format == 'csv':
            lines = ['IMO,Name,Flag,Type,DWT,GRT,YearBuilt,Status']
            for vessel in fleet.vessels:
                lines.append(f"{vessel.imo},{vessel.name},{vessel.flag},{vessel.vessel_type},{vessel.dwt or ''},{vessel.grt or ''},{vessel.year_built or ''},{vessel.status or ''}")
            return '\n'.join(lines)
        else:  # table format
            output = f"\nFleet Information: {fleet.company_name}\n"
            output += f"Total Vessels: {fleet.total_vessels}\n"
            output += "=" * 50 + "\n"
            for vessel in fleet.vessels:
                output += f"IMO: {vessel.imo} | Name: {vessel.name} | Flag: {vessel.flag} | Type: {vessel.vessel_type}\n"
            return output

    @staticmethod
    def format_batch_vessel_info(results: List[BatchResult], output_format: str = 'table') -> str:
        """Format batch vessel processing results"""
        # Calculate summary statistics
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        total_time = sum(r.processing_time for r in results)
        failed_imos = [r.imo for r in results if not r.success]

        summary = BatchSummary(
            total_vessels=total,
            successful=successful,
            failed=failed,
            processing_time=total_time,
            failed_imos=failed_imos,
            timestamp=datetime.now().isoformat()
        )

        if output_format == 'json':
            return OutputFormatter._format_batch_json(results, summary)
        elif output_format == 'csv':
            return OutputFormatter._format_batch_csv(results)
        else:  # table format
            return OutputFormatter._format_batch_table(results, summary)

    @staticmethod
    def _format_batch_json(results: List[BatchResult], summary: BatchSummary) -> str:
        """Format batch results as JSON"""
        output_data = {
            "batch_summary": {
                "total_vessels": summary.total_vessels,
                "successful": summary.successful,
                "failed": summary.failed,
                "processing_time": round(summary.processing_time, 2),
                "timestamp": summary.timestamp,
                "failed_imos": summary.failed_imos
            },
            "results": []
        }

        for result in results:
            if result.success and result.vessel_data:
                result_entry = {
                    "imo": result.imo,
                    "success": True,
                    "processing_time": round(result.processing_time, 2),
                    "vessel_data": {
                        "basic_info": asdict(result.vessel_data.basic_info),
                        "overview": result.vessel_data.overview,
                        "management": [asdict(c) for c in result.vessel_data.management],
                        "classification": [asdict(c) for c in result.vessel_data.classification],
                        "geographical": [asdict(g) for g in result.vessel_data.geographical],
                        "inspections": [asdict(i) for i in result.vessel_data.inspections],
                        "historical_names": [asdict(h) for h in result.vessel_data.historical_names],
                        "historical_flags": [asdict(h) for h in result.vessel_data.historical_flags],
                        "historical_companies": [asdict(h) for h in result.vessel_data.historical_companies]
                    }
                }
            else:
                result_entry = {
                    "imo": result.imo,
                    "success": False,
                    "processing_time": round(result.processing_time, 2),
                    "error": result.error_message or "Unknown error"
                }

            output_data["results"].append(result_entry)

        return json.dumps(output_data, indent=2)

    @staticmethod
    def _format_batch_csv(results: List[BatchResult]) -> str:
        """Format batch results as CSV"""
        lines = ["IMO,Name,Flag,Type,GT,DWT,Year,Status,Error"]

        for result in results:
            if result.success and result.vessel_data:
                basic = result.vessel_data.basic_info
                lines.append(
                    f"{basic.imo},"
                    f"{basic.name},"
                    f"{basic.flag},"
                    f"{basic.vessel_type or ''},"
                    f"{basic.gross_tonnage or ''},"
                    f"{basic.dwt or ''},"
                    f"{basic.year_built or ''},"
                    f"{basic.status or ''},"
                )
            else:
                lines.append(f"{result.imo},,,,,,,,\"{result.error_message or 'Unknown error'}\"")

        return '\n'.join(lines)

    @staticmethod
    def _format_batch_table(results: List[BatchResult], summary: BatchSummary) -> str:
        """Format batch results as a table"""
        output = []
        output.append("\n" + "=" * 70)
        output.append("BATCH PROCESSING RESULTS")
        output.append("=" * 70)
        output.append(f"Total Vessels: {summary.total_vessels}")
        output.append(f"Successful: {summary.successful}")
        output.append(f"Failed: {summary.failed}")
        output.append(f"Processing Time: {summary.processing_time:.1f}s")
        output.append(f"Timestamp: {summary.timestamp}")
        output.append("")

        # Successful vessels
        successful_results = [r for r in results if r.success and r.vessel_data]
        if successful_results:
            output.append("Successfully Retrieved:")
            output.append("-" * 70)
            output.append(f"{'IMO':<10} | {'Name':<25} | {'Flag':<15} | {'Type':<15}")
            output.append("-" * 70)

            for result in successful_results:
                basic = result.vessel_data.basic_info
                output.append(
                    f"{basic.imo:<10} | "
                    f"{basic.name[:25]:<25} | "
                    f"{(basic.flag or 'N/A')[:15]:<15} | "
                    f"{(basic.vessel_type or 'N/A')[:15]:<15}"
                )

        # Failed lookups
        failed_results = [r for r in results if not r.success]
        if failed_results:
            output.append("")
            output.append("Failed Lookups:")
            output.append("-" * 70)
            output.append(f"{'IMO':<10} | {'Error':<58}")
            output.append("-" * 70)

            for result in failed_results:
                error_msg = (result.error_message or "Unknown error")[:58]
                output.append(f"{result.imo:<10} | {error_msg}")

        output.append("=" * 70)
        return '\n'.join(output)

    @staticmethod
    def format_batch_fleet_info(results: List[CompanyBatchResult], output_format: str = 'table') -> str:
        """Format batch company processing results"""
        # Calculate summary statistics
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        total_time = sum(r.processing_time for r in results)
        total_vessels = sum(r.fleet_data.total_vessels for r in results if r.success and r.fleet_data)
        failed_companies = [r.company_name for r in results if not r.success]

        summary = CompanyBatchSummary(
            total_companies=total,
            successful=successful,
            failed=failed,
            total_vessels=total_vessels,
            processing_time=total_time,
            failed_companies=failed_companies,
            timestamp=datetime.now().isoformat()
        )

        if output_format == 'json':
            return OutputFormatter._format_batch_fleet_json(results, summary)
        elif output_format == 'csv':
            return OutputFormatter._format_batch_fleet_csv(results)
        else:  # table format
            return OutputFormatter._format_batch_fleet_table(results, summary)

    @staticmethod
    def _format_batch_fleet_json(results: List[CompanyBatchResult], summary: CompanyBatchSummary) -> str:
        """Format batch fleet results as JSON"""
        output_data = {
            "batch_summary": {
                "total_companies": summary.total_companies,
                "successful": summary.successful,
                "failed": summary.failed,
                "total_vessels": summary.total_vessels,
                "processing_time": round(summary.processing_time, 2),
                "timestamp": summary.timestamp,
                "failed_companies": summary.failed_companies
            },
            "results": []
        }

        for result in results:
            if result.success and result.fleet_data:
                result_entry = {
                    "company_name": result.company_name,
                    "success": True,
                    "processing_time": round(result.processing_time, 2),
                    "fleet_data": {
                        "company_name": result.fleet_data.company_name,
                        "total_vessels": result.fleet_data.total_vessels,
                        "vessels": [asdict(vessel) for vessel in result.fleet_data.vessels]
                    }
                }
            else:
                result_entry = {
                    "company_name": result.company_name,
                    "success": False,
                    "processing_time": round(result.processing_time, 2),
                    "error": result.error_message or "Unknown error"
                }

            output_data["results"].append(result_entry)

        return json.dumps(output_data, indent=2)

    @staticmethod
    def _format_batch_fleet_csv(results: List[CompanyBatchResult]) -> str:
        """Format batch fleet results as CSV"""
        lines = ["Company,IMO,Name,Flag,Type,DWT,GRT,YearBuilt,Status,Error"]

        for result in results:
            if result.success and result.fleet_data:
                # Add each vessel with company name
                for vessel in result.fleet_data.vessels:
                    lines.append(
                        f"{result.company_name},"
                        f"{vessel.imo},"
                        f"{vessel.name},"
                        f"{vessel.flag},"
                        f"{vessel.vessel_type or ''},"
                        f"{vessel.dwt or ''},"
                        f"{vessel.grt or ''},"
                        f"{vessel.year_built or ''},"
                        f"{vessel.status or ''},"
                    )
            else:
                # Add error row for failed company
                lines.append(f"{result.company_name},,,,,,,,\"{result.error_message or 'Unknown error'}\"")

        return '\n'.join(lines)

    @staticmethod
    def _format_batch_fleet_table(results: List[CompanyBatchResult], summary: CompanyBatchSummary) -> str:
        """Format batch fleet results as a table"""
        output = []
        output.append("\n" + "=" * 80)
        output.append("COMPANY BATCH PROCESSING RESULTS")
        output.append("=" * 80)
        output.append(f"Total Companies: {summary.total_companies}")
        output.append(f"Successful: {summary.successful}")
        output.append(f"Failed: {summary.failed}")
        output.append(f"Total Vessels: {summary.total_vessels:,}")
        output.append(f"Processing Time: {summary.processing_time:.1f}s")
        output.append(f"Timestamp: {summary.timestamp}")
        output.append("")

        # Successful company fleets
        successful_results = [r for r in results if r.success and r.fleet_data]
        if successful_results:
            output.append("Successfully Retrieved Fleet Data:")
            output.append("-" * 80)
            output.append(f"{'Company':<30} | {'Vessels':<8} | {'Processing Time':<15}")
            output.append("-" * 80)

            for result in successful_results:
                vessel_count = result.fleet_data.total_vessels
                processing_time = f"{result.processing_time:.1f}s"
                company_name = result.company_name[:29] if len(result.company_name) > 29 else result.company_name
                output.append(
                    f"{company_name:<30} | "
                    f"{vessel_count:<8} | "
                    f"{processing_time:<15}"
                )

        # Failed lookups
        failed_results = [r for r in results if not r.success]
        if failed_results:
            output.append("")
            output.append("Failed Company Lookups:")
            output.append("-" * 80)
            output.append(f"{'Company':<30} | {'Error':<48}")
            output.append("-" * 80)

            for result in failed_results:
                error_msg = (result.error_message or "Unknown error")[:47]
                company_name = result.company_name[:29] if len(result.company_name) > 29 else result.company_name
                output.append(f"{company_name:<30} | {error_msg}")

        output.append("=" * 80)
        return '\n'.join(output)
