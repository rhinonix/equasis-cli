#!/usr/bin/env python3
"""
Equasis Client - Handles authentication and web scraping of Equasis website
"""

import requests
import time
import logging
import random
from typing import Optional, List, Callable
from bs4 import BeautifulSoup
from dataclasses import dataclass
from requests.exceptions import (
    ConnectionError, Timeout, HTTPError, RequestException,
    ChunkedEncodingError, ContentDecodingError
)

from .parser import EquasisParser, EquasisVesselData

logger = logging.getLogger(__name__)

@dataclass
class RetryConfig:
    """Configuration for retry behavior following industry best practices"""
    max_retries: int = 3
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 60.0  # Maximum delay in seconds
    exponential_base: float = 2.0  # Exponential backoff multiplier
    jitter: bool = True  # Add randomness to prevent thundering herd

    def __post_init__(self):
        """Initialize mutable defaults after object creation"""
        if not hasattr(self, '_retryable_exceptions'):
            self._retryable_exceptions = (
                ConnectionError,
                Timeout,
                ChunkedEncodingError,
                ContentDecodingError,
                HTTPError,  # Will check status code separately
            )
        if not hasattr(self, '_retryable_status_codes'):
            self._retryable_status_codes = {
                429,  # Too Many Requests
                500,  # Internal Server Error
                502,  # Bad Gateway
                503,  # Service Unavailable
                504,  # Gateway Timeout
                520,  # CloudFlare: Unknown Error
                521,  # CloudFlare: Web Server Is Down
                522,  # CloudFlare: Connection Timed Out
                523,  # CloudFlare: Origin Is Unreachable
                524,  # CloudFlare: A Timeout Occurred
            }

    @property
    def retryable_exceptions(self):
        return self._retryable_exceptions

    @property
    def retryable_status_codes(self):
        return self._retryable_status_codes

def with_retry(retry_config: RetryConfig = None):
    """
    Decorator that implements exponential backoff with jitter for network operations

    Based on AWS best practices:
    https://docs.aws.amazon.com/general/latest/gr/api-retries.html
    """
    if retry_config is None:
        retry_config = RetryConfig()

    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(retry_config.max_retries + 1):
                try:
                    result = func(*args, **kwargs)

                    # Check for HTTP errors that should be retried
                    if hasattr(result, 'status_code') and result.status_code in retry_config.retryable_status_codes:
                        raise HTTPError(f"HTTP {result.status_code}", response=result)

                    # Success - reset any session issues and return
                    if attempt > 0:
                        logger.info(f"Operation succeeded on attempt {attempt + 1}")
                    return result

                except retry_config.retryable_exceptions as e:
                    last_exception = e

                    if attempt == retry_config.max_retries:
                        logger.error(f"Operation failed after {retry_config.max_retries + 1} attempts: {e}")
                        break

                    # Calculate delay with exponential backoff and jitter
                    delay = min(
                        retry_config.base_delay * (retry_config.exponential_base ** attempt),
                        retry_config.max_delay
                    )

                    if retry_config.jitter:
                        # Add jitter: delay ± 25%
                        jitter_range = delay * 0.25
                        delay = delay + random.uniform(-jitter_range, jitter_range)
                        delay = max(0.1, delay)  # Ensure minimum delay

                    logger.warning(f"Attempt {attempt + 1} failed ({e}), retrying in {delay:.1f}s...")
                    time.sleep(delay)

                except Exception as e:
                    # Non-retryable exception
                    logger.error(f"Non-retryable error: {e}")
                    raise

            # All retries exhausted
            raise last_exception

        return wrapper
    return decorator

@dataclass
class BatchResult:
    """Result from batch vessel processing"""
    imo: str
    success: bool
    vessel_data: Optional[EquasisVesselData] = None
    error_message: Optional[str] = None
    processing_time: float = 0.0

@dataclass
class BatchSummary:
    """Summary of batch processing operation"""
    total_vessels: int
    successful: int
    failed: int
    processing_time: float
    failed_imos: List[str]
    timestamp: str = ""

@dataclass
class CompanyBatchResult:
    """Result from batch company processing"""
    company_name: str
    success: bool
    fleet_data: Optional['FleetInfo'] = None
    error_message: Optional[str] = None
    processing_time: float = 0.0

