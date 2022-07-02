
__gefyra_complete_flags_up() {
    opts="${opts} --endpoint --operator --stowaway --carrier --cargo --registry --help"
}

__gefyra_complete_flags_run() {
    opts="${opts} --image --name --command --namespace --env --volume --env-from --help"
}

__gefyra_complete_flags_bridge() {
    opts="${opts} --name --container-name --bridge-name --port --namespace --no-probe-handling --help --deployment --statefulset --pod --container"
}

__gefyra_complete_flags_unbridge() {
    opts="${opts} --name --all --help"
}

__gefyra_complete_flags_list() {
    opts="${opts} --containers --bridges --help"
}

__gefyra_complete_flags_version() {
    opts="${opts} --no-check"
}

__gefyra_complete_flags_noargs() {
    opts="${opts} --help"
}


_gefyra_complete()
{
    local cur script coms opts com
    COMPREPLY=()
    _get_comp_words_by_ref -n : cur prev words
    # for an alias, get the real script behind it
    if [[ $(type -t ${words[0]}) == "alias" ]]; then
        script=$(alias ${words[0]} | sed -E "s/alias ${words[0]}='(.*)'/\1/")
    else
        script=${words[0]}
    fi
    # lookup for command
    for word in ${words[@]:1}; do
        if [[ $word != -* ]]; then
            com=$word
            break
        fi
    done

    # completing for an option
    if [[ ${cur} == --* ]] ; then
        opts=""
        case "$com" in
            (up)
                __gefyra_complete_flags_up
                ;;

            (run)
                __gefyra_complete_flags_run
                ;;

            (bridge)
                __gefyra_complete_flags_bridge
                ;;

            (unbridge)
                __gefyra_complete_flags_unbridge
                ;;

            (list)
                __gefyra_complete_flags_list
                ;;

            (version)
                __gefyra_complete_flags_version
                ;;

            (down)
                __gefyra_complete_flags_noargs
                ;;

            (check)
                __gefyra_complete_flags_noargs
                ;;
        esac
        COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
        __ltrim_colon_completions "$cur"
        return 0;
    fi

    if [[ $prev != $com ]]; then
        case "$com" in
        (bridge)
          case $prev in
          (--name)
            coms=$(docker ps --format '{{ .Names }}' | tr '\n' ' ')
            COMPREPLY=($(compgen -W "${coms}" -- ${cur}))
            __ltrim_colon_completions "$cur"
            return 0;
            ;;
          (--namespace)
            coms=$(kubectl get ns --template '{{range .items}}{{.metadata.name}}{{"\n"}}{{end}}')
            COMPREPLY=($(compgen -W "${coms}" -- ${cur}))
            __ltrim_colon_completions "$cur"
            return 0;
            ;;
          esac
        ;;
        (run)
          case $prev in
          (--image)
            coms=$(docker image ls --format '{{ .Repository }}' | tr '\n' ' ')
            COMPREPLY=($(compgen -W "${coms}" -- ${cur}))
            __ltrim_colon_completions "$cur"
            return 0;
            ;;

          (--namespace)
            coms=$(kubectl get ns --template '{{range .items}}{{.metadata.name}}{{"\n"}}{{end}}')
            COMPREPLY=($(compgen -W "${coms}" -- ${cur}))
            __ltrim_colon_completions "$cur"
            return 0;
            ;;
          esac
        ;;
        esac
    fi

    # completing for a command
    if [[ $cur == $com ]]; then
        coms="up run bridge unbridge version check list down"
        COMPREPLY=($(compgen -W "${coms}" -- ${cur}))
        __ltrim_colon_completions "$cur"
        return 0
    fi
}
complete -o default -F _gefyra_complete gefyra
