#!/usr/bin/env python3
"""
scx-man.py - Generate and view sched_ext (scx) man pages

Based on kernel/sched/ext.c
Kernel version: 6.12+ (sched_ext merged)

Usage:
  python3 scx-man.py --generate /usr/local/share/man/man7
  python3 scx-man.py scx_bpf_dsq_insert
  python3 scx-man.py scx
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, Optional


# Comprehensive scx documentation database
# Based on kernel/sched/ext.c and include/linux/sched/ext.h
SCX_DOCS = {
    # ========== Overview ==========
    "scx": {
        "section": "7",
        "name": "scx - sched_ext overview",
        "description": (
            "sched_ext (scx) is a Linux kernel feature introduced in kernel version 6.12 "
            "that enables implementing kernel thread schedulers in BPF (Berkeley Packet Filter) "
            "and dynamically loading them.\n\n"
            "It allows developers to define custom scheduling policies as BPF programs, "
            "which can be loaded, unloaded, and switched at runtime without recompiling "
            "the kernel or rebooting.\n\n"
            "The core components of sched_ext are:\n"
            "  - Dispatch Queues (DSQs): Where tasks are queued for scheduling\n"
            "  - Ops Callbacks: BPF functions called by the scheduler core\n"
            "  - Helper Functions (kfuncs): scx_bpf_* functions for scheduler operations\n\n"
            "Key concepts:\n"
            "  DSQ (Dispatch Queue): Queue where tasks wait to be scheduled.\n"
            "    - SCX_DSQ_LOCAL: Per-CPU local runqueue\n"
            "    - SCX_DSQ_LOCAL_ON|cpu: Specific CPU's local runqueue\n"
            "    - SCX_DSQ_GLOBAL: Global runqueue shared across all CPUs\n"
            "    - Custom DSQs: User-defined queues for advanced scheduling\n\n"
            "  slice: Time slice allocated to a task (in nanoseconds)\n"
            "  vtime: Virtual time for fair scheduling priority\n"
            "  weight: Task weight for proportional fair scheduling"
        ),
        "see_also": "bpf(2), bpf-helpers(7), sched(7)"
    },

    # ========== Ops Callbacks ==========
    "ops.init": {
        "section": "7",
        "name": "ops.init - scx initialization callback",
        "signature": "s32 BPF_STRUCT_OPS_SLEEPABLE(init)",
        "description": (
            "Initialization routine called when the BPF scheduler is loaded.\n\n"
            "This callback is used to set up dispatch queues (DSQs), initialize maps, "
            "allocate state, and perform any one-time setup required by the scheduler.\n\n"
            "This callback is marked as SLEEPABLE, meaning it can call sleepable BPF helpers "
            "and blocking functions like scx_bpf_create_dsq()."
        ),
        "return": "0 on success, negative errno on failure",
        "context": "Called once during scheduler registration",
        "sleepable": True,
        "example": (
            "s32 BPF_STRUCT_OPS_SLEEPABLE(init)\n"
            "{\n"
            "    s32 ret;\n"
            "\n"
            "    /* Create a shared DSQ for all tasks */\n"
            "    ret = scx_bpf_create_dsq(SHARED_DSQ, -1);\n"
            "    if (ret < 0) {\n"
            "        scx_bpf_error_bstr(\"Failed to create DSQ: %d\", ret, 0);\n"
            "        return ret;\n"
            "    }\n"
            "    return 0;\n"
            "}"
        )
    },

    "ops.select_cpu": {
        "section": "7",
        "name": "ops.select_cpu - scx CPU selection callback",
        "signature": "s32 BPF_STRUCT_OPS(select_cpu, struct task_struct *p, s32 prev_cpu, u64 wake_flags)",
        "description": (
            "Invoked first on task wakeup to select a target CPU.\n\n"
            "This callback provides an optimization hint for CPU selection. The scheduler "
            "core will use the returned CPU ID as a suggestion, but is not bound to it.\n\n"
            "If you dispatch the task to SCX_DSQ_LOCAL from this callback AND the selected "
            "CPU is idle, the core will skip calling .enqueue entirely for better performance.\n\n"
            "Use scx_bpf_select_cpu_dfl() or scx_bpf_select_cpu_and() to get CPU suggestions, "
            "then modify based on your scheduling policy.\n\n"
            "Parameters:\n"
            "  p            - The waking task (struct task_struct *)\n"
            "  prev_cpu     - The CPU the task was previously running on\n"
            "  wake_flags   - Wake reason flags"
        ),
        "return": "Suggested CPU ID. Invalid CPUs (outside task's cpumask) are ignored by core.",
        "context": "Called on task wakeup, before ops.enqueue",
        "example": (
            "s32 BPF_STRUCT_OPS(select_cpu, struct task_struct *p, s32 prev_cpu, u64 wake_flags)\n"
            "{\n"
            "    s32 cpu;\n"
            "    bool is_idle = false;\n"
            "\n"
            "    cpu = scx_bpf_select_cpu_dfl(p, prev_cpu, wake_flags, &is_idle);\n"
            "    if (is_idle) {\n"
            "        scx_bpf_dsq_insert(p, SCX_DSQ_LOCAL, SCX_SLICE_DFL, 0);\n"
            "    }\n"
            "    return cpu;\n"
            "}"
        )
    },

    "ops.enqueue": {
        "section": "7",
        "name": "ops.enqueue - scx enqueue callback",
        "signature": "void BPF_STRUCT_OPS(enqueue, struct task_struct *p, u64 enq_flags)",
        "description": (
            "Invoked after CPU selection (unless the task was dispatched from .select_cpu).\n\n"
            "This callback decides where to place the task. Options include:\n"
            "  - SCX_DSQ_GLOBAL: Global runqueue, any CPU can consume\n"
            "  - SCX_DSQ_LOCAL: Current CPU's local runqueue\n"
            "  - SCX_DSQ_LOCAL_ON | cpu: Specific CPU's local runqueue\n"
            "  - Custom DSQ: User-defined queue for advanced scheduling\n\n"
            "If the task was already dispatched from .select_cpu (to SCX_DSQ_LOCAL), "
            "this callback is skipped entirely.\n\n"
            "Enqueue flags:\n"
            "  SCX_ENQ_WAKEUP       - Task is waking up\n"
            "  SCX_ENQ_HEAD         - Insert at head of DSQ\n"
            "  SCX_ENQ_CPU_SELECTED - CPU was selected in select_cpu\n"
            "  SCX_ENQ_PREEMPT      - Preemptive enqueue\n"
            "  SCX_ENQ_IMMED        - Immediate dispatch\n"
            "  SCX_ENQ_REENQ        - Re-enqueue\n"
            "  SCX_ENQ_LAST         - Last task on CPU\n\n"
            "Parameters:\n"
            "  p            - The task to enqueue\n"
            "  enq_flags    - Enqueue flags"
        ),
        "return": "void",
        "context": "Called when task is enqueued (if not dispatched from select_cpu)",
        "example": (
            "void BPF_STRUCT_OPS(enqueue, struct task_struct *p, u64 enq_flags)\n"
            "{\n"
            "    scx_bpf_dsq_insert(p, SHARED_DSQ, SCX_SLICE_DFL, enq_flags);\n"
            "}"
        )
    },

    "ops.dequeue": {
        "section": "7",
        "name": "ops.dequeue - scx dequeue callback",
        "signature": "void BPF_STRUCT_OPS(dequeue, struct task_struct *p, u64 deq_flags)",
        "description": (
            "Invoked when a task is removed from a runqueue.\n\n"
            "Dequeue flags:\n"
            "  SCX_DEQ_SLEEP           - Task is going to sleep\n"
            "  SCX_DEQ_CORE_SCHED_EXEC - Core sched exec\n"
            "  SCX_DEQ_SCHED_CHANGE    - Scheduler change\n\n"
            "Parameters:\n"
            "  p            - The task being dequeued\n"
            "  deq_flags    - Dequeue flags"
        ),
        "return": "void",
        "context": "Called when task is removed from runqueue"
    },

    "ops.dispatch": {
        "section": "7",
        "name": "ops.dispatch - scx dispatch callback",
        "signature": "void BPF_STRUCT_OPS(dispatch, s32 cpu, struct task_struct *prev)",
        "description": (
            "Invoked when a CPU's local DSQ and the global DSQ are both empty.\n\n"
            "This callback is responsible for populating the local DSQ by moving tasks "
            "from custom DSQs. Use scx_bpf_dsq_move_to_local(), scx_bpf_dsq_move_to_local___v2(), "
            "or the DSQ iterator API (bpf_iter_scx_dsq_*) for advanced dispatch logic.\n\n"
            "The dispatch is batched - use scx_bpf_dispatch_nr_slots() to check remaining "
            "slots and scx_bpf_dispatch_cancel() to cancel a pending dispatch.\n\n"
            "For sub-schedulers, use scx_bpf_sub_dispatch() to trigger child dispatch.\n\n"
            "Parameters:\n"
            "  cpu          - The CPU that needs tasks dispatched\n"
            "  prev         - The previously running task (may be NULL)"
        ),
        "return": "void",
        "context": "Called when CPU runqueues are empty",
        "example": (
            "void BPF_STRUCT_OPS(dispatch, s32 cpu, struct task_struct *prev)\n"
            "{\n"
            "    if (!scx_bpf_dsq_move_to_local___v2(HI_PRIO_DSQ, 0))\n"
            "        scx_bpf_dsq_move_to_local___v2(NORM_PRIO_DSQ, 0);\n"
            "}"
        )
    },

    "ops.tick": {
        "section": "7",
        "name": "ops.tick - scx tick callback",
        "signature": "void BPF_STRUCT_OPS(tick, struct task_struct *p)",
        "description": (
            "Called on each scheduler tick for the currently running task.\n\n"
            "Parameters:\n"
            "  p            - The currently running task"
        ),
        "return": "void",
        "context": "Called on each scheduler tick"
    },

    "ops.runnable": {
        "section": "7",
        "name": "ops.runnable - scx runnable callback",
        "signature": "void BPF_STRUCT_OPS(runnable, struct task_struct *p, u64 enq_flags)",
        "description": (
            "Called when a task becomes runnable (wants to be scheduled).\n\n"
            "This is distinct from .enqueue - a task may become runnable "
            "before it is actually enqueued.\n\n"
            "Parameters:\n"
            "  p            - The task becoming runnable\n"
            "  enq_flags    - Enqueue flags"
        ),
        "return": "void",
        "context": "Called when task becomes runnable"
    },

    "ops.running": {
        "section": "7",
        "name": "ops.running - scx running callback",
        "signature": "void BPF_STRUCT_OPS(running, struct task_struct *p)",
        "description": (
            "Called when a task begins running on a CPU.\n\n"
            "Parameters:\n"
            "  p            - The task that started running"
        ),
        "return": "void",
        "context": "Called when task starts running on CPU",
        "example": (
            "void BPF_STRUCT_OPS(running, struct task_struct *p)\n"
            "{\n"
            "    __sync_fetch_and_add(&vtime_now, SCX_SLICE_DFL);\n"
            "}"
        )
    },

    "ops.stopping": {
        "section": "7",
        "name": "ops.stopping - scx stopping callback",
        "signature": "void BPF_STRUCT_OPS(stopping, struct task_struct *p, bool runnable)",
        "description": (
            "Called when a task stops running on a CPU.\n\n"
            "Updates the task's dsq_vtime based on consumed slice and task weight.\n\n"
            "Parameters:\n"
            "  p            - The task that stopped running\n"
            "  runnable     - Whether the task remains runnable"
        ),
        "return": "void",
        "context": "Called when task stops running on CPU",
        "example": (
            "void BPF_STRUCT_OPS(stopping, struct task_struct *p, bool runnable)\n"
            "{\n"
            "    u64 weight = p->scx.weight;\n"
            "    p->scx.dsq_vtime += p->scx.slice_consumed * 1000000 / weight;\n"
            "}"
        )
    },

    "ops.quiescent": {
        "section": "7",
        "name": "ops.quiescent - scx quiescent callback",
        "signature": "void BPF_STRUCT_OPS(quiescent, struct task_struct *p, u64 deq_flags)",
        "description": (
            "Called when a task enters a quiescent state (not runnable).\n\n"
            "Parameters:\n"
            "  p            - The task entering quiescent state\n"
            "  deq_flags    - Dequeue flags"
        ),
        "return": "void",
        "context": "Called when task becomes non-runnable"
    },

    "ops.yield": {
        "section": "7",
        "name": "ops.yield - scx yield callback",
        "signature": "bool BPF_STRUCT_OPS(yield, struct task_struct *from, struct task_struct *to)",
        "description": (
            "Called when a task attempts to yield to another task.\n\n"
            "Parameters:\n"
            "  from         - The yielding task\n"
            "  to           - The target task (may be NULL)"
        ),
        "return": "true if yield was performed, false otherwise",
        "context": "Called during task yield"
    },

    "ops.core_sched_before": {
        "section": "7",
        "name": "ops.core_sched_before - scx core sched before callback",
        "signature": "bool BPF_STRUCT_OPS(core_sched_before, struct task_struct *a, struct task_struct *b)",
        "description": (
            "Called to determine core scheduling priority between two tasks.\n\n"
            "Parameters:\n"
            "  a            - First task\n"
            "  b            - Second task"
        ),
        "return": "true if a > b in core scheduling priority",
        "context": "Called during core scheduling decisions"
    },

    "ops.set_weight": {
        "section": "7",
        "name": "ops.set_weight - scx set weight callback",
        "signature": "void BPF_STRUCT_OPS(set_weight, struct task_struct *p, u32 weight)",
        "description": (
            "Called when a task's weight changes.\n\n"
            "Parameters:\n"
            "  p            - The task whose weight changed\n"
            "  weight       - New weight value"
        ),
        "return": "void",
        "context": "Called when task weight changes"
    },

    "ops.set_cpumask": {
        "section": "7",
        "name": "ops.set_cpumask - scx set cpumask callback",
        "signature": "void BPF_STRUCT_OPS(set_cpumask, struct task_struct *p, const struct cpumask *cpumask)",
        "description": (
            "Called when a task's CPU affinity mask changes.\n\n"
            "Parameters:\n"
            "  p            - The task whose cpumask changed\n"
            "  cpumask      - New CPU affinity mask"
        ),
        "return": "void",
        "context": "Called when task cpumask changes"
    },

    "ops.enable": {
        "section": "7",
        "name": "ops.enable - scx enable callback",
        "signature": "void BPF_STRUCT_OPS(enable, struct task_struct *p)",
        "description": (
            "Initializes a task's scx state when the BPF scheduler is activated.\n\n"
            "Parameters:\n"
            "  p            - The task being enabled"
        ),
        "return": "void",
        "context": "Called when task becomes schedulable",
        "example": (
            "void BPF_STRUCT_OPS(enable, struct task_struct *p)\n"
            "{\n"
            "    p->scx.dsq_vtime = vtime_now;\n"
            "}"
        )
    },

    "ops.disable": {
        "section": "7",
        "name": "ops.disable - scx disable callback",
        "signature": "void BPF_STRUCT_OPS(disable, struct task_struct *p)",
        "description": (
            "Called when a task is being disabled or becomes non-schedulable.\n\n"
            "Parameters:\n"
            "  p            - The task being disabled"
        ),
        "return": "void",
        "context": "Called when task becomes non-schedulable"
    },

    "ops.init_task": {
        "section": "7",
        "name": "ops.init_task - scx init task callback",
        "signature": "s32 BPF_STRUCT_OPS(init_task, struct task_struct *p, struct scx_init_task_args *args)",
        "description": (
            "Called when a new task is created.\n\n"
            "Parameters:\n"
            "  p            - The new task\n"
            "  args         - Init task arguments"
        ),
        "return": "0 on success, negative errno on failure",
        "context": "Called during task creation"
    },

    "ops.exit_task": {
        "section": "7",
        "name": "ops.exit_task - scx exit task callback",
        "signature": "void BPF_STRUCT_OPS(exit_task, struct task_struct *p, struct scx_exit_task_args *args)",
        "description": (
            "Called when a task is exiting.\n\n"
            "Parameters:\n"
            "  p            - The exiting task\n"
            "  args         - Exit task arguments"
        ),
        "return": "void",
        "context": "Called during task exit"
    },

    "ops.update_idle": {
        "section": "7",
        "name": "ops.update_idle - scx update idle callback",
        "signature": "void BPF_STRUCT_OPS(update_idle, s32 cpu, bool idle)",
        "description": (
            "Called when a CPU's idle state changes.\n\n"
            "Parameters:\n"
            "  cpu          - CPU whose idle state changed\n"
            "  idle         - true if CPU is now idle"
        ),
        "return": "void",
        "context": "Called when CPU idle state changes"
    },

    "ops.cpu_acquire": {
        "section": "7",
        "name": "ops.cpu_acquire - scx CPU acquire callback",
        "signature": "void BPF_STRUCT_OPS(cpu_acquire, s32 cpu, struct scx_cpu_acquire_args *args)",
        "description": (
            "Called when a CPU is coming online and being acquired by the BPF scheduler.\n\n"
            "Parameters:\n"
            "  cpu          - CPU being acquired\n"
            "  args         - Acquire arguments"
        ),
        "return": "void",
        "context": "Called during CPU hotplug (online)"
    },

    "ops.cpu_release": {
        "section": "7",
        "name": "ops.cpu_release - scx CPU release callback",
        "signature": "void BPF_STRUCT_OPS(cpu_release, s32 cpu, struct scx_cpu_release_args *args)",
        "description": (
            "Called when the sched_ext core is releasing a CPU from the BPF scheduler.\n\n"
            "Parameters:\n"
            "  cpu          - CPU being released\n"
            "  args         - Release arguments"
        ),
        "return": "void",
        "context": "Called during CPU hotplug or scheduler switch"
    },

    "ops.cpu_online": {
        "section": "7",
        "name": "ops.cpu_online - scx CPU online callback",
        "signature": "void BPF_STRUCT_OPS(cpu_online, s32 cpu)",
        "description": (
            "Called when a CPU is fully online and ready for scheduling.\n\n"
            "Parameters:\n"
            "  cpu          - CPU that is now online"
        ),
        "return": "void",
        "context": "Called after CPU is fully online"
    },

    "ops.cpu_offline": {
        "section": "7",
        "name": "ops.cpu_offline - scx CPU offline callback",
        "signature": "void BPF_STRUCT_OPS(cpu_offline, s32 cpu)",
        "description": (
            "Called when a CPU has gone offline.\n\n"
            "Parameters:\n"
            "  cpu          - CPU that went offline"
        ),
        "return": "void",
        "context": "Called after CPU goes offline"
    },

    "ops.exit": {
        "section": "7",
        "name": "ops.exit - scx exit callback",
        "signature": "void BPF_STRUCT_OPS(exit, struct scx_exit_info *info)",
        "description": (
            "Called when the scheduler unregisters, terminates, or encounters a fatal error.\n\n"
            "Parameters:\n"
            "  info         - Pointer to exit info struct with debug metadata"
        ),
        "return": "void",
        "context": "Called during scheduler unregistration or error"
    },

    "ops.dump": {
        "section": "7",
        "name": "ops.dump - scx dump callback",
        "signature": "void BPF_STRUCT_OPS(dump, struct scx_dump_ctx *ctx)",
        "description": (
            "Called during sched_ext_dump to generate scheduler-specific debug output.\n\n"
            "Use scx_bpf_dump_bstr() to output debug information.\n\n"
            "Parameters:\n"
            "  ctx          - Dump context"
        ),
        "return": "void",
        "context": "Called during sched_ext_dump (SysRq-D)"
    },

    "ops.dump_cpu": {
        "section": "7",
        "name": "ops.dump_cpu - scx per-CPU dump callback",
        "signature": "void BPF_STRUCT_OPS(dump_cpu, struct scx_dump_ctx *ctx, s32 cpu, bool idle)",
        "description": (
            "Called during sched_ext_dump to generate per-CPU debug output.\n\n"
            "Parameters:\n"
            "  ctx          - Dump context\n"
            "  cpu          - CPU being dumped\n"
            "  idle         - Whether CPU is idle"
        ),
        "return": "void",
        "context": "Called during per-CPU dump"
    },

    "ops.dump_task": {
        "section": "7",
        "name": "ops.dump_task - scx per-task dump callback",
        "signature": "void BPF_STRUCT_OPS(dump_task, struct scx_dump_ctx *ctx, struct task_struct *p)",
        "description": (
            "Called during sched_ext_dump to generate per-task debug output.\n\n"
            "Parameters:\n"
            "  ctx          - Dump context\n"
            "  p            - Task being dumped"
        ),
        "return": "void",
        "context": "Called during per-task dump"
    },

    "ops.dispatch_max_batch": {
        "section": "7",
        "name": "ops.dispatch_max_batch - scx dispatch batch size",
        "description": (
            "Maximum number of tasks that can be queued for dispatch at once.\n\n"
            "Typical values: 4-32 depending on workload."
        )
    },

    "ops.flags": {
        "section": "7",
        "name": "ops.flags - scx ops flags",
        "description": (
            "Flags controlling scheduler behavior (u64):\n\n"
            "  SCX_OPS_KEEP_BUILTIN_IDLE    - Keep built-in idle tracking\n"
            "  SCX_OPS_ENQ_LAST             - Enqueue last task on CPU\n"
            "  SCX_OPS_ENQ_EXITING          - Enqueue exiting tasks\n"
            "  SCX_OPS_SWITCH_PARTIAL       - Partial CPU switch\n"
            "  SCX_OPS_ENQ_MIGRATION_DISABLED - Migration disabled\n"
            "  SCX_OPS_ALLOW_QUEUED_WAKEUP  - Allow queued wakeup\n"
            "  SCX_OPS_BUILTIN_IDLE_PER_NODE - Per-node idle tracking\n"
            "  SCX_OPS_ALWAYS_ENQ_IMMED     - Always use immediate dispatch"
        )
    },

    "ops.timeout_ms": {
        "section": "7",
        "name": "ops.timeout_ms - scx timeout",
        "description": (
            "Timeout in milliseconds for BPF scheduler operations. Default: 30000 (30s)."
        )
    },

    "ops.exit_dump_len": {
        "section": "7",
        "name": "ops.exit_dump_len - scx exit dump length",
        "description": (
            "Length of the exit dump buffer."
        )
    },

    "ops.hotplug_seq": {
        "section": "7",
        "name": "ops.hotplug_seq - scx hotplug sequence number",
        "description": (
            "Sequence number tracking CPU hotplug events."
        )
    },

    "ops.sub_cgroup_id": {
        "section": "7",
        "name": "ops.sub_cgroup_id - scx sub-scheduler cgroup ID",
        "description": (
            "Cgroup ID for sub-scheduler attachment."
        )
    },

    "ops.name": {
        "section": "7",
        "name": "ops.name - scx scheduler name",
        "description": (
            "Name of the scheduler (up to 128 chars)."
        )
    },

    # ========== Helper Functions (kfuncs) ==========
    "scx_bpf_select_cpu_dfl": {
        "section": "7",
        "name": "scx_bpf_select_cpu_dfl - default CPU selection for scx",
        "signature": "s32 scx_bpf_select_cpu_dfl(struct task_struct *p, s32 prev_cpu, u64 wake_flags, bool *is_idle)",
        "description": (
            "Default CPU selection logic for sched_ext.\n\n"
            "If *is_idle is true, the BPF scheduler should call scx_bpf_dsq_insert() "
            "with SCX_DSQ_LOCAL from ops.select_cpu(), which will cause ops.enqueue() "
            "to be skipped entirely.\n\n"
            "Parameters:\n"
            "  p            - The waking task\n"
            "  prev_cpu     - The CPU the task was previously running on\n"
            "  wake_flags   - Wake reason flags\n"
            "  is_idle      - Output: set to true if suggested CPU is idle"
        ),
        "return": "Suggested CPU ID",
        "context": "Available in ops.select_cpu callback",
        "example": (
            "s32 BPF_STRUCT_OPS(select_cpu, struct task_struct *p, s32 prev_cpu, u64 wake_flags)\n"
            "{\n"
            "    s32 cpu;\n"
            "    bool is_idle = false;\n"
            "    cpu = scx_bpf_select_cpu_dfl(p, prev_cpu, wake_flags, &is_idle);\n"
            "    if (is_idle) {\n"
            "        scx_bpf_dsq_insert(p, SCX_DSQ_LOCAL, SCX_SLICE_DFL, 0);\n"
            "    }\n"
            "    return cpu;\n"
            "}"
        )
    },

    "scx_bpf_select_cpu_and": {
        "section": "7",
        "name": "scx_bpf_select_cpu_and - CPU selection with cpumask constraint",
        "signature": "s32 scx_bpf_select_cpu_and(struct task_struct *p, s32 prev_cpu, u64 wake_flags, const struct cpumask *cpus_allowed, u64 flags)",
        "description": (
            "CPU selection logic constrained to a specific cpumask.\n\n"
            "Parameters:\n"
            "  p            - The waking task\n"
            "  prev_cpu     - Previous CPU\n"
            "  wake_flags   - Wake reason flags\n"
            "  cpus_allowed - CPU mask to constrain selection\n"
            "  flags        - Selection flags (SCX_PICK_IDLE_*)"
        ),
        "return": "Suggested CPU ID",
        "context": "Available in ops.select_cpu callback"
    },

    "scx_bpf_dsq_insert": {
        "section": "7",
        "name": "scx_bpf_dsq_insert - insert task into DSQ (FIFO)",
        "signature": "bool scx_bpf_dsq_insert(struct task_struct *p, u64 dsq_id, u64 slice, u64 enq_flags)",
        "description": (
            "Insert a task into the FIFO of the specified dispatch queue.\n\n"
            "This is the PRIMARY function for dispatching tasks to scheduling queues. "
            "Tasks can be inserted into:\n"
            "  - SCX_DSQ_LOCAL: Current CPU's local runqueue\n"
            "  - SCX_DSQ_LOCAL_ON | cpu: Specific CPU's local runqueue\n"
            "  - SCX_DSQ_GLOBAL: Global runqueue accessible by all CPUs\n"
            "  - Custom DSQ: User-defined queue (ID < 2^63)\n\n"
            "Returns bool indicating whether the task was successfully dispatched.\n\n"
            "Parameters:\n"
            "  p            - The task to insert\n"
            "  dsq_id       - Target DSQ ID\n"
            "  slice        - Time slice (nanoseconds, or SCX_SLICE_DFL)\n"
            "  enq_flags    - Enqueue flags (0, SCX_ENQ_WAKEUP, SCX_ENQ_IMMED, etc.)"
        ),
        "return": "true if task was dispatched, false otherwise",
        "context": "Available in ops.select_cpu, ops.enqueue",
        "example": (
            "scx_bpf_dsq_insert(p, SCX_DSQ_GLOBAL, SCX_SLICE_DFL, enq_flags);\n"
            "scx_bpf_dsq_insert(p, SCX_DSQ_LOCAL, SCX_SLICE_DFL, 0);\n"
            "scx_bpf_dsq_insert(p, SHARED_DSQ, SCX_SLICE_DFL, SCX_ENQ_IMMED);"
        )
    },

    "scx_bpf_dsq_insert_vtime": {
        "section": "7",
        "name": "scx_bpf_dsq_insert_vtime - insert task into DSQ (priority/vtime)",
        "signature": "void scx_bpf_dsq_insert_vtime(struct task_struct *p, u64 dsq_id, u64 slice, u64 vtime, u64 enq_flags)",
        "description": (
            "Insert a task into a DSQ as a priority queue, ordered by virtual time (vtime).\n\n"
            "IMPORTANT: Internal DSQs (SCX_DSQ_LOCAL, SCX_DSQ_GLOBAL) do NOT support "
            "priority dispatching. They must use scx_bpf_dsq_insert() instead.\n\n"
            "Only custom DSQs created via scx_bpf_create_dsq() support vtime ordering.\n\n"
            "Parameters:\n"
            "  p            - The task to insert\n"
            "  dsq_id       - Target custom DSQ ID (NOT LOCAL or GLOBAL)\n"
            "  slice        - Time slice (nanoseconds)\n"
            "  vtime        - Virtual time for ordering (lower = higher priority)\n"
            "  enq_flags    - Enqueue flags"
        ),
        "return": "void",
        "context": "Available in ops.enqueue",
        "example": (
            "void BPF_STRUCT_OPS(enqueue, struct task_struct *p, u64 enq_flags)\n"
            "{\n"
            "    u64 vtime = p->scx.dsq_vtime + consumed / weight;\n"
            "    scx_bpf_dsq_insert_vtime(p, SHARED_DSQ, SCX_SLICE_DFL, vtime, enq_flags);\n"
            "}"
        )
    },

    "scx_bpf_dispatch_nr_slots": {
        "section": "7",
        "name": "scx_bpf_dispatch_nr_slots - get remaining dispatch slots",
        "signature": "u32 scx_bpf_dispatch_nr_slots(void)",
        "description": (
            "Get the number of remaining dispatch batch slots.\n\n"
            "Use this in ops.dispatch() to check how many more tasks can be "
            "dispatched before the batch limit is reached."
        ),
        "return": "Remaining dispatch slots",
        "context": "Available in ops.dispatch"
    },

    "scx_bpf_dispatch_cancel": {
        "section": "7",
        "name": "scx_bpf_dispatch_cancel - cancel pending dispatch",
        "signature": "void scx_bpf_dispatch_cancel(void)",
        "description": (
            "Cancel the last pending dispatch.\n\n"
            "This undoes the most recent scx_bpf_dsq_insert() call in the "
            "current dispatch cycle."
        ),
        "return": "void",
        "context": "Available in ops.dispatch"
    },

    "scx_bpf_dsq_move_to_local": {
        "section": "7",
        "name": "scx_bpf_dsq_move_to_local - move task from DSQ to local",
        "signature": "bool scx_bpf_dsq_move_to_local(u64 dsq_id)",
        "description": (
            "Move the first task from a specified non-local DSQ to the dispatching "
            "CPU's local DSQ.\n\n"
            "Parameters:\n"
            "  dsq_id       - Source DSQ ID to move task from"
        ),
        "return": "true if a task was moved, false if DSQ was empty",
        "context": "Available in ops.dispatch",
        "example": (
            "void BPF_STRUCT_OPS(dispatch, s32 cpu, struct task_struct *prev)\n"
            "{\n"
            "    if (!scx_bpf_dsq_move_to_local___v2(HI_PRIO_DSQ, 0))\n"
            "        scx_bpf_dsq_move_to_local___v2(NORM_PRIO_DSQ, 0);\n"
            "}"
        )
    },

    "scx_bpf_dsq_move_to_local___v2": {
        "section": "7",
        "name": "scx_bpf_dsq_move_to_local___v2 - move task with flags",
        "signature": "bool scx_bpf_dsq_move_to_local___v2(u64 dsq_id, u64 enq_flags)",
        "description": (
            "Move the first task from a specified non-local DSQ to the dispatching "
            "CPU's local DSQ, with enqueue flags.\n\n"
            "Parameters:\n"
            "  dsq_id       - Source DSQ ID\n"
            "  enq_flags    - Enqueue flags"
        ),
        "return": "true if a task was moved, false if DSQ was empty",
        "context": "Available in ops.dispatch"
    },

    "scx_bpf_dsq_move": {
        "section": "7",
        "name": "scx_bpf_dsq_move - move task from iterator",
        "signature": "bool scx_bpf_dsq_move(struct bpf_iter_scx_dsq *iter, struct task_struct *p, u64 dsq_id, u64 enq_flags)",
        "description": (
            "Move a task from a DSQ iterator to another DSQ.\n\n"
            "Parameters:\n"
            "  iter         - DSQ iterator\n"
            "  p            - Task to move\n"
            "  dsq_id       - Target DSQ ID\n"
            "  enq_flags    - Enqueue flags"
        ),
        "return": "true if task was moved, false otherwise",
        "context": "Available in ops.dispatch (within DSQ iterator)"
    },

    "scx_bpf_dsq_move_vtime": {
        "section": "7",
        "name": "scx_bpf_dsq_move_vtime - move task to DSQ with vtime",
        "signature": "bool scx_bpf_dsq_move_vtime(struct bpf_iter_scx_dsq *iter, struct task_struct *p, u64 dsq_id, u64 slice, u64 vtime, u64 enq_flags)",
        "description": (
            "Move a task from a DSQ iterator to another DSQ with vtime ordering.\n\n"
            "Parameters:\n"
            "  iter         - DSQ iterator\n"
            "  p            - Task to move\n"
            "  dsq_id       - Target DSQ ID\n"
            "  slice        - Time slice\n"
            "  vtime        - Virtual time\n"
            "  enq_flags    - Enqueue flags"
        ),
        "return": "true if task was moved, false otherwise",
        "context": "Available in ops.dispatch (within DSQ iterator)"
    },

    "scx_bpf_dsq_move_set_slice": {
        "section": "7",
        "name": "scx_bpf_dsq_move_set_slice - set slice for iter move",
        "signature": "void scx_bpf_dsq_move_set_slice(struct bpf_iter_scx_dsq *iter, u64 slice)",
        "description": (
            "Set the time slice for the next scx_bpf_dsq_move() call.\n\n"
            "Parameters:\n"
            "  iter         - DSQ iterator\n"
            "  slice        - Time slice"
        ),
        "return": "void",
        "context": "Available in ops.dispatch (within DSQ iterator)"
    },

    "scx_bpf_dsq_move_set_vtime": {
        "section": "7",
        "name": "scx_bpf_dsq_move_set_vtime - set vtime for iter move",
        "signature": "void scx_bpf_dsq_move_set_vtime(struct bpf_iter_scx_dsq *iter, u64 vtime)",
        "description": (
            "Set the virtual time for the next scx_bpf_dsq_move() call.\n\n"
            "Parameters:\n"
            "  iter         - DSQ iterator\n"
            "  vtime        - Virtual time"
        ),
        "return": "void",
        "context": "Available in ops.dispatch (within DSQ iterator)"
    },

    "scx_bpf_sub_dispatch": {
        "section": "7",
        "name": "scx_bpf_sub_dispatch - trigger sub-scheduler dispatch",
        "signature": "bool scx_bpf_sub_dispatch(u64 cgroup_id)",
        "description": (
            "Trigger dispatch from a child sub-scheduler.\n\n"
            "Parameters:\n"
            "  cgroup_id    - Cgroup ID of the sub-scheduler"
        ),
        "return": "true if sub-scheduler dispatched tasks",
        "context": "Available in ops.dispatch"
    },

    "scx_bpf_reenqueue_local": {
        "section": "7",
        "name": "scx_bpf_reenqueue_local - re-enqueue local DSQ tasks",
        "signature": "u32 scx_bpf_reenqueue_local(void)",
        "description": (
            "Re-enqueue tasks from the local DSQ back to the BPF scheduler.\n\n"
            "Called during CPU release to return pending tasks."
        ),
        "return": "Number of tasks re-enqueued",
        "context": "Available in ops.cpu_release"
    },

    "scx_bpf_reenqueue_local___v2": {
        "section": "7",
        "name": "scx_bpf_reenqueue_local___v2 - re-enqueue local v2",
        "signature": "void scx_bpf_reenqueue_local___v2(void)",
        "description": (
            "V2 variant - wraps dsq_reenq() on the local DSQ."
        ),
        "return": "void",
        "context": "Available in ops.cpu_release"
    },

    "scx_bpf_create_dsq": {
        "section": "7",
        "name": "scx_bpf_create_dsq - create custom dispatch queue",
        "signature": "s32 scx_bpf_create_dsq(u64 dsq_id, s32 node)",
        "description": (
            "Create a custom Dispatch Queue for advanced scheduling algorithms.\n\n"
            "DSQ IDs must be unique and less than 2^63.\n\n"
            "This is a SLEEPABLE function.\n\n"
            "Parameters:\n"
            "  dsq_id       - Unique ID for the new DSQ (< 2^63)\n"
            "  node         - NUMA node affinity (-1 for global/non-affine)"
        ),
        "return": "0 on success, negative errno on failure",
        "context": "Available in ops.init (sleepable context only)",
        "sleepable": True
    },

    "scx_bpf_destroy_dsq": {
        "section": "7",
        "name": "scx_bpf_destroy_dsq - destroy custom dispatch queue",
        "signature": "void scx_bpf_destroy_dsq(u64 dsq_id)",
        "description": (
            "Destroy a custom Dispatch Queue.\n\n"
            "Parameters:\n"
            "  dsq_id       - ID of the DSQ to destroy"
        ),
        "return": "void",
        "context": "Available in ops.exit (sleepable context)",
        "sleepable": True
    },

    "scx_bpf_dsq_nr_queued": {
        "section": "7",
        "name": "scx_bpf_dsq_nr_queued - get number of tasks in DSQ",
        "signature": "s32 scx_bpf_dsq_nr_queued(u64 dsq_id)",
        "description": (
            "Get the number of tasks queued in a specified DSQ.\n\n"
            "Parameters:\n"
            "  dsq_id       - DSQ ID to query"
        ),
        "return": "Number of tasks queued, or negative errno on error",
        "context": "Available in all callbacks"
    },

    "scx_bpf_dsq_peek": {
        "section": "7",
        "name": "scx_bpf_dsq_peek - lockless peek at DSQ head",
        "signature": "struct task_struct *scx_bpf_dsq_peek(u64 dsq_id)",
        "description": (
            "Locklessly peek at the head of a DSQ.\n\n"
            "WARNING: The returned pointer is not protected by locks "
            "and may become invalid at any time.\n\n"
            "Parameters:\n"
            "  dsq_id       - DSQ ID to peek"
        ),
        "return": "Pointer to task at head, or NULL if empty",
        "context": "Available in all callbacks"
    },

    "scx_bpf_dsq_reenq": {
        "section": "7",
        "name": "scx_bpf_dsq_reenq - re-enqueue DSQ tasks",
        "signature": "void scx_bpf_dsq_reenq(u64 dsq_id, u64 reenq_flags)",
        "description": (
            "Asynchronously re-enqueue tasks from a DSQ.\n\n"
            "Parameters:\n"
            "  dsq_id         - DSQ ID\n"
            "  reenq_flags    - Re-enqueue flags"
        ),
        "return": "void",
        "context": "Available in ops.cpu_release"
    },

    "scx_bpf_task_set_slice": {
        "section": "7",
        "name": "scx_bpf_task_set_slice - set task time slice",
        "signature": "bool scx_bpf_task_set_slice(struct task_struct *p, u64 slice)",
        "description": (
            "Set the time slice for a specific task.\n\n"
            "Parameters:\n"
            "  p            - The task\n"
            "  slice        - New time slice (nanoseconds)"
        ),
        "return": "true if successful",
        "context": "Available in all callbacks"
    },

    "scx_bpf_task_set_dsq_vtime": {
        "section": "7",
        "name": "scx_bpf_task_set_dsq_vtime - set task vtime",
        "signature": "bool scx_bpf_task_set_dsq_vtime(struct task_struct *p, u64 vtime)",
        "description": (
            "Set the virtual time for a specific task.\n\n"
            "Parameters:\n"
            "  p            - The task\n"
            "  vtime        - New virtual time"
        ),
        "return": "true if successful",
        "context": "Available in all callbacks"
    },

    "scx_bpf_kick_cpu": {
        "section": "7",
        "name": "scx_bpf_kick_cpu - kick/wake a specific CPU",
        "signature": "s32 scx_bpf_kick_cpu(s32 cpu, u64 flags)",
        "description": (
            "Wake up (kick) a specific CPU.\n\n"
            "Flags:\n"
            "  SCX_KICK_IDLE    - Only kick if CPU is idle\n"
            "  SCX_KICK_PREEMPT - Preempt current task\n"
            "  SCX_KICK_WAIT    - Wait for CPU to be ready\n\n"
            "Parameters:\n"
            "  cpu          - CPU to kick\n"
            "  flags        - Kick flags"
        ),
        "return": "0 on success, negative errno on failure",
        "context": "Available in all callbacks"
    },

    "scx_bpf_cpuperf_cap": {
        "section": "7",
        "name": "scx_bpf_cpuperf_cap - get CPU performance capacity",
        "signature": "u32 scx_bpf_cpuperf_cap(s32 cpu)",
        "description": (
            "Get the maximum performance capacity of a CPU (0-1024).\n\n"
            "Parameters:\n"
            "  cpu          - CPU to query"
        ),
        "return": "Maximum performance capacity",
        "context": "Available in all callbacks"
    },

    "scx_bpf_cpuperf_cur": {
        "section": "7",
        "name": "scx_bpf_cpuperf_cur - get CPU current perf level",
        "signature": "u32 scx_bpf_cpuperf_cur(s32 cpu)",
        "description": (
            "Get the current performance level of a CPU (0-1024).\n\n"
            "Parameters:\n"
            "  cpu          - CPU to query"
        ),
        "return": "Current performance level",
        "context": "Available in all callbacks"
    },

    "scx_bpf_cpuperf_set": {
        "section": "7",
        "name": "scx_bpf_cpuperf_set - set CPU perf target",
        "signature": "void scx_bpf_cpuperf_set(s32 cpu, u32 perf)",
        "description": (
            "Set the target performance level for a CPU (0-1024).\n\n"
            "Parameters:\n"
            "  cpu          - CPU to set\n"
            "  perf         - Target performance level"
        ),
        "return": "void",
        "context": "Available in all callbacks"
    },

    "scx_bpf_nr_node_ids": {
        "section": "7",
        "name": "scx_bpf_nr_node_ids - get number of NUMA nodes",
        "signature": "u32 scx_bpf_nr_node_ids(void)",
        "description": "Get the number of NUMA nodes in the system.",
        "return": "Number of NUMA nodes",
        "context": "Available in all callbacks"
    },

    "scx_bpf_nr_cpu_ids": {
        "section": "7",
        "name": "scx_bpf_nr_cpu_ids - get number of CPUs",
        "signature": "u32 scx_bpf_nr_cpu_ids(void)",
        "description": "Get the number of possible CPUs.",
        "return": "Number of possible CPUs",
        "context": "Available in all callbacks"
    },

    "scx_bpf_get_possible_cpumask": {
        "section": "7",
        "name": "scx_bpf_get_possible_cpumask - get possible CPU mask",
        "signature": "const struct cpumask *scx_bpf_get_possible_cpumask(void)",
        "description": (
            "Get the cpumask of all possible CPUs.\n\n"
            "Must be released with scx_bpf_put_cpumask()."
        ),
        "return": "Pointer to cpumask",
        "context": "Available in all callbacks"
    },

    "scx_bpf_get_online_cpumask": {
        "section": "7",
        "name": "scx_bpf_get_online_cpumask - get online CPU mask",
        "signature": "const struct cpumask *scx_bpf_get_online_cpumask(void)",
        "description": (
            "Get the cpumask of currently online CPUs.\n\n"
            "Must be released with scx_bpf_put_cpumask()."
        ),
        "return": "Pointer to cpumask",
        "context": "Available in all callbacks"
    },

    "scx_bpf_put_cpumask": {
        "section": "7",
        "name": "scx_bpf_put_cpumask - release cpumask reference",
        "signature": "void scx_bpf_put_cpumask(const struct cpumask *cpumask)",
        "description": (
            "Release a cpumask reference.\n\n"
            "Parameters:\n"
            "  cpumask      - cpumask to release"
        ),
        "return": "void",
        "context": "Available in all callbacks"
    },

    "scx_bpf_task_running": {
        "section": "7",
        "name": "scx_bpf_task_running - check if task is running",
        "signature": "bool scx_bpf_task_running(const struct task_struct *p)",
        "description": (
            "Check if a task is currently running.\n\n"
            "Parameters:\n"
            "  p            - The task"
        ),
        "return": "true if running",
        "context": "Available in all callbacks"
    },

    "scx_bpf_task_cpu": {
        "section": "7",
        "name": "scx_bpf_task_cpu - get task's CPU",
        "signature": "s32 scx_bpf_task_cpu(const struct task_struct *p)",
        "description": (
            "Get the CPU a task is assigned to.\n\n"
            "Parameters:\n"
            "  p            - The task"
        ),
        "return": "CPU ID, or negative if not running",
        "context": "Available in all callbacks"
    },

    "scx_bpf_locked_rq": {
        "section": "7",
        "name": "scx_bpf_locked_rq - get current locked rq",
        "signature": "struct rq *scx_bpf_locked_rq(void)",
        "description": "Get the currently locked runqueue pointer.",
        "return": "Pointer to current runqueue, or NULL",
        "context": "Available in ops.dispatch"
    },

    "scx_bpf_cpu_curr": {
        "section": "7",
        "name": "scx_bpf_cpu_curr - get remote CPU's current task",
        "signature": "struct task_struct *scx_bpf_cpu_curr(s32 cpu)",
        "description": (
            "Get the currently running task on a remote CPU.\n\n"
            "WARNING: Not refcounted, may become invalid.\n\n"
            "Parameters:\n"
            "  cpu          - CPU to query"
        ),
        "return": "Pointer to current task, or NULL",
        "context": "Available in ops.dispatch"
    },

    "scx_bpf_now": {
        "section": "7",
        "name": "scx_bpf_now - monotonic clock",
        "signature": "u64 scx_bpf_now(void)",
        "description": (
            "Get a high-performance monotonic clock (nanoseconds since boot)."
        ),
        "return": "Current time in nanoseconds",
        "context": "Available in all callbacks"
    },

    "scx_bpf_events": {
        "section": "7",
        "name": "scx_bpf_events - get scheduler events",
        "signature": "void scx_bpf_events(struct scx_event_stats *events, size_t events__sz)",
        "description": (
            "Fill struct with scheduler event statistics.\n\n"
            "Parameters:\n"
            "  events       - Event stats struct\n"
            "  events__sz   - Size of struct"
        ),
        "return": "void",
        "context": "Available in all callbacks"
    },

    "scx_bpf_test_and_clear_cpu_idle": {
        "section": "7",
        "name": "scx_bpf_test_and_clear_cpu_idle - test and clear CPU idle",
        "signature": "bool scx_bpf_test_and_clear_cpu_idle(s32 cpu)",
        "description": (
            "Test if a CPU is idle and clear its idle state.\n\n"
            "Parameters:\n"
            "  cpu          - CPU to test"
        ),
        "return": "true if CPU was idle",
        "context": "Available in all callbacks"
    },

    "scx_bpf_pick_idle_cpu": {
        "section": "7",
        "name": "scx_bpf_pick_idle_cpu - pick idle CPU from cpumask",
        "signature": "s32 scx_bpf_pick_idle_cpu(const struct cpumask *cpus_allowed, u64 flags)",
        "description": (
            "Pick an idle CPU from the given cpumask.\n\n"
            "Flags:\n"
            "  SCX_PICK_IDLE_CORE    - Full core (all SMT siblings idle)\n"
            "  SCX_PICK_IDLE_IN_NODE - Specific NUMA node\n\n"
            "Parameters:\n"
            "  cpus_allowed - CPU mask\n"
            "  flags        - Pick flags"
        ),
        "return": "CPU ID, or negative errno",
        "context": "Available in all callbacks"
    },

    "scx_bpf_pick_idle_cpu_node": {
        "section": "7",
        "name": "scx_bpf_pick_idle_cpu_node - pick idle CPU from NUMA node",
        "signature": "s32 scx_bpf_pick_idle_cpu_node(const struct cpumask *cpus_allowed, s32 node, u64 flags)",
        "description": (
            "Pick an idle CPU constrained to a NUMA node.\n\n"
            "Parameters:\n"
            "  cpus_allowed - CPU mask\n"
            "  node         - NUMA node\n"
            "  flags        - Pick flags"
        ),
        "return": "CPU ID, or negative errno",
        "context": "Available in all callbacks"
    },

    "scx_bpf_pick_any_cpu": {
        "section": "7",
        "name": "scx_bpf_pick_any_cpu - pick any CPU from cpumask",
        "signature": "s32 scx_bpf_pick_any_cpu(const struct cpumask *cpus_allowed, u64 flags)",
        "description": (
            "Pick any CPU from cpumask (not necessarily idle).\n\n"
            "Parameters:\n"
            "  cpus_allowed - CPU mask\n"
            "  flags        - Pick flags"
        ),
        "return": "CPU ID, or negative errno",
        "context": "Available in all callbacks"
    },

    "scx_bpf_pick_any_cpu_node": {
        "section": "7",
        "name": "scx_bpf_pick_any_cpu_node - pick any CPU from NUMA node",
        "signature": "s32 scx_bpf_pick_any_cpu_node(const struct cpumask *cpus_allowed, s32 node, u64 flags)",
        "description": (
            "Pick any CPU from cpumask, constrained to NUMA node.\n\n"
            "Parameters:\n"
            "  cpus_allowed - CPU mask\n"
            "  node         - NUMA node\n"
            "  flags        - Pick flags"
        ),
        "return": "CPU ID, or negative errno",
        "context": "Available in all callbacks"
    },

    "scx_bpf_get_idle_cpumask": {
        "section": "7",
        "name": "scx_bpf_get_idle_cpumask - get idle CPU mask",
        "signature": "const struct cpumask *scx_bpf_get_idle_cpumask(void)",
        "description": "Get the current idle CPU mask.",
        "return": "Pointer to idle cpumask",
        "context": "Available in all callbacks"
    },

    "scx_bpf_get_idle_cpumask_node": {
        "section": "7",
        "name": "scx_bpf_get_idle_cpumask_node - get idle CPU mask for node",
        "signature": "const struct cpumask *scx_bpf_get_idle_cpumask_node(int node)",
        "description": (
            "Get idle CPU mask for a NUMA node.\n\n"
            "Parameters:\n"
            "  node         - NUMA node"
        ),
        "return": "Pointer to idle cpumask",
        "context": "Available in all callbacks"
    },

    "scx_bpf_get_idle_smtmask": {
        "section": "7",
        "name": "scx_bpf_get_idle_smtmask - get idle SMT mask",
        "signature": "const struct cpumask *scx_bpf_get_idle_smtmask(void)",
        "description": "Get the current idle SMT mask.",
        "return": "Pointer to idle SMT mask",
        "context": "Available in all callbacks"
    },

    "scx_bpf_get_idle_smtmask_node": {
        "section": "7",
        "name": "scx_bpf_get_idle_smtmask_node - get idle SMT mask for node",
        "signature": "const struct cpumask *scx_bpf_get_idle_smtmask_node(int node)",
        "description": (
            "Get idle SMT mask for a NUMA node.\n\n"
            "Parameters:\n"
            "  node         - NUMA node"
        ),
        "return": "Pointer to idle SMT mask",
        "context": "Available in all callbacks"
    },

    "bpf_iter_scx_dsq_new": {
        "section": "7",
        "name": "bpf_iter_scx_dsq_new - create DSQ iterator",
        "signature": "int bpf_iter_scx_dsq_new(struct bpf_iter_scx_dsq *it, u64 dsq_id, u64 flags)",
        "description": (
            "Create a new iterator for a DSQ.\n\n"
            "Parameters:\n"
            "  it           - Iterator struct\n"
            "  dsq_id       - DSQ ID\n"
            "  flags        - Iterator flags"
        ),
        "return": "0 on success, negative errno on failure",
        "context": "Available in ops.dispatch"
    },

    "bpf_iter_scx_dsq_next": {
        "section": "7",
        "name": "bpf_iter_scx_dsq_next - get next task from iterator",
        "signature": "struct task_struct *bpf_iter_scx_dsq_next(struct bpf_iter_scx_dsq *it)",
        "description": (
            "Get the next task from a DSQ iterator.\n\n"
            "Parameters:\n"
            "  it           - DSQ iterator"
        ),
        "return": "Next task, or NULL when done",
        "context": "Available in ops.dispatch"
    },

    "bpf_iter_scx_dsq_destroy": {
        "section": "7",
        "name": "bpf_iter_scx_dsq_destroy - destroy DSQ iterator",
        "signature": "void bpf_iter_scx_dsq_destroy(struct bpf_iter_scx_dsq *it)",
        "description": (
            "Destroy a DSQ iterator.\n\n"
            "Parameters:\n"
            "  it           - DSQ iterator"
        ),
        "return": "void",
        "context": "Available in ops.dispatch"
    },

    "scx_bpf_exit_bstr": {
        "section": "7",
        "name": "scx_bpf_exit_bstr - exit with formatted message",
        "signature": "void scx_bpf_exit_bstr(s64 exit_code, char *fmt, u64 *data, u32 data__sz)",
        "description": (
            "Trigger BPF-initiated exit with bstr formatted message.\n\n"
            "Parameters:\n"
            "  exit_code    - Exit code\n"
            "  fmt          - Format string\n"
            "  data         - Format arguments\n"
            "  data__sz     - Size of data"
        ),
        "return": "void (does not return)",
        "context": "Available in all callbacks"
    },

    "scx_bpf_error_bstr": {
        "section": "7",
        "name": "scx_bpf_error_bstr - trigger error with message",
        "signature": "void scx_bpf_error_bstr(char *fmt, u64 *data, u32 data__sz)",
        "description": (
            "Trigger BPF-initiated exit (SCX_EXIT_ERROR_BPF) with bstr message.\n\n"
            "Parameters:\n"
            "  fmt          - Format string\n"
            "  data         - Format arguments\n"
            "  data__sz     - Size of data"
        ),
        "return": "void (does not return)",
        "context": "Available in all callbacks"
    },

    "scx_bpf_dump_bstr": {
        "section": "7",
        "name": "scx_bpf_dump_bstr - debug dump with bstr",
        "signature": "void scx_bpf_dump_bstr(char *fmt, u64 *data, u32 data__sz)",
        "description": (
            "Generate debug output using bstr formatting.\n\n"
            "Parameters:\n"
            "  fmt          - Format string\n"
            "  data         - Format arguments\n"
            "  data__sz     - Size of data"
        ),
        "return": "void",
        "context": "Available in ops.dump, ops.dump_cpu, ops.dump_task"
    },

    "scx_bpf_task_cgroup": {
        "section": "7",
        "name": "scx_bpf_task_cgroup - get task's cgroup",
        "signature": "struct cgroup *scx_bpf_task_cgroup(struct task_struct *p)",
        "description": (
            "Get the cgroup a task belongs to. Requires CONFIG_CGROUP_SCHED.\n\n"
            "Parameters:\n"
            "  p            - The task"
        ),
        "return": "Pointer to cgroup, or NULL",
        "context": "Available in all callbacks"
    },
}


def generate_man_page(func_name: str, info: Dict) -> str:
    """Generate a troff-formatted man page."""

    def escape(text: str) -> str:
        text = text.replace('\\', '\\[rs]')
        text = text.replace('.', '\\&.')
        text = text.replace('-', '\\-')
        return text

    section = info.get('section', '7')
    name = info.get('name', func_name)

    page = []
    page.append(f'.TH {func_name.upper().replace(".", "_")} {section} "2026-04-06" "Linux" "sched_ext Manual"')
    page.append('.SH NAME')
    page.append(f'{escape(func_name)} \\- {escape(name.split(" - ", 1)[1] if " - " in name else name)}')
    page.append('')

    if info.get('signature'):
        page.append('.SH SYNOPSIS')
        page.append('.nf')
        page.append(escape(info['signature']))
        page.append('.fi')
        page.append('')

    page.append('.SH DESCRIPTION')
    page.append('.PP')
    if info.get('description'):
        for line in info['description'].split('\n'):
            if line.strip():
                page.append(escape(line))
            else:
                page.append('.PP')
    page.append('')

    if info.get('return'):
        page.append('.SH RETURN VALUE')
        page.append('.PP')
        page.append(escape(info['return']))
        page.append('')

    if info.get('context'):
        page.append('.SH CONTEXT')
        page.append('.PP')
        page.append(escape(info['context']))
        page.append('')

    if info.get('sleepable'):
        page.append('.SH SLEEPABLE')
        page.append('.PP')
        page.append('This function can be called from sleepable contexts.')
        page.append('')

    if info.get('example'):
        page.append('.SH EXAMPLE')
        page.append('.nf')
        page.append(escape(info['example']))
        page.append('.fi')
        page.append('')

    page.append('.SH SEE ALSO')
    see_also = info.get('see_also', 'scx(7), bpf(2)')
    page.append(escape(see_also))
    page.append('')

    page.append('.SH NOTES')
    page.append('.PP')
    page.append(
        'The sched_ext API has no stability guarantees. Callbacks, helpers, '
        'and constants may change between kernel versions without warning.'
    )
    page.append('.PP')
    page.append('For complete documentation, see:')
    page.append('.IP')
    page.append('.B https://docs.kernel.org/scheduler/sched-ext.html')
    page.append('.IP')
    page.append('.B https://git.kernel.org/pub/scm/linux/kernel/git/tj/sched_ext.git/')
    page.append('')

    return '\n'.join(page)


def generate_all_man_pages(output_dir: str) -> int:
    """Generate man pages for all scx functions."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    count = 0
    for func_name, info in SCX_DOCS.items():
        filename = func_name.replace('.', '_')
        man_content = generate_man_page(func_name, info)
        output_file = output_path / f"{filename}.{info.get('section', '7')}"
        output_file.write_text(man_content, encoding='utf-8')
        count += 1

    print(f"Generated {count} scx man pages in {output_dir}")
    return count