@dataclass
class CompanyBatchSummary:
    """Summary of company batch processing operation"""
    total_companies: int
    successful: int
    failed: int
    total_vessels: int  # Sum across all fleets
    processing_time: float
    failed_companies: List[str]
    timestamp: str = ""

@dataclass
class SimpleVesselInfo:
    """Simple vessel info for fleet/search operations"""
    imo: str
    name: str
    flag: str
    vessel_type: str
    dwt: Optional[str] = None
    grt: Optional[str] = None
    year_built: Optional[str] = None
    status: Optional[str] = None

@dataclass
class FleetInfo:
    """Data class for fleet information"""
    company_name: str
    vessels: List[SimpleVesselInfo]
    total_vessels: int


class EquasisClient:
    """Client for interacting with Equasis API"""

    def __init__(self, username: str, password: str, retry_config: RetryConfig = None):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.base_url = "https://www.equasis.org"
        self.logged_in = False
        self.comprehensive_parser = EquasisParser()
        self.retry_config = retry_config or RetryConfig()

        # Configure session timeouts (industry standard)
        self.session.timeout = (10, 30)  # (connect_timeout, read_timeout)

        # Set headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })

    @with_retry()
    def _safe_get(self, url: str, **kwargs):
        """HTTP GET with retry logic"""
        logger.debug(f"GET request to: {url}")
        response = self.session.get(url, timeout=self.session.timeout, **kwargs)
        response.raise_for_status()
        return response

    @with_retry()
    def _safe_post(self, url: str, **kwargs):
        """HTTP POST with retry logic"""
        logger.debug(f"POST request to: {url}")
        response = self.session.post(url, timeout=self.session.timeout, **kwargs)
        response.raise_for_status()
        return response

    def login(self) -> bool:
        """Login to Equasis"""
        try:
            # Get login page first
            login_url = f"{self.base_url}/EquasisWeb/authen/HomePage?fs=HomePage"
            response = self._safe_get(login_url)

            # Parse login form to get any hidden fields
            soup = BeautifulSoup(response.text, 'html.parser')

            # Prepare login data
            login_data = {
                'j_email': self.username,
                'j_password': self.password,
                'submit': 'Ok'
            }

            # Submit login
            response = self._safe_post(login_url, data=login_data)

            # Check if login was successful (you may need to adjust this check)
            if "restricted" in response.url or "Welcome" in response.text:
                self.logged_in = True
                logger.info("Successfully logged in to Equasis")
                return True
            else:
                logger.error("Login failed - check credentials")
                return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    def get_comprehensive_vessel_info(self, imo: str) -> Optional[EquasisVesselData]:
        """Get comprehensive vessel information from all tabs"""
        if not self.logged_in and not self.login():
            return None

        try:
            # URLs for the three tabs
            tab_urls = {
                'ship_info': f"{self.base_url}/EquasisWeb/restricted/ShipInfo?fs=ShipInfo&P_IMO={imo}",
                'inspections': f"{self.base_url}/EquasisWeb/restricted/ShipInspection?fs=ShipInfo&P_IMO={imo}",
                'ship_history': f"{self.base_url}/EquasisWeb/restricted/ShipHistory?fs=ShipInfo&P_IMO={imo}"
            }

            vessel_data = None

            # Fetch each tab
            for tab_name, url in tab_urls.items():
                logger.info(f"Fetching {tab_name} tab for IMO {imo}")

                try:
                    response = self._safe_get(url)
                    time.sleep(1)  # Rate limiting
                    # Parse this tab's content
                    tab_data = self.comprehensive_parser.parse_html(response.text, tab_name)

                    if tab_data:
                        if vessel_data is None:
                            # First successful tab - use as base
                            vessel_data = tab_data
                        else:
                            # Merge data from additional tabs
                            self._merge_vessel_data(vessel_data, tab_data, tab_name)
                    else:
                        logger.warning(f"Failed to parse {tab_name} tab")

                except Exception as e:
                    logger.error(f"Failed to fetch {tab_name} tab for IMO {imo}: {e}")
                    # Continue with other tabs even if one fails

            return vessel_data

        except Exception as e:
            logger.error(f"Error getting comprehensive vessel info for {imo}: {e}")
            return None

    def _merge_vessel_data(self, base_data: EquasisVesselData, new_data: EquasisVesselData, tab_name: str):
        """Merge data from additional tabs into base vessel data"""
        if tab_name == 'inspections':
            base_data.inspections = new_data.inspections
        elif tab_name == 'ship_history':
            base_data.historical_names = new_data.historical_names
            base_data.historical_flags = new_data.historical_flags
            base_data.historical_companies = new_data.historical_companies
        elif tab_name == 'ship_info':
            # Update ship info specific data
            if new_data.overview:
                base_data.overview = new_data.overview
            if new_data.management:
                base_data.management = new_data.management
            if new_data.classification:
                base_data.classification = new_data.classification
            if new_data.geographical:
                base_data.geographical = new_data.geographical

    def search_vessel_by_imo(self, imo: str) -> Optional[EquasisVesselData]:
        """Search for vessel by IMO number - returns comprehensive vessel data"""
        return self.get_comprehensive_vessel_info(imo)

    def search_vessel_by_name(self, name: str) -> List[SimpleVesselInfo]:
        """
        Search for vessels by name using general search endpoint

        This uses the same search mechanism as company search,
        which returns both ship and company results.
        """
        if not self.logged_in and not self.login():
            return []

        try:
            logger.info(f"Searching for vessels matching: {name}")
            # Use general search endpoint (same as company search)
            search_url = f"{self.base_url}/EquasisWeb/restricted/Search?fs=Search"
            search_data = {
                'P_PAGE': '1',
                'P_PAGE_COMP': '1',
                'P_PAGE_SHIP': '1',
                'P_ENTREE_ENTETE': name,
                'P_ENTREE_ENTETE_HIDDEN': name
            }

            response = self._safe_post(search_url, data=search_data)
            time.sleep(1)

            vessels = self._parse_vessel_list(response.text)

            if not vessels:
                logger.warning(f"No vessels found matching: {name}")
            else:
                logger.info(f"Found {len(vessels)} vessels matching: {name}")

            return vessels

        except Exception as e:
            logger.error(f"Error searching vessel by name {name}: {e}")
            return []

    def search_companies(self, company_identifier: str) -> List[dict]:
        """
        Search for companies by name, returns list of matching companies

        Returns:
            List of dicts with keys: p_comp, name, address
        """
        if not self.logged_in and not self.login():
            return []

        try:
            logger.info(f"Searching for company: {company_identifier}")
            search_url = f"{self.base_url}/EquasisWeb/restricted/Search?fs=Search"
            search_data = {
                'P_PAGE': '1',
                'P_PAGE_COMP': '1',
                'P_PAGE_SHIP': '1',
                'P_ENTREE_ENTETE': company_identifier,
                'P_ENTREE_ENTETE_HIDDEN': company_identifier
            }

            response = self._safe_post(search_url, data=search_data)
            time.sleep(1)

            # Parse search results to extract P_COMP IDs and company names
            company_results = self._parse_company_search_results(response.text)

            if not company_results:
                logger.warning(f"No companies found matching: {company_identifier}")
            else:
                logger.info(f"Found {len(company_results)} companies matching: {company_identifier}")

            return company_results

        except Exception as e:
            logger.error(f"Error searching for company {company_identifier}: {e}")
            return []

    def get_fleet_by_company_id(self, p_comp: str, company_name: str) -> Optional[FleetInfo]:
        """
        Get fleet information using P_COMP ID

        Args:
            p_comp: Company ID from Equasis
            company_name: Company name for display

        Returns:
            FleetInfo object or None
        """
        if not self.logged_in and not self.login():
            return None

        try:
            logger.info(f"Fetching fleet info for {company_name} (P_COMP={p_comp})")
            fleet_url = f"{self.base_url}/EquasisWeb/restricted/FleetInfo?fs=CompanyInfo"
            fleet_data = {
                'P_PAGE': '1',
                'P_COMP': p_comp,
                'ongletActifSC': 'comp'
            }

            response = self._safe_post(fleet_url, data=fleet_data)
            time.sleep(1)

            # Parse fleet info
            return self._parse_fleet_info(response.text, company_name)

        except Exception as e:
            logger.error(f"Error getting fleet info for {company_name}: {e}")
            return None

    def get_fleet_info(self, company_identifier: str) -> Optional[FleetInfo]:
        """
        Get fleet information for a company (convenience method - uses first match)
        For interactive selection, use search_companies() then get_fleet_by_company_id()
        """
        company_results = self.search_companies(company_identifier)

        if not company_results:
            return None

        # Use first match for backward compatibility
        if len(company_results) > 1:
            logger.info(f"Multiple companies found, using first match: {company_results[0]['name']}")

        return self.get_fleet_by_company_id(
            company_results[0]['p_comp'],
            company_results[0]['name']
        )

    def _parse_company_search_results(self, html: str) -> List[dict]:
        """
        Parse company search results to extract P_COMP IDs and company names

        Returns list of dicts with keys: p_comp, name, address
        """
        from bs4 import BeautifulSoup
        import re

        soup = BeautifulSoup(html, 'html.parser')
        companies = []

        # Find the company results div
        company_div = soup.find('div', id='CompanyResultId')
        if not company_div:
            return companies

        # Find the company table
        table = company_div.find('table')
        if not table:
            return companies

        tbody = table.find('tbody')
        if not tbody:
            return companies

        # Parse each company row
        # Structure: <tr><th><a onclick="...P_COMP.value='0310062'...">0310062</a></th><td>TORM A/S</td><td>Address...</td></tr>
        for row in tbody.find_all('tr'):
            try:
                cells = row.find_all(['th', 'td'])
                if len(cells) >= 2:
                    # First cell is <th> with <a> tag containing onclick handler
                    first_cell = cells[0]

                    # Look for <a> tag with onClick attribute
                    link = first_cell.find('a', attrs={'onClick': True})
                    if not link:
                        # Try lowercase onclick
                        link = first_cell.find('a', attrs={'onclick': True})

                    if link:
                        onclick = link.get('onClick') or link.get('onclick', '')

                        # Extract P_COMP value from onclick handler
                        match = re.search(r"P_COMP\.value\s*=\s*['\"](\d+)['\"]", onclick)
                        if match:
                            p_comp = match.group(1)
                            name = cells[1].get_text(strip=True) if len(cells) > 1 else ''
                            address = cells[2].get_text(strip=True) if len(cells) > 2 else ''

                            # Skip companies with empty names or address-only entries
                            # (Equasis has responsive duplicate rows for mobile view)
                            if name and not name.startswith('C/O:') and (',' in name and len(name) > 50 or address):
                                companies.append({
                                    'p_comp': p_comp,
                                    'name': name,
                                    'address': address
                                })
            except Exception as e:
                logger.warning(f"Error parsing company row: {e}")
                continue

        # Deduplicate by P_COMP (Equasis has duplicate rows for responsive design)
        seen_comps = set()
        unique_companies = []
        for company in companies:
            if company['p_comp'] not in seen_comps:
                seen_comps.add(company['p_comp'])
                unique_companies.append(company)

        return unique_companies

    def _parse_vessel_list(self, html: str) -> List[SimpleVesselInfo]:
        """
        Parse vessel list from search results using robust element-based parsing

        Applies same principles as fleet parsing:
        - Find IMO link first (most reliable)
        - Normalize whitespace
        - Position-based text extraction
        """
        from bs4 import BeautifulSoup
        import re

        soup = BeautifulSoup(html, 'html.parser')
        vessels = []

        # Find tables - ship results are in the first table
        tables = soup.find_all('table', class_='table')
        if not tables:
            return vessels

        # First table should be ship results
        ship_table = tables[0]
        tbody = ship_table.find('tbody')
        if not tbody:
            return vessels

        # Parse each vessel row
        # Structure may vary: check if first cell contains IMO in link or just text
        for row in tbody.find_all('tr'):
            try:
                cells = row.find_all(['th', 'td'])
                if len(cells) >= 6:
                    # Try robust parsing (with IMO link) first
                    first_cell = cells[0]
                    imo_link = first_cell.find('a')

                    if imo_link:
                        # Robust parsing: IMO in link, vessel name after
                        imo = imo_link.get_text(strip=True)

                        # Validate IMO format
                        if not imo.isdigit() or len(imo) != 7:
                            # Fallback to simple text extraction
                            imo = first_cell.get_text(strip=True)

                        # Normalize whitespace and extract vessel name
                        full_text = ' '.join(first_cell.get_text().split())
                        if imo in full_text:
                            imo_pos = full_text.find(imo)
                            after_imo = full_text[imo_pos + len(imo):].strip()
                            name = after_imo.lstrip(')').lstrip('(').strip()
                        else:
                            name = cells[1].get_text(strip=True) if len(cells) > 1 else ''

                        # If name is empty, it's in next cell
                        if not name and len(cells) > 1:
                            name = cells[1].get_text(strip=True)
                    else:
                        # Simple parsing: no link structure
                        imo = cells[0].get_text(strip=True)
                        name = cells[1].get_text(strip=True)

                    # Extract remaining fields with whitespace normalization
                    vessel = SimpleVesselInfo(
                        imo=imo,
                        name=name,
                        grt=' '.join(cells[2].get_text().split()),
                        vessel_type=' '.join(cells[3].get_text().split()),
                        year_built=' '.join(cells[4].get_text().split()),
                        flag=' '.join(cells[5].get_text().split()),
                        dwt=None,
                        status=None
                    )
                    vessels.append(vessel)
            except Exception as e:
                logger.warning(f"Error parsing vessel row: {e}")
                continue

        # Deduplicate by IMO (handle responsive design duplicates)
        seen_imos = set()
        unique_vessels = []
        for vessel in vessels:
            if vessel.imo and vessel.imo not in seen_imos:
                seen_imos.add(vessel.imo)
                unique_vessels.append(vessel)

        return unique_vessels

    def _parse_fleet_info(self, html: str, company: str) -> Optional[FleetInfo]:
        """Parse fleet information from Fleet Info page"""
        from bs4 import BeautifulSoup
        import re

        soup = BeautifulSoup(html, 'html.parser')

        # Find tables
        tables = soup.find_all('table', class_='table')
        if not tables:
            logger.warning(f"No tables found in fleet info for {company}")
            return None

        # Parse the fleet table (should be first table)
        fleet_table = tables[0]
        tbody = fleet_table.find('tbody')
        if not tbody:
            logger.warning(f"No tbody found in fleet table for {company}")
            return None

        vessels = []

        # Parse each vessel row
        # Fleet table structure: "(IMO)\nVessel Name", GRT, Type, Year, Flag, Class, Detentions..., Acting as, Details
        for row in tbody.find_all('tr'):
            try:
                cells = row.find_all(['th', 'td'])
                if len(cells) >= 6:
                    # Strategy: Find the IMO link in the first cell, then extract vessel name from remaining text
                    first_cell = cells[0]

                    # Find the <a> tag with IMO - it contains the IMO number
                    imo_link = first_cell.find('a')
                    if not imo_link:
                        continue  # Skip rows without IMO link

                    # Extract IMO from the link text (most reliable)
                    imo = imo_link.get_text(strip=True)

                    # Validate it's a 7-digit IMO
                    if not imo.isdigit() or len(imo) != 7:
                        continue

                    # Get all text from the cell and normalize whitespace
                    full_text = ' '.join(first_cell.get_text().split())

                    # Remove the IMO and parentheses to get vessel name
                    # The pattern is usually: "( IMO ) Vessel Name"
                    # After normalization: "(IMO) Vessel Name" or "( IMO ) Vessel Name"
                    # Strategy: Split by IMO, take everything after it, remove closing paren
                    if imo in full_text:
                        # Find position of IMO and take everything after
                        imo_pos = full_text.find(imo)
                        after_imo = full_text[imo_pos + len(imo):].strip()
                        # Remove leading/trailing parentheses and whitespace
                        name_text = after_imo.lstrip(')').strip()
                    else:
                        name_text = ''

                    vessel = SimpleVesselInfo(
                        imo=imo,
                        name=name_text,
                        grt=cells[1].get_text(strip=True),
                        vessel_type=cells[2].get_text(strip=True),
                        year_built=cells[3].get_text(strip=True),
                        flag=cells[4].get_text(strip=True),
                        dwt=None,
                        status=None
                    )
                    vessels.append(vessel)
            except Exception as e:
                logger.warning(f"Error parsing fleet vessel row: {e}")
                continue

        if not vessels:
            logger.warning(f"No vessels found in fleet for {company}")
            return None

        return FleetInfo(
            company_name=company,
            vessels=vessels,
            total_vessels=len(vessels)
        )

    def search_vessels_by_imo_batch(self, imos: List[str],
                                   progress_callback=None,
                                   stop_on_error: bool = False) -> List[BatchResult]:
        """
        Process multiple IMO numbers with progress tracking

        Args:
            imos: List of IMO numbers to process
            progress_callback: Optional callback for progress updates (current, total, imo, status)
            stop_on_error: Whether to stop processing on first error

        Returns:
            List of BatchResult objects
        """
        import time
        from datetime import datetime

        results = []
        start_time = time.time()

        for idx, imo in enumerate(imos, 1):
            vessel_start = time.time()

            # Call progress callback if provided
            if progress_callback:
                progress_callback(idx, len(imos), imo, "processing")

            try:
                # Use existing method to get vessel data
                vessel_data = self.search_vessel_by_imo(imo)

                if vessel_data:
                    result = BatchResult(
                        imo=imo,
                        success=True,
                        vessel_data=vessel_data,
                        processing_time=time.time() - vessel_start
                    )
                    if progress_callback:
                        progress_callback(idx, len(imos), imo, "success")
                else:
                    result = BatchResult(
                        imo=imo,
                        success=False,
                        error_message="Vessel not found",
                        processing_time=time.time() - vessel_start
                    )
                    if progress_callback:
                        progress_callback(idx, len(imos), imo, "not_found")

            except Exception as e:
                result = BatchResult(
                    imo=imo,
                    success=False,
                    error_message=str(e),
                    processing_time=time.time() - vessel_start
                )
                if progress_callback:
                    progress_callback(idx, len(imos), imo, "error")

                if stop_on_error:
                    logger.error(f"Stopping batch processing due to error: {e}")
                    break

            results.append(result)

            # Rate limiting - already handled in search_vessel_by_imo, but add extra safety
            if idx < len(imos):  # Don't delay after last vessel
                time.sleep(0.1)  # Small additional delay between vessels

        return results

    def search_companies_batch(self, companies: List[str],
                              progress_callback=None,
                              stop_on_error: bool = False) -> List[CompanyBatchResult]:
        """
        Process multiple company names with progress tracking

        Args:
            companies: List of company names to process
            progress_callback: Optional callback for progress updates (current, total, company, status)
            stop_on_error: Whether to stop processing on first error

        Returns:
            List of CompanyBatchResult objects
        """
        import time
        from datetime import datetime

        results = []
        start_time = time.time()

        for idx, company in enumerate(companies, 1):
            company_start = time.time()

            # Call progress callback if provided
            if progress_callback:
                progress_callback(idx, len(companies), company, "processing")

            try:
                # Use existing method to get fleet data
                fleet_data = self.get_fleet_info(company)

                if fleet_data:
                    result = CompanyBatchResult(
                        company_name=company,
                        success=True,
                        fleet_data=fleet_data,
                        processing_time=time.time() - company_start
                    )
                    if progress_callback:
                        progress_callback(idx, len(companies), company, "success")
                else:
                    result = CompanyBatchResult(
                        company_name=company,
                        success=False,
                        error_message="Company not found or no fleet data available",
                        processing_time=time.time() - company_start
                    )
                    if progress_callback:
                        progress_callback(idx, len(companies), company, "not_found")

            except Exception as e:
                result = CompanyBatchResult(
                    company_name=company,
                    success=False,
                    error_message=str(e),
                    processing_time=time.time() - company_start
                )
                if progress_callback:
                    progress_callback(idx, len(companies), company, "error")

                if stop_on_error:
                    logger.error(f"Stopping company batch processing due to error: {e}")
                    break

            results.append(result)

            # Rate limiting - already handled in get_fleet_info, but add extra safety
            if idx < len(companies):  # Don't delay after last company
                time.sleep(0.1)  # Small additional delay between companies

        return results
