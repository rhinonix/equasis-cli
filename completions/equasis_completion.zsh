#compdef equasis

_equasis() {
    local context state state_descr line
    typeset -A opt_args

    _arguments -C \
        '(--help -h)'{--help,-h}'[Show help message]' \
        '--username[Equasis username]:username:' \
        '--password[Equasis password]:password:' \
        '--output[Output format]:format:_equasis_output_formats' \
        '--output-file[Output file path]:file:_files' \
        '1: :_equasis_commands' \
        '*:: :->command_args' \
    && return 0

    case $state in
        command_args)
            case $words[1] in
                vessel)
                    _equasis_vessel_args
                    ;;
                search)
                    _equasis_search_args
                    ;;
                fleet)
                    _equasis_fleet_args
                    ;;
            esac
            ;;
    esac
}

_equasis_commands() {
    local -a commands=(
        'vessel:Get detailed vessel information by IMO number'
        'search:Search for vessels by name (supports partial matches)'
        'fleet:Get fleet information for a shipping company'
    )
    _describe 'equasis commands' commands
}

_equasis_vessel_args() {
    _arguments \
        '(--help -h)'{--help,-h}'[Show help for vessel command]' \
        '--imo[IMO number (7 digits)]:imo_number:_equasis_imo_examples' \
        '--username[Equasis username]:username:' \
        '--password[Equasis password]:password:' \
        '--output[Output format]:format:_equasis_output_formats' \
        '--output-file[Output file path]:file:_files'
}

_equasis_search_args() {
    _arguments \
        '(--help -h)'{--help,-h}'[Show help for search command]' \
        '--name[Vessel name (partial match supported)]:vessel_name:_equasis_vessel_examples' \
        '--username[Equasis username]:username:' \
        '--password[Equasis password]:password:' \
        '--output[Output format]:format:_equasis_output_formats' \
        '--output-file[Output file path]:file:_files'
}

_equasis_fleet_args() {
    _arguments \
        '(--help -h)'{--help,-h}'[Show help for fleet command]' \
        '--company[Company name or identifier]:company_name:_equasis_company_examples' \
        '--username[Equasis username]:username:' \
        '--password[Equasis password]:password:' \
        '--output[Output format]:format:_equasis_output_formats' \
        '--output-file[Output file path]:file:_files'
}

_equasis_output_formats() {
    local -a formats=(
        'table:Human-readable table format (default)'
        'json:JSON format for programmatic use'
        'csv:Comma-separated values for spreadsheets'
    )
    _describe 'output formats' formats
}

_equasis_imo_examples() {
    # Provide actual example IMO numbers that users can select
    local -a examples=(
        '9074729:EVER GIVEN (container ship)'
        '9321483:MSC GULSUN (container ship)'
        '9516579:HMM ALGECIRAS (container ship)'
        '9811000:SYMPHONY OF THE SEAS (cruise ship)'
        '9398538:ALLURE OF THE SEAS (cruise ship)'
    )
    _describe 'example IMO numbers' examples
    # Also allow typing custom numbers
    _message 'or enter 7-digit IMO number'
}

_equasis_vessel_examples() {
    # Provide example vessel names
    local -a examples=(
        '"EVER GIVEN":Famous container ship'
        '"MSC GULSUN":Large container vessel'
        '"MAERSK":Search all Maersk vessels'
        '"COSCO":Search all COSCO vessels'
        '"SYMPHONY":Search Symphony vessels'
    )
    _describe 'example vessel names' examples
    _message 'or enter vessel name (partial matches supported)'
}

_equasis_company_examples() {
    # Provide common shipping companies as actual completions
    local -a companies=(
        '"MAERSK LINE":A.P. Moller - Maersk'
        '"MSC":Mediterranean Shipping Company'
        '"COSCO SHIPPING":China COSCO Shipping'
        '"CMA CGM":CMA CGM Group'
        '"HAPAG-LLOYD":Hapag-Lloyd'
        '"EVERGREEN MARINE":Evergreen Marine'
        '"YANG MING":Yang Ming Marine Transport'
        '"HMM":Hyundai Merchant Marine'
        '"ONE":Ocean Network Express'
        '"ZIM":ZIM Integrated Shipping Services'
    )
    _describe 'major shipping companies' companies
    _message 'or enter company name'
}

_equasis "$@"
