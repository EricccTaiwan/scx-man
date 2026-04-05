# Bash completion for scx-man
_scx_man_completion() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    opts="--generate --list --help -h"

    if [[ "${cur}" == -* ]]; then
        COMPREPLY=( $(compgen -W "${opts}" -- "${cur}") )
        return 0
    fi

    if [[ "${prev}" == "--generate" ]]; then
        compopt -o dirnames
        COMPREPLY=( $(compgen -d -- "${cur}") )
        return 0
    fi

    # Complete function names (hardcoded for speed - for-7.1)
    local functions="scx \
        ops.cpu_acquire ops.cpu_offline ops.cpu_online ops.cpu_release \
        ops.core_sched_before ops.dequeue ops.disable ops.dispatch \
        ops.dispatch_max_batch ops.dump ops.dump_cpu ops.dump_task \
        ops.enable ops.enqueue ops.exit ops.exit_dump_len ops.flags \
        ops.hotplug_seq ops.init ops.init_task ops.keep_preempt_ops \
        ops.name ops.quiescent ops.running ops.runnable ops.select_cpu \
        ops.set_cpumask ops.set_weight ops.stopping ops.sub_cgroup_id \
        ops.tick ops.timeout_ms ops.update_idle ops.yield \
        bpf_iter_scx_dsq_destroy bpf_iter_scx_dsq_new bpf_iter_scx_dsq_next \
        scx_bpf_consume_task scx_bpf_cpuperf_cap scx_bpf_cpuperf_cur \
        scx_bpf_cpuperf_set scx_bpf_create_dsq scx_bpf_cpu_curr \
        scx_bpf_destroy_dsq scx_bpf_dispatch_cancel scx_bpf_dispatch_nr_slots \
        scx_bpf_dsq_insert scx_bpf_dsq_insert_vtime scx_bpf_dsq_move \
        scx_bpf_dsq_move_set_slice scx_bpf_dsq_move_set_vtime \
        scx_bpf_dsq_move_to_local scx_bpf_dsq_move_to_local___v2 \
        scx_bpf_dsq_move_vtime scx_bpf_dsq_nr_queued scx_bpf_dsq_peek \
        scx_bpf_dsq_reenq scx_bpf_dump_bstr scx_bpf_error_bstr \
        scx_bpf_events scx_bpf_exit_bstr scx_bpf_get_idle_cpumask \
        scx_bpf_get_idle_cpumask_node scx_bpf_get_idle_smtmask \
        scx_bpf_get_idle_smtmask_node scx_bpf_get_online_cpumask \
        scx_bpf_get_possible_cpumask scx_bpf_kick_cpu scx_bpf_locked_rq \
        scx_bpf_now scx_bpf_nr_cpu_ids scx_bpf_nr_node_ids \
        scx_bpf_pick_any_cpu scx_bpf_pick_any_cpu_node scx_bpf_pick_idle_cpu \
        scx_bpf_pick_idle_cpu_node scx_bpf_put_cpumask scx_bpf_reenqueue_local \
        scx_bpf_reenqueue_local___v2 scx_bpf_select_cpu_and \
        scx_bpf_select_cpu_dfl scx_bpf_sub_dispatch scx_bpf_task_cgroup \
        scx_bpf_task_cpu scx_bpf_task_running scx_bpf_task_set_dsq_vtime \
        scx_bpf_task_set_slice scx_bpf_test_and_clear_cpu_idle"

    COMPREPLY=( $(compgen -W "${functions}" -- "${cur}") )

    return 0
}

complete -F _scx_man_completion scx-man

# Bash completion for "man scx_*" and "man ops.*"
_scx_man_man_completion() {
    local cur prev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    local scx_pages="scx \
        ops.cpu_acquire ops.cpu_offline ops.cpu_online ops.cpu_release \
        ops.core_sched_before ops.dequeue ops.disable ops.dispatch \
        ops.dispatch_max_batch ops.dump ops.dump_cpu ops.dump_task \
        ops.enable ops.enqueue ops.exit ops.exit_dump_len ops.flags \
        ops.hotplug_seq ops.init ops.init_task ops.keep_preempt_ops \
        ops.name ops.quiescent ops.running ops.runnable ops.select_cpu \
        ops.set_cpumask ops.set_weight ops.stopping ops.sub_cgroup_id \
        ops.tick ops.timeout_ms ops.update_idle ops.yield \
        bpf_iter_scx_dsq_destroy bpf_iter_scx_dsq_new bpf_iter_scx_dsq_next \
        scx_bpf_consume_task scx_bpf_cpuperf_cap scx_bpf_cpuperf_cur \
        scx_bpf_cpuperf_set scx_bpf_create_dsq scx_bpf_cpu_curr \
        scx_bpf_destroy_dsq scx_bpf_dispatch_cancel scx_bpf_dispatch_nr_slots \
        scx_bpf_dsq_insert scx_bpf_dsq_insert_vtime scx_bpf_dsq_move \
        scx_bpf_dsq_move_set_slice scx_bpf_dsq_move_set_vtime \
        scx_bpf_dsq_move_to_local scx_bpf_dsq_move_to_local___v2 \
        scx_bpf_dsq_move_vtime scx_bpf_dsq_nr_queued scx_bpf_dsq_peek \
        scx_bpf_dsq_reenq scx_bpf_dump_bstr scx_bpf_error_bstr \
        scx_bpf_events scx_bpf_exit_bstr scx_bpf_get_idle_cpumask \
        scx_bpf_get_idle_cpumask_node scx_bpf_get_idle_smtmask \
        scx_bpf_get_idle_smtmask_node scx_bpf_get_online_cpumask \
        scx_bpf_get_possible_cpumask scx_bpf_kick_cpu scx_bpf_locked_rq \
        scx_bpf_now scx_bpf_nr_cpu_ids scx_bpf_nr_node_ids \
        scx_bpf_pick_any_cpu scx_bpf_pick_any_cpu_node scx_bpf_pick_idle_cpu \
        scx_bpf_pick_idle_cpu_node scx_bpf_put_cpumask scx_bpf_reenqueue_local \
        scx_bpf_reenqueue_local___v2 scx_bpf_select_cpu_and \
        scx_bpf_select_cpu_dfl scx_bpf_sub_dispatch scx_bpf_task_cgroup \
        scx_bpf_task_cpu scx_bpf_task_running scx_bpf_task_set_dsq_vtime \
        scx_bpf_task_set_slice scx_bpf_test_and_clear_cpu_idle"

    if [[ "${cur}" == scx* ]] || [[ "${cur}" == ops.* ]] || [[ "${cur}" == bpf_iter_* ]]; then
        COMPREPLY=( $(compgen -W "${scx_pages}" -- "${cur}") )
    fi

    return 0
}

complete -F _scx_man_man_completion man