def view_doc(func_name: str):
    """View documentation in terminal."""
    info = SCX_DOCS.get(func_name)

    if info is None:
        info = SCX_DOCS.get(func_name.replace('_', '.'))

    if info is None:
        for key in SCX_DOCS:
            if func_name in key or key in func_name:
                info = SCX_DOCS[key]
                func_name = key
                break

    if info is None:
        print(f"No documentation found for '{func_name}'")
        print(f"\nAvailable scx functions:")
        for key in sorted(SCX_DOCS.keys()):
            print(f"  - {key}")
        sys.exit(1)

    width = 80
    print("=" * width)
    print(f"sched_ext: {func_name}")
    print("=" * width)
    print()

    if info.get('signature'):
        print("SYNOPSIS:")
        print("-" * width)
        print(f"  {info['signature']}")
        print()

    if info.get('description'):
        print("DESCRIPTION:")
        print("-" * width)
        for line in info['description'].split('\n'):
            print(f"  {line}")
        print()

    if info.get('return'):
        print("RETURN VALUE:")
        print("-" * width)
        print(f"  {info['return']}")
        print()

    if info.get('context'):
        print("CONTEXT:")
        print("-" * width)
        print(f"  {info['context']}")
        print()

    if info.get('sleepable'):
        print("SLEEPABLE: Yes")
        print()

    if info.get('example'):
        print("EXAMPLE:")
        print("-" * width)
        for line in info['example'].split('\n'):
            print(f"  {line}")
        print()

    print("ONLINE RESOURCES:")
    print("-" * width)
    print(f"  https://docs.kernel.org/scheduler/sched-ext.html")
    print(f"  https://git.kernel.org/pub/scm/linux/kernel/git/tj/sched_ext.git/")
    print()
    print("=" * width)


