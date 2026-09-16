#!/usr/bin/env python3
"""
Comprehensive Equasis Parser for extracting vessel data from all tabs
Handles Ship Info, Inspections, Ship History tabs plus common vessel information
"""

import re
import json
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime

# Data classes for structured vessel information
@dataclass
class VesselBasicInfo:
    """Basic vessel information from infoship section"""
    imo: str
    name: str
    flag: str
    flag_code: Optional[str] = None
    call_sign: Optional[str] = None
    mmsi: Optional[str] = None
    gross_tonnage: Optional[str] = None
    dwt: Optional[str] = None
    vessel_type: Optional[str] = None
    year_built: Optional[str] = None
    status: Optional[str] = None
    status_date: Optional[str] = None
    last_update: Optional[str] = None

@dataclass
class CompanyInfo:
    """Company management information"""
    imo: Optional[str]
    name: str
    role: str
    address: Optional[str] = None
    date_effect: Optional[str] = None

@dataclass
class ClassificationInfo:
    """Classification society information"""
    society: str
    status: str
    date_effect: Optional[str] = None

@dataclass
class GeographicalInfo:
    """Geographical location information"""
    date: str
    area: str
    source: str

@dataclass
class InspectionInfo:
    """Port State Control inspection information"""
    authority: Optional[str]
    port: Optional[str]
    date: str
    detention: str
    psc_organization: str
    inspection_type: Optional[str] = None
    duration: Optional[str] = None
    deficiencies: Optional[str] = None
    inspection_id: Optional[str] = None

@dataclass
class HistoricalName:
    """Historical vessel name"""
    name: str
    date_effect: str
    source: str

@dataclass
class HistoricalFlag:
    """Historical flag registration"""
    flag: str
    date_effect: str
    source: str

@dataclass
class HistoricalCompany:
    """Historical company management"""
    company: str
    role: str
    date_effect: str
    source: str

@dataclass
class EquasisVesselData:
    """Complete vessel data from Equasis"""
    # Basic info (always present)
    basic_info: VesselBasicInfo

    # Ship Info tab data
    overview: Optional[Dict[str, Any]] = None
    management: List[CompanyInfo] = field(default_factory=list)
    classification: List[ClassificationInfo] = field(default_factory=list)
    geographical: List[GeographicalInfo] = field(default_factory=list)

    # Inspections tab data
    inspections: List[InspectionInfo] = field(default_factory=list)

    # Ship History tab data
    historical_names: List[HistoricalName] = field(default_factory=list)
    historical_flags: List[HistoricalFlag] = field(default_factory=list)
    historical_companies: List[HistoricalCompany] = field(default_factory=list)


