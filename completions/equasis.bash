# bash completion for equasis-cli. Source this file from ~/.bashrc.

_equasis() {
    local cur prev words cword
    _init_completion 2>/dev/null || {
        cur="${COMP_WORDS[COMP_CWORD]}"
        prev="${COMP_WORDS[COMP_CWORD-1]}"
        words=("${COMP_WORDS[@]}")
        cword=$COMP_CWORD
    }

    local commands="vessel search fleet configure cache interactive"
    local common="--format --output-file --quiet --no-color --username --password --delay --debug --save-html --no-cache --refresh --help"

    case "$prev" in
        -f|--format|--output)
            COMPREPLY=($(compgen -W "table json jsonl csv" -- "$cur"))
            return
            ;;
        -o|--output-file|--imo-file|--company-file)
            COMPREPLY=($(compgen -f -- "$cur"))
            return
            ;;
        --save-html)
            COMPREPLY=($(compgen -d -- "$cur"))
            return
            ;;
        --type)
            COMPREPLY=($(compgen -W "all ships companies" -- "$cur"))
            return
            ;;
    esac

    local command="" word
    for word in "${words[@]:1:cword-1}"; do
        case "$word" in
            vessel|search|fleet|configure|cache|interactive) command="$word"; break ;;
        esac
    done

    local options
    case "$command" in
        "") options="$commands --version --interactive $common" ;;
        vessel) options="--imo-file --fail-fast $common" ;;
        search) options="--imo --mmsi --call-sign --type --max-pages --all-pages $common" ;;
        fleet) options="--company-id --company-file --first-match --max-pages --fail-fast $common" ;;
        configure) options="--setup --show --test --clear $common" ;;
        cache) options="info clear $common" ;;
        interactive) options="" ;;
    esac
    COMPREPLY=($(compgen -W "$options" -- "$cur"))
}

complete -F _equasis equasis
