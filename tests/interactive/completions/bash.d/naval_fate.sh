#!/usr/bin/env bash

_naval_fate_complete() {
  node_6() { optional 7; }
node_1() { sequence 2 3 4 5 6; }
node_8() { sequence 9 4 5; }
node_0() { choice 1 8; }
  node_2() { arg "<name>"; }
node_3() { cmd "move"; }
node_4() { arg "<x>"; }
node_5() { arg "<y>"; }
node_7() { opt "--speed"; }
node_9() { cmd "shoot"; }

  sequence() {
    local initial_left=("${left[@]}")
    local node_idx
    for node_idx in "$@"; do
      if ! "node_$node_idx"; then
        left=("${initial_left[@]}")
        return 1
      fi
    done
    left=("${initial_left[@]}")
    for node_idx in "$@"; do
      "node_$node_idx"
    done
    return 0
  }

  choice() {
    local initial_left=("${left[@]}")
    local best_match_idx
    local match_count
    local node_idx
    for node_idx in "$@"; do
      if "node_$node_idx"; then
        if [[ -z $match_count || ${#left[@]} -lt $match_count ]]; then
          best_match_idx=$node_idx
          match_count=${#left[@]}
        fi
      fi
      left=("${initial_left[@]}")
    done
    if [[ -n $best_match_idx ]]; then
      "node_$best_match_idx"
      return 0
    fi
    left=("${initial_left[@]}")
    return 1
  }

  optional() {
    local node_idx
    for node_idx in "$@"; do
      "node_$node_idx"
    done
    return 0
  }

  repeatable() {
    local i=0
    local prev=${#left[@]}
    while "node_$1"; do
      ((i++)) || true
      [[ $prev -eq ${#left[@]} ]] && break
      prev=${#left[@]}
    done
    if [[ $i -ge 1 ]]; then
      return 0
    fi
    return 1
  }

  _command() {
    local i
    local name=${2:-$1}
    for i in "${!left[@]}"; do
      local l=${left[$i]}
      if [[ ${parsed_params[$l]} = 'a' ]]; then
        if [[ ${parsed_values[$l]} != "$name" ]]; then
          return 1
        fi
        left=("${left[@]:0:$i}" "${left[@]:((i+1))}")
        if [[ $3 = true ]]; then
          eval "((var_$1++)) || true"
        else
          eval "var_$1=true"
        fi
        return 0
      fi
    done
    return 1
  }

  switch() {
    local i
    for i in "${!left[@]}"; do
      local l=${left[$i]}
      if [[ ${parsed_params[$l]} = "$2" ]]; then
        left=("${left[@]:0:$i}" "${left[@]:((i+1))}")
        if [[ $3 = true ]]; then
          eval "((var_$1++))" || true
        else
          eval "var_$1=true"
        fi
        return 0
      fi
    done
    return 1
  }

  value() {
    local i
    for i in "${!left[@]}"; do
      local l=${left[$i]}
      if [[ ${parsed_params[$l]} = "$2" ]]; then
        left=("${left[@]:0:$i}" "${left[@]:((i+1))}")
        local value
        value=$(printf -- "%q" "${parsed_values[$l]}")
        if [[ $3 = true ]]; then
          eval "var_$1+=($value)"
        else
          eval "var_$1=$value"
        fi
        return 0
      fi
    done
    return 1
  }

  local compopt_available
  if type compopt &>/dev/null; then
    compopt_available=true
    compopt +o default +o nospace
    COMPREPLY=()
  else
    compopt_available=false
    COMPREPLY=('')
  fi

  local cur="${COMP_WORDS[COMP_CWORD]}"
  echo ''
  echo $cur
  echo ${COMP_WORDS[*]}
  echo $COMP_CWORD
  # compgen -W "$long_opts" -- "$cur"

}

complete -o default -F _naval_fate_complete naval_fate
