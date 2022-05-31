
__unikube_complete_flags_app() {
    if [[ $com == $prev ]]; then
        opts="${opts} --help"
    else
        case "$prev" in

        (env)
            opts="${opts} --init --organization --project --deck --help"
            ;;

        (exec)
            opts="${opts} --organization --project --deck --help"
            ;;

        (info)
            opts="${opts} --organization --project --deck --help"
            ;;

        (list)
            opts="${opts} --organization --project --deck --help"
            ;;

        (logs)
            opts="${opts} --container --organization --project --deck --follow --help"
            ;;

        (shell)
            opts="${opts} --organization --project --deck --container --help"
            ;;

        (switch)
            opts="${opts} --organization --project --deck --deployment --unikubefile --no-build --help"
            ;;

        (update)
            opts="${opts} --organization --project --deck --help"
            ;;
        esac
    fi
}


__unikube_complete_flags_auth() {
    if [[ $com == $prev ]]; then
        opts="${opts} --help"
    else
        case "$prev" in

        (login)
            opts="${opts} --email --password --help"
            ;;

        (logout)
            opts="${opts} --help"
            ;;

        (status)
            opts="${opts} --token --help"
            ;;
        esac
    fi
}


__unikube_complete_flags_context() {
    if [[ $com == $prev ]]; then
        opts="${opts} --help"
    else
        case "$prev" in

        (remove)
            opts="${opts} --organization --project --deck --help"
            ;;

        (set)
            opts="${opts} --organization --project --deck --help"
            ;;

        (show)
            opts="${opts} --help"
            ;;
        esac
    fi
}


__unikube_complete_flags_deck() {
    if [[ $com == $prev ]]; then
        opts="${opts} --help"
    else
        case "$prev" in

        (info)
            opts="${opts} --organization --project --help"
            ;;

        (ingress)
            opts="${opts} --organization --project --help"
            ;;

        (install)
            opts="${opts} --organization --project --help"
            ;;

        (list)
            opts="${opts} --organization --project --help"
            ;;

        (uninstall)
            opts="${opts} --organization --project --help"
            ;;
        esac
    fi
}


__unikube_complete_flags_install() {
    opts="${opts} --organization --project --help"
}


__unikube_complete_flags_login() {
    opts="${opts} --email --password --help"
}


__unikube_complete_flags_logout() {
    opts="${opts} --help"
}


__unikube_complete_flags_orga() {
    if [[ $com == $prev ]]; then
        opts="${opts} --help"
    else
        case "$prev" in

        (info)
            opts="${opts} --help"
            ;;

        (list)
            opts="${opts} --help"
            ;;
        esac
    fi
}


__unikube_complete_flags_project() {
    if [[ $com == $prev ]]; then
        opts="${opts} --help"
    else
        case "$prev" in

        (delete)
            opts="${opts} --organization --help"
            ;;

        (down)
            opts="${opts} --organization --help"
            ;;

        (info)
            opts="${opts} --organization --help"
            ;;

        (list)
            opts="${opts} --organization --help"
            ;;

        (prune)
            opts="${opts} --help"
            ;;

        (up)
            opts="${opts} --organization --ingress --provider --workers --help"
            ;;
        esac
    fi
}


__unikube_complete_flags_ps() {
    opts="${opts} --help"
}


__unikube_complete_flags_shell() {
    opts="${opts} --organization --project --deck --container --help"
}


__unikube_complete_flags_system() {
    if [[ $com == $prev ]]; then
        opts="${opts} --help"
    else
        case "$prev" in

        (completion)
            opts="${opts} --help"
            ;;

        (install)
            opts="${opts} --reinstall --help"
            ;;

        (verify)
            opts="${opts} --verbose --help"
            ;;
        esac
    fi
}


__unikube_complete_flags_up() {
    opts="${opts} --organization --ingress --provider --workers --help"
}


__unikube_complete_flags_version() {
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

            (app)
                __unikube_complete_flags_app
                ;;

            (auth)
                __unikube_complete_flags_auth
                ;;

            (context)
                __unikube_complete_flags_context
                ;;

            (deck)
                __unikube_complete_flags_deck
                ;;

            (install)
                __unikube_complete_flags_install
                ;;

            (login)
                __unikube_complete_flags_login
                ;;

            (logout)
                __unikube_complete_flags_logout
                ;;

            (orga)
                __unikube_complete_flags_orga
                ;;

            (project)
                __unikube_complete_flags_project
                ;;

            (ps)
                __unikube_complete_flags_ps
                ;;

            (shell)
                __unikube_complete_flags_shell
                ;;

            (system)
                __unikube_complete_flags_system
                ;;

            (up)
                __unikube_complete_flags_up
                ;;

            (version)
                __unikube_complete_flags_version
                ;;
        esac
        COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
        __ltrim_colon_completions "$cur"
        return 0;
    fi

    if [[ $prev == $com ]]; then
        case "$com" in
            
    (app)
        coms="env exec info list logs shell switch update"
        COMPREPLY=($(compgen -W "${coms}" -- ${cur}))
        __ltrim_colon_completions "$cur"
        return 0;
        ;;
    

    (auth)
        coms="login logout status"
        COMPREPLY=($(compgen -W "${coms}" -- ${cur}))
        __ltrim_colon_completions "$cur"
        return 0;
        ;;
    

    (context)
        coms="remove set show"
        COMPREPLY=($(compgen -W "${coms}" -- ${cur}))
        __ltrim_colon_completions "$cur"
        return 0;
        ;;
    

    (deck)
        coms="info ingress install list uninstall"
        COMPREPLY=($(compgen -W "${coms}" -- ${cur}))
        __ltrim_colon_completions "$cur"
        return 0;
        ;;
    

    (orga)
        coms="info list"
        COMPREPLY=($(compgen -W "${coms}" -- ${cur}))
        __ltrim_colon_completions "$cur"
        return 0;
        ;;
    

    (project)
        coms="delete down info list prune up"
        COMPREPLY=($(compgen -W "${coms}" -- ${cur}))
        __ltrim_colon_completions "$cur"
        return 0;
        ;;
    

    (run)
        coms=$(docker ps --format '{{ .Names }}' | tr '\n' ' ')
        COMPREPLY=($(compgen -W "${coms}" -- ${cur}))
        __ltrim_colon_completions "$cur"
        return 0;
        ;;
    
        esac
    fi

    # completing for a command
    if [[ $cur == $com ]]; then
        coms="run"
        COMPREPLY=($(compgen -W "${coms}" -- ${cur}))
        __ltrim_colon_completions "$cur"
        return 0
    fi
}
complete -o default -F _gefyra_complete gefyra
