#!/bin/bash
#
# install-scx.sh - Install sched_ext (scx) man pages
#
# Usage: sudo ./install-scx.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAN_DIR="/usr/local/share/man/man7"
BIN_DIR="/usr/local/bin"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (sudo ./install-scx.sh)"
    exit 1
fi

info "Installing sched_ext (scx) man pages..."

mkdir -p "${MAN_DIR}"

info "Generating man pages..."
python3 "${SCRIPT_DIR}/scx-man.py" --generate "${MAN_DIR}"

info "Installing scx-man lookup script..."
cp "${SCRIPT_DIR}/scx-man.py" "${BIN_DIR}/scx-man"
chmod +x "${BIN_DIR}/scx-man"

info "Installing tab completion..."
COMPLETION_DIR="/etc/bash_completion.d"
mkdir -p "${COMPLETION_DIR}"
cp "${SCRIPT_DIR}/scx-man-completion.bash" "${COMPLETION_DIR}/scx-man"

info "Updating man database..."
if command -v mandb &> /dev/null; then
    mandb -q
fi

info ""
info "[v] Installation complete!"
info ""
info "You can now view sched_ext documentation using:"
info "  man scx                        # Overview of sched_ext"
info "  man scx_bpf_dsq_insert         # Primary dispatch function"
info "  man scx_bpf_create_dsq         # Create DSQ"
info "  man ops_init                   # Init callback"
info "  man ops_select_cpu             # CPU selection callback"
info "  man ops_enqueue                # Enqueue callback"
info ""
info "Quick lookup:"
info "  scx-man scx_bpf_dsq_insert"
info "  scx-man ops.dispatch"
info "  scx-man -h                     # Help"
info ""
info "Tab completion is enabled! Type 'scx-man ' and press Tab to autocomplete."
info ""
info "List all scx functions:"
info "  scx-man --list"
info ""
info "Search scx functions:"
info "  man -k scx"
info "  apropos sched_ext"
info ""
