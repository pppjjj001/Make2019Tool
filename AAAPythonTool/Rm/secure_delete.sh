#!/usr/bin/env bash
# secure_delete.sh
# Overwrite -> rename -> delete  a file or directory so contents can't be
# trivially recovered.  Called by secure_delete.bat or secure_delete_gui.pyw.

set -u

PASSES=${PASSES:-3}

if [ $# -lt 1 ]; then
    echo "Usage: $0 <target-path>" >&2
    exit 2
fi

TARGET="$1"

# Convert Windows path (C:\foo\bar) to MSYS path (/c/foo/bar)
if [[ "$TARGET" =~ ^[A-Za-z]:[\\/] ]]; then
    drive=$(echo "${TARGET:0:1}" | tr 'A-Z' 'a-z')
    rest="${TARGET:2}"
    rest="${rest//\\//}"
    TARGET="/$drive$rest"
fi

if [ ! -e "$TARGET" ]; then
    echo "[ERROR] target does not exist: $TARGET" >&2
    exit 1
fi

# Detect mode
if [ -d "$TARGET" ]; then
    MODE=dir
elif [ -f "$TARGET" ]; then
    MODE=file
else
    echo "[ERROR] unsupported target type: $TARGET" >&2
    exit 1
fi

# Refuse obviously dangerous targets (dir mode only)
if [ "$MODE" = dir ]; then
    case "$TARGET" in
        "/"|"/c"|"/c/"|"/c/Windows"*|"/c/Program Files"*|"/c/Program Files (x86)"*|"/c/Users"|"/c/Users/")
            echo "[ABORT] refusing to operate on system path: $TARGET" >&2
            exit 3
            ;;
    esac
fi

has_shred=0
command -v shred >/dev/null 2>&1 && has_shred=1

rand_name() { tr -dc 'a-z0-9' </dev/urandom 2>/dev/null | head -c 16; }

overwrite_one() {
    local f="$1"
    if [ $has_shred -eq 1 ]; then
        shred -f -n "$PASSES" -z "$f" 2>/dev/null \
            || echo "     ! shred failed: $f"
    else
        local size blocks p
        size=$(stat -c %s "$f" 2>/dev/null || echo 0)
        if [ "$size" -gt 0 ]; then
            blocks=$(( (size + 1048575) / 1048576 ))
            p=1
            while [ $p -le $PASSES ]; do
                dd if=/dev/urandom of="$f" bs=1M count=$blocks conv=notrunc status=none 2>/dev/null
                p=$((p+1))
            done
            dd if=/dev/zero of="$f" bs=1M count=$blocks conv=notrunc status=none 2>/dev/null
        fi
        : > "$f" 2>/dev/null
    fi
}

echo "[*] target : $TARGET"
echo "[*] mode   : $MODE"
echo "[*] passes : $PASSES"
echo "[*] tool   : $([ $has_shred -eq 1 ] && echo shred || echo 'dd fallback')"

chmod -R u+w "$TARGET" 2>/dev/null

# =====================================================================
# FILE MODE  -- just overwrite + rename + unlink
# =====================================================================
if [ "$MODE" = file ]; then
    echo "[1/3] overwriting file..."
    overwrite_one "$TARGET"

    echo "[2/3] renaming..."
    parent=$(dirname "$TARGET")
    new="$parent/$(rand_name)"
    while [ -e "$new" ]; do new="$parent/$(rand_name)"; done
    if mv -f "$TARGET" "$new" 2>/dev/null; then
        TARGET="$new"
    fi

    echo "[3/3] unlinking..."
    rm -f "$TARGET"
    if [ -e "$TARGET" ]; then
        echo "[FAIL] could not delete: $TARGET" >&2
        exit 1
    fi
    echo "[OK] securely deleted."
    exit 0
fi

# =====================================================================
# DIRECTORY MODE
# =====================================================================
total=$(find "$TARGET" -type f 2>/dev/null | wc -l | tr -d ' ')
echo "[*] file count: $total"

echo "[1/4] overwriting file contents..."
i=0
while IFS= read -r -d '' f; do
    i=$((i+1))
    overwrite_one "$f"
    [ $((i % 25)) -eq 0 ] && echo "     ... $i / $total"
done < <(find "$TARGET" -type f -print0 2>/dev/null)
echo "     done ($i files)."

echo "[2/4] renaming files to random names..."
while IFS= read -r -d '' f; do
    dir=$(dirname "$f")
    new="$dir/$(rand_name)"
    while [ -e "$new" ]; do new="$dir/$(rand_name)"; done
    mv -f "$f" "$new" 2>/dev/null
done < <(find "$TARGET" -depth -type f -print0 2>/dev/null)

echo "[3/4] renaming sub-directories..."
while IFS= read -r -d '' d; do
    [ "$d" = "$TARGET" ] && continue
    parent=$(dirname "$d")
    new="$parent/$(rand_name)"
    while [ -e "$new" ]; do new="$parent/$(rand_name)"; done
    mv -f "$d" "$new" 2>/dev/null
done < <(find "$TARGET" -depth -type d -print0 2>/dev/null)

echo "[4/4] removing tree..."
rm -rf "$TARGET"
if [ -e "$TARGET" ]; then sleep 1; rm -rf "$TARGET" 2>/dev/null; fi

if [ -e "$TARGET" ]; then
    echo "[FAIL] could not fully delete: $TARGET" >&2
    exit 1
fi

echo "[OK] securely deleted."
exit 0
