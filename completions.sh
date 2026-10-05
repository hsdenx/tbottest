_newbot()
{
    local cur prev words cword
    _init_completion || return

    # bash looks up the completion before it expands an alias, so replace
    # an alias in the first word by its definition, e.g. tbBOARDNAME from
    # setup.sh by newtbot_starter.py @.../argsBOARDNAME, to see its
    # argumentfiles
    local depth=0
    local expansion=()
    while [[ -n "${BASH_ALIASES[${words[0]}]+set}" && $depth -lt 10 ]]; do
        read -r -a expansion <<< "${BASH_ALIASES[${words[0]}]}"
        words=("${expansion[@]}" "${words[@]:1}")
        cword=$((cword + ${#expansion[@]} - 1))
        depth=$((depth + 1))
    done

    # expand a leading shell variable, e.g. $conint from setup.sh, and put
    # it back into the completions at the end
    local varprefix=""
    local varvalue=""
    if [[ "$cur" =~ ^\$([A-Za-z_][A-Za-z0-9_]*)(.*)$ ]]; then
        varprefix="\$${BASH_REMATCH[1]}"
        varvalue="${!BASH_REMATCH[1]}"
        cur="${varvalue}${BASH_REMATCH[2]}"
    fi

    local index=0
    local path_args=()
    local argfiles=""
    local curdir="$PWD"
    local workdir="${curdir}"
    while [[ $index -lt ${#words[@]} ]]; do
        local current_word="${words[$index]}"

        if [[ "$current_word" == -C ]]; then
            local index=$((index + 1))
            [[ "${words[$index]}" == "=" ]] && index=$((index + 1))
            local path="${words[$index]}"
            __expand_tilde_by_ref path
            path_args+=("$current_word" "$path")
            workdir="$path"
        fi

	# save all arguments which start with @
	# this arguments are argumentfiles, which contain tbot flags
	# sw we need to call later tbot with this argumentfiles so
	# it get the correct arguments
        if [[ "$current_word" == *"@"* ]]; then
		argfiles="${argfiles} ${current_word}"
	fi

        local index=$((index + 1))
    done

    if [[ "$prev" == @(-b|-l|--board|--lab|-c|--config) ]]; then
        compopt -o nospace
        mapfile -t COMPREPLY < <(python3 ${workdir}/tbottest/newtbot_starter.py -C "${workdir}" ${argfiles} --complete-module "$cur")
        _newbot_varprefix
        return
    fi

    if [[ "$prev" == -C ]]; then
        _filedir -d
        return
    fi

    if [[ "$cur" == -* ]]; then
        mapfile -t COMPREPLY < <(compgen -W '-h -C -c -f -v -q
            --help
            --config
            --version
        ' -- "$cur")
        return
    fi

    if [[ "$cur" == \@* ]]; then
        cur="${cur:1}"
        _filedir

        # If the completion is a directory, append a / and prevent a space
        # being added.
        for i in "${!COMPREPLY[@]}"; do
            if [[ -d "${COMPREPLY[$i]}" ]]; then
                COMPREPLY[$i]+=/
                compopt -o nospace
            fi
        done

        COMPREPLY=("${COMPREPLY[@]/#/@}")
        return
    fi

    compopt -o nospace
    mapfile -t COMPREPLY < <(python3 ${workdir}/tbottest/newtbot_starter.py -C "${workdir}" ${argfiles} --complete-testcase "$cur")
    _newbot_varprefix
} &&
complete -F _newbot newbot.py
complete -F _newbot newtbot_starter.py

# replace the value of the variable _newbot expanded by its name again
_newbot_varprefix()
{
    if [[ -n "$varprefix" ]]; then
        COMPREPLY=("${COMPREPLY[@]/#"${varvalue}"/${varprefix}}")
    fi
}

# complete every alias that starts newtbot_starter.py, e.g. the ones
# setup.sh defines; setup.sh calls this again when it is sourced after
# this file
_newbot_aliases()
{
    local name first depth
    for name in "${!BASH_ALIASES[@]}"; do
        first="$name"
        depth=0
        while [[ -n "${BASH_ALIASES[$first]+set}" && $depth -lt 10 ]]; do
            read -r first _ <<< "${BASH_ALIASES[$first]}"
            depth=$((depth + 1))
        done
        if [[ "${first##*/}" == newtbot_starter.py ]]; then
            complete -F _newbot "$name"
        fi
    done
}
_newbot_aliases
