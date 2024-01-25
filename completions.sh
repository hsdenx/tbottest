_newbot()
{
    local cur prev words
    _init_completion || return

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
} &&
complete -F _newbot newbot.py
complete -F _newbot newtbot_starter.py
