# sched_ext (scx) Man Pages

Offline man page documentation for **sched_ext** — the Linux kernel's extensible scheduler class (kernel 6.12+).

## Install

```bash
sudo ./install-scx.sh
```

Installs 31 man pages and the `scx-man` lookup tool.

## Usage

### View with man

```bash
man scx                        # Overview
man scx_bpf_dsq_insert         # PRIMARY dispatch function
man scx_bpf_dsq_insert_vtime   # Priority/vtime dispatch
man scx_bpf_dsq_move_to_local  # Move task to local DSQ
man scx_bpf_select_cpu_dfl     # Default CPU selection
man scx_bpf_create_dsq         # Create custom DSQ
man ops_init                   # Initialization (sleepable)
man ops_select_cpu             # CPU selection on wakeup
man ops_enqueue                # Enqueue decision
man ops_dispatch               # Dispatch when CPU idle
man ops_stopping               # Task stopped
man ops_exit                   # Exit/cleanup
man -k scx                     # List all
```

### Quick terminal lookup

```bash
scx-man scx_bpf_dsq_insert
scx-man ops.dispatch
scx-man -h                     # Help
```

### List all functions

```bash
scx-man --LIST
```

## Files

| File | Purpose |
|------|---------|
| `scx-man.py` | Documentation database and man page generator |
| `install-scx.sh` | Installation script (installs man pages + `scx-man` tool) |

## Online Resources

- Kernel docs: https://docs.kernel.org/scheduler/sched-ext.html
- Kernel source: https://git.kernel.org/pub/scm/linux/kernel/git/tj/sched_ext.git/
- GitHub: https://github.com/sched-ext/scx
