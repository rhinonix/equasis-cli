# Equasis CLI Tool

![Alt text](https://github.com/user-attachments/assets/d8efd954-438b-4e91-b000-8391b2f0321f "Screenshot of equasis-cli")

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-lightgrey.svg)](LICENSING.md)
[![GitHub Stars](https://img.shields.io/github/stars/rhinonix/equasis-cli?style=social)](https://github.com/rhinonix/equasis-cli/stargazers)
[![GitHub Issues](https://img.shields.io/github/issues/rhinonix/equasis-cli)](https://github.com/rhinonix/equasis-cli/issues)

A command-line tool for accessing Equasis maritime intelligence. Created to solve a real problem: investigating large numbers of vessels and management companies is cumbersome through the web interface. This tool provides a scriptable way to query vessel data, export in multiple formats, and analyze fleets efficiently.

> **Major Update**: Now provides comprehensive vessel intelligence with 50+ data points including management companies, PSC inspections, historical names/flags, and classification details - all collected automatically from multiple Equasis tabs.

> [!IMPORTANT]
> The HTML parsing may need updates if Equasis changes their website structure. If you encounter parsing errors or missing data, please [submit an issue](https://github.com/rhinonix/equasis-cli/issues) with details about the error. Developers are welcome to submit pull requests with fixes.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Output Formats](#output-formats)
- [Examples](#examples)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Legal and Compliance](#legal-and-compliance)
- [Contributing](#contributing)
- [License](#license)

## Overview

Equasis CLI Tool is a Python-based command-line application that interfaces with the Equasis maritime database to retrieve vessel and fleet information. Unlike web-based tools, this CLI provides:

- Fast, scriptable access to maritime data
- Multiple output formats (table, JSON, CSV)
- Batch processing capabilities
- Integration with automation workflows
- Clean separation from GUI dependencies

## Features

### Current Features

#### Core Vessel Intelligence

- **Comprehensive Vessel Lookup**: Get complete vessel profiles with 50+ data points from multiple Equasis tabs
- **3-Tab Data Collection**: Automatically fetches Ship Info, Inspections, and Ship History data
- **Management Company Details**: Current and historical management with roles and dates
- **PSC Inspection History**: Port State Control inspections with detention records
- **Historical Vessel Data**: Name changes, flag changes, and ownership history over time
- **Classification Society Info**: Current and historical classification with status
- **Geographical Tracking**: Vessel location history and movement patterns
- **Flag Performance**: Paris MOU and Tokyo MOU ratings, USCG targeting status

#### Search & Fleet Operations

- **Vessel Search by IMO**: Look up comprehensive vessel information using IMO numbers
- **Vessel Search by Name**: Search for vessels using partial or complete names
- **Fleet Information**: Retrieve fleet data for shipping companies
- **Batch Processing**: Process multiple vessels or companies in a single operation with progress tracking

#### Technical Features

- **Professional Package Structure**: Modular architecture ready for distribution (Homebrew, PyPI)
- **Multiple Output Formats**: Export data as formatted tables, structured JSON, or CSV
- **File Output**: Save results directly to files
- **Session Management**: Automatic login and session handling with error recovery
- **Rate Limiting**: Built-in delays to respect server resources (1-second intervals)
- **Environment Variables**: Secure credential management via .env files
- **Comprehensive Logging**: Debug and monitor operations with detailed logging
- **Enterprise-Grade Retry Logic**: Exponential backoff with jitter for network resilience

### [Planned Features](https://github.com/users/rhinonix/projects/1/views/1)

#### Near-Term Enhancements

- **Data Caching**: Reduce redundant API calls with intelligent caching
- **Enhanced Search/Fleet Parsing**: Apply comprehensive parsing to search results
- **Progress Indicators**: Visual feedback for long operations
- **Configuration Files**: User preferences and custom settings

#### Medium-Term Goals

- **Homebrew Distribution**: Native macOS installation via `brew install equasis-cli`
- **Additional Maritime Data**: Integration with other vessel databases
- **Export Formats**: Excel, PDF reports, specialized maritime formats
- **Vessel Analytics**: Risk assessment and compliance scoring
- **Fleet Intelligence**: Company-wide vessel analysis and reporting

#### Advanced Features

- **Maritime Intelligence Platform**: Beyond basic vessel lookup
- **API Service**: RESTful API for integration with other maritime tools
- **Visualization**: Charts and graphs for historical vessel data
- **Automated Monitoring**: Alerts for vessel status changes

## Prerequisites

- **Python 3.10+**: Required for modern features and type hints
- **Equasis Account**: Valid username and password from equasis.org
- **Internet Connection**: Required for accessing Equasis servers

### System Requirements

- macOS, Linux, or Windows
- 50MB disk space for virtual environment
- Stable internet connection

## Installation

### Prerequisites

- **pipx**: Recommended for isolated installation of Python CLI tools
- **Python 3.10+**: Required for the application
- **Git** (optional): For cloning the repository

### Install pipx (if not already installed)

```bash
# On macOS with Homebrew
brew install pipx

# On other systems, use pip
python3 -m pip install --user pipx

# Add pipx to PATH
pipx ensurepath

# Restart your terminal or run:
source ~/.zshrc  # or ~/.bashrc
```

### Install Equasis CLI

#### Option 1: Install from Source (Recommended for Development)

```bash
# Clone or download the project
cd ~/Projects/  # or your preferred location
git clone <repository-url> equasis-cli  # or download and extract
cd equasis-cli

# Install with pipx in editable mode
pipx install -e .

# Verify installation
equasis --help
```

#### Option 2: Install from Git (if available)

```bash
# Install directly from repository
pipx install git+<repository-url>
```

#### Option 3: Traditional Virtual Environment (Alternative)

If you prefer not to use pipx:

```bash
cd ~/Projects/equasis-cli

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Note: You'll need to activate the venv each time you use the tool
```

## Configuration

### Recommended: Secure Credential Storage

Set up your Equasis credentials using the built-in credential manager:

```bash
# Interactive credential setup (recommended)
equasis configure --setup
```

This securely stores your credentials in `~/.config/equasis-cli/credentials.json` with proper file permissions (owner-only access). Works from any directory and follows industry standards.

### Alternative Methods

**Environment Variables:**
```bash
# Set environment variables (works globally)
export EQUASIS_USERNAME=your_username_here
export EQUASIS_PASSWORD=your_password_here
```

**Command Line Arguments:**
```bash
# Pass credentials directly (least secure, not recommended)
equasis --username your_user --password your_pass vessel --imo 9074729
```

### Credential Management Commands

```bash
# Set up credentials interactively
equasis configure --setup

# Check credential status (helpful for debugging)
equasis configure --show

# Remove stored credentials
equasis configure --clear
```

### Security Features

- **XDG-compliant storage**: Follows industry standards (`~/.config/equasis-cli/`)
- **Secure file permissions**: Config file readable only by owner (600 permissions)
- **Credential hierarchy**: Command-line args override environment vars override config file
- **Cross-platform**: Works on macOS, Linux, Windows with appropriate config directories
- **Global operation**: No dependency on project directories or local files

## Usage

The tool is available globally after installation via pipx. No need to activate virtual environments or navigate to specific directories.

### Interactive Mode (Recommended)

Simply type `equasis` with no arguments to enter interactive mode:

```bash
equasis
```

This launches a **modern professional TUI** with advanced features:

**TUI Features:**
- **Fixed input area** at bottom (doesn't scroll away)
- **Persistent status bar** showing connection, format, and operation status
- **Gradient color scheme** (professional magenta-to-purple gradient banner)
- **Context-aware ephemeral menus** - Press `?` for help, `Tab` for slash parameters
- **Interactive company selection** - Automatic disambiguation for fleet queries
- **Ephemeral help menu** - Press `?` to show available commands
- **Vim/Less-style scrolling** - Navigate output with `j`/`k` keys
- **Animated loading indicators** - Spinner with shine effect during operations
- **Custom styled output** - Gradient ASCII art and syntax highlighting
- **Auto-completion** - Tab completion for slash parameters

**Example session:**
```
────────────────────────────────────────
> vessel /imo 9074729
────────────────────────────────────────
[vessel data table appears here]
────────────────────────────────────────
● Connected • Format: table • ✓ Vessel 9074729 found

────────────────────────────────────────
> search /name "MAERSK"
────────────────────────────────────────
[search results appear here]
────────────────────────────────────────
● Connected • Format: table • ✓ Found 45 vessel(s)
> exit
```

**Interactive Commands:**
```bash
# Vessel lookup
vessel /imo 9074729
vessel /imo 9074729 /format json
vessel /imo 9074729 /output vessel_data.json

# Vessel search
search /name "MAERSK"
search /imo 9074729               # Search by IMO (useful for companies)
search /name "EVER GIVEN" /format json

# Fleet information
fleet /company "MSC"
fleet /company "MAERSK LINE" /format csv

# Batch processing
batch /imos "9074729,8515128,9632179"
batch /file fleet_imos.txt /format json /output results.json
batch /companies "MSC,MAERSK,COSCO" /progress

# Utility commands
format json          # Set default output format
status              # Show connection status
clear               # Clear screen
?                   # Quick help (clears screen first)
help                # Full command list
help vessel         # Command-specific help
exit                # Exit interactive mode
```

**Keyboard Shortcuts:**
- **`?`** - Toggle help menu (keyboard shortcuts overlay)
- **`/`** - Show context-aware command/parameter menu with filtering
- **`Tab`** - Select from menu (replaces from last `/` for parameters)
- **`Enter`** - Execute command
- **`Up/Down`** - Navigate menu / scroll output / command history (context-aware)
- **`Esc`** - Enter scroll mode (navigate output buffer)
- **`i`** - Return to input mode from scroll mode
- **`Ctrl+K/J`** - Quick scroll up/down (5 lines)
- **`Page Up/Down`**, **`Shift+Up/Down`** - Scroll output buffer
- **`Ctrl+C`** - Cancel input and hide menus
- **`Ctrl+D`** - Exit application

**Interactive Mode Benefits:**
- **Persistent Session**: Authenticate once, run multiple queries
- **Modern Syntax**: Use `/param value` slash command syntax
- **Fast Queries**: No re-authentication between commands
- **Context-Aware Menus**: Commands without `/`, parameters with `/`
- **Format Control**: Set default output format or override per-command
- **File Output**: Save results with `/output filename.ext`
- **Batch Processing**: Process multiple vessels or companies efficiently
- **Scroll Mode**: Vim/less-style navigation for reviewing output

### Traditional CLI Mode

You can also use traditional command-line syntax:

```bash
equasis [global_options] command [command_options]
```

### Global Options

- `--username USERNAME`: Equasis username (optional if set in .env)
- `--password PASSWORD`: Equasis password (optional if set in .env)
- `--output FORMAT`: Output format (table, json, csv) - default: table
- `--output-file FILE`: Save output to file instead of printing

### Tab Completion

The tool includes comprehensive tab completion for zsh with intelligent suggestions and examples.

**Completion Features:**

- **Commands**: `equasis <TAB>` shows available commands with descriptions
- **Command-specific options**: `equasis vessel <TAB>` shows only vessel-related options
- **Output formats**: `equasis --output <TAB>` shows format options with descriptions
- **Real examples**: Completion provides actual IMO numbers, vessel names, and company names
- **Context-aware**: Different completions for different commands

**What you can complete:**

- Commands: `vessel`, `search`, `fleet`
- Global options: `--username`, `--password`, `--output`, `--output-file`, `--help`
- Output formats: `table`, `json`, `csv` (with descriptions)
- Example IMO numbers: Real vessels like EVER GIVEN (9074729)
- Example vessel names: "EVER GIVEN", "MAERSK", "COSCO", etc.
- Major shipping companies: "MAERSK LINE", "MSC", "COSCO SHIPPING", etc.

**Setting up tab completion:**

1. **Ensure completion directory exists:**

   ```bash
   mkdir -p ~/.zsh/completions
   ```

2. **Copy completion script** (if installed from source):

   ```bash
   cp ~/Projects/equasis-cli/completions/equasis_completion.zsh ~/.zsh/completions/_equasis
   ```

3. **Add to .zshrc** (if not already present):

   ```bash
   echo 'fpath=(~/.zsh/completions $fpath)' >> ~/.zshrc
   echo 'autoload -Uz compinit && compinit' >> ~/.zshrc
   ```

4. **Reload shell:**
   ```bash
   source ~/.zshrc
   ```

**Usage tips:**

- Always add a space before pressing TAB: `equasis vessel --imo <TAB>` (not `equasis vessel --imo<TAB>`)
- Use TAB at any point to see available options
- Select from examples or type your own values
- Descriptions help you understand what each option does

### Commands

#### Interactive Mode Commands

When in interactive mode (started with `equasis`), use these commands:

##### vessel

Get comprehensive vessel information by IMO number.

```bash
> vessel /imo 9074729
> vessel /imo 9074729 /format json
> vessel /imo 9074729 /output vessel_data.json
```

**Parameters:**
- `/imo IMO_NUMBER`: Required. The IMO number of the vessel
- `/format FORMAT`: Optional. Output format (table, json, csv)
- `/output FILE_OR_FORMAT`: Optional. Save to file or set format

##### search

Search for vessels by name (partial matches supported).

```bash
> search /name "MAERSK"
> search /name "EVER GIVEN" /format json
> search /name "CONTAINER" /output results.csv
```

**Parameters:**
- `/name VESSEL_NAME`: Required. Full or partial vessel name
- `/format FORMAT`: Optional. Output format (table, json, csv)
- `/output FILE_OR_FORMAT`: Optional. Save to file or set format

##### fleet

Get fleet information for a shipping company.

```bash
> fleet /company "MSC"
> fleet /company "MAERSK LINE" /format json
> fleet /company "COSCO" /output fleet_data.json
```

**Parameters:**
- `/company COMPANY_NAME`: Required. Company name or identifier
- `/format FORMAT`: Optional. Output format (table, json, csv)
- `/output FILE_OR_FORMAT`: Optional. Save to file or set format

##### format

Set default output format for all commands.

```bash
> format json
> format table
> format csv
```

##### status

Show current session status.

```bash
> status
```

Displays:
- Connection status
- Current output format
- Debug mode status

##### clear

Clear the terminal screen.

```bash
> clear
```

##### help

Show help information.

```bash
> help              # List all commands
> help vessel       # Show help for vessel command
> help output       # Show help for file output
```

##### exit / quit

Exit interactive mode.

```bash
> exit
> quit
```

You can also use `Ctrl+D` to exit.

#### Traditional CLI Mode Commands

When using traditional syntax:

##### vessel

```bash
equasis vessel --imo IMO_NUMBER
```

**Options:**
- `--imo IMO_NUMBER`: Required. The IMO number of the vessel

##### search

```bash
equasis search --name VESSEL_NAME
```

**Options:**
- `--name VESSEL_NAME`: Required. Full or partial vessel name

##### fleet

```bash
equasis fleet --company COMPANY_NAME
```

**Options:**
- `--company COMPANY_NAME`: Required. Company name or identifier

## Output Formats

### Table Format (Default) - Comprehensive Intelligence

Human-readable formatted output with comprehensive vessel intelligence.

```
Vessel Information (Comprehensive):
===================================
IMO Number:    8515128
Name:          ALMAHER
Flag:          St.Kitts and Nevis (KNA)
Call Sign:     V4FN6
MMSI:          341787001
Type:          Passenger/Ro-Ro Ship (vehicles)
Gross Tonnage: 1792
DWT:           964
Year Built:    1986
Status:        In Service/Commission
Last Update:   02/07/2025

Management Companies (3):
------------------------------
• AL JADARA MEMIZA (Ship manager/Commercial manager)
• AL JADARA MEMIZA (Registered owner)
• UNKNOWN (ISM Manager)

Classification (1):
----------------
• International Register of Shipping (IS) - Withdrawn

Recent PSC Inspections (1 of 1):
-----------------------------------
• 03/04/2009: Tokyo MoU
  ⚠️  Detention: N

Historical Names (3 total):
----------------------
• ALMAHER (since 01/07/2024)
• St. Anthony de Padua (since 01/08/2012)
• Cebu Ferry 2 (since 01/04/2009)
```

### JSON Format - Rich Nested Structure

Structured data with comprehensive vessel intelligence for programmatic processing.

```json
{
  "basic_info": {
    "imo": "8515128",
    "name": "ALMAHER",
    "flag": "St.Kitts and Nevis",
    "flag_code": "KNA",
    "call_sign": "V4FN6",
    "mmsi": "341787001",
    "vessel_type": "Passenger/Ro-Ro Ship (vehicles)",
    "gross_tonnage": "1792",
    "dwt": "964",
    "year_built": "1986",
    "status": "In Service/Commission",
    "last_update": "02/07/2025"
  },
  "management": [
    {
      "name": "AL JADARA MEMIZA",
      "role": "Ship manager/Commercial manager",
      "imo": "0050002",
      "date_effect": "since 01/07/2024"
    }
  ],
  "inspections": [
    {
      "date": "03/04/2009",
      "psc_organization": "Tokyo MoU",
      "detention": "N",
      "authority": "Japan",
      "port": "Osaka"
    }
  ],
  "historical_names": [
    {
      "name": "ALMAHER",
      "date_effect": "since 01/07/2024",
      "source": "Equasis"
    }
  ]
}
```

### CSV Format

Basic CSV format for spreadsheet compatibility (basic fields only).

```csv
8515128,ALMAHER,St.Kitts and Nevis,Passenger/Ro-Ro Ship,964,1792,1986
```

## Examples

### Interactive Mode Examples

#### Starting Interactive Mode

```bash
# Simply run equasis with no arguments
equasis
```

You'll see the banner and enter interactive mode:

```
                               _                 ___
  ___  ____ ___  ______ ______(_)____      _____/ (_)
 / _ \/ __ `/ / / / __ `/ ___/ / ___/_____/ ___/ / /
/  __/ /_/ / /_/ / /_/ (__  ) (__  )_____/ /__/ / /
\___/\__, /\__,_/\__,_/____/_/____/      \___/_/_/
       /_/

Maritime Intelligence Tool                                         v2.0.0

┌──────────────────────────────────────────────────────────────────────────┐
│ Important Disclaimers                                                    │
└──────────────────────────────────────────────────────────────────────────┘
• This tool is NOT associated with, endorsed by, or affiliated with Equasis
• May break if Equasis changes their website structure
• Users must monitor for changes and update parsing logic accordingly
• Respect Equasis Terms of Service and rate limiting
• Use for legitimate maritime research and safety purposes only

Type 'help' for available commands or 'exit' to quit.
Press ? for quick help.

>
```

#### Comprehensive Vessel Lookup

Get complete vessel intelligence with management, inspections, and history:

```bash
> vessel /imo 9074729

# Get data in JSON format
> vessel /imo 9074729 /format json

# Save to file (format auto-detected from extension)
> vessel /imo 9074729 /output vessel_data.json

# Set JSON as default format for all subsequent commands
> format json
> vessel /imo 9074729
```

**What you get**: Complete vessel profile including management companies, PSC inspection history, historical names/flags, classification details, and geographical tracking - all from a single command!

#### Batch Processing Multiple Vessels and Companies

Process multiple vessels at once:

```bash
# Process multiple IMO numbers directly
> batch /imos "9074729,9632179,9839333"

# Process IMOs from a file
> batch /file fleet_imos.txt

# Save batch results to JSON
> batch /imos "9074729,9632179" /format json /output batch_results.json

# Process with CSV output
> batch /file my_vessels.txt /format csv /output fleet_analysis.csv
```

Process multiple companies for fleet analysis:

```bash
# Process multiple companies directly
> batch /companies "MSC,MAERSK,COSCO"

# Process companies from a file
> batch /company-file shipping_companies.txt

# Save company batch results to JSON
> batch /companies "MSC,EVERGREEN" /format json /output fleet_comparison.json

# Process with progress indicators
> batch /companies "MSC,MAERSK,COSCO,EVERGREEN" /format csv /output major_fleets.csv
```

**File Format for Batch Processing:**
```text
# fleet_imos.txt - IMO numbers with comments
9074729   # EMMA MAERSK
9632179   # MSC OSCAR
9839333   # EVER GIVEN
# Empty lines are ignored

# shipping_companies.txt - Company names with comments
MSC                    # Mediterranean Shipping Company
MAERSK                # A.P. Moller-Maersk
COSCO SHIPPING        # China COSCO Shipping
# Comments and empty lines are supported
```

#### Multiple Queries in One Session

```bash
> vessel /imo 9074729
> search /name "MAERSK"
> fleet /company "MSC"
> status
> exit
```

No re-authentication needed between commands!

### Traditional CLI Examples

#### Comprehensive Vessel Lookup

```bash
# Using environment variables for credentials (recommended)
equasis vessel --imo 8515128

# Using command-line credentials
equasis --username myuser --password mypass vessel --imo 8515128

# Use tab completion for IMO examples
equasis vessel --imo <TAB>  # Shows real vessel examples like EVER GIVEN

# Get comprehensive data in JSON format
equasis --output json vessel --imo 8515128

# Save comprehensive report to file
equasis --output json --output-file vessel_intelligence.json vessel --imo 8515128

# BATCH PROCESSING: Multiple vessels at once
equasis vessel --imo 9074729 9632179 9839333 --progress

# Process IMOs from a file
equasis vessel --imo-file fleet_imos.txt --output csv --output-file results.csv

# Continue on errors with progress display
equasis vessel --imo-file large_fleet.txt --continue-on-error --progress
```

#### Search by Name

Interactive mode:
```bash
> search /name "MAERSK"
> search /name "EVER GIVEN" /output results.json
```

Traditional CLI:
```bash
# Search for vessels with "MAERSK" in the name
equasis search --name "MAERSK"

# Use tab completion for vessel name examples
equasis search --name <TAB>  # Shows examples like "EVER GIVEN", "MAERSK"

# Partial name search
equasis search --name "EVER"
```

#### Fleet Information

Interactive mode:
```bash
> fleet /company "MSC"
> fleet /company "MAERSK LINE" /output fleet.csv
```

Traditional CLI:
```bash
# Get fleet information for a company
equasis fleet --company "MAERSK LINE"

# Use tab completion for company examples
equasis fleet --company <TAB>  # Shows major shipping companies
```

### Tab Completion Examples

```bash
# Complete commands
equasis <TAB>                    # Shows: vessel, search, fleet

# Complete command-specific options
equasis vessel <TAB>             # Shows: --imo, --help, --username, etc.
equasis search <TAB>             # Shows: --name, --help, --username, etc.

# Complete with real examples
equasis vessel --imo <TAB>       # Shows real IMO numbers with vessel names
equasis fleet --company <TAB>    # Shows major shipping companies

# Complete output formats with descriptions
equasis --output <TAB>           # Shows: table, json, csv with descriptions
```

#### Different Output Formats

Interactive mode:
```bash
# Set default format
> format json
> vessel /imo 9074729

# Override format for one command
> vessel /imo 9074729 /format csv

# Save to file (format auto-detected)
> vessel /imo 9074729 /output vessel_data.json
> vessel /imo 9074729 /output vessel_data.csv
```

Traditional CLI:
```bash
# JSON output
equasis --output json vessel --imo 9074729

# CSV output
equasis --output csv vessel --imo 9074729

# Save to file
equasis --output json --output-file vessel_data.json vessel --imo 9074729
```

### Batch Processing

#### Built-in Batch Processing (Recommended)

**Vessel Batch Processing:**
```bash
# Process multiple IMO numbers directly
equasis vessel --imo 9074729 9632179 9839333 --output json

# Process from file with progress indicators
equasis vessel --imo-file fleet_imos.txt --progress --output csv --output-file batch_results.csv

# Continue on errors instead of stopping
equasis vessel --imo-file fleet_imos.txt --continue-on-error --progress
```

**Company Fleet Batch Processing:**
```bash
# Process multiple companies directly
equasis fleet --company "MSC" "MAERSK" "COSCO" --output json

# Process from file with progress indicators
equasis fleet --company-file shipping_companies.txt --progress --output csv --output-file fleet_analysis.csv

# Continue on errors instead of stopping
equasis fleet --company-file shipping_companies.txt --continue-on-error --progress
```

#### Manual Batch Processing (Legacy)

```bash
# Process multiple IMO numbers from a file (manual approach)
while read imo; do
    echo "Processing IMO: $imo"
    equasis vessel --imo "$imo" --output csv >> vessels.csv
    sleep 2  # Be respectful to the server
done < imo_list.txt
```

#### Integration with Other Tools

Traditional CLI works great with pipes:

```bash
# Use with jq for JSON processing
equasis --output json vessel --imo 9074729 | jq '.name'

# Pipe to grep for filtering
equasis search --name "CONTAINER" | grep "Singapore"

# Count results
equasis search --name "MAERSK" --output csv | wc -l

# Use tab completion with pipes
equasis vessel --imo <TAB>  # Select example, then continue with pipe
equasis vessel --imo 9074729 | head -5
```

Interactive mode is best for exploration, traditional CLI for scripting.

## Architecture & Data Collection

### Comprehensive Intelligence Strategy

The Equasis CLI uses a **3-request multi-tab strategy** to collect comprehensive vessel data:

1. **Ship Info Tab**: Management, classification, geographical data
2. **Inspections Tab**: PSC inspection history and detention records
3. **Ship History Tab**: Historical names, flags, and ownership changes

Each vessel lookup automatically:

- Authenticates with Equasis using your credentials
- Makes 3 targeted requests to different Equasis tabs
- Parses rich HTML data structures from each tab
- Merges all data into a comprehensive vessel profile
- Formats output with smart summarization

### Data Architecture

```
Single IMO Request → 3 Parallel Tab Requests → Comprehensive Profile

┌─────────────────┐    ┌──────────────┐    ┌─────────────────────┐
│  Ship Info Tab  │    │Inspections   │    │  Ship History Tab   │
│                 │    │Tab           │    │                     │
│ • Management    │    │              │    │ • Historical Names  │
│ • Classification│ → │ • PSC Records│ → │ • Historical Flags  │
│ • Geographical  │    │ • Detentions │    │ • Historical Owners │
│ • Flag Performance│    │ • Authorities│    │ • Name Changes     │
└─────────────────┘    └──────────────┘    └─────────────────────┘
         ↓                       ↓                        ↓
         └─────────────── Merge Data ──────────────┘
                              ↓
                    ┌─────────────────────┐
                    │ Complete Vessel     │
                    │ Intelligence Profile│
                    │                     │
                    │ 50+ Data Points     │
                    │ Across 9 Categories │
                    └─────────────────────┘
```

### Professional Package Structure

```
equasis-cli/
├── equasis_cli/              # Main package
│   ├── __init__.py          # Package initialization
│   ├── main.py              # CLI interface & argument parsing
│   ├── client.py            # EquasisClient & authentication
│   ├── parser.py            # HTML parser & data structures
│   └── formatter.py         # Output formatting
├── setup.py                 # Package distribution config
├── requirements.txt         # Dependencies
├── completions/             # Tab completion
│   └── equasis_completion.zsh
├── old_files/              # Backup of original code
└── .env                    # Credentials (not in git)
```

## Development

### Updated Project Structure

The tool now uses a professional package structure:

```
equasis-cli/
├── equasis_cli/                    # Main package directory
│   ├── __init__.py                # Package initialization & public API
│   ├── main.py                    # CLI interface & argument parsing
│   ├── client.py                  # EquasisClient & web scraping
│   ├── parser.py                  # Comprehensive HTML parser
│   └── formatter.py               # Output formatting (table/JSON/CSV)
├── setup.py                       # Package distribution configuration
├── requirements.txt               # Python dependencies
├── completions/                   # Tab completion scripts
│   └── equasis_completion.zsh     # Zsh completion (unchanged)
├── local/                         # Development and archive files
│   ├── archive/                   # Original monolithic code backup
│   ├── development/               # Intermediate development versions
│   └── debug/                     # HTML debug files and analysis tools
├── .env                          # Environment variables (not in git)
├── .env.example                  # Environment template
├── SESSION_SUMMARY.md            # Development session documentation
├── SOLUTION_SUMMARY.md           # Technical implementation notes
├── README.md                     # This file
└── MANIFEST.in                   # Package manifest
```

### Setting Up Development Environment

```bash
# Clone or download the project
cd ~/Projects/
git clone <repository-url> equasis-cli  # or create directory manually
cd equasis-cli

# Install in editable mode with pipx (recommended)
pipx install -e .

# Or use traditional virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### Making Changes

With the new package structure, changes to individual modules are automatically available with pipx editable installation:

```bash
# Code changes in equasis_cli/*.py files (automatic)
# No action needed - changes are immediately available

# After modifying setup.py, requirements.txt, or package structure
cd ~/Projects/equasis-cli
pipx install -e . --force

# Alternative: upgrade command
pipx upgrade equasis-cli
```

### Module-Specific Development

```bash
# Test individual components
cd ~/Projects/equasis-cli

# Test parser independently
python3 -c "from equasis_cli.parser import EquasisParser; print('Parser loaded successfully')"

# Test client authentication
python3 -c "from equasis_cli.client import EquasisClient; print('Client loaded successfully')"

# Test output formatting
python3 -c "from equasis_cli.formatter import OutputFormatter; print('Formatter loaded successfully')"
```

### Package Management

```bash
# List installed pipx packages
pipx list

# Show package details
pipx list --include-deps

# Uninstall if needed
pipx uninstall equasis-cli

# Reinstall from scratch
pipx install -e . --force
```

### Debugging

Enable debug logging by modifying the logging level:

```python
logging.basicConfig(level=logging.DEBUG)
```

Or set environment variable:

```bash
export PYTHONPATH=$(pwd)
python3 -c "import logging; logging.basicConfig(level=logging.DEBUG)" equasis_cli.py vessel --imo 9074729
```

### Testing HTML Parsing

Since Equasis HTML structure may change, you can test parsing with saved HTML:

```python
def test_parsing():
    with open("sample_vessel_page.html", "r") as f:
        html = f.read()

    # Import the client class
    from equasis_cli import EquasisClient

    client = EquasisClient("", "")
    result = client._parse_vessel_info(html, "1234567")
    print(result)


if __name__ == "__main__":
    test_parsing()
```

### Extending Functionality

The modular design makes it easy to add features:

1. **Add new search types**: Extend the argument parser and add methods to `EquasisClient`
2. **Create new formatters**: Add methods to `OutputFormatter` class
3. **Add data validation**: Create validation functions for input data
4. **Implement caching**: Add caching layer to reduce redundant requests

## Network Resilience & Retry Logic

equasis-cli includes enterprise-grade retry functionality to handle network issues and server-side problems gracefully.

### Automatic Retry Features

- **Exponential Backoff**: Delays increase exponentially between retry attempts (1s, 2s, 4s, etc.)
- **Jitter**: Random variance added to prevent "thundering herd" problems
- **Smart Error Classification**: Distinguishes between retryable and non-retryable errors
- **Configurable Parameters**: Customizable retry limits and timing

### Retried Error Types

**Network Errors (Always Retried):**
- Connection timeouts and failures
- DNS resolution failures
- Network interruptions
- Remote connection drops

**HTTP Errors (Conditionally Retried):**
- `429` Too Many Requests
- `500` Internal Server Error
- `502` Bad Gateway
- `503` Service Unavailable
- `504` Gateway Timeout
- CloudFlare error codes (520-524)

**Non-Retried Errors:**
- `401` Unauthorized (credential issues)
- `404` Not Found (vessel doesn't exist)
- `400` Bad Request (malformed request)

### Default Retry Configuration

- **Maximum Retries**: 3 attempts per request
- **Base Delay**: 1 second
- **Maximum Delay**: 60 seconds
- **Backoff Multiplier**: 2.0 (exponential)
- **Jitter**: ±25% randomization

Example retry sequence for a connection error:
```
Attempt 1: Immediate
Attempt 2: ~1s delay
Attempt 3: ~2s delay
Attempt 4: ~4s delay
```

### Viewing Retry Activity

Enable debug logging to see retry attempts:
```bash
equasis --debug vessel --imo 9074729
```

## Troubleshooting

### Common Issues

#### Command Not Found

```
zsh: command not found: equasis
```

**Solutions:**

1. Ensure pipx installation was successful: `pipx list`
2. Check that pipx is in your PATH: `pipx ensurepath` then restart terminal
3. Verify the package is installed: `pipx list | grep equasis`
4. If using virtual environment instead of pipx, ensure it's activated

#### Tab Completion Not Working

**Solutions:**

1. Ensure completion script exists: `ls ~/.zsh/completions/_equasis`
2. Check completion script is properly formatted (no syntax errors)
3. Verify your `.zshrc` has completion initialization:
   ```bash
   grep -E "(fpath|compinit)" ~/.zshrc
   ```
   Should show:
   ```bash
   fpath=(~/.zsh/completions $fpath)
   autoload -Uz compinit && compinit
   ```
4. Clear completion cache and reload:
   ```bash
   rm -f ~/.zcompdump*
   source ~/.zshrc
   ```
5. Test with a simple completion first: `equasis <TAB>`

#### Completion Shows Wrong Options

**Solutions:**

1. Ensure you're using spaces correctly: `equasis vessel --imo <TAB>` (space before TAB)
2. Clear old cached completions: `unfunction _equasis 2>/dev/null && autoload -Uz compinit && compinit`
3. Reinstall completion script: `cp ~/Projects/equasis-cli/completions/equasis_completion.zsh ~/.zsh/completions/_equasis`

#### Connection Issues

```
Error: Failed to access login page: 500
```

**Solutions:**

1. Check your internet connection
2. Verify Equasis website is accessible (equasis.org)
3. Try again later (server may be temporarily unavailable)
4. Check if you're behind a firewall or proxy

#### Parsing Errors

```
Error: No vessel found with IMO: 1234567
```

**Solutions:**

1. Verify the IMO number is correct and exists in Equasis
2. The HTML parsing may need adjustment for current Equasis structure
3. Enable debug logging to see raw HTML response
4. Check if Equasis has changed their page structure

#### Python Environment Issues

```
ModuleNotFoundError: No module named 'requests'
```

**Solutions:**

1. Ensure virtual environment is activated
2. Reinstall requirements: `pip install -r requirements.txt`
3. Check Python version compatibility

### Rate Limiting

If you encounter rate limiting:

1. Increase delay between requests in the code
2. Reduce concurrent operations
3. Implement exponential backoff
4. Consider contacting Equasis for API access

### Debug Mode

Enable comprehensive logging:

```bash
PYTHONPATH=$(pwd) python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
exec(open('equasis_cli.py').read())
" vessel --imo 9074729
```

## Legal and Compliance

### Terms of Service

- This tool accesses publicly available data from Equasis
- Users must comply with Equasis Terms of Service
- Respect rate limits and server resources
- Use for legitimate maritime research and safety purposes only

### Best Practices

- **Rate Limiting**: Don't overload Equasis servers
- **Data Usage**: Use retrieved data responsibly
- **Authentication**: Keep credentials secure
- **Compliance**: Follow maritime industry regulations

### Disclaimer

- This tool is for educational and research purposes
- Users are responsible for compliance with applicable laws
- No warranty is provided for data accuracy or availability
- The tool may break if Equasis changes their website structure

## Contributing

Contributions are welcome! Please follow these guidelines:

### Reporting Issues

1. Check existing issues before creating new ones
2. Provide detailed error messages and steps to reproduce
3. Include your Python version and operating system
4. Don't include credentials in issue reports

### Submitting Changes

1. Fork the repository
2. Create a feature branch
3. Make your changes with appropriate tests
4. Update documentation as needed
5. Submit a pull request with clear description

### Development Guidelines

- Follow PEP 8 style guidelines
- Add type hints for new functions
- Include docstrings for public methods
- Test changes with different Equasis data
- Update README for new features

## License

equasis-cli is source-available software licensed under the
[PolyForm Noncommercial License 1.0.0](LICENSE).

- Free for personal, research, educational, nonprofit, and government use
- Journalists and nonprofit researchers have an additional permission, described in [LICENSING.md](LICENSING.md)
- Commercial use requires a separate license: contact [rhinonix.github.exclaim769@slmail.me](mailto:rhinonix.github.exclaim769@slmail.me)

Releases up to and including v2.0.0 remain available under the
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
license.

---

**Note**: This tool interfaces with Equasis through web scraping. The HTML parsing may need updates if Equasis changes their website structure. Users should monitor for any changes and update the parsing logic accordingly.
