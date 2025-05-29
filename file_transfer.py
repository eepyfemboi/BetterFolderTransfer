import os
import shutil
import hashlib
import threading
import time
import sys
from datetime import timedelta

progress_lock = threading.Lock()
total_files = 0
total_bytes = 0
moved_files = 0
moved_bytes = 0
start_time = time.time()
current_file = ""
current_file_size = 0
last_update_time = start_time
last_moved_bytes = 0
last_moved_files = 0
is_transferring = True
SOURCE = ""
DEST = ""

def sha256sum(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def is_available(path):
    try:
        return os.path.exists(path)
    except Exception:
        return False

def debug_thread1():
    global last_update_time, last_moved_bytes, last_moved_files
    while is_transferring:
        time.sleep(1)
        with progress_lock:
            elapsed = time.time() - start_time
            bytes_per_sec = (moved_bytes - last_moved_bytes)
            files_per_sec = (moved_files - last_moved_files)
            last_moved_bytes = moved_bytes
            last_moved_files = moved_files
            last_update_time = time.time()

            if elapsed == 0:
                continue

            remaining_files = total_files - moved_files
            remaining_bytes = total_bytes - moved_bytes

            progress_percent = (moved_bytes / total_bytes) * 100 if total_bytes else 0
            eta = timedelta(seconds=(remaining_bytes / (moved_bytes / elapsed)) if moved_bytes else 0)

            print("\033c", end="")
            print(f"Progress: [{progress_percent:6.2f}%] {moved_files}/{total_files} files ({remaining_files} remaining), {moved_bytes / (1024**3):.2f} GB / {total_bytes / (1024**3):.2f} GB")
            print(f"ETA: {eta}, Transfer Rate: {bytes_per_sec:.2f} B/s ({bytes_per_sec/1024:.2f} KB/s, {bytes_per_sec/1024**2:.2f} MB/s, {bytes_per_sec/1024**3:.2f} GB/s), {files_per_sec} files/s")
            print(f"Current File: {current_file} ({current_file_size / (1024**2):.2f} MB)")


def debug_thread():
    global last_update_time, last_moved_bytes, last_moved_files
    import sys

    last_lines = 0

    while is_transferring:
        time.sleep(0.05)
        with progress_lock:
            elapsed = time.time() - start_time
            bytes_per_sec = moved_bytes - last_moved_bytes
            files_per_sec = moved_files - last_moved_files
            last_moved_bytes = moved_bytes
            last_moved_files = moved_files
            last_update_time = time.time()

            if elapsed == 0:
                continue

            remaining_files = total_files - moved_files
            remaining_bytes = total_bytes - moved_bytes

            progress_percent = (moved_bytes / total_bytes) * 100 if total_bytes else 0
            eta = timedelta(seconds=(remaining_bytes / (moved_bytes / elapsed)) if moved_bytes else 0)

            total_width = os.get_terminal_size().columns

            bar_len = total_width - 10 #40
            filled_len = int(bar_len * progress_percent / 100)
            bar = '█' * filled_len + '-' * (bar_len - filled_len)

            rate_i = ""
            if bytes_per_sec > 1024**3:
                rate_i = f"{bytes_per_sec / (1024**3):.2f} GiB/s"
            elif bytes_per_sec > 1024**2:
                rate_i = f"{bytes_per_sec / (1024**2):.2f} MiB/s"
            elif bytes_per_sec > 1024:
                rate_i = f"{bytes_per_sec / 1024:.2f} KiB/s"
            else:
                rate_i = f"{bytes_per_sec:.2f} B/s"
            
            rate_n = ""
            if files_per_sec > 1000**3:
                rate_n = f"{files_per_sec / (1000**3):.2f} GB/s"
            elif files_per_sec > 1000**2:
                rate_n = f"{files_per_sec / (1000**2):.2f} MB/s"
            elif files_per_sec > 1000:
                rate_n = f"{files_per_sec / 1000:.2f} KB/s"
            else:
                rate_n = ""

            lines = [
                f"[{bar}]",
                f"{progress_percent:6.2f}% ({moved_files}/{total_files} files), {moved_bytes / (1024**3):.2f} GB / {total_bytes / (1024**3):.2f} GB)",
                f"ETA: {eta}, {remaining_files} remaining, {remaining_bytes / (1024**3):.2f} GB",
                f"Rate: {rate_i} ({rate_n}), {files_per_sec} files/s",
                f"Current File: {current_file} ({current_file_size / (1024**2):.2f} MB)"
            ]

            if last_lines:
                sys.stdout.write(f"\x1b[{last_lines}A")
            for line in lines:
                sys.stdout.write("\x1b[2K")
                sys.stdout.write(line + "\n")
            sys.stdout.flush()
            last_lines = len(lines)


def count_files_and_size(src_dir):
    count = 0
    size = 0
    for root, _, files in os.walk(src_dir):
        for name in files:
            full_path = os.path.join(root, name)
            try:
                size += os.path.getsize(full_path)
                count += 1
            except Exception:
                continue
    return count, size

def wait_for_device(path):
    while not is_available(path):
        print(f"Waiting for {path} to become available...")
        time.sleep(5)

def main():
    global total_files, total_bytes, moved_files, moved_bytes
    global current_file, current_file_size, is_transferring, SOURCE, DEST

    if len(sys.argv) != 3:
        print("Usage: python file_transfer.py <source_folder> <destination_folder>")
        sys.exit(1)

    SOURCE = os.path.abspath(sys.argv[1])
    DEST = os.path.abspath(sys.argv[2])

    wait_for_device(SOURCE)
    wait_for_device(DEST)

    total_files, total_bytes = count_files_and_size(SOURCE)

    threading.Thread(target=debug_thread, daemon=True).start()

    for root, _, files in os.walk(SOURCE):
        for file in files:
            rel_path = os.path.relpath(os.path.join(root, file), SOURCE)
            src_path = os.path.join(root, file)
            dst_path = os.path.join(DEST, rel_path)

            try:
                wait_for_device(SOURCE)
                wait_for_device(DEST)

                with progress_lock:
                    current_file = rel_path
                    current_file_size = os.path.getsize(src_path)

                dst_dir = os.path.dirname(dst_path)
                os.makedirs(dst_dir, exist_ok=True)

                if os.path.exists(dst_path):
                    if os.path.getsize(dst_path) == os.path.getsize(src_path):
                        if sha256sum(src_path) == sha256sum(dst_path):
                            continue

                shutil.copy2(src_path, dst_path)

                if sha256sum(src_path) != sha256sum(dst_path):
                    print(f"Hash mismatch: {rel_path}")
                    continue

                os.remove(src_path)

                with progress_lock:
                    moved_files += 1
                    moved_bytes += current_file_size

            except Exception as e:
                print(f"Error processing {rel_path}: {e}")
                time.sleep(5)
                continue

    is_transferring = False
    time.sleep(2)
    print("Transfer complete.")

if __name__ == "__main__":
    main()