def main():
    parser = argparse.ArgumentParser(
        description=(
            'After running --generate and installing to your man path:\n'
            '  man scx                       View overview\n'
            '  man scx_bpf_dsq_insert        View function docs\n'
            '  man -k scx                    Search all scx pages'
        ),
        epilog=(
            'Examples:\n'
            '  scx-man scx_bpf_dsq_insert    View dispatch function docs\n'
            '  scx-man ops.select_cpu         View select_cpu callback\n'
            '  scx-man scx                    View overview\n'
            '  scx-man --list                 List all available functions\n'
            '  scx-man --generate /tmp/man    Generate man pages to directory'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('function', nargs='?', help='scx function name (e.g., scx_bpf_dsq_insert)')
    parser.add_argument('--generate', metavar='DIR', help='Generate all man pages to directory')
    parser.add_argument('--list', action='store_true', help='List all available scx functions')

    args = parser.parse_args()

    if args.generate:
        generate_all_man_pages(args.generate)
        return

    if args.list:
        print("Available sched_ext functions:")
        print()
        print("Overview:")
        print("  scx")
        print()
        print("Ops Callbacks:")
        for k in sorted(SCX_DOCS.keys()):
            if k.startswith('ops.'):
                print(f"  {k}")
        print()
        print("Helper Functions (kfuncs):")
        for k in sorted(SCX_DOCS.keys()):
            if k.startswith('scx_bpf_') or k.startswith('bpf_iter_'):
                print(f"  {k}")
        return

    if args.function:
        view_doc(args.function)
    else:
        print("Usage: scx-man <function_name>")
        print("Example: scx-man scx_bpf_dsq_insert")
        print("         scx-man ops.dispatch")
        print("         scx-man scx")
        print()
        print("Options:")
        print("  --generate DIR   Generate all man pages to directory")
        print("  --list           List all available scx functions")
        sys.exit(1)


if __name__ == '__main__':
    main()