class EquasisParser:
    """Comprehensive parser for Equasis vessel information"""

    def __init__(self):
        self.debug = False

    def parse_html(self, html: str, tab: str = "ship_info") -> Optional[EquasisVesselData]:
        """
        Parse Equasis HTML content based on the active tab

        Args:
            html: HTML content from Equasis
            tab: Which tab is active ("ship_info", "inspections", "ship_history")

        Returns:
            EquasisVesselData object or None if parsing fails
        """
        soup = BeautifulSoup(html, 'html.parser')

        # First, extract basic info that's present on all tabs
        basic_info = self._parse_basic_info(soup)
        if not basic_info:
            print("Failed to extract basic vessel information")
            return None

        # Create the vessel data object
        vessel_data = EquasisVesselData(basic_info=basic_info)

        # Parse tab-specific content based on which tab is active
        if tab == "ship_info":
            self._parse_ship_info_tab(soup, vessel_data)
        elif tab == "inspections":
            self._parse_inspections_tab(soup, vessel_data)
        elif tab == "ship_history":
            self._parse_ship_history_tab(soup, vessel_data)

        return vessel_data

    def _parse_basic_info(self, soup: BeautifulSoup) -> Optional[VesselBasicInfo]:
        """Parse basic vessel info from the infoship section (present on all tabs)"""

        # Initialize data dictionary
        data = {}

        # Method 1: Extract vessel name and IMO from h4 tag
        h4 = soup.find('h4', class_='color-gris-bleu-copyright')
        if h4:
            # Extract name from first <b> tag
            name_tag = h4.find('b')
            if name_tag:
                data['name'] = name_tag.get_text(strip=True)

            # Extract IMO from second <b> tag or from text
            imo_match = re.search(r'IMO[^0-9]*(\d{7})', h4.get_text())
            if imo_match:
                data['imo'] = imo_match.group(1)

        # Method 2: Parse vessel details from row structure
        rows = soup.find_all('div', class_='row')
        for row in rows:
            cols = row.find_all('div', class_=re.compile(r'col-'))
            if len(cols) >= 2:
                # Check if first column has a bold label
                label_tag = cols[0].find('b')
                if label_tag:
                    label = label_tag.get_text(strip=True).lower()
                    value = cols[1].get_text(strip=True) if len(cols) > 1 else ''

                    # Map labels to data fields
                    if 'flag' in label:
                        # Check for flag image
                        img = cols[1].find('img')
                        if img and 'src' in img.attrs:
                            # Extract flag code from image src (e.g., /flags/KNA.png)
                            flag_match = re.search(r'/flags/([A-Z]+)\.', img['src'])
                            if flag_match:
                                data['flag_code'] = flag_match.group(1)

                        # Flag country name might be in third column
                        if len(cols) > 2:
                            third = cols[2].get_text(strip=True)
                            if third.startswith('(') and third.endswith(')'):
                                data['flag'] = third.strip('()')

                    elif 'call sign' in label:
                        data['call_sign'] = value

                    elif 'mmsi' in label:
                        data['mmsi'] = value

                    elif 'gross tonnage' in label:
                        data['gross_tonnage'] = value
                        # Check for date in third column
                        if len(cols) > 2:
                            third = cols[2].get_text(strip=True)
                            if 'during' in third:
                                data['gt_date'] = third

                    elif 'dwt' in label:
                        data['dwt'] = value

                    elif 'type of ship' in label:
                        data['vessel_type'] = value

                    elif 'year of build' in label or 'year built' in label:
                        data['year_built'] = value

                    elif label == 'status':
                        data['status'] = value
                        # Check for date in third column
                        if len(cols) > 2:
                            third = cols[2].get_text(strip=True)
                            if 'since' in third or 'during' in third:
                                data['status_date'] = third

        # Look for last update date
        update_badge = soup.find('p', class_='badge gris-bleu-copyright badge-notification')
        if update_badge:
            update_text = update_badge.get_text(strip=True)
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', update_text)
            if date_match:
                data['last_update'] = date_match.group(1)

        # Create VesselBasicInfo object if we have minimum required data
        if data.get('name') and data.get('imo'):
            return VesselBasicInfo(
                imo=data.get('imo', ''),
                name=data.get('name', ''),
                flag=data.get('flag', ''),
                flag_code=data.get('flag_code'),
                call_sign=data.get('call_sign'),
                mmsi=data.get('mmsi'),
                gross_tonnage=data.get('gross_tonnage'),
                dwt=data.get('dwt'),
                vessel_type=data.get('vessel_type'),
                year_built=data.get('year_built'),
                status=data.get('status'),
                status_date=data.get('status_date'),
                last_update=data.get('last_update')
            )

        return None

    def _parse_ship_info_tab(self, soup: BeautifulSoup, vessel_data: EquasisVesselData):
        """Parse Ship Info tab content"""

        # Parse Overview section
        overview_section = soup.find('div', id='collapse1')
        if overview_section:
            vessel_data.overview = self._parse_overview(overview_section)

        # Parse Management Details
        mgmt_section = soup.find('div', id='collapse3')
        if mgmt_section:
            vessel_data.management = self._parse_management(mgmt_section)

        # Parse Classification
        class_section = soup.find('div', id='collapse4')
        if class_section:
            vessel_data.classification = self._parse_classification(class_section)

        # Parse Geographical Information
        geo_section = soup.find('div', id='collapse7')
        if geo_section:
            vessel_data.geographical = self._parse_geographical(geo_section)

    def _parse_overview(self, section) -> Dict[str, Any]:
        """Parse overview section with flag performance and targeting"""
        overview = {}

        # Look for flag performance badges
        badges = section.find_all('div', class_='badge bleu-equasis')
        for badge in badges:
            text = badge.get_text(strip=True)

            # Parse Paris MOU
            if 'Paris MOU' in text:
                # Look for color indicator
                color_div = badge.find('div', class_=re.compile(r'round-\d+'))
                if color_div:
                    classes = ' '.join(color_div.get('class', []))
                    if 'black' in classes:
                        overview['paris_mou'] = 'Black'
                    elif 'grey' in classes or 'gray' in classes:
                        overview['paris_mou'] = 'Grey'
                    elif 'white' in classes:
                        overview['paris_mou'] = 'White'

            # Parse Tokyo MOU
            elif 'Tokyo MOU' in text or 'Tokyo MoU' in text:
                color_div = badge.find('div', class_=re.compile(r'round-\d+'))
                if color_div:
                    classes = ' '.join(color_div.get('class', []))
                    if 'black' in classes:
                        overview['tokyo_mou'] = 'Black'
                    elif 'grey' in classes or 'gray' in classes:
                        overview['tokyo_mou'] = 'Grey'
                    elif 'white' in classes:
                        overview['tokyo_mou'] = 'White'

            # Parse USCG targeting
            elif 'USCG' in text:
                if 'not targeted' in text:
                    overview['uscg_targeting'] = 'Not targeted'
                else:
                    overview['uscg_targeting'] = 'Targeted'

        return overview

    def _parse_management(self, section) -> List[CompanyInfo]:
        """Parse management companies from table"""
        companies = []

        # Look for table
        table = section.find('table', class_='tableLS')
        if table:
            tbody = table.find('tbody')
            if tbody:
                for row in tbody.find_all('tr'):
                    cells = row.find_all('td')
                    if len(cells) >= 5:
                        company = CompanyInfo(
                            imo=cells[0].get_text(strip=True) if cells[0] else None,
                            name=cells[2].get_text(strip=True) if cells[2] else '',
                            role=cells[1].get_text(strip=True) if cells[1] else '',
                            address=cells[3].get_text(strip=True) if cells[3] else None,
                            date_effect=cells[4].get_text(strip=True) if cells[4] else None
                        )
                        companies.append(company)

        return companies

    def _parse_classification(self, section) -> List[ClassificationInfo]:
        """Parse classification society information"""
        classifications = []

        # Look for classification entries
        items = section.find_all('div', class_='access-body')
        for item in items:
            # Look for society name
            society_p = item.find('p')
            if society_p:
                society_text = society_p.get_text(strip=True)

                # Look for status badge
                status_badge = item.find('span', class_='badge')
                status = status_badge.get_text(strip=True) if status_badge else ''

                # Look for date
                date_p = item.find_all('p')
                date_text = ''
                for p in date_p:
                    text = p.get_text(strip=True)
                    if 'during' in text or 'since' in text:
                        date_text = text
                        break

                if society_text:
                    classifications.append(ClassificationInfo(
                        society=society_text,
                        status=status,
                        date_effect=date_text
                    ))

        return classifications

    def _parse_geographical(self, section) -> List[GeographicalInfo]:
        """Parse geographical location history"""
        locations = []

        # Look for table
        table = section.find('table', class_='tableLS')
        if table:
            tbody = table.find('tbody')
            if tbody:
                for row in tbody.find_all('tr'):
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        locations.append(GeographicalInfo(
                            date=cells[0].get_text(strip=True),
                            area=cells[1].get_text(strip=True),
                            source=cells[2].get_text(strip=True)
                        ))

        return locations

    def _parse_inspections_tab(self, soup: BeautifulSoup, vessel_data: EquasisVesselData):
        """Parse Inspections tab content"""

        # Find PSC inspections section
        psc_section = soup.find('div', id='collapse1DD')
        if not psc_section:
            # Try alternative ID
            psc_section = soup.find('div', class_='tableLSDD')

        if psc_section:
            # Look for inspection table
            table = psc_section.find('table', class_='tableLSDD') or psc_section.find('table', class_='table')
            if table:
                tbody = table.find('tbody')
                if tbody:
                    for row in tbody.find_all('tr'):
                        cells = row.find_all('td')
                        if len(cells) >= 5:
                            # Extract inspection ID from onclick if available
                            insp_id = None
                            onclick = row.get('onclick') or (cells[-1].find('a', onclick=True) if cells else None)
                            if onclick:
                                id_match = re.search(r"P_INSP\.value='(\d+)'", str(onclick))
                                if id_match:
                                    insp_id = id_match.group(1)

                            inspection = InspectionInfo(
                                authority=cells[0].get_text(strip=True) if cells[0] else None,
                                port=cells[1].get_text(strip=True) if cells[1] else None,
                                date=cells[2].get_text(strip=True) if len(cells) > 2 else '',
                                detention=cells[3].get_text(strip=True) if len(cells) > 3 else '',
                                psc_organization=cells[4].get_text(strip=True) if len(cells) > 4 else '',
                                inspection_type=cells[5].get_text(strip=True) if len(cells) > 5 else None,
                                duration=cells[6].get_text(strip=True) if len(cells) > 6 else None,
                                deficiencies=cells[7].get_text(strip=True) if len(cells) > 7 else None,
                                inspection_id=insp_id
                            )
                            vessel_data.inspections.append(inspection)

    def _parse_ship_history_tab(self, soup: BeautifulSoup, vessel_data: EquasisVesselData):
        """Parse Ship History tab content"""

        # Parse historical names
        names_section = soup.find('div', id='collapse1')
        if names_section:
            table = names_section.find('table', class_='tableLS')
            if table and table.find('tbody'):
                for row in table.find('tbody').find_all('tr'):
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        vessel_data.historical_names.append(HistoricalName(
                            name=cells[0].get_text(strip=True),
                            date_effect=cells[1].get_text(strip=True),
                            source=cells[2].get_text(strip=True)
                        ))

        # Parse historical flags
        flags_section = soup.find('div', id='collapse2')
        if flags_section:
            table = flags_section.find('table', class_='tableLS')
            if table and table.find('tbody'):
                for row in table.find('tbody').find_all('tr'):
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        vessel_data.historical_flags.append(HistoricalFlag(
                            flag=cells[0].get_text(strip=True),
                            date_effect=cells[1].get_text(strip=True),
                            source=cells[2].get_text(strip=True)
                        ))

        # Parse historical companies
        companies_section = soup.find('div', id='collapse4')
        if companies_section:
            table = companies_section.find('table', class_='tableLS')
            if table and table.find('tbody'):
                for row in table.find('tbody').find_all('tr'):
                    cells = row.find_all('td')
                    if len(cells) >= 4:
                        vessel_data.historical_companies.append(HistoricalCompany(
                            company=cells[0].get_text(strip=True),
                            role=cells[1].get_text(strip=True),
                            date_effect=cells[2].get_text(strip=True),
                            source=cells[3].get_text(strip=True)
                        ))
