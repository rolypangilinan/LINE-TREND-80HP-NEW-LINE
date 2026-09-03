# 4 PROGRAM IN 1 SCRIPT
"LOGICAL COMPUTATION"
# USL LSL - EDITABLE MODEL MASTER + DIRECT RANGE CHECK
# FIND THE NEAREST GOOD
# ACCU AVG (TOL 5%)
# AKH (DOUBLE NOZZLE) (not working)
# DUO (SINGLE NOZZLE) W/ 2 SERIAL NUMBER (not working)

# SEARCH
# Display Python file name
# SERIAL NO AT 2ND TKINTER GUI
# DISPLAY SETTINGS TKINTER GUI

# CUSTOMTKINTER VERSION - Converted from Tkinter to CustomTkinter



import pandas as pd
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import os
import time
import threading
import queue
import io
import calendar
from datetime import datetime, timedelta
import matplotlib.dates as mdates
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.ticker as ticker

ctk.set_default_color_theme("blue")

# USL/LSL master table columns. Blank limits are treated as NOT APPLICABLE.
USL_LSL_MASTER_COLUMNS = [
    "MODEL CODE",
    "50Hz WAT USL", "50Hz WAT LSL",
    "50Hz VOL USL", "50Hz VOL LSL",
    "50Hz AMP USL", "50Hz AMP LSL",
    "50Hz CP USL", "50Hz CP LSL",
    "60Hz WAT USL", "60Hz WAT LSL",
    "60Hz VOL USL", "60Hz VOL LSL",
    "60Hz AMP USL", "60Hz AMP LSL",
    "60Hz CP USL", "60Hz CP LSL"
]

# One shared USL/LSL model master is used by ALL database locations.
# FASTLINE is the source of the existing master data, so TESTING/HP1/HP2/
# MULTILINE read and edit the same file instead of creating separate masters.
USL_LSL_SHARED_MASTER_PATH = r"\\192.168.2.19\general\INSPECTION-MACHINE\FAST-LINE\USL_LSL_MASTER.csv"

USL_LSL_LIMIT_MAP = {
    "50Hz_WATTAGE": ("50Hz WAT USL", "50Hz WAT LSL"),
    "50Hz_AIR_VOLUME": ("50Hz VOL USL", "50Hz VOL LSL"),
    "50Hz_AMPERAGE": ("50Hz AMP USL", "50Hz AMP LSL"),
    "50Hz_CLOSED_PRESSURE": ("50Hz CP USL", "50Hz CP LSL"),
    "60Hz_WATTAGE": ("60Hz WAT USL", "60Hz WAT LSL"),
    "60Hz_AIR_VOLUME": ("60Hz VOL USL", "60Hz VOL LSL"),
    "60Hz_AMPERAGE": ("60Hz AMP USL", "60Hz AMP LSL"),
    "60Hz_CLOSED_PRESSURE": ("60Hz CP USL", "60Hz CP LSL")
}

# CSV layout requested for the USL/LSL computation. The screenshot uses merged
# 50 HZ / 60 HZ headings, but CSV cannot store merged cells or fill colors, so
# each USL/LSL column is given a unique machine-readable name.
USL_LSL_OUTPUT_MAP = [
    ("DATE", "DATE"),
    ("TIME", "TIME"),
    ("MODEL CODE", "MODEL CODE"),
    ("TYPE", "TYPE"),
    ("BARCODE", "BARCODE"),
    ("SERIAL No.", "SERIAL No."),
    ("PASS/NG", "PASS/NG"),
    ("50Hz WAT", "50Hz WATTAGE"),
    ("50Hz WAT USL", "50Hz WAT USL"),
    ("50Hz WAT LSL", "50Hz WAT LSL"),
    ("50Hz VOL", "50Hz AIR VOLUME"),
    ("50Hz VOL USL", "50Hz VOL USL"),
    ("50Hz VOL LSL", "50Hz VOL LSL"),
    ("50Hz AMP", "50Hz AMPERAGE"),
    ("50Hz AMP USL", "50Hz AMP USL"),
    ("50Hz AMP LSL", "50Hz AMP LSL"),
    ("50Hz CP", "50Hz CLOSED PRESSURE"),
    ("50Hz CP USL", "50Hz CP USL"),
    ("50Hz CP LSL", "50Hz CP LSL"),
    ("60Hz WAT", "60Hz WATTAGE"),
    ("60Hz WAT USL", "60Hz WAT USL"),
    ("60Hz WAT LSL", "60Hz WAT LSL"),
    ("60Hz VOL", "60Hz AIR VOLUME"),
    ("60Hz VOL USL", "60Hz VOL USL"),
    ("60Hz VOL LSL", "60Hz VOL LSL"),
    ("60Hz AMP", "60Hz AMPERAGE"),
    ("60Hz AMP USL", "60Hz AMP USL"),
    ("60Hz AMP LSL", "60Hz AMP LSL"),
    ("60Hz CP", "60Hz CLOSED PRESSURE"),
    ("60Hz CP USL", "60Hz CP USL"),
    ("60Hz CP LSL", "60Hz CP LSL"),
    ("DATETIME", "DATETIME")
]

# LINE TREND shows four large graphs for the current MODEL CODE.
# Previous inspection rows are blue; the newest inspection row is green.
LINE_TREND_METRICS = [
    ("WATTAGE", "WATTAGE"),
    ("AIR VOLUME", "AIR VOLUME"),
    ("AMPERAGE", "AMPERAGE"),
    ("CLOSED PRESSURE", "CLOSED PRESSURE"),
]

def _prepare_line_trend_payload(compiled_frame, usl_lsl_lookup, max_points=50):
    """Prepare model-specific trend data without changing the inspection logic.

    The newest row supplies the MODEL CODE. The displayed frequency is selected
    from that model's configured USL/LSL master first, then from the newest
    inspection's non-zero values as a fallback. This keeps the four-chart layout
    from the reference screen while supporting both 50Hz and 60Hz log formats.
    """
    if compiled_frame is None or compiled_frame.empty or "MODEL CODE" not in compiled_frame.columns:
        return None

    latest = compiled_frame.iloc[-1]
    model = str(latest.get("MODEL CODE", "")).strip().upper()
    if not model:
        return None

    model_codes = compiled_frame["MODEL CODE"].astype(str).str.strip().str.upper()
    model_df = compiled_frame.loc[model_codes == model].tail(max_points).copy()
    if model_df.empty:
        return None

    master_row = usl_lsl_lookup.get(model, {}) if isinstance(usl_lsl_lookup, dict) else {}

    def _number_or_none(value):
        try:
            if value is None or pd.isna(value) or str(value).strip().upper() in ("", "N/A", "NA", "NONE"):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _configured_limit_count(freq):
        count = 0
        for _, suffix in LINE_TREND_METRICS:
            key = f"{freq}_{suffix.replace(' ', '_')}"
            usl_col, lsl_col = USL_LSL_LIMIT_MAP[key]
            if _number_or_none(master_row.get(usl_col)) is not None:
                count += 1
            if _number_or_none(master_row.get(lsl_col)) is not None:
                count += 1
        return count

    def _newest_nonzero_count(freq):
        count = 0
        magnitude = 0.0
        for _, suffix in LINE_TREND_METRICS:
            col = f"{freq} {suffix}"
            try:
                value = float(latest.get(col, 0))
                if pd.notna(value) and value != 0:
                    count += 1
                    magnitude += abs(value)
            except (TypeError, ValueError):
                pass
        return count, magnitude

    configured_50 = _configured_limit_count("50Hz")
    configured_60 = _configured_limit_count("60Hz")
    if configured_50 != configured_60:
        frequency = "50Hz" if configured_50 > configured_60 else "60Hz"
    else:
        nonzero_50, magnitude_50 = _newest_nonzero_count("50Hz")
        nonzero_60, magnitude_60 = _newest_nonzero_count("60Hz")
        if nonzero_50 != nonzero_60:
            frequency = "50Hz" if nonzero_50 > nonzero_60 else "60Hz"
        else:
            frequency = "50Hz" if magnitude_50 >= magnitude_60 else "60Hz"

    series = []
    for title, suffix in LINE_TREND_METRICS:
        col = f"{frequency} {suffix}"
        values = pd.to_numeric(model_df[col], errors="coerce").tolist() if col in model_df.columns else []
        key = f"{frequency}_{suffix.replace(' ', '_')}"
        usl_col, lsl_col = USL_LSL_LIMIT_MAP[key]
        series.append({
            "title": title,
            "column": col,
            "values": values,
            "usl": _number_or_none(master_row.get(usl_col)),
            "lsl": _number_or_none(master_row.get(lsl_col)),
        })

    serials = model_df["SERIAL No."].astype(str).tolist() if "SERIAL No." in model_df.columns else []
    return {
        "model": model,
        "frequency": frequency,
        "serials": serials,
        "series": series,
    }

def _draw_line_trend_axis(ax, item, frequency, compact=False):
    """Draw one USL/LSL trend axis.

    This helper is shared by the main Historical Measurement Trends panel and
    the LINE TREND tab so both views use the exact same data points, USL/LSL
    limits, and automatic Y-axis range.
    """
    ax.clear()
    values = item["values"]
    x = list(range(len(values)))

    # Previous inspection data = blue.
    if len(values) > 1:
        ax.plot(
            x[:-1], values[:-1], color="blue", marker="o",
            markersize=3 if compact else 4, linewidth=1.5 if compact else 1.8,
            label="Previous Data"
        )

    # Newest inspection data = green.  Connect it to the immediately previous
    # inspection to make the latest direction/change easy to see.
    if values:
        if len(values) > 1 and pd.notna(values[-2]) and pd.notna(values[-1]):
            ax.plot(
                [x[-2], x[-1]], [values[-2], values[-1]],
                color="green", marker="o",
                markersize=5 if compact else 6, linewidth=2.0 if compact else 2.4,
                label="New Data"
            )
        elif pd.notna(values[-1]):
            ax.scatter(
                [x[-1]], [values[-1]], color="green",
                s=35 if compact else 45, label="New Data", zorder=5
            )

    # Exact MODEL CODE USL/LSL limits = red dashed lines.
    if item["usl"] is not None:
        ax.axhline(item["usl"], color="red", linestyle="--", linewidth=1.3 if compact else 1.5, label="USL")
    if item["lsl"] is not None:
        ax.axhline(item["lsl"], color="red", linestyle="--", linewidth=1.3 if compact else 1.5, label="LSL")

    ax.set_title(
        f"{item['title']} TREND ({frequency})",
        fontsize=10 if compact else 13, fontweight="bold"
    )
    ax.set_ylabel("Value", fontsize=8 if compact else None)
    ax.set_xlabel("Inspection Sequence", fontsize=8 if compact else None)
    ax.grid(True, linestyle="--", alpha=0.55)
    ax.tick_params(axis="both", labelsize=7 if compact else 8)

    handles, labels = ax.get_legend_handles_labels()
    unique = {}
    for handle, label in zip(handles, labels):
        if label not in unique:
            unique[label] = handle
    if unique:
        ax.legend(unique.values(), unique.keys(), loc="best", fontsize=6 if compact else 8)

def _cancel_all_after(root):
    """Cancel all pending 'after' callbacks on a Tk root to prevent Tcl errors on destroy."""
    try:
        after_ids = root.tk.call('after', 'info')
        for after_id in after_ids:
            try:
                root.after_cancel(after_id)
            except Exception:
                pass
    except Exception:
        pass

def _open_binary_shared_read(path):
    """Open a file for reading while allowing the writer to keep its SMB handle open.

    On Windows this explicitly requests FILE_SHARE_READ | FILE_SHARE_WRITE |
    FILE_SHARE_DELETE. This is useful for ATU log CSV files that are being
    updated by another application. On non-Windows systems it falls back to
    the normal binary open.
    """
    if os.name != "nt":
        return open(path, "rb")

    import ctypes
    import msvcrt
    from ctypes import wintypes

    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    FILE_SHARE_DELETE = 0x00000004
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x00000080
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    create_file = ctypes.windll.kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
    ]
    create_file.restype = wintypes.HANDLE

    handle = create_file(
        path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None
    )
    if handle == INVALID_HANDLE_VALUE:
        error_code = ctypes.get_last_error()
        if not error_code:
            error_code = ctypes.windll.kernel32.GetLastError()
        raise PermissionError(error_code, os.strerror(error_code), path)

    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    except Exception:
        ctypes.windll.kernel32.CloseHandle(handle)
        raise

    return os.fdopen(fd, "rb", closefd=True)


class DatabaseSelection:
    def __init__(self, root):
        self.root = root

        # Reuse ONE CTk root for the whole application.
        # When returning from the monitoring screen, restore the Settings window
        # instead of creating another CTk root/mainloop.
        try:
            self.root.state("normal")
        except tk.TclError:
            pass

        self.root.title("Settings")
        self.root.geometry("580x650+383+50")  # (WIDTHxHEIGHT+LeftRight+UpDown)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

        self.scrollable_frame = ctk.CTkScrollableFrame(self.root)
        self.scrollable_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ctk.CTkLabel(self.scrollable_frame, text="CHOOSE DATABASE LOCATION:", font=('Arial', 12, 'bold')).pack(pady=10)
        self.location_var = tk.StringVar()
        locations = [
            ("SWITCH 1 - ATU006", "HP2"),
            ("SWITCH 2 - ATU003", "HP1"),
            ("FAST-LINE - ATU007", "FASTLINE"),
            ("MULTILINE - ATU005", "MULTILINE"),
            ("TESTING", "TESTING")
        ]
        for text, location in locations:
            ctk.CTkRadioButton(self.scrollable_frame, text=text, variable=self.location_var,
                          value=location).pack(anchor='w', padx=40, pady=2)

        ctk.CTkLabel(self.scrollable_frame, text="SELECT DATABASE FILE:", font=('Arial', 12, 'bold')).pack(pady=10)
        self.csv_var = tk.StringVar()
        self.location_to_dir = {
            "HP2": r"\\192.168.2.19\general\INSPECTION-MACHINE\HP2",
            "HP1": r"\\192.168.2.19\general\INSPECTION-MACHINE\HP1",
            "FASTLINE": r"\\192.168.2.19\general\INSPECTION-MACHINE\FAST-LINE",
            "MULTILINE": r"\\192.168.2.19\general\INSPECTION-MACHINE\HP3",
            "TESTING": r"\\192.168.2.19\ai_team\INDIVIDUAL FOLDER\June-San\p2LTG\p2LTG_TransferData\OTHER PROJECT",
        }
        self.location_to_atu = {
            "HP2": "ATU006",
            "HP1": "ATU003",
            "FASTLINE": "ATU007",
            "MULTILINE": "ATU005",
            "TESTING": None,
        }
        # FAST START:
        # Do NOT scan every network folder while the program is starting.
        # UNC/network folders can take many seconds or minutes to time out.
        # Files are loaded only for the location selected by the user.
        self.csv_files_by_location = {}
        self._file_scan_queue = queue.Queue()
        self._file_scan_token = 0
        self._scan_after_id = None

# DROPDOWN LIST COMBOBOX 
        self.csv_combo = ctk.CTkComboBox(
            self.scrollable_frame,
            variable=self.csv_var,
            values=["SELECT A LOCATION FIRST"],
            width=500
        )
        self.csv_combo.set("SELECT A LOCATION FIRST")
        self.csv_combo.pack(pady=5)
        self.location_var.trace("w", self.on_location_change)

        # Poll completed background network scans without freezing the GUI.
        self._scan_after_id = self.root.after(100, self._check_file_scan_result)

        ctk.CTkLabel(self.scrollable_frame, text="TOLERANCE:", font=('Arial', 12, 'bold')).pack(pady=10)
        # OFF is the default. OFF means there is no percentage-tolerance
        # comparison at all; it is intentionally different from 0%.
        self.tolerance_var = tk.StringVar(value="off")
        tolerances = [
            ("3%", "3"),
            ("5%", "5"),
            ("OTHERS", "others"),
            ("OFF", "off")
        ]
        for text, val in tolerances:
            ctk.CTkRadioButton(self.scrollable_frame, text=text, variable=self.tolerance_var, value=val).pack(anchor='w', padx=40, pady=2)

        self.other_frame = ctk.CTkFrame(self.scrollable_frame)
        ctk.CTkLabel(self.other_frame, text="Enter %:").pack(side=tk.LEFT, padx=5)
        self.other_entry = ctk.CTkEntry(self.other_frame, width=60)
        self.other_entry.insert(0, "5")
        self.other_entry.pack(side=tk.LEFT)
        self.tolerance_var.trace("w", self.on_tolerance_change)

        ctk.CTkLabel(self.scrollable_frame, text="GENERATE CSV FILE:", font=('Arial', 12, 'bold')).pack(pady=10)
        self.generate_csv_var = tk.StringVar(value="NO")
        ctk.CTkRadioButton(self.scrollable_frame, text="YES", variable=self.generate_csv_var,
                       value="YES").pack(anchor='w', padx=40, pady=2)
        ctk.CTkRadioButton(self.scrollable_frame, text="NO", variable=self.generate_csv_var,
                       value="NO").pack(anchor='w', padx=40, pady=2)

        ctk.CTkLabel(self.scrollable_frame, text="LOGICAL COMPUTATION:", font=('Arial', 12, 'bold')).pack(pady=10)
        self.logic_var = tk.StringVar(value="USL LSL")
        logics = [
            ("USL LSL", "USL LSL"),
            ("FIND THE NEAREST GOOD", "FIND THE NEAREST GOOD"),
            ("ACCU AVG (TOL 5%)", "ACCU AVG (TOL 5%)"),
            ("AKH (DOUBLE NOZZLE)", "AKH (DOUBLE NOZZLE)"),
            ("DUO (SINGLE NOZZLE) W/ 2 SERIAL NUMBER", "DUO (SINGLE NOZZLE) W/ 2 SERIAL NUMBER")
        ]
        for text, val in logics:
            ctk.CTkRadioButton(self.scrollable_frame, text=text, variable=self.logic_var, value=val).pack(anchor='w', padx=40, pady=2)

        ctk.CTkLabel(self.scrollable_frame, text="APPEARANCE MODE:", font=('Arial', 12, 'bold')).pack(pady=10)
        self.appearance_var = tk.StringVar(value="Dark")
        ctk.CTkRadioButton(self.scrollable_frame, text="DARK MODE", variable=self.appearance_var,
                       value="Dark").pack(anchor='w', padx=40, pady=2)
        ctk.CTkRadioButton(self.scrollable_frame, text="LIGHT MODE", variable=self.appearance_var,
                       value="Light").pack(anchor='w', padx=40, pady=2)
        self.appearance_var.trace("w", self.on_appearance_change)

        ctk.CTkButton(self.scrollable_frame, text="Confirm", command=self.confirm_selection).pack(pady=15)

    def on_appearance_change(self, *args):
        ctk.set_appearance_mode(self.appearance_var.get())

    def on_location_change(self, *args):
        location = self.location_var.get()
        if not location:
            return

        # If this location was already loaded, use the cached file list immediately.
        if location in self.csv_files_by_location:
            self._apply_file_list(location, self.csv_files_by_location[location])
            return

        # Show the Settings GUI immediately and scan only the selected network
        # location in a background thread so Windows SMB/UNC delays cannot freeze it.
        self.csv_var.set("")
        self.csv_combo.configure(values=["LOADING DATABASE FILES..."])
        self.csv_combo.set("LOADING DATABASE FILES...")

        self._file_scan_token += 1
        scan_token = self._file_scan_token

        threading.Thread(
            target=self._scan_location_files,
            args=(location, scan_token),
            daemon=True
        ).start()

    def _scan_location_files(self, location, scan_token):
        """Scan one selected network folder in the background."""
        directory = self.location_to_dir.get(location)
        atu = self.location_to_atu.get(location)
        files_with_mtime = []
        error = None

        try:
            # os.scandir is faster than os.listdir + os.path.getmtime because
            # it can reuse directory-entry metadata returned by the network share.
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        if not entry.is_file():
                            continue

                        name = entry.name
                        if name.startswith("log") and name.endswith(".csv"):
                            if atu is None or atu in name:
                                try:
                                    modified = entry.stat().st_mtime
                                except OSError:
                                    modified = 0
                                files_with_mtime.append(
                                    (modified, os.path.join(directory, name))
                                )
                    except OSError:
                        continue

            files_with_mtime.sort(key=lambda item: item[0])
            files = [path for _, path in files_with_mtime]

        except Exception as exc:
            files = []
            error = str(exc)

        # Worker thread only writes to Queue; all Tkinter updates stay on main thread.
        self._file_scan_queue.put((scan_token, location, files, error))

    def _check_file_scan_result(self):
        """Apply finished file scans from the Tkinter/main thread."""
        try:
            while True:
                scan_token, location, files, error = self._file_scan_queue.get_nowait()

                # Ignore an old result if the user already selected another location.
                if scan_token != self._file_scan_token:
                    continue

                self.csv_files_by_location[location] = files

                if self.location_var.get() == location:
                    self._apply_file_list(location, files, error)

        except queue.Empty:
            pass

        # Keep polling only while this Settings screen still exists.
        try:
            if self.scrollable_frame.winfo_exists():
                self._scan_after_id = self.root.after(100, self._check_file_scan_result)
        except tk.TclError:
            self._scan_after_id = None

    def _apply_file_list(self, location, files, error=None):
        """Update the database-file combobox after a selected folder is scanned."""
        if files:
            self.csv_combo.configure(values=files)
            self.csv_combo.set(files[-1])
            self.csv_var.set(files[-1])
        else:
            if error:
                display = "NETWORK LOCATION NOT AVAILABLE"
            else:
                display = "NO MATCHING CSV FILE FOUND"

            self.csv_var.set("")
            self.csv_combo.configure(values=[display])
            self.csv_combo.set(display)

    def on_tolerance_change(self, *args):
        if self.tolerance_var.get() == "others":
            self.other_frame.pack(anchor='w', padx=40, pady=5)
            self.other_entry.focus()
            self.root.update_idletasks()
        else:
            self.other_frame.pack_forget()
            self.root.update_idletasks()

    def confirm_selection(self):
        location = self.location_var.get()
        generate_csv = self.generate_csv_var.get()
        file_path = self.csv_var.get()
        tolerance_str = self.tolerance_var.get()
        appearance = self.appearance_var.get()
        if tolerance_str == "off":
            # None is used internally to mean tolerance is disabled.
            # Do not convert OFF to 0%, because 0% would flag every difference.
            tolerance = None
        else:
            if tolerance_str == "others":
                tolerance_str = self.other_entry.get().strip()
            try:
                tolerance = float(tolerance_str)
            except ValueError:
                tolerance = 5.0
        logic = self.logic_var.get()
        if location and generate_csv and file_path:
            # Stop the Settings-screen queue poll before replacing its widgets.
            if self._scan_after_id is not None:
                try:
                    self.root.after_cancel(self._scan_after_id)
                except tk.TclError:
                    pass
                self._scan_after_id = None

            # IMPORTANT:
            # Do NOT destroy the CTk root and do NOT start another mainloop here.
            # Tkinter/CustomTkinter should have one root and one mainloop.
            ctk.set_appearance_mode(appearance)

            # Remove the Settings widgets, then build the monitoring screen
            # on the SAME root window.
            for widget in self.root.winfo_children():
                widget.destroy()

            app = FluctuationMonitor(
                self.root,
                location,
                generate_csv,
                tolerance,
                file_path,
                logic,
                appearance
            )

            # Keep an explicit reference to the current screen controller.
            self.root._current_app = app
            self.root.protocol("WM_DELETE_WINDOW", app.on_closing)

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback

    def on_modified(self, event):
        if event.src_path.endswith('.csv'):
            # Watchdog runs on its own worker thread.  Do NOT run pandas or
            # Tkinter/CustomTkinter work from that thread.  Only mark that a
            # file change happened; the normal Tk main-loop poll will process it.
            self.callback()

class FluctuationMonitor:
    def __init__(self, root, location, generate_csv, tolerance, file_path, logic, appearance="Dark"):
        self.root = root
        self.appearance_var = tk.StringVar(value=appearance)
        self.line_width_var = tk.StringVar(value="Small")
        self.xaxis_var = tk.StringVar(value="Numerical Numbering")
        self.show_title_var = tk.BooleanVar(value=True)
        self.datapoints_var = tk.StringVar(value="None")
        self.scatter_color_var = tk.StringVar(value="Normal Blue")
        self.root.title(f"Fluctuation Status Monitor        Logical Computation: {logic}        File Name: {os.path.basename(__file__)}") # Display Python file name
        # self.root.geometry("1000x800")            # 2ND TKINTER GUI WINDOW SIZE
        self.root.attributes('-fullscreen', False)
        self.root.state('zoomed')
        self.zoom_level = 1.0
        self.generate_csv = generate_csv
        self.logic = logic  # Moved logic assignment here to ensure it's defined early
        self.line_trend_window = None
        self.line_trend_fig = None
        self.line_trend_canvas = None
        self.line_trend_axes = []
        # Separate date-filtered historical view. It is intentionally isolated
        # from the live monitoring dataframe so opening the history window cannot
        # alter inspection calculations, GOOD/NG logic, or console output.
        self.historical_settings_window = None
        self.historical_trend_window = None
        self.historical_trend_fig = None
        self.historical_trend_canvas = None
        self.historical_trend_axes = []
        self.historical_from_var = None
        self.historical_to_var = None
        self.historical_all_var = None
        self.history_x_axis_mode = None
        self.history_show_title_var = None
        self.history_layout_mode = None
        self.history_line_width_var = None
        self.history_line_other_entry = None
        self.history_datapoints_var = None
        self.history_scatter_color_var = None
        self.history_limitations_var = None
        self.historical_status_var = None
        self.historical_model_label = None
        self._historical_request_token = 0

        self.scrollable_frame = ctk.CTkScrollableFrame(root)
        self.scrollable_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        back_button_frame = ctk.CTkFrame(self.scrollable_frame)
        back_button_frame.pack(anchor='nw', pady=5, padx=5)
        ctk.CTkButton(back_button_frame, text="<- Back", command=self.go_back, width=80).pack(side=tk.LEFT)
        if self.logic == "USL LSL":
            # Teal is intentionally used here so the navigation tab is not confused
            # with the existing RED=NG and GREEN=GOOD inspection status colors.
            ctk.CTkButton(
                back_button_frame, text="USL LSL", command=self.open_usl_lsl_tab,
                width=120, fg_color="#0F8B8D", hover_color="#0B6E70"
            ).pack(side=tk.LEFT, padx=(12, 0))
            # Separate full-size trend view. Blue = previous data; green = newest data.
            ctk.CTkButton(
                back_button_frame, text="LINE TREND", command=self.open_line_trend_tab,
                width=120, fg_color="#3B6EA8", hover_color="#2F5A8A"
            ).pack(side=tk.LEFT, padx=(8, 0))
            ctk.CTkButton(
                back_button_frame, text="HISTORICAL TREND", command=self.open_historical_trend_tab,
                width=150, fg_color="#6B5B95", hover_color="#574A7A"
            ).pack(side=tk.LEFT, padx=(8, 0))

        zoom_frame = ctk.CTkFrame(self.scrollable_frame)
        zoom_frame.pack(pady=2, anchor='ne')
        ctk.CTkButton(zoom_frame, text="Zoom In (+)", command=lambda: self.zoom(1.1), width=100).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(zoom_frame, text="Zoom Out (-)", command=lambda: self.zoom(0.9), width=100).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(zoom_frame, text="Reset Zoom", command=lambda: self.zoom(1.0), width=100).pack(side=tk.LEFT, padx=2)

        self.status_vars = {}
        self.status_labels = {}
        self.current_model = None
        self.last_date = None
        self.last_good_values = {}
        self.last_good_serial = None
        self.fluctuation_count = 0
        self.tolerance_enabled = tolerance is not None
        # Infinity makes every percentage-based comparison pass when tolerance
        # is OFF, while USL/LSL mode continues to use the model master only.
        self.threshold = (tolerance / 100) if self.tolerance_enabled else float('inf')
        self.file_path = file_path
        if location == "HP2":
            self.output_path = r"\\192.168.2.19\general\INSPECTION-MACHINE\HP2\fluctuatedQC_CSV.csv"
        elif location == "HP1":
            self.output_path = r"\\192.168.2.19\general\INSPECTION-MACHINE\HP1\fluctuatedQC_CSV.csv"
        elif location == "TESTING":
            self.output_path = r"\\192.168.2.19\ai_team\INDIVIDUAL FOLDER\June-San\p2LTG\p2LTG_TransferData\OTHER PROJECT\fluctuatedQC_CSV.csv"
        elif location == "MULTILINE":
            self.output_path = r"\\192.168.2.19\general\INSPECTION-MACHINE\HP3\FLUCTUATED PROGRAM\NEW VERSION\fluctuatedQC_CSV.csv"
        else:  # FASTLINE     
            self.output_path = r"\\192.168.2.19\general\INSPECTION-MACHINE\FAST-LINE\fluctuatedQC_CSV.csv"
        self.log_path = os.path.join(os.path.dirname(self.output_path), "FLUCTUATION_QC.txt")
        # Shared across HP1, HP2, FASTLINE, MULTILINE and TESTING.
        self.usl_lsl_path = USL_LSL_SHARED_MASTER_PATH
        if self.logic == "USL LSL":
            self.usl_lsl_master = self._load_usl_lsl_master()
            self._refresh_usl_lsl_lookup()
        else:
            # Do not add any master-file/network work to the existing computations.
            self.usl_lsl_master = pd.DataFrame(columns=USL_LSL_MASTER_COLUMNS)
            self.usl_lsl_lookup = {}

        self.main_frame = ctk.CTkFrame(self.scrollable_frame)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.top_frame = ctk.CTkFrame(self.main_frame)
        self.top_frame.pack(fill=tk.X, pady=5)

        self.left_frame = ctk.CTkFrame(self.top_frame)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        ctk.CTkLabel(self.left_frame, text="Fluctuation Status Monitor", 
                 font=('Arial', 14, 'bold')).pack(pady=5)
        ctk.CTkLabel(self.left_frame, text=f"Location: {location}", 
                 font=('Arial', 12)).pack(pady=2)
        tolerance_display = f"{tolerance}%" if self.tolerance_enabled else "OFF"
        ctk.CTkLabel(self.left_frame, text=f"Tolerance: {tolerance_display}", 
                 font=('Arial', 12)).pack(pady=2)

        self.model_display = ctk.CTkLabel(self.left_frame, text="MODEL CODE: N/A", 
                                    font=('Arial', 12), text_color="#DA70D6")
        self.model_display.pack(pady=2)

        self.serial_display = ctk.CTkLabel(self.left_frame, text="SERIAL No.", 
                                      font=('Arial', 12), text_color="#66CCFF")
        self.serial_display.pack(pady=2)

        ref_label_text = "REFERENCE: USL/LSL MASTER" if self.logic == "USL LSL" else "REF SERIAL NO: N/A"
        self.ref_serial_display = ctk.CTkLabel(self.left_frame, text=ref_label_text, 
                                         font=('Arial', 12), text_color="green")
        if self.logic != "AKH (DOUBLE NOZZLE)":
            self.ref_serial_display.pack(pady=2)

        # Status box - redesigned from tk.Canvas to CTkFrame + CTkLabel
        self.status_box = ctk.CTkFrame(self.left_frame, width=300, height=150,
                                       fg_color="gray", corner_radius=8)
        self.status_box.pack(pady=10)
        self.status_box.pack_propagate(False)  # Prevent frame from shrinking

        self.status_text_label = ctk.CTkLabel(self.status_box, text="NO FLUCTUATION DETECTED", 
                                              font=('Arial', 14, 'bold'), text_color="white")
        self.status_text_label.pack(pady=(30, 10))

        self.counter_text_label = ctk.CTkLabel(self.status_box, text="Fluctuations: 0/8", 
                                               font=('Arial', 10), text_color="white")
        self.counter_text_label.pack(pady=5)

        self.serial_log = ctk.CTkTextbox(self.left_frame, height=80, width=300)
        self.serial_log.pack(pady=5)
        self.serial_log.insert("end", "Serial Number Log:\n")
        self.serial_log.configure(state='disabled')

        self.details_frame = ctk.CTkFrame(self.top_frame)
        self.details_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.create_section("50Hz Measurements", [
            "50Hz WATTAGE FLUCTUATED",
            "50Hz AIR VOLUME FLUCTUATED",
            "50Hz CLOSED PRESSURE FLUCTUATED",
            "50Hz AMPERAGE FLUCTUATED"
        ])
        # Separator
        ctk.CTkFrame(self.details_frame, height=2, fg_color="gray50").pack(fill='x', pady=5)
        self.create_section("60Hz Measurements", [
            "60Hz WATTAGE FLUCTUATED",
            "60Hz AIR VOLUME FLUCTUATED",
            "60Hz CLOSED PRESSURE FLUCTUATED",
            "60Hz AMPERAGE FLUCTUATED"
        ])
        # Separator
        ctk.CTkFrame(self.details_frame, height=2, fg_color="gray50").pack(fill='x', pady=5)

        self.avg_frame = None
        self.avg_vars = {}
        self.current_avgs = {}
        if logic in ["ACCU AVG (TOL 5%)", "AKH (DOUBLE NOZZLE)", "DUO (SINGLE NOZZLE) W/ 2 SERIAL NUMBER"]:
            self.avg_frame = ctk.CTkFrame(self.details_frame)
            self.avg_frame.pack(fill=tk.X, pady=5)
            avg_columns = [
                "50Hz WATTAGE",
                "50Hz AIR VOLUME",
                "50Hz CLOSED PRESSURE",
                "50Hz AMPERAGE",
                "60Hz WATTAGE",
                "60Hz AIR VOLUME",
                "60Hz CLOSED PRESSURE",
                "60Hz AMPERAGE"
            ]
            avg_columns_50 = avg_columns[:4]
            avg_columns_60 = avg_columns[4:]
            ctk.CTkLabel(self.avg_frame, text="50Hz AVERAGES:", font=('Arial', 10, 'bold')).pack(anchor='w')
            for col in avg_columns_50:
                row = ctk.CTkFrame(self.avg_frame)
                row.pack(fill=tk.X)
                ctk.CTkLabel(row, text=f"{col} AVG:", width=220, anchor='w').pack(side=tk.LEFT)
                self.avg_vars[col] = tk.StringVar(value="NONE")
                ctk.CTkLabel(row, textvariable=self.avg_vars[col]).pack(side=tk.LEFT)
            ctk.CTkLabel(self.avg_frame, text="60Hz AVERAGES:", font=('Arial', 10, 'bold')).pack(anchor='w')
            for col in avg_columns_60:
                row = ctk.CTkFrame(self.avg_frame)
                row.pack(fill=tk.X)
                ctk.CTkLabel(row, text=f"{col}:", width=220, anchor='w').pack(side=tk.LEFT)
                self.avg_vars[col] = tk.StringVar(value="NONE")
                ctk.CTkLabel(row, textvariable=self.avg_vars[col]).pack(side=tk.LEFT)
            self.ref_serial_display.configure(text="REF SERIAL NO: N/A")

        self.right_frame = ctk.CTkFrame(self.top_frame)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)
        self.create_bar_graph()

        self.line_graph_frame = ctk.CTkFrame(self.main_frame)
        self.line_graph_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.create_line_graph()

        button_frame = ctk.CTkFrame(self.main_frame)
        button_frame.pack(pady=5)
        ctk.CTkButton(button_frame, text="Refresh Values", 
                  command=self.process_and_update, width=120).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(button_frame, text="Reset All", 
                  command=self.reset_all_fluctuations, width=100).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(button_frame, text="Focus", 
                  command=self.open_focus_selection, width=80).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(button_frame, text="Display Settings", 
                  command=self.open_display_settings, width=120).pack(side=tk.LEFT, padx=2)

        # Dark/Light mode toggle
        mode_frame = ctk.CTkFrame(button_frame)
        mode_frame.pack(side=tk.LEFT, padx=10)
        ctk.CTkLabel(mode_frame, text="Theme:", font=('Arial', 10)).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(mode_frame, text="Dark", width=60,
                      command=lambda: self.switch_appearance("Dark")).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(mode_frame, text="Light", width=60,
                      command=lambda: self.switch_appearance("Light")).pack(side=tk.LEFT, padx=2)

        fluct_log_frame = ctk.CTkFrame(self.main_frame)
        fluct_log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        ctk.CTkLabel(fluct_log_frame, text="FLUCTUATION LOG", font=('Arial', 12, 'bold')).pack(anchor='center', pady=5)

        self.fluctuation_log = ctk.CTkTextbox(fluct_log_frame, height=300, width=700)
        self.fluctuation_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Network/SMB read state.  The inspection CSV is being written by the
        # ATU at the same time this program reads it, so transient disconnects
        # (for example Errno 32 / broken pipe) must be retried without flooding
        # the console or losing the file-change notification.
        self._file_change_event = threading.Event()
        self._processing_update = False
        self._network_error_active = False
        self._last_network_error_print = 0.0

        try:
            self.last_modified = os.path.getmtime(self.file_path)
        except OSError:
            # Initial load will keep retrying through periodic_check().
            self.last_modified = 0.0

        event_handler = FileChangeHandler(self._mark_file_changed)
        self.observer = Observer()
        self.observer.schedule(event_handler, os.path.dirname(self.file_path))
        self.observer.start()
        self.previous_measurements = {
            '50Hz_WATTAGE': [],
            '50Hz_AIR_VOLUME': [],
            '50Hz_CLOSED_PRESSURE': [],
            '50Hz_AMPERAGE': [],
            '60Hz_WATTAGE': [],
            '60Hz_AIR_VOLUME': [],
            '60Hz_CLOSED_PRESSURE': [],
            '60Hz_AMPERAGE': []
        }
        self.previous_model = None
        if self.logic != "ACCU AVG (TOL 5%)":
            self.last_good_values = {}
            self.last_good_serial = None
        if self.logic == "AKH (DOUBLE NOZZLE)":
            self.last_good_values_per_model = {'60HP20220S': {}, '60HP20220P': {}}
            self.last_good_serial_per_model = {'60HP20220S': None, '60HP20220P': None}
            self.previous_measurements_per_model = {
                '60HP20220S': {
                    '50Hz_WATTAGE': [], '50Hz_AIR_VOLUME': [], '50Hz_CLOSED_PRESSURE': [], '50Hz_AMPERAGE': [],
                    '60Hz_WATTAGE': [], '60Hz_AIR_VOLUME': [], '60Hz_CLOSED_PRESSURE': [], '60Hz_AMPERAGE': []
                },
                '60HP20220P': {
                    '50Hz_WATTAGE': [], '50Hz_AIR_VOLUME': [], '50Hz_CLOSED_PRESSURE': [], '50Hz_AMPERAGE': [],
                    '60Hz_WATTAGE': [], '60Hz_AIR_VOLUME': [], '60Hz_CLOSED_PRESSURE': [], '60Hz_AMPERAGE': []
                }
            }
        if self.logic == "DUO (SINGLE NOZZLE) W/ 2 SERIAL NUMBER":
            self.serial_to_runs = {}
            self.previous_measurements_by_run = {}
            self.reference_values = {}
            self.reference_serials = {}
        # Let the monitor window paint first, then load data.
        # This prevents the GUI from appearing half-drawn while the CSV is being processed.
        self._closing = False
        self.after_id = None
        self.root.after(100, self._initial_data_load)

    def switch_appearance(self, mode):
        ctk.set_appearance_mode(mode)
        self.appearance_var.set(mode)

    def _load_usl_lsl_master(self):
        """Load the editable model master without changing console output."""
        columns = USL_LSL_MASTER_COLUMNS
        try:
            if not os.path.exists(self.usl_lsl_path):
                return pd.DataFrame(columns=columns)
            master = pd.read_csv(self.usl_lsl_path, dtype={"MODEL CODE": str})
            for col in columns:
                if col not in master.columns:
                    master[col] = "" if col == "MODEL CODE" else pd.NA
            master = master[columns].copy()
            master["MODEL CODE"] = master["MODEL CODE"].fillna("").astype(str).str.strip().str.upper()
            for col in columns[1:]:
                master[col] = pd.to_numeric(master[col], errors="coerce")
            master = master[master["MODEL CODE"] != ""]
            master = master.drop_duplicates(subset=["MODEL CODE"], keep="last")
            return master.reset_index(drop=True)
        except Exception:
            # Keep monitoring available even if the master file is temporarily unavailable.
            return pd.DataFrame(columns=columns)

    def _refresh_usl_lsl_lookup(self):
        """Rebuild fast in-memory lookup after loading/saving the master table."""
        self.usl_lsl_lookup = {}
        if self.usl_lsl_master is None or self.usl_lsl_master.empty:
            return
        for _, row in self.usl_lsl_master.iterrows():
            model = str(row.get("MODEL CODE", "")).strip().upper()
            if not model:
                continue
            self.usl_lsl_lookup[model] = row.to_dict()

    def _get_usl_lsl_axis_max(self, model_code):
        """
        Return the USL/LSL bar-graph Y-axis maximum for the exact MODEL CODE.

        Rule requested for USL/LSL mode:
        1. Find the exact MODEL CODE from the newest log entry in the master.
        2. Find the highest configured USL across all 50 Hz and 60 Hz points.
        3. Add 5.
        4. Remove the decimal part (example: 79.8 + 5 = 84.8 -> 84).
        """
        model = str(model_code).strip().upper()
        master_row = self.usl_lsl_lookup.get(model)
        if master_row is None:
            return None

        usl_values = []
        for usl_col, _ in USL_LSL_LIMIT_MAP.values():
            usl = self._limit_or_none(master_row.get(usl_col))
            if usl is not None:
                usl_values.append(usl)

        if not usl_values:
            return None

        return max(1, int(max(usl_values) + 5))

    @staticmethod
    def _limit_or_none(value):
        """Convert a master-table value to float; blank/NaN means not applicable."""
        try:
            if value is None or pd.isna(value) or str(value).strip() == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _evaluate_usl_lsl(self, model_code, current_values):
        """
        Return binary inspection results for each point: 0=within limits / N.A., 1=NG.
        A model missing from the master is fail-safe NG for all 8 inspection points.
        A measurement with both USL and LSL blank is treated as NOT APPLICABLE.
        """
        # Exact MODEL CODE match only (after trimming spaces and normalizing case).
        # The model_code passed here comes from the current/new log entry.
        model = str(model_code).strip().upper()
        master_row = self.usl_lsl_lookup.get(model)
        limits = {key: (None, None) for key in USL_LSL_LIMIT_MAP}
        if master_row is None:
            return {key: 1.0 for key in current_values}, limits, False

        configured_points = 0
        results = {}
        for key, actual_raw in current_values.items():
            usl_col, lsl_col = USL_LSL_LIMIT_MAP[key]
            usl = self._limit_or_none(master_row.get(usl_col))
            lsl = self._limit_or_none(master_row.get(lsl_col))
            limits[key] = (usl, lsl)

            if usl is None and lsl is None:
                results[key] = 0.0
                continue

            configured_points += 1
            try:
                actual = float(actual_raw)
                invalid_actual = pd.isna(actual)
            except (TypeError, ValueError):
                invalid_actual = True
                actual = 0.0

            is_ng = invalid_actual
            if not is_ng and usl is not None and actual > usl:
                is_ng = True
            if not is_ng and lsl is not None and actual < lsl:
                is_ng = True
            results[key] = 1.0 if is_ng else 0.0

        # A model row with no actual specification values is not a valid reference.
        if configured_points == 0:
            return {key: 1.0 for key in current_values}, limits, False
        return results, limits, True

    def _write_compiled_output(self):
        """Write the requested USL/LSL CSV layout only for USL LSL logic."""
        if self.generate_csv != "YES":
            return
        if self.logic != "USL LSL":
            self.compiledFrame.to_csv(self.output_path, index=False, encoding='utf-8-sig')
            return

        output_df = pd.DataFrame()
        for output_col, source_col in USL_LSL_OUTPUT_MAP:
            if source_col in self.compiledFrame.columns:
                output_df[output_col] = self.compiledFrame[source_col]
            else:
                output_df[output_col] = ""
        output_df.to_csv(self.output_path, index=False, encoding='utf-8-sig')

    def open_usl_lsl_tab(self):
        """Open an editable, scrollable model USL/LSL master table."""
        if self.logic != "USL LSL":
            return

        # Reload first so external/manual changes are visible when the tab opens.
        self.usl_lsl_master = self._load_usl_lsl_master()
        self._refresh_usl_lsl_lookup()

        win = ctk.CTkToplevel(self.root)
        win.title("USL LSL - Model Master")
        win.geometry("1500x700+20+40")
        win.minsize(1000, 500)

        top = ctk.CTkFrame(win)
        top.pack(fill=tk.X, padx=10, pady=(10, 5))
        ctk.CTkLabel(
            top,
            text="USL / LSL MODEL MASTER  |  Double-click any cell to edit  |  Blank limit = N/A",
            font=('Arial', 13, 'bold')
        ).pack(side=tk.LEFT, padx=8, pady=8)

        table_frame = ctk.CTkFrame(win)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = USL_LSL_MASTER_COLUMNS
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=145 if col == "MODEL CODE" else 95, minwidth=80, anchor="center")

        def display_value(value):
            if value is None or pd.isna(value):
                return ""
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value)

        def load_rows(frame):
            for item in tree.get_children():
                tree.delete(item)
            for _, row in frame.iterrows():
                tree.insert("", "end", values=[display_value(row.get(col, "")) for col in columns])

        load_rows(self.usl_lsl_master)

        editor = {"entry": None}

        def commit_editor(save=True):
            entry = editor.get("entry")
            if entry is None:
                return
            item = editor.get("item")
            column_index = editor.get("column_index")
            if save and item and column_index is not None:
                values = list(tree.item(item, "values"))
                while len(values) < len(columns):
                    values.append("")
                values[column_index] = entry.get().strip()
                tree.item(item, values=values)
            try:
                entry.destroy()
            except tk.TclError:
                pass
            editor["entry"] = None

        def begin_edit(event):
            commit_editor(True)
            if tree.identify_region(event.x, event.y) != "cell":
                return
            item = tree.identify_row(event.y)
            col_id = tree.identify_column(event.x)
            if not item or not col_id:
                return
            column_index = int(col_id.replace("#", "")) - 1
            bbox = tree.bbox(item, col_id)
            if not bbox:
                return
            x, y, width, height = bbox
            values = list(tree.item(item, "values"))
            current = values[column_index] if column_index < len(values) else ""
            entry = ttk.Entry(tree)
            entry.insert(0, current)
            entry.select_range(0, "end")
            entry.place(x=x, y=y, width=width, height=height)
            entry.focus_set()
            editor.update({"entry": entry, "item": item, "column_index": column_index})
            entry.bind("<Return>", lambda _e: commit_editor(True))
            entry.bind("<Escape>", lambda _e: commit_editor(False))
            entry.bind("<FocusOut>", lambda _e: commit_editor(True))

        tree.bind("<Double-1>", begin_edit)

        footer = ctk.CTkFrame(win)
        footer.pack(fill=tk.X, padx=10, pady=(5, 10))
        status_var = tk.StringVar(value=f"Master file: {self.usl_lsl_path}")
        status_label = ctk.CTkLabel(footer, textvariable=status_var, anchor="w")
        status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

        def add_model():
            commit_editor(True)
            item = tree.insert("", "end", values=[""] * len(columns))
            tree.selection_set(item)
            tree.focus(item)
            tree.see(item)
            status_var.set("New blank model row added. Double-click cells to enter values, then Save All.")

        def delete_selected():
            commit_editor(True)
            selected = tree.selection()
            if not selected:
                status_var.set("Select one or more model rows to delete.")
                return
            for item in selected:
                tree.delete(item)
            status_var.set(f"Deleted {len(selected)} row(s) from the editor. Click Save All to make it permanent.")

        def save_all():
            commit_editor(True)
            rows = []
            seen = set()
            for item in tree.get_children():
                raw = list(tree.item(item, "values"))
                raw += [""] * (len(columns) - len(raw))
                model = str(raw[0]).strip().upper()
                if not model:
                    continue
                if model in seen:
                    status_var.set(f"SAVE ERROR: Duplicate MODEL CODE: {model}")
                    return
                seen.add(model)
                row = {"MODEL CODE": model}
                for idx, col in enumerate(columns[1:], start=1):
                    value = str(raw[idx]).strip()
                    # Treat N/A typed in the editable table exactly like a blank
                    # specification so one-sided USL/LSL limits can be saved.
                    if value.upper() in ("", "N/A", "NA", "NONE"):
                        row[col] = pd.NA
                    else:
                        try:
                            row[col] = float(value)
                        except ValueError:
                            status_var.set(f"SAVE ERROR: {model} / {col} must be numeric, N/A, or blank.")
                            return
                for _, (usl_col, lsl_col) in USL_LSL_LIMIT_MAP.items():
                    usl = self._limit_or_none(row.get(usl_col))
                    lsl = self._limit_or_none(row.get(lsl_col))
                    if usl is not None and lsl is not None and usl < lsl:
                        status_var.set(f"SAVE ERROR: {model} / {usl_col} cannot be lower than {lsl_col}.")
                        return
                rows.append(row)

            master = pd.DataFrame(rows, columns=columns)
            try:
                folder = os.path.dirname(self.usl_lsl_path)
                os.makedirs(folder, exist_ok=True)
                temp_path = self.usl_lsl_path + ".tmp"
                master.to_csv(temp_path, index=False, encoding="utf-8-sig")
                os.replace(temp_path, self.usl_lsl_path)
                self.usl_lsl_master = master
                self._refresh_usl_lsl_lookup()
                self.update_line_trend_tab()
                load_rows(master)
                status_var.set(f"SAVED: {len(master)} model(s) -> {self.usl_lsl_path}")
            except Exception as exc:
                status_var.set(f"SAVE ERROR: {exc}")

        def reload_master():
            commit_editor(True)
            self.usl_lsl_master = self._load_usl_lsl_master()
            self._refresh_usl_lsl_lookup()
            load_rows(self.usl_lsl_master)
            status_var.set(f"RELOADED: {len(self.usl_lsl_master)} model(s)")

        ctk.CTkButton(footer, text="Add Model", command=add_model, width=100).pack(side=tk.LEFT, padx=3)
        ctk.CTkButton(footer, text="Delete Selected", command=delete_selected, width=120).pack(side=tk.LEFT, padx=3)
        ctk.CTkButton(footer, text="Reload", command=reload_master, width=90).pack(side=tk.LEFT, padx=3)
        ctk.CTkButton(
            footer, text="Save All", command=save_all, width=100,
            fg_color="#0F8B8D", hover_color="#0B6E70"
        ).pack(side=tk.LEFT, padx=3)
        ctk.CTkButton(footer, text="Close", command=win.destroy, width=80).pack(side=tk.LEFT, padx=3)

    def open_line_trend_tab(self):
        """Open the four-chart LINE TREND view using all available window space."""
        if self.logic != "USL LSL":
            return

        try:
            if self.line_trend_window is not None and self.line_trend_window.winfo_exists():
                self.line_trend_window.deiconify()
                self.line_trend_window.lift()
                self.line_trend_window.focus_force()
                self.update_line_trend_tab()
                return
        except tk.TclError:
            self.line_trend_window = None

        win = ctk.CTkToplevel(self.root)
        win.title("LINE TREND")
        try:
            win.state("zoomed")
        except tk.TclError:
            win.geometry("1400x850+20+20")
        win.minsize(900, 600)
        self.line_trend_window = win

        graph_frame = ctk.CTkFrame(win)
        graph_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.line_trend_fig = Figure(figsize=(14, 8), dpi=100)
        self.line_trend_axes = [
            self.line_trend_fig.add_subplot(221),
            self.line_trend_fig.add_subplot(222),
            self.line_trend_fig.add_subplot(223),
            self.line_trend_fig.add_subplot(224),
        ]
        self.line_trend_fig.subplots_adjust(left=0.07, right=0.98, bottom=0.08, top=0.94, wspace=0.18, hspace=0.26)
        self.line_trend_canvas = FigureCanvasTkAgg(self.line_trend_fig, master=graph_frame)
        self.line_trend_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        win.protocol("WM_DELETE_WINDOW", self._close_line_trend_tab)
        self.update_line_trend_tab()

    def _close_line_trend_tab(self):
        """Close only the LINE TREND view and release its Matplotlib figure."""
        try:
            if self.line_trend_fig is not None:
                plt.close(self.line_trend_fig)
        except Exception:
            pass
        try:
            if self.line_trend_window is not None and self.line_trend_window.winfo_exists():
                self.line_trend_window.destroy()
        except tk.TclError:
            pass
        self.line_trend_window = None
        self.line_trend_fig = None
        self.line_trend_canvas = None
        self.line_trend_axes = []

    def update_line_trend_tab(self):
        """Refresh the four trend charts when a new inspection row is processed."""
        try:
            if self.line_trend_window is None or not self.line_trend_window.winfo_exists():
                return
            if self.line_trend_canvas is None or len(self.line_trend_axes) != 4:
                return

            payload = _prepare_line_trend_payload(
                getattr(self, "compiledFrame", None),
                getattr(self, "usl_lsl_lookup", {}),
                max_points=50,
            )

            if payload is None:
                for ax, (title, _) in zip(self.line_trend_axes, LINE_TREND_METRICS):
                    ax.clear()
                    ax.set_title(f"{title} TREND")
                    ax.text(0.5, 0.5, "NO DATA", ha="center", va="center", transform=ax.transAxes, fontsize=14)
                    ax.grid(True, linestyle="--", alpha=0.5)
                self.line_trend_canvas.draw_idle()
                return

            frequency = payload["frequency"]
            model = payload["model"]

            for ax, item in zip(self.line_trend_axes, payload["series"]):
                _draw_line_trend_axis(ax, item, frequency, compact=False)

            self.line_trend_fig.suptitle(
                f"LINE TREND   MODEL CODE: {model}   {frequency}",
                fontsize=14, fontweight="bold"
            )
            self.line_trend_canvas.draw_idle()
        except Exception:
            # LINE TREND must never interrupt the existing monitoring process or
            # add new console messages to the established console display.
            pass

    def _current_history_model(self):
        """Return the exact current MODEL CODE shown by the live monitor."""
        frame = getattr(self, "compiledFrame", None)
        if frame is None or frame.empty or "MODEL CODE" not in frame.columns:
            return ""
        return str(frame.iloc[-1].get("MODEL CODE", "")).strip().upper()

    @staticmethod
    def _history_date_text(value):
        """Format a date-like value for the friendly date controls."""
        try:
            return pd.to_datetime(value).strftime("%Y-%m-%d")
        except Exception:
            return datetime.now().strftime("%Y-%m-%d")

    def _history_default_dates(self):
        """Choose a useful initial range from data already loaded by the monitor."""
        frame = getattr(self, "compiledFrame", None)
        if frame is not None and not frame.empty and "DATETIME" in frame.columns:
            dts = pd.to_datetime(frame["DATETIME"], errors="coerce").dropna()
            if not dts.empty:
                latest = dts.max().normalize()
                earliest = dts.min().normalize()
                start = max(earliest, latest - pd.Timedelta(days=6))
                return start.strftime("%Y-%m-%d"), latest.strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        return today, today

    def _open_history_calendar(self, target_var, parent=None):
        """Open a real clickable month calendar for START/END date selection."""
        try:
            initial = datetime.strptime(target_var.get().strip(), "%Y-%m-%d")
        except Exception:
            initial = datetime.now()

        parent_window = parent or self.historical_settings_window or self.historical_trend_window or self.root
        picker = ctk.CTkToplevel(parent_window)
        picker.title("Select Date")
        picker.geometry("380x390")
        picker.resizable(False, False)
        try:
            picker.transient(parent_window)
        except tk.TclError:
            pass
        picker.grab_set()

        body = ctk.CTkFrame(picker)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        state = {"year": initial.year, "month": initial.month}
        title_var = tk.StringVar()

        header = ctk.CTkFrame(body)
        header.pack(fill=tk.X, pady=(0, 8))
        ctk.CTkButton(header, text="<", width=45,
                      command=lambda: change_month(-1)).pack(side=tk.LEFT, padx=3)
        ctk.CTkLabel(header, textvariable=title_var, font=('Arial', 15, 'bold')).pack(side=tk.LEFT, expand=True)
        ctk.CTkButton(header, text=">", width=45,
                      command=lambda: change_month(1)).pack(side=tk.RIGHT, padx=3)

        weekdays = ctk.CTkFrame(body)
        weekdays.pack(fill=tk.X)
        for idx, name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            weekdays.grid_columnconfigure(idx, weight=1)
            ctk.CTkLabel(weekdays, text=name, width=42, font=('Arial', 10, 'bold')).grid(
                row=0, column=idx, padx=1, pady=2
            )

        month_grid = ctk.CTkFrame(body)
        month_grid.pack(fill=tk.BOTH, expand=True)
        for idx in range(7):
            month_grid.grid_columnconfigure(idx, weight=1)
        for idx in range(6):
            month_grid.grid_rowconfigure(idx, weight=1)

        def close_picker():
            try:
                picker.grab_release()
            except tk.TclError:
                pass
            picker.destroy()

        def choose_day(day):
            selected = datetime(state["year"], state["month"], day)
            target_var.set(selected.strftime("%Y-%m-%d"))
            close_picker()

        def render_month():
            for child in month_grid.winfo_children():
                child.destroy()
            year, month = state["year"], state["month"]
            title_var.set(f"{calendar.month_name[month]} {year}")
            weeks = calendar.monthcalendar(year, month)
            for r in range(6):
                week = weeks[r] if r < len(weeks) else [0] * 7
                for c, day in enumerate(week):
                    if day == 0:
                        ctk.CTkLabel(month_grid, text="", width=42).grid(
                            row=r, column=c, padx=1, pady=2, sticky="nsew"
                        )
                    else:
                        selected = target_var.get().strip() == f"{year:04d}-{month:02d}-{day:02d}"
                        kwargs = {"fg_color": "#3B6EA8"} if selected else {}
                        ctk.CTkButton(
                            month_grid, text=str(day), width=42, height=34,
                            command=lambda d=day: choose_day(d), **kwargs
                        ).grid(row=r, column=c, padx=1, pady=2, sticky="nsew")

        def change_month(delta):
            month_index = state["year"] * 12 + (state["month"] - 1) + delta
            state["year"], month0 = divmod(month_index, 12)
            state["month"] = month0 + 1
            render_month()

        render_month()

        footer = ctk.CTkFrame(body)
        footer.pack(fill=tk.X, pady=(6, 0))
        ctk.CTkButton(
            footer, text="Today", width=90,
            command=lambda: [target_var.set(datetime.now().strftime("%Y-%m-%d")), close_picker()]
        ).pack(side=tk.LEFT, padx=4)
        ctk.CTkButton(footer, text="Cancel", width=90, command=close_picker).pack(side=tk.RIGHT, padx=4)

    def open_historical_trend_tab(self):
        """Show the SS2-style Historical Trend settings popup before any graph opens."""
        if self.logic != "USL LSL":
            return

        try:
            if self.historical_settings_window is not None and self.historical_settings_window.winfo_exists():
                self.historical_settings_window.deiconify()
                self.historical_settings_window.lift()
                self.historical_settings_window.focus_force()
                return
        except tk.TclError:
            self.historical_settings_window = None

        popup = ctk.CTkToplevel(self.root)
        popup.title("Historical Trend - Date Selection")
        popup.geometry("520x820+30+30")
        popup.minsize(450, 620)
        self.historical_settings_window = popup

        container = ctk.CTkScrollableFrame(popup)
        container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        ctk.CTkLabel(container, text="DATE SELECTION:", font=('Arial', 13, 'bold')).pack(pady=(8, 10))
        from_text, to_text = self._history_default_dates()
        self.historical_from_var = tk.StringVar(value=from_text)
        self.historical_to_var = tk.StringVar(value=to_text)
        self.historical_all_var = tk.BooleanVar(value=False)

        start_frame = ctk.CTkFrame(container)
        start_frame.pack(fill=tk.X, padx=14, pady=4)
        ctk.CTkLabel(start_frame, text="START DATE:", width=110, anchor="w").pack(side=tk.LEFT, padx=(8, 4), pady=5)
        start_entry = ctk.CTkEntry(start_frame, textvariable=self.historical_from_var, width=150, state="readonly")
        start_entry.pack(side=tk.LEFT, padx=4, pady=5)
        ctk.CTkButton(
            start_frame, text="Calendar", width=90,
            command=lambda: self._open_history_calendar(self.historical_from_var, popup)
        ).pack(side=tk.LEFT, padx=4, pady=5)

        end_frame = ctk.CTkFrame(container)
        end_frame.pack(fill=tk.X, padx=14, pady=4)
        ctk.CTkLabel(end_frame, text="END DATE:", width=110, anchor="w").pack(side=tk.LEFT, padx=(8, 4), pady=5)
        end_entry = ctk.CTkEntry(end_frame, textvariable=self.historical_to_var, width=150, state="readonly")
        end_entry.pack(side=tk.LEFT, padx=4, pady=5)
        ctk.CTkButton(
            end_frame, text="Calendar", width=90,
            command=lambda: self._open_history_calendar(self.historical_to_var, popup)
        ).pack(side=tk.LEFT, padx=4, pady=5)

        ctk.CTkCheckBox(
            container, text="ALL (START AT NOV 2024 ONWARDS)", variable=self.historical_all_var
        ).pack(anchor="w", padx=28, pady=(6, 10))

        ctk.CTkLabel(container, text="X-AXIS:", font=('Arial', 13, 'bold')).pack(pady=(10, 6))
        self.history_x_axis_mode = tk.StringVar(value="Numerical")
        for text_value, value in (
            ("Numerical Numbering", "Numerical"),
            ("Month/Year", "Month/Year"),
            ("Serial No.", "Serial No."),
        ):
            ctk.CTkRadioButton(container, text=text_value, variable=self.history_x_axis_mode, value=value).pack(
                anchor="w", padx=28, pady=2
            )
        self.history_show_title_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(container, text="Show Title", variable=self.history_show_title_var).pack(
            anchor="w", padx=28, pady=(4, 10)
        )

        ctk.CTkLabel(container, text="LAYOUT:", font=('Arial', 13, 'bold')).pack(pady=(10, 6))
        self.history_layout_mode = tk.StringVar(value="HORIZONTAL")
        ctk.CTkRadioButton(container, text="HORIZONTAL", variable=self.history_layout_mode, value="HORIZONTAL").pack(
            anchor="w", padx=28, pady=2
        )
        ctk.CTkRadioButton(container, text="VERTICAL", variable=self.history_layout_mode, value="VERTICAL").pack(
            anchor="w", padx=28, pady=2
        )

        ctk.CTkLabel(container, text="SPC LINE TREND WIDTH", font=('Arial', 13, 'bold')).pack(pady=(12, 6))
        self.history_line_width_var = tk.StringVar(value="MEDIUM")
        for label, value in (
            ("EXTRA EXTRA SMALL", "EXTRA EXTRA SMALL"),
            ("EXTRA SMALL", "EXTRA SMALL"),
            ("SMALL", "SMALL"),
            ("MEDIUM", "MEDIUM"),
            ("OTHERS", "OTHERS"),
        ):
            ctk.CTkRadioButton(container, text=label, variable=self.history_line_width_var, value=value).pack(
                anchor="w", padx=28, pady=2
            )
        other_width_frame = ctk.CTkFrame(container)
        ctk.CTkLabel(other_width_frame, text="Enter Width:").pack(side=tk.LEFT, padx=5)
        self.history_line_other_entry = ctk.CTkEntry(other_width_frame, width=70)
        self.history_line_other_entry.insert(0, "3.0")
        self.history_line_other_entry.pack(side=tk.LEFT, padx=5)

        def toggle_other_width(*_args):
            if self.history_line_width_var.get() == "OTHERS":
                other_width_frame.pack(anchor="w", padx=28, pady=4)
            else:
                other_width_frame.pack_forget()
        self.history_line_width_var.trace_add("write", toggle_other_width)

        ctk.CTkLabel(container, text="DATAPOINTS", font=('Arial', 13, 'bold')).pack(pady=(12, 6))
        self.history_datapoints_var = tk.StringVar(value="Scatter")
        ctk.CTkRadioButton(container, text="Scatter", variable=self.history_datapoints_var, value="Scatter").pack(
            anchor="w", padx=28, pady=2
        )
        ctk.CTkRadioButton(container, text="None", variable=self.history_datapoints_var, value="None").pack(
            anchor="w", padx=28, pady=2
        )

        ctk.CTkLabel(container, text="SCATTER COLOR:", font=('Arial', 13, 'bold')).pack(pady=(12, 6))
        self.history_scatter_color_var = tk.StringVar(value="Fluctuation Red")
        for label, value in (
            ("Normal Blue", "Normal Blue"),
            ("Fluctuation Red", "Fluctuation Red"),
            ("None", "None"),
        ):
            ctk.CTkRadioButton(container, text=label, variable=self.history_scatter_color_var, value=value).pack(
                anchor="w", padx=28, pady=2
            )

        ctk.CTkLabel(container, text="LIMITATIONS", font=('Arial', 13, 'bold')).pack(pady=(12, 6))
        self.history_limitations_var = tk.StringVar(value="USL/LSL")
        for label, value in (
            ("UCL/LCL", "UCL/LCL"),
            ("USL/LSL", "USL/LSL"),
            ("None", "None"),
        ):
            ctk.CTkRadioButton(container, text=label, variable=self.history_limitations_var, value=value).pack(
                anchor="w", padx=28, pady=2
            )
        ctk.CTkLabel(
            container,
            text="Note: limitations are used only to identify red scatter points. No dotted limit lines are drawn.",
            font=('Arial', 10), text_color="gray70", wraplength=420, justify="left"
        ).pack(anchor="w", padx=28, pady=(5, 10))

        button_frame = ctk.CTkFrame(container)
        button_frame.pack(fill=tk.X, padx=20, pady=(12, 15))
        ctk.CTkButton(
            button_frame, text="CONFIRM", width=120, fg_color="#6B5B95", hover_color="#574A7A",
            command=self._confirm_historical_settings
        ).pack(side=tk.LEFT, padx=8, pady=8)
        ctk.CTkButton(
            button_frame, text="CANCEL", width=100, command=self._close_historical_settings
        ).pack(side=tk.LEFT, padx=8, pady=8)

        popup.protocol("WM_DELETE_WINDOW", self._close_historical_settings)

    def _close_historical_settings(self):
        try:
            if self.historical_settings_window is not None and self.historical_settings_window.winfo_exists():
                self.historical_settings_window.destroy()
        except tk.TclError:
            pass
        self.historical_settings_window = None

    def _history_selected_dates(self):
        """Resolve popup dates, including the ALL option, without changing live data."""
        if self.historical_all_var is not None and self.historical_all_var.get():
            return datetime(2024, 11, 1), datetime.now()
        start = datetime.strptime(self.historical_from_var.get().strip(), "%Y-%m-%d")
        end = datetime.strptime(self.historical_to_var.get().strip(), "%Y-%m-%d")
        return start, end

    def _history_line_width(self):
        mapping = {
            "EXTRA EXTRA SMALL": 0.25,
            "EXTRA SMALL": 0.5,
            "SMALL": 1.0,
            "MEDIUM": 2.0,
        }
        selected = self.history_line_width_var.get() if self.history_line_width_var is not None else "MEDIUM"
        if selected == "OTHERS":
            try:
                value = float(self.history_line_other_entry.get().strip())
                return min(max(value, 0.1), 10.0)
            except Exception:
                return 2.0
        return mapping.get(selected, 2.0)

    def _confirm_historical_settings(self):
        """Validate SS2-style options, close popup, then open the SS1-style graph view."""
        try:
            start, end = self._history_selected_dates()
        except Exception:
            return
        if start > end:
            return
        model = self._current_history_model()
        if not model:
            return

        self._close_historical_settings()
        self._open_historical_graph_window(model, start, end)
        self.refresh_historical_trend(start, end, model)

    def _open_historical_graph_window(self, model, start, end):
        """Open the graph-only Historical Trend display after popup confirmation."""
        self._close_historical_trend_tab(close_settings=False)
        win = ctk.CTkToplevel(self.root)
        win.title("HISTORICAL TREND")
        try:
            win.state("zoomed")
        except tk.TclError:
            win.geometry("1450x900+10+10")
        win.minsize(950, 650)
        self.historical_trend_window = win

        top = ctk.CTkFrame(win)
        top.pack(fill=tk.X, padx=6, pady=(6, 2))
        ctk.CTkButton(top, text="<- Back", width=80, command=lambda: self._close_historical_trend_tab(close_settings=False)).pack(
            side=tk.LEFT, padx=4, pady=4
        )
        self.historical_model_label = ctk.CTkLabel(
            top,
            text=f"MODEL CODE: {model}    {start:%Y-%m-%d} to {end:%Y-%m-%d}",
            font=('Arial', 12, 'bold')
        )
        self.historical_model_label.pack(side=tk.LEFT, padx=12)
        self.historical_status_var = tk.StringVar(value="Loading historical data...")
        ctk.CTkLabel(top, textvariable=self.historical_status_var, anchor="w").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=12
        )

        graph_frame = ctk.CTkFrame(win)
        graph_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(2, 6))

        layout = self.history_layout_mode.get() if self.history_layout_mode is not None else "HORIZONTAL"
        if layout == "VERTICAL":
            self.historical_trend_fig = Figure(figsize=(14, 9), dpi=100)
            self.historical_trend_axes = [
                self.historical_trend_fig.add_subplot(221),
                self.historical_trend_fig.add_subplot(222),
                self.historical_trend_fig.add_subplot(223),
                self.historical_trend_fig.add_subplot(224),
            ]
            self.historical_trend_fig.subplots_adjust(left=0.07, right=0.985, bottom=0.09, top=0.92, hspace=0.34, wspace=0.20)
        else:
            # HORIZONTAL = four wide charts stacked vertically, matching SS1.
            self.historical_trend_fig = Figure(figsize=(15, 11), dpi=100)
            self.historical_trend_axes = [
                self.historical_trend_fig.add_subplot(411),
                self.historical_trend_fig.add_subplot(412),
                self.historical_trend_fig.add_subplot(413),
                self.historical_trend_fig.add_subplot(414),
            ]
            self.historical_trend_fig.subplots_adjust(left=0.065, right=0.99, bottom=0.07, top=0.95, hspace=0.28)

        self.historical_trend_canvas = FigureCanvasTkAgg(self.historical_trend_fig, master=graph_frame)
        self.historical_trend_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        win.protocol("WM_DELETE_WINDOW", lambda: self._close_historical_trend_tab(close_settings=False))

    def _close_historical_trend_tab(self, close_settings=True):
        """Close history graph/settings windows without touching live monitoring."""
        self._historical_request_token += 1
        try:
            if self.historical_trend_fig is not None:
                plt.close(self.historical_trend_fig)
        except Exception:
            pass
        try:
            if self.historical_trend_window is not None and self.historical_trend_window.winfo_exists():
                self.historical_trend_window.destroy()
        except tk.TclError:
            pass
        self.historical_trend_window = None
        self.historical_trend_fig = None
        self.historical_trend_canvas = None
        self.historical_trend_axes = []
        self.historical_status_var = None
        self.historical_model_label = None
        if close_settings:
            self._close_historical_settings()

    def _read_full_historical_csv(self):
        """Read history with short SMB retries; this does not alter live calculations."""
        retry_delays = (0.0, 0.15, 0.35)
        last_error = None
        for delay in retry_delays:
            if delay:
                time.sleep(delay)
            try:
                with _open_binary_shared_read(self.file_path) as f:
                    raw = f.read()
                text = raw.decode('latin1', errors='replace')
                return pd.read_csv(io.StringIO(text))
            except Exception as exc:
                last_error = exc
                if not self._is_transient_network_error(exc):
                    raise
        raise last_error

    def refresh_historical_trend(self, start=None, end=None, model=None):
        """Load date-filtered history in a background thread after confirmation."""
        if self.historical_trend_window is None or not self.historical_trend_window.winfo_exists():
            return
        if start is None or end is None:
            try:
                start, end = self._history_selected_dates()
            except Exception:
                if self.historical_status_var is not None:
                    self.historical_status_var.set("Invalid START/END date.")
                return
        if start > end:
            if self.historical_status_var is not None:
                self.historical_status_var.set("START DATE cannot be later than END DATE.")
            return
        model = (model or self._current_history_model()).strip().upper()
        if not model:
            if self.historical_status_var is not None:
                self.historical_status_var.set("No current MODEL CODE is available yet.")
            return

        self._historical_request_token += 1
        token = self._historical_request_token

        def worker():
            try:
                frame = self._read_full_historical_csv()
                result = (True, frame, None)
            except Exception as exc:
                result = (False, None, str(exc))
            try:
                self.root.after(0, lambda: self._apply_historical_data(token, model, start, end, result))
            except tk.TclError:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _history_scatter_out_mask(self, values, model, frequency, suffix):
        """Return NG/outlier mask for point colors only; never draws dotted limit lines."""
        values = pd.to_numeric(values, errors="coerce")
        mode = self.history_limitations_var.get() if self.history_limitations_var is not None else "None"
        if mode == "None":
            return pd.Series(False, index=values.index)

        if mode == "USL/LSL":
            master_row = getattr(self, "usl_lsl_lookup", {}).get(model, {})
            key = f"{frequency}_{suffix.replace(' ', '_')}"
            usl_col, lsl_col = USL_LSL_LIMIT_MAP[key]
            usl = self._limit_or_none(master_row.get(usl_col))
            lsl = self._limit_or_none(master_row.get(lsl_col))
            mask = pd.Series(False, index=values.index)
            if usl is not None:
                mask = mask | values.gt(usl)
            if lsl is not None:
                mask = mask | values.lt(lsl)
            return mask.fillna(False)

        # Reference popup's UCL/LCL option: use tolerance when enabled.
        # If tolerance is OFF, do not invent a threshold or mark false NG points.
        if mode == "UCL/LCL" and self.tolerance_enabled and not values.dropna().empty:
            mean = values.mean()
            upper = mean * (1 + self.threshold)
            lower = mean * (1 - self.threshold)
            return (values.gt(upper) | values.lt(lower)).fillna(False)
        return pd.Series(False, index=values.index)

    def _apply_historical_data(self, token, model, start, end, result):
        """Filter by exact MODEL CODE/date range and draw SS1-style graphs without dotted lines."""
        if token != self._historical_request_token:
            return
        try:
            if self.historical_trend_window is None or not self.historical_trend_window.winfo_exists():
                return
        except tk.TclError:
            return

        ok, frame, error = result
        if not ok:
            if self.historical_status_var is not None:
                self.historical_status_var.set(f"Unable to read historical log: {error}")
            return
        if frame is None or frame.empty:
            if self.historical_status_var is not None:
                self.historical_status_var.set("No historical records were found in the selected log file.")
            return

        frame = frame.copy()
        frame.columns = frame.columns.str.strip()
        required = {"DATE", "TIME", "MODEL CODE"}
        if not required.issubset(frame.columns):
            if self.historical_status_var is not None:
                self.historical_status_var.set("Selected log file is missing DATE, TIME, or MODEL CODE columns.")
            return

        def fix_time(value):
            value_text = str(value).strip()
            try:
                parts = value_text.split(':')
                if len(parts) >= 2 and int(parts[0]) >= 24:
                    parts[0] = f"{int(parts[0]) % 24:02d}"
                    return ':'.join(parts)
            except Exception:
                pass
            return value_text

        frame["TIME"] = frame["TIME"].apply(fix_time)
        frame["DATETIME"] = pd.to_datetime(
            frame["DATE"].astype(str).str.strip() + " " + frame["TIME"].astype(str).str.strip(),
            format="mixed", errors="coerce"
        )
        frame = frame.dropna(subset=["DATETIME"])
        end_exclusive = end + timedelta(days=1)
        model_codes = frame["MODEL CODE"].astype(str).str.strip().str.upper()
        frame = frame[(model_codes == model) & (frame["DATETIME"] >= start) & (frame["DATETIME"] < end_exclusive)].copy()

        if "TYPE" in frame.columns:
            frame = frame[~frame["TYPE"].astype(str).isin(['T', 'D', 'A'])]
        if "PASS/NG" in frame.columns:
            pass_numeric = pd.to_numeric(frame["PASS/NG"], errors="coerce")
            frame = frame[pass_numeric.ne(0) | pass_numeric.isna()]
        frame = frame.sort_values("DATETIME").reset_index(drop=True)

        if frame.empty:
            if self.historical_status_var is not None:
                self.historical_status_var.set(
                    f"No {model} records found from {start:%Y-%m-%d} to {end:%Y-%m-%d}."
                )
            for ax, (title, _) in zip(self.historical_trend_axes, LINE_TREND_METRICS):
                ax.clear()
                if self.history_show_title_var is None or self.history_show_title_var.get():
                    ax.set_title(f"{title} HISTORICAL TREND")
                ax.text(0.5, 0.5, "NO DATA IN SELECTED RANGE", ha="center", va="center", transform=ax.transAxes)
                ax.grid(True, linestyle="-", alpha=0.20)
            self.historical_trend_canvas.draw_idle()
            return

        payload = _prepare_line_trend_payload(frame, getattr(self, "usl_lsl_lookup", {}), max_points=len(frame))
        if payload is None:
            if self.historical_status_var is not None:
                self.historical_status_var.set("Unable to prepare historical trend data for this model.")
            return
        frequency = payload["frequency"]
        line_width = self._history_line_width()

        # Plot every selected record. X is sequence-based so all three popup x-axis modes remain friendly.
        x = list(range(len(frame)))
        num_ticks = min(10, len(frame))
        tick_positions = sorted(set(int(v) for v in pd.Series(
            [round(i * (len(frame) - 1) / max(num_ticks - 1, 1)) for i in range(num_ticks)]
        ).tolist())) if len(frame) else []

        serial_col = "SERIAL No." if "SERIAL No." in frame.columns else ("S/N" if "S/N" in frame.columns else None)

        for ax, (title, suffix) in zip(self.historical_trend_axes, LINE_TREND_METRICS):
            ax.clear()
            col = f"{frequency} {suffix}"
            if col not in frame.columns:
                if self.history_show_title_var is None or self.history_show_title_var.get():
                    ax.set_title(f"{title} HISTORICAL TREND ({frequency})", fontweight="bold")
                ax.text(0.5, 0.5, "COLUMN NOT AVAILABLE", ha="center", va="center", transform=ax.transAxes)
                ax.grid(True, linestyle="-", alpha=0.20)
                continue

            values = pd.to_numeric(frame[col], errors="coerce")
            y = values.tolist()
            ax.plot(x, y, color="blue", linewidth=line_width)

            if self.history_datapoints_var is not None and self.history_datapoints_var.get() == "Scatter":
                color_mode = self.history_scatter_color_var.get() if self.history_scatter_color_var is not None else "Normal Blue"
                if color_mode != "None":
                    if color_mode == "Fluctuation Red":
                        out_mask = self._history_scatter_out_mask(values, model, frequency, suffix)
                        colors = ["red" if bool(flag) else "blue" for flag in out_mask.tolist()]
                    else:
                        colors = ["blue"] * len(values)
                    ax.scatter(x, y, c=colors, s=16, zorder=4)

            # IMPORTANT: user requested NO DOTTED REFERENCE LINES in Historical Trend.
            # Limitations are used only for scatter-point classification above.
            if self.history_show_title_var is None or self.history_show_title_var.get():
                ax.set_title(f"{title} HISTORICAL TREND ({frequency})", fontsize=10, fontweight="bold")
            else:
                ax.set_title("")
            ax.set_ylabel("Value", fontsize=8)
            ax.grid(True, linestyle="-", linewidth=0.5, alpha=0.22)
            ax.tick_params(axis="both", labelsize=7)

            axis_mode = self.history_x_axis_mode.get() if self.history_x_axis_mode is not None else "Numerical"
            if tick_positions:
                ax.set_xticks(tick_positions)
                if axis_mode == "Month/Year":
                    labels = [frame["DATETIME"].iloc[pos].strftime("%m/%Y") for pos in tick_positions]
                    ax.set_xlabel("Month/Year", fontsize=8)
                elif axis_mode == "Serial No." and serial_col is not None:
                    labels = [str(frame[serial_col].iloc[pos]) for pos in tick_positions]
                    ax.set_xlabel("Serial No.", fontsize=8)
                else:
                    labels = [str(pos + 1) for pos in tick_positions]
                    ax.set_xlabel("Sample Number", fontsize=8)
                ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)

        self.historical_trend_fig.suptitle(
            f"HISTORICAL TREND   MODEL CODE: {model}   {frequency}   {start:%Y-%m-%d} to {end:%Y-%m-%d}",
            fontsize=12, fontweight="bold"
        )
        self.historical_trend_canvas.draw_idle()
        if self.historical_status_var is not None:
            self.historical_status_var.set(f"Loaded {len(frame)} records.")

    def go_back(self):
        self._closing = True

        # Cancel only this screen's own scheduled callback.
        # Do not cancel every "after" callback on the CTk root because
        # CustomTkinter itself may use scheduled callbacks internally.
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None

        # Stop the watchdog observer used by the monitoring screen.
        try:
            self.observer.stop()
            self.observer.join()
        except Exception:
            pass

        # Close Matplotlib figures before rebuilding the Settings screen.
        self._close_line_trend_tab()
        self._close_historical_trend_tab()
        try:
            if hasattr(self, "fig"):
                plt.close(self.fig)
            if hasattr(self, "line_fig"):
                plt.close(self.line_fig)
        except Exception:
            pass

        # Remove the monitoring widgets, but KEEP the same CTk root alive.
        for widget in self.root.winfo_children():
            try:
                widget.destroy()
            except tk.TclError:
                pass

        # Rebuild Settings on the same root. No new CTk(), no nested mainloop().
        DatabaseSelection(self.root)

    def zoom(self, factor):
        if factor != 1.0:
            self.zoom_level *= factor
        else:
            self.zoom_level = 1.0
        self.zoom_level = max(0.5, min(self.zoom_level, 2.0))
        widgets = [
            (self.serial_display, 12),
            (self.ref_serial_display, 12),
            (self.model_display, 12),
        ]
        for widget, base_size in widgets:
            new_size = int(base_size * self.zoom_level)
            widget.configure(font=('Arial', new_size))

        new_width = int(300 * self.zoom_level)
        new_height = int(150 * self.zoom_level)
        self.status_box.configure(width=new_width, height=new_height)

        new_size_status = int(14 * self.zoom_level)
        self.status_text_label.configure(font=('Arial', new_size_status, 'bold'))
        new_size_counter = int(10 * self.zoom_level)
        self.counter_text_label.configure(font=('Arial', new_size_counter))

        for column in self.status_vars:
            new_size = int(10 * self.zoom_level)
            self.status_labels[column].configure(font=('Arial', new_size, 'bold'))

        if hasattr(self, 'fig'):
            self.fig.set_size_inches(6 * self.zoom_level, 4 * self.zoom_level)
            self.canvas_graph.draw()
        if hasattr(self, 'line_fig'):
            if self.logic == "USL LSL":
                self.line_fig.set_size_inches(8 * self.zoom_level, 5 * self.zoom_level)
            else:
                self.line_fig.set_size_inches(8 * self.zoom_level, 3 * self.zoom_level)
            self.line_canvas.draw()

    def create_bar_graph(self):
        """Create the matplotlib bar graph for displaying current fluctuation values"""
        self.fig, self.ax = plt.subplots(figsize=(6, 3.9))
        self.fluctuation_measurements = [
            '50 WAT', '50 VOL', '50 CloP.', '50 AMP',
            '60 WAT', '60 VOL', '60 CloP.', '60 AMP'
        ]
        self.fluctuation_values = [0] * len(self.fluctuation_measurements)
        self.bars = self.ax.bar(self.fluctuation_measurements, self.fluctuation_values, color='blue')
        self.ax.grid(True)
        self.ax.set_xticks(range(len(self.fluctuation_measurements)))
        self.ax.set_xticklabels(self.fluctuation_measurements, rotation=45, ha='right', fontsize=7)
        if self.logic == "USL LSL":
            # Actual inspection values are displayed. The final Y-axis maximum
            # is recalculated from the exact model's highest USL after data loads.
            self.ax.set_title('Current Inspection Values vs USL/LSL')
            self.ax.set_ylabel('Inspection Value')
            self.ax.set_ylim(0, 10)
        else:
            self.ax.set_title('Current Fluctuation Values')
            self.ax.set_ylabel('Fluctuation Amount (%)')
            if self.tolerance_enabled:
                self.ax.axhline(y=self.threshold * 100, color='r', linestyle='--', linewidth=1)
                self.ax.text(1.01, self.threshold * 100, 'Threshold (%.1f%%)' % (self.threshold * 100), color='r', va='center', ha='left', 
                             transform=self.ax.get_yaxis_transform(), fontsize=8, 
                             bbox=dict(facecolor='white', edgecolor='none', alpha=0.8))
        # Adjust layout with larger margins to avoid tight_layout warning
        self.fig.subplots_adjust(left=0.1, right=0.85, top=0.9, bottom=0.25)
        self.canvas_graph = FigureCanvasTkAgg(self.fig, master=self.right_frame)
        self.canvas_graph.draw()
        self.canvas_graph.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def create_line_graph(self):
        """Create historical trend graph(s).

        USL LSL mode uses the same four independent axes as the LINE TREND tab
        so each measurement keeps its own meaningful Y-axis range.  Other
        computation modes retain the original combined 8-series chart.
        """
        self.line_fig = Figure(figsize=(8, 6), dpi=100)

        if self.logic == "USL LSL":
            self.line_axes = [
                self.line_fig.add_subplot(221),
                self.line_fig.add_subplot(222),
                self.line_fig.add_subplot(223),
                self.line_fig.add_subplot(224),
            ]
            # Keep line_ax available for compatibility with any existing code that
            # expects the attribute, although USL/LSL now uses line_axes.
            self.line_ax = self.line_axes[0]
            for ax, (title, _) in zip(self.line_axes, LINE_TREND_METRICS):
                ax.set_title(f"{title} TREND")
                ax.set_ylabel("Value")
                ax.set_xlabel("Inspection Sequence")
                ax.grid(True, linestyle="--", alpha=0.55)
            self.line_fig.suptitle('Historical Measurement Trends', fontsize=11, fontweight='bold')
            self.line_fig.subplots_adjust(left=0.07, right=0.98, bottom=0.10, top=0.90, wspace=0.20, hspace=0.38)
        else:
            self.line_axes = []
            self.line_ax = self.line_fig.add_subplot(111)
            self.line_ax.set_title('Historical Measurement Trends')
            self.line_ax.set_ylabel('Value')
            self.line_ax.grid(True)
            self.line_ax.plot([], [], label='50Hz WATTAGE', color='blue', linewidth=1.5)
            self.line_ax.plot([], [], label='50Hz AIR VOLUME', color='green', linewidth=1.5)
            self.line_ax.plot([], [], label='50Hz CLOSED PRESSURE', color='red', linewidth=1.5)
            self.line_ax.plot([], [], label='50Hz AMPERAGE', color='cyan', linewidth=1.5)
            self.line_ax.plot([], [], label='60Hz WATTAGE', color='magenta', linewidth=1.5)
            self.line_ax.plot([], [], label='60Hz AIR VOLUME', color='yellow', linewidth=1.5)
            self.line_ax.plot([], [], label='60Hz CLOSED PRESSURE', color='black', linewidth=1.5)
            self.line_ax.plot([], [], label='60Hz AMPERAGE', color='orange', linewidth=1.5)
            legend = self.line_ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
            for line in legend.get_lines():
                line.set_linewidth(4.0)  # Thicker legend lines
            self.line_ax.tick_params(axis='x', rotation=45, labelsize=8)
            self.line_fig.subplots_adjust(left=0.1, right=0.75, bottom=0.25, top=0.9)

        self.line_canvas = FigureCanvasTkAgg(self.line_fig, master=self.line_graph_frame)
        self.line_canvas.draw()
        self.line_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def downsample_data(self, df, max_points=50):
        if len(df) <= max_points:
            return df
        step = len(df) // max_points
        return df.iloc[::step]

    def update_line_graph(self):
        """Update the line graph with historical data"""
        try:
            if not hasattr(self, 'compiledFrame') or self.compiledFrame.empty:
                return

            # In USL/LSL mode the main historical panel intentionally uses the
            # exact same payload and axis-drawing helper as the LINE TREND tab.
            # This makes the plotted data and Y-axis ranges match between both
            # screens instead of compressing WATT/VOL/CP/AMP onto one shared axis.
            if self.logic == "USL LSL":
                if not hasattr(self, "line_axes") or len(self.line_axes) != 4:
                    return
                payload = _prepare_line_trend_payload(
                    self.compiledFrame,
                    getattr(self, "usl_lsl_lookup", {}),
                    max_points=50,
                )
                if payload is None:
                    for ax, (title, _) in zip(self.line_axes, LINE_TREND_METRICS):
                        ax.clear()
                        ax.set_title(f"{title} TREND")
                        ax.text(0.5, 0.5, "NO DATA", ha="center", va="center", transform=ax.transAxes, fontsize=10)
                        ax.grid(True, linestyle="--", alpha=0.55)
                    self.line_fig.suptitle('Historical Measurement Trends', fontsize=11, fontweight='bold')
                else:
                    frequency = payload["frequency"]
                    model = payload["model"]
                    for ax, item in zip(self.line_axes, payload["series"]):
                        _draw_line_trend_axis(ax, item, frequency, compact=True)
                    self.line_fig.suptitle(
                        f"Historical Measurement Trends   MODEL CODE: {model}   {frequency}",
                        fontsize=11, fontweight='bold'
                    )
                self.line_fig.subplots_adjust(left=0.07, right=0.98, bottom=0.10, top=0.90, wspace=0.20, hspace=0.38)
                self.line_canvas.draw()
                return
            self.line_ax.clear()
            df = self.compiledFrame.tail(50)
            df = self.downsample_data(df)
            measurements = [
                ('50Hz WATTAGE', 'blue'),
                ('50Hz AIR VOLUME', 'green'),
                ('50Hz CLOSED PRESSURE', 'red'),
                ('50Hz AMPERAGE', 'cyan'),
                ('60Hz WATTAGE', 'magenta'),
                ('60Hz AIR VOLUME', 'yellow'),
                ('60Hz CLOSED PRESSURE', 'black'),
                ('60Hz AMPERAGE', 'orange')
            ]
            linewidth_map = {
                'Extra Small': 0.8,
                'Small': 1.2,
                'Medium': 1.8
            }
            linewidth = linewidth_map.get(self.line_width_var.get(), 1.5)
            if self.xaxis_var.get() == "Numerical Numbering":
                x = range(len(df))
                self.line_ax.set_xticks(x)
                self.line_ax.set_xticklabels(x, rotation=45)
            elif self.xaxis_var.get() == "Month/Year":
                x = df['DATETIME']
                xticklabels = df['DATETIME'].dt.strftime('%m/%Y')
                self.line_ax.set_xticks(x)
                self.line_ax.set_xticklabels(xticklabels, rotation=45)
            elif self.xaxis_var.get() == "Serial No":
                x = df['DATETIME']
                xticklabels = df['SERIAL No.']
                self.line_ax.set_xticks(x)
                self.line_ax.set_xticklabels(xticklabels, rotation=45)
            else:
                x = df['DATETIME']
            for meas, color in measurements:
                y = df[meas]
                mean = y.mean()
                std = y.std()
                ucl = mean + 3 * std
                lcl = mean - 3 * std
                self.line_ax.plot(x, y, label=meas, color=color, linewidth=linewidth)
                self.line_ax.axhline(mean, color=color, linestyle='-', alpha=0.5)
                self.line_ax.axhline(ucl, color=color, linestyle='--', alpha=0.5)
                self.line_ax.axhline(lcl, color=color, linestyle='--', alpha=0.5)
                if self.datapoints_var.get() == "Scatter" and self.scatter_color_var.get() == "Normal Blue":
                    self.line_ax.scatter(x, y, color='blue', s=10)
            if self.show_title_var.get():
                self.line_ax.set_title('Historical Measurement Trends')
            else:
                self.line_ax.set_title('')
            self.line_ax.set_ylabel('Value')
            self.line_ax.grid(True)
            self.line_ax.tick_params(axis='x', rotation=45, labelsize=8)
            legend = self.line_ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
            for line in legend.get_lines():
                line.set_linewidth(4.0)  # Thicker legend lines
            self.line_fig.subplots_adjust(left=0.1, right=0.75, bottom=0.25, top=0.9)
            self.line_canvas.draw()
        except Exception as e:
            print(f"Error updating line graph: {e}")

    def update_bar_graph(self, last_row):
        """Update the bar graph with current inspection or fluctuation values."""
        try:
            self.ax.clear()
            status_values = [
                last_row['50Hz WATTAGE FLUCTUATED'],
                last_row['50Hz AIR VOLUME FLUCTUATED'],
                last_row['50Hz CLOSED PRESSURE FLUCTUATED'],
                last_row['50Hz AMPERAGE FLUCTUATED'],
                last_row['60Hz WATTAGE FLUCTUATED'],
                last_row['60Hz AIR VOLUME FLUCTUATED'],
                last_row['60Hz CLOSED PRESSURE FLUCTUATED'],
                last_row['60Hz AMPERAGE FLUCTUATED']
            ]
            self.ax.grid(True)
            self.ax.set_xticks(range(len(self.fluctuation_measurements)))
            self.ax.set_xticklabels(self.fluctuation_measurements, rotation=45, ha='right', fontsize=7)

            if self.logic == "USL LSL":
                # MODEL CODE always comes from the newest/current log row. The exact
                # same MODEL CODE is used to locate the master specifications.
                model_code = str(last_row.get('MODEL CODE', '')).strip().upper()
                actual_values = [
                    float(last_row['50Hz WATTAGE']),
                    float(last_row['50Hz AIR VOLUME']),
                    float(last_row['50Hz CLOSED PRESSURE']),
                    float(last_row['50Hz AMPERAGE']),
                    float(last_row['60Hz WATTAGE']),
                    float(last_row['60Hz AIR VOLUME']),
                    float(last_row['60Hz CLOSED PRESSURE']),
                    float(last_row['60Hz AMPERAGE'])
                ]
                statuses = [float(v) for v in status_values]
                self.fluctuation_values = actual_values

                # USL/LSL status color: keep GOOD inspection bars blue and make
                # only the specific inspection point(s) that are NG red.
                bar_colors = ['red' if status > 0 else 'blue' for status in statuses]
                self.bars = self.ax.bar(
                    self.fluctuation_measurements, actual_values, color=bar_colors
                )
                self.ax.set_title('Current Inspection Values vs USL/LSL')
                self.ax.set_ylabel('Inspection Value')

                # User rule: highest USL (50/60 Hz) + 5, then remove decimals.
                axis_max = self._get_usl_lsl_axis_max(model_code)
                if axis_max is None:
                    # Fail-safe display only when the model has no master USL data.
                    # This does not change the NG decision or master lookup.
                    fallback = max(actual_values) if actual_values else 0
                    axis_max = max(10, int(fallback + 5))
                self.ax.set_ylim(0, axis_max)

                for bar, actual, status in zip(self.bars, actual_values, statuses):
                    self.ax.text(
                        bar.get_x() + bar.get_width()/2., actual,
                        f'{actual:.2f}  {"NG" if status > 0 else "GOOD"}',
                        ha='center', va='bottom', fontsize=7
                    )
            else:
                self.fluctuation_values = [float(v) * 100 for v in status_values]
                self.bars = self.ax.bar(self.fluctuation_measurements, self.fluctuation_values, color='blue')
                self.ax.set_title('Current Fluctuation Values')
                self.ax.set_ylabel('Fluctuation Amount (%)')
                max_value = max(self.fluctuation_values) if max(self.fluctuation_values) > 0 else 10
                self.ax.set_ylim(0, max_value * 1.1)
                for bar in self.bars:
                    height = bar.get_height()
                    self.ax.text(bar.get_x() + bar.get_width()/2., height,
                                f'{height:.2f}',
                                ha='center', va='bottom')
                if self.tolerance_enabled:
                    self.ax.axhline(y=self.threshold * 100, color='r', linestyle='--', linewidth=1)
                    self.ax.text(1.01, self.threshold * 100, 'Threshold (%.1f%%)' % (self.threshold * 100), color='r', va='center', ha='left', 
                                 transform=self.ax.get_yaxis_transform(), fontsize=8, 
                                 bbox=dict(facecolor='white', edgecolor='none', alpha=0.8))

            self.fig.subplots_adjust(left=0.1, right=0.85, top=0.9, bottom=0.25)
            self.canvas_graph.draw()
        except Exception as e:
            print(f"Error updating bar graph: {e}")

    def update_status_box(self, has_fluctuation, count=0):
        if has_fluctuation:
            self.status_box.configure(fg_color="red")
            if self.logic == "USL LSL":
                self.status_text_label.configure(text="NG - OUTSIDE USL/LSL")
                self.counter_text_label.configure(text=f"NG Points: {count}/8")
            else:
                self.status_text_label.configure(text="FLUCTUATION DETECTED!")
                self.counter_text_label.configure(text=f"Fluctuations: {count}/8")
        else:
            self.status_box.configure(fg_color="green")
            if self.logic == "USL LSL":
                self.status_text_label.configure(text="GOOD - WITHIN USL/LSL")
                self.counter_text_label.configure(text="NG Points: 0/8")
            else:
                self.status_text_label.configure(text="NO FLUCTUATION DETECTED")
                self.counter_text_label.configure(text="Fluctuations: 0/8")

    def _initial_data_load(self):
        """Load the initial data after the GUI has had a chance to draw."""
        if self._closing:
            return
        self.process_and_update()
        if not self._closing:
            self.after_id = self.root.after(1000, self.periodic_check)

    def _mark_file_changed(self):
        """Called by watchdog worker thread; never touch Tk widgets here."""
        if not self._closing:
            self._file_change_event.set()

    @staticmethod
    def _is_transient_network_error(exc):
        """Return True for temporary SMB/network I/O failures worth retrying."""
        if isinstance(exc, (BrokenPipeError, ConnectionError, TimeoutError)):
            return True
        if isinstance(exc, OSError):
            errno_value = getattr(exc, "errno", None)
            winerror_value = getattr(exc, "winerror", None)
            # 32  = broken pipe (as seen in the current console)
            # 53  = network path not found
            # 64  = network name no longer available
            # 109 = pipe ended
            # 121 = semaphore timeout
            # 1231 = network location cannot be reached
            transient_codes = {32, 53, 64, 109, 121, 1231}
            return errno_value in transient_codes or winerror_value in transient_codes
        return False

    def _report_network_read_error(self, exc):
        """Print one useful network warning, then suppress repeats for 30 seconds."""
        now = time.monotonic()
        if (not self._network_error_active) or (now - self._last_network_error_print >= 30.0):
            print(f"NETWORK READ TEMPORARILY UNAVAILABLE: {exc} | automatic retry enabled")
            self._last_network_error_print = now
        self._network_error_active = True

    def _report_network_recovered(self):
        """Print recovery only once after a previously reported network failure."""
        if self._network_error_active:
            print("NETWORK READ RESTORED")
            self._network_error_active = False

    def _read_recent_csv(self):
        """Retry the live SMB CSV read by reopening the file on each attempt."""
        retry_delays = (0.0, 0.15, 0.35)
        last_error = None
        for delay in retry_delays:
            if delay:
                time.sleep(delay)
            try:
                return self._read_recent_csv_once()
            except Exception as exc:
                last_error = exc
                if not self._is_transient_network_error(exc):
                    raise
        raise last_error

    def _read_recent_csv_once(self):
        """
        Read only the recent end of the inspection CSV instead of loading the
        entire historical network file on every refresh.

        The processing logic resets when the DATE changes, so for the current
        screen we only need the complete latest day plus a small amount of the
        previous day for the historical graph. The reader expands backwards
        until it reaches the previous date (or a safety limit).
        """
        initial_bytes = 1024 * 1024       # Start with the newest 1 MB
        max_bytes = 32 * 1024 * 1024      # Safety cap: 32 MB
        previous_day_rows_needed = 100

        # Use an explicit Windows shared-read handle so the ATU software can
        # continue writing while this monitor reads the same network CSV.
        with _open_binary_shared_read(self.file_path) as f:
            header = f.readline()
            data_start = f.tell()
            f.seek(0, os.SEEK_END)
            file_size = f.tell()

            if file_size <= data_start:
                return pd.DataFrame()

            available = file_size - data_start
            chunk_size = min(initial_bytes, available)
            last_df = None

            while True:
                start = max(data_start, file_size - chunk_size)
                f.seek(start)
                raw = f.read(file_size - start)

                # If starting in the middle of the file, discard the first
                # partial line so pandas always receives a complete CSV row.
                if start > data_start:
                    newline_pos = raw.find(b'\n')
                    if newline_pos >= 0:
                        raw = raw[newline_pos + 1:]

                csv_bytes = header + raw
                text = csv_bytes.decode('latin1', errors='replace')
                try:
                    df = pd.read_csv(io.StringIO(text))
                except Exception:
                    # Expand the tail and retry if the first cut happened in
                    # an unusual CSV record.
                    if chunk_size < min(max_bytes, available):
                        chunk_size = min(chunk_size * 2, max_bytes, available)
                        continue
                    raise

                last_df = df
                if df.empty or 'DATE' not in df.columns:
                    break

                dates = df['DATE'].astype(str).str.strip()
                latest_date = dates.iloc[-1]
                latest_mask = dates == latest_date
                latest_positions = [i for i, is_latest in enumerate(latest_mask.tolist()) if is_latest]
                first_latest_pos = latest_positions[0] if latest_positions else 0
                rows_before_latest = first_latest_pos

                # Once the chunk reaches before the latest date, all records
                # for the latest date are present. Keep some earlier rows too
                # so the 50-point historical graph still has context.
                if start == data_start or rows_before_latest >= previous_day_rows_needed:
                    break

                new_size = min(chunk_size * 2, max_bytes, available)
                if new_size == chunk_size:
                    print('FAST LOAD WARNING: latest-day data exceeded the 32 MB tail limit.')
                    break
                chunk_size = new_size

            return last_df if last_df is not None else pd.DataFrame()

    def periodic_check(self):
        if self._closing:
            return
        self.check_file_update()
        self.after_id = self.root.after(1000, self.periodic_check)  # Store the after ID

    def check_file_update(self):
        try:
            current_modified = os.path.getmtime(self.file_path)
            # If startup happened while the network CSV was busy, continue trying
            # on the normal 1-second cycle until the first inspection row loads.
            needs_initial_retry = (
                not hasattr(self, 'compiledFrame') or self.compiledFrame.empty
            )
            watchdog_change = self._file_change_event.is_set()
            if current_modified > self.last_modified or needs_initial_retry or watchdog_change:
                # IMPORTANT: do not advance last_modified until processing succeeds.
                # Otherwise a broken-pipe read can cause a newly written inspection
                # row to be treated as already seen.
                success = self.process_and_update()
                if success:
                    self.last_modified = max(self.last_modified, current_modified)
                    self._file_change_event.clear()
        except Exception as exc:
            if self._is_transient_network_error(exc):
                self._report_network_read_error(exc)
            # Keep the pending file-change event set; periodic_check will retry.

    def process_and_update(self):
        """Serialized/safe wrapper around the original inspection processing."""
        if self._closing:
            return False
        if self._processing_update:
            # Another update is already running. Keep any watchdog event pending
            # so the next 1-second main-loop pass can process it.
            return False

        self._processing_update = True
        try:
            self._process_and_update_core()
            self._report_network_recovered()
            return True
        except Exception as exc:
            if self._is_transient_network_error(exc):
                self._report_network_read_error(exc)
            else:
                # Non-network processing errors are still important and should
                # remain visible instead of being silently swallowed.
                print(f"Error processing file: {exc}")
            return False
        finally:
            self._processing_update = False

    def _process_and_update_core(self):
        global compiledFrame
        try:
            dataList = []
            pd.set_option('display.max_columns', None)
            # FAST DATA LOAD: read the recent end of the network CSV instead
            # of re-reading the complete historical file.
            df = self._read_recent_csv()
            if df.empty:
                return
            df.columns = df.columns.str.strip()
            def fix_time(time_str):
                try:
                    hours, minutes, seconds = map(int, time_str.split(':'))
                    if hours >= 24:
                        hours = hours % 24
                        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    return time_str
                except:
                    return time_str
            df['TIME'] = df['TIME'].apply(fix_time)
            df['DATETIME'] = pd.to_datetime(
                df['DATE'] + ' ' + df['TIME'],
                format='mixed',
                errors='coerce'
            )
            df = df.dropna(subset=['DATETIME'])
            df = df.sort_values('DATETIME')
            emptyColumn = [
                "DATE", "TIME", "MODEL CODE", "TYPE", "BARCODE", "SERIAL No.", "PASS/NG",
                "50Hz WATTAGE", "50Hz WATTAGE FLUCTUATED",
                "50Hz AIR VOLUME", "50Hz AIR VOLUME FLUCTUATED",
                "50Hz CLOSED PRESSURE", "50Hz CLOSED PRESSURE FLUCTUATED",
                "50Hz AMPERAGE", "50Hz AMPERAGE FLUCTUATED",
                "60Hz WATTAGE", "60Hz WATTAGE FLUCTUATED",
                "60Hz AIR VOLUME", "60Hz AIR VOLUME FLUCTUATED",
                "60Hz CLOSED PRESSURE", "60Hz CLOSED PRESSURE FLUCTUATED",
                "60Hz AMPERAGE", "60Hz AMPERAGE FLUCTUATED",
                "REFERENCE SERIAL", "DATETIME"
            ]
            # Define dtypes for compiledFrame to ensure consistency
            dtype_dict = {
                "DATE": str,
                "TIME": str,
                "MODEL CODE": str,
                "TYPE": str,
                "BARCODE": str,
                "SERIAL No.": str,
                "PASS/NG": str,
                "50Hz WATTAGE": float,
                "50Hz WATTAGE FLUCTUATED": float,
                "50Hz AIR VOLUME": float,
                "50Hz AIR VOLUME FLUCTUATED": float,
                "50Hz CLOSED PRESSURE": float,
                "50Hz CLOSED PRESSURE FLUCTUATED": float,
                "50Hz AMPERAGE": float,
                "50Hz AMPERAGE FLUCTUATED": float,
                "60Hz WATTAGE": float,
                "60Hz WATTAGE FLUCTUATED": float,
                "60Hz AIR VOLUME": float,
                "60Hz AIR VOLUME FLUCTUATED": float,
                "60Hz CLOSED PRESSURE": float,
                "60Hz CLOSED PRESSURE FLUCTUATED": float,
                "60Hz AMPERAGE": float,
                "60Hz AMPERAGE FLUCTUATED": float,
                "REFERENCE SERIAL": str,
                "DATETIME": "datetime64[ns]"
            }
            if self.logic == "USL LSL":
                limit_columns = [col for col in USL_LSL_MASTER_COLUMNS if col != "MODEL CODE"]
                emptyColumn.extend(limit_columns)
                dtype_dict.update({col: float for col in limit_columns})
            if not hasattr(self, 'compiledFrame') or self.compiledFrame.empty:
                self.compiledFrame = pd.DataFrame(columns=emptyColumn).astype(dtype_dict)
            if hasattr(self, 'compiledFrame') and not self.compiledFrame.empty:
                last_dt = self.compiledFrame['DATETIME'].max()
                df = df[df['DATETIME'] > last_dt]
            if df.empty:
                return
            df = df[(~df["MODEL CODE"].isin(['120HP1000M', '60CAT0203M']))]
            df = df[(~df["TYPE"].isin(['T', 'D', 'A']))]
            df = df[(~df["PASS/NG"].isin([0]))]
            previous_values = {
                '50Hz_WATTAGE': None,
                '50Hz_AIR_VOLUME': None,
                '50Hz_CLOSED_PRESSURE': None,
                '50Hz_AMPERAGE': None,
                '60Hz_WATTAGE': None,
                '60Hz_AIR_VOLUME': None,
                '60Hz_CLOSED_PRESSURE': None,
                '60Hz_AMPERAGE': None
            }
            previous_date = None
            previous_model = self.previous_model

            # Batch GUI/log updates. Updating CustomTkinter widgets once per
            # CSV row is very slow when thousands of records are loaded.
            serial_entries = []
            fluct_log_entries = []

            for a in range(len(df)):
                tempdf = df.iloc[[a]]
                current_date = tempdf["DATE"].values[0]
                model_code = tempdf["MODEL CODE"].values[0]
                serial_no = tempdf["SERIAL No."].values[0]
                current_time = tempdf["TIME"].values[0]
                if self.logic == "DUO (SINGLE NOZZLE) W/ 2 SERIAL NUMBER":
                    display_serial = f"{serial_no}_{current_time}"
                else:
                    display_serial = serial_no
                # Do not redraw Tk widgets for every historical row.
                # update_display() will set the final model/serial once, and
                # the serial log is inserted in one batch after processing.
                serial_entries.append(display_serial)
                model_changed = (self.current_model is not None and model_code != self.current_model)
                is_new_date = (current_date != self.last_date) if self.last_date is not None else True
                is_new_model_in_day = (model_code != previous_model) if previous_model is not None else False
                if model_changed:
                    self.current_model = model_code
                    if self.logic != "AKH (DOUBLE NOZZLE)":
                        self.last_good_values = {}
                        self.last_good_serial = None
                if is_new_date:
                    self.last_date = current_date
                    previous_model = None
                    if self.logic == "AKH (DOUBLE NOZZLE)":
                        self.last_good_values_per_model = {'60HP20220S': {}, '60HP20220P': {}}
                        self.last_good_serial_per_model = {'60HP20220S': None, '60HP20220P': None}
                        self.previous_measurements_per_model = {
                            '60HP20220S': {
                                '50Hz_WATTAGE': [], '50Hz_AIR_VOLUME': [], '50Hz_CLOSED_PRESSURE': [], '50Hz_AMPERAGE': [],
                                '60Hz_WATTAGE': [], '60Hz_AIR_VOLUME': [], '60Hz_CLOSED_PRESSURE': [], '60Hz_AMPERAGE': []
                            },
                            '60HP20220P': {
                                '50Hz_WATTAGE': [], '50Hz_AIR_VOLUME': [], '50Hz_CLOSED_PRESSURE': [], '50Hz_AMPERAGE': [],
                                '60Hz_WATTAGE': [], '60Hz_AIR_VOLUME': [], '60Hz_CLOSED_PRESSURE': [], '60Hz_AMPERAGE': []
                            }
                        }
                    if self.logic == "DUO (SINGLE NOZZLE) W/ 2 SERIAL NUMBER":
                        self.serial_to_runs = {}
                        self.previous_measurements_by_run = {}
                        self.reference_values = {}
                        self.reference_serials = {}
                current_values = {
                    '50Hz_WATTAGE': tempdf["50Hz WATTAGE"].values[0],
                    '50Hz_AIR_VOLUME': tempdf["50Hz AIR VOLUME"].values[0],
                    '50Hz_CLOSED_PRESSURE': tempdf["50Hz CLOSED PRESSURE"].values[0],
                    '50Hz_AMPERAGE': tempdf["50Hz AMPERAGE"].values[0],
                    '60Hz_WATTAGE': tempdf["60Hz WATTAGE"].values[0],
                    '60Hz_AIR_VOLUME': tempdf["60Hz AIR VOLUME"].values[0],
                    '60Hz_CLOSED_PRESSURE': tempdf["60Hz CLOSED PRESSURE"].values[0],
                    '60Hz_AMPERAGE': tempdf["60Hz AMPERAGE"].values[0]
                }
                fluctuations = {}
                ref_serial = "N/A"
                usl_lsl_limits = {key: (None, None) for key in current_values}
                usl_lsl_found = True
                if self.logic == "ACCU AVG (TOL 5%)":
                    if model_changed or is_new_date or is_new_model_in_day:
                        for key in self.previous_measurements:
                            self.previous_measurements[key] = []
                        self.current_model = model_code
                    avg_values = {}
                    for key in current_values:
                        prev_list = self.previous_measurements[key]
                        if len(prev_list) == 0:
                            ref = 0
                            fluctuations[key] = 0
                        else:
                            ref = sum(prev_list) / len(prev_list)
                            if current_values[key] == 0 or ref == 0:
                                fluctuations[key] = 0
                            else:
                                fluctuations[key] = abs((current_values[key] / ref) - 1)
                        if len(prev_list) < 2:
                            avg_values[key] = "NONE"
                        else:
                            avg_values[key] = f"{ref:.2f}"
                    ref_serial = "N/A"
                    for key in current_values:
                        self.previous_measurements[key].append(current_values[key])
                    self.current_avgs = avg_values
                elif self.logic == "USL LSL":
                    # Direct specification check from the editable MODEL CODE master.
                    # 0 = within configured range / N.A.; 1 = NG. Tolerance % is
                    # intentionally NOT used by this computation.
                    fluctuations, usl_lsl_limits, usl_lsl_found = self._evaluate_usl_lsl(
                        model_code, current_values
                    )
                    ref_serial = "USL/LSL MASTER" if usl_lsl_found else "USL/LSL DATA NOT FOUND"
                elif self.logic == "FIND THE NEAREST GOOD":
                    if model_changed or is_new_date or not self.last_good_values or is_new_model_in_day:
                        for key in current_values:
                            fluctuations[key] = 0
                        ref_serial = serial_no
                    else:
                        for key in current_values:
                            if current_values[key] == 0:
                                fluctuations[key] = 0
                            else:
                                fluctuations[key] = abs((self.last_good_values[key] - current_values[key]) / self.last_good_values[key]) if self.last_good_values[key] != 0 else 0
                        ref_serial = self.last_good_serial
                    self.ref_serial_display.configure(text=f"REF SERIAL NO: {ref_serial}")
                    if all(v <= self.threshold for v in fluctuations.values()):
                        self.last_good_values = current_values.copy()
                        self.last_good_serial = serial_no
                elif self.logic == "DUO (SINGLE NOZZLE) W/ 2 SERIAL NUMBER":
                    current_serial = tempdf["SERIAL No."].values[0]
                    current_time = tempdf["TIME"].values[0]
                    current_key = f"{current_serial}_{current_time}"
                    if current_serial not in self.serial_to_runs:
                        self.serial_to_runs[current_serial] = 0
                    self.serial_to_runs[current_serial] += 1
                    run_number = self.serial_to_runs[current_serial]
                    total_runs = sum(self.serial_to_runs.values())
                    if model_changed or is_new_date or is_new_model_in_day:
                        self.serial_to_runs = {current_serial: 1}
                        self.previous_measurements_by_run = {}
                        self.reference_values = {}
                        self.reference_serials = {}
                        run_number = 1
                        total_runs = 1
                    # Store current measurements
                    self.previous_measurements_by_run[current_key] = current_values.copy()
                    if total_runs <= 2:
                        fluctuations = {k: 0 for k in current_values}
                        ref_serial = "N/A"
                        avg_values = {k: "NONE" for k in current_values}
                    else:
                        all_keys = list(self.previous_measurements_by_run.keys())
                        previous_keys = all_keys[:-1]
                        group_parity = total_runs % 2
                        previous_group_keys = [previous_keys[i] for i in range(len(previous_keys)) if (i + 1) % 2 == group_parity]
                        if len(previous_group_keys) > 0:
                            ref_key = previous_group_keys[-1]
                            ref_serial = ref_key
                            ref_values = {}
                            for key in current_values:
                                values = [self.previous_measurements_by_run[k][key] for k in previous_group_keys]
                                ref_values[key] = sum(values) / len(values) if values else 0
                        else:
                            ref_key = None
                            ref_serial = "N/A"
                            ref_values = {k: 0 for k in current_values}
                        fluctuations = {}
                        for key in current_values:
                            if current_values[key] == 0 or ref_values[key] == 0:
                                fluctuations[key] = 0
                            else:
                                fluctuations[key] = abs((current_values[key] / ref_values[key]) - 1)
                        avg_values = {}
                        for key in current_values:
                            if len(previous_group_keys) > 0:
                                avg_values[key] = f"{ref_values[key]:.2f}" if ref_values[key] != 0 else "NONE"
                            else:
                                avg_values[key] = "NONE"
                    self.ref_serial_display.configure(text=f"REF SERIAL NO: {ref_serial}")
                    self.current_avgs = avg_values
                elif self.logic == "AKH (DOUBLE NOZZLE)":
                    model = model_code
                    if model not in ['60HP20220S', '60HP20220P']:
                        fluctuations = {k: 0 for k in current_values}
                        ref_serial = serial_no
                    else:
                        run_number = len(self.previous_measurements_per_model[model]['50Hz_WATTAGE']) + 1
                        if is_new_date or run_number == 1:
                            fluctuations = {k: 0 for k in current_values}
                            ref_serial = serial_no
                            self.last_good_values_per_model[model] = current_values.copy()
                            self.last_good_serial_per_model[model] = serial_no
                        else:
                            prev_runs = self.previous_measurements_per_model[model]
                            avg_values = {}
                            for key in current_values:
                                prev_list = prev_runs[key]
                                if run_number <= 2:
                                    ref = prev_list[0] if prev_list else 0
                                    if current_values[key] == 0 or ref == 0:
                                        fluctuations[key] = 0
                                    else:
                                        fluctuations[key] = abs((current_values[key] / ref) - 1)
                                else:
                                    avg = sum(prev_list) / len(prev_list)
                                    avg_values[key] = avg
                                    if current_values[key] == 0 or avg == 0:
                                        fluctuations[key] = 0
                                    else:
                                        fluctuations[key] = abs((current_values[key] / avg) - 1)
                            ref_serial = self.last_good_serial_per_model[model] or "N/A"
                        if all(v <= self.threshold for v in fluctuations.values()):
                            self.last_good_values_per_model[model] = current_values.copy()
                            self.last_good_serial_per_model[model] = serial_no
                        for key in current_values:
                            self.previous_measurements_per_model[model][key].append(current_values[key])
                    self.ref_serial_display.configure(text=f"REF SERIAL NO: {ref_serial}")
                    avg_values = {}
                    for key in current_values:
                        if model in ['60HP20220S', '60HP20220P']:
                            prev_list = self.previous_measurements_per_model[model][key][:-1]
                            if len(prev_list) < 2:
                                avg_values[key] = "NONE"
                            else:
                                avg = sum(prev_list) / len(prev_list)
                                avg_values[key] = f"{avg:.2f}"
                        else:
                            avg_values[key] = "NONE"
                    self.current_avgs = avg_values
                previous_model = model_code
                if self.logic == "USL LSL":
                    usl_lsl_ng = (not usl_lsl_found) or any(v > 0 for v in fluctuations.values())
                    final_pass_ng = 0 if usl_lsl_ng else tempdf["PASS/NG"].values[0]
                else:
                    final_pass_ng = tempdf["PASS/NG"].values[0]
                dataFrame = {
                    "DATE": current_date,
                    "TIME": tempdf["TIME"].values[0],
                    "MODEL CODE": model_code,
                    "TYPE": tempdf["TYPE"].values[0],
                    "BARCODE": tempdf["BARCODE"].values[0],
                    "SERIAL No.": serial_no,
                    "PASS/NG": final_pass_ng,
                    "50Hz WATTAGE": current_values['50Hz_WATTAGE'],
                    "50Hz WATTAGE FLUCTUATED": fluctuations['50Hz_WATTAGE'],
                    "50Hz AIR VOLUME": current_values['50Hz_AIR_VOLUME'],
                    "50Hz AIR VOLUME FLUCTUATED": fluctuations['50Hz_AIR_VOLUME'],
                    "50Hz CLOSED PRESSURE": current_values['50Hz_CLOSED_PRESSURE'],
                    "50Hz CLOSED PRESSURE FLUCTUATED": fluctuations['50Hz_CLOSED_PRESSURE'],
                    "50Hz AMPERAGE": current_values['50Hz_AMPERAGE'],
                    "50Hz AMPERAGE FLUCTUATED": fluctuations['50Hz_AMPERAGE'],
                    "60Hz WATTAGE": current_values['60Hz_WATTAGE'],
                    "60Hz WATTAGE FLUCTUATED": fluctuations['60Hz_WATTAGE'],
                    "60Hz AIR VOLUME": current_values['60Hz_AIR_VOLUME'],
                    "60Hz AIR VOLUME FLUCTUATED": fluctuations['60Hz_AIR_VOLUME'],
                    "60Hz CLOSED PRESSURE": current_values['60Hz_CLOSED_PRESSURE'],
                    "60Hz CLOSED PRESSURE FLUCTUATED": fluctuations['60Hz_CLOSED_PRESSURE'],
                    "60Hz AMPERAGE": current_values['60Hz_AMPERAGE'],
                    "60Hz AMPERAGE FLUCTUATED": fluctuations['60Hz_AMPERAGE'],
                    "REFERENCE SERIAL": ref_serial,
                    "DATETIME": tempdf["DATETIME"].values[0]
                }
                if self.logic == "USL LSL":
                    for key, (usl_col, lsl_col) in USL_LSL_LIMIT_MAP.items():
                        usl, lsl = usl_lsl_limits.get(key, (None, None))
                        dataFrame[usl_col] = usl if usl is not None else pd.NA
                        dataFrame[lsl_col] = lsl if lsl is not None else pd.NA
                    has_fluct = any(f > 0 for f in fluctuations.values())
                else:
                    has_fluct = any(f > self.threshold for f in fluctuations.values())
                if has_fluct:
                    log_text = f"SERIAL NO: {serial_no}  DATE: {current_date}   TIME: {tempdf['TIME'].values[0]}   MODEL CODE:{model_code}\n"
                    log_text += "PROCESS INSPECTION:       VALUE:          TOLERANCE:     \n"
                    for key in fluctuations:
                        if fluctuations[key] > self.threshold:
                            name = key.replace('_', ' ')
                            value = current_values[key]
                            if self.logic == "ACCU AVG (TOL 5%)":
                                prev_list = self.previous_measurements[key]
                                if len(prev_list) > 1:
                                    ref = sum(prev_list[:-1]) / len(prev_list[:-1])
                                else:
                                    ref = 0
                            elif self.logic == "AKH (DOUBLE NOZZLE)":
                                if model in self.last_good_values_per_model and self.last_good_values_per_model[model]:
                                    ref = self.last_good_values_per_model[model][key]
                                else:
                                    ref = 0
                            elif self.logic == "DUO (SINGLE NOZZLE) W/ 2 SERIAL NUMBER":
                                ref_key = ref_serial
                                ref = self.previous_measurements_by_run.get(ref_key, {}).get(key, 0) if ref_key != "N/A" else 0
                            elif self.logic == "USL LSL":
                                usl, lsl = usl_lsl_limits.get(key, (None, None))
                                if usl is not None and value > usl:
                                    ref = usl
                                elif lsl is not None and value < lsl:
                                    ref = lsl
                                else:
                                    ref = 0
                            else:
                                ref = self.last_good_values[key] if self.last_good_values else 0
                            log_text += f"{name.ljust(30)} {value:.2f}            REF  :{ref:.2f}\n"
                    log_text += "\n---\n"
                    # Buffer fluctuation logs and update the GUI/file once
                    # after the CSV loop instead of once per record.
                    fluct_log_entries.append(log_text)
                previous_values = current_values.copy()
                previous_date = current_date
                dataList.append(dataFrame)
            # Apply serial-number log updates once after all calculations.
            if serial_entries:
                self.serial_log.configure(state='normal')
                # Keep the visible log compact during initial loading.
                for serial_text in serial_entries[-100:]:
                    self.serial_log.insert("end", f"{serial_text}\n")
                self.serial_log.see("end")
                self.serial_log.configure(state='disabled')

            # Apply fluctuation log updates in one GUI operation and one file write.
            if fluct_log_entries:
                combined_log = ''.join(fluct_log_entries)
                self.fluctuation_log.configure(state='normal')
                self.fluctuation_log.insert("end", combined_log)
                self.fluctuation_log.see("end")
                self.fluctuation_log.configure(state='disabled')
                with open(self.log_path, 'a', encoding='utf-8') as f:
                    f.write(combined_log)

            self.previous_model = previous_model
            if dataList:
                new_data = pd.DataFrame(dataList)
                # Ensure new_data has all columns from emptyColumn with correct dtypes
                for col in emptyColumn:
                    if col not in new_data.columns:
                        new_data[col] = pd.Series([None] * len(new_data), dtype=dtype_dict[col])
                    else:
                        new_data[col] = new_data[col].astype(dtype_dict[col], errors='ignore')
                # Filter out any all-NA columns from new_data before concatenation
                new_data = new_data.loc[:, ~new_data.isna().all()]
                # Concatenate with compiledFrame, ensuring dtypes are preserved
                self.compiledFrame = pd.concat([self.compiledFrame, new_data], ignore_index=True)
            self._write_compiled_output()
            self.update_display()
        except Exception:
            # Let process_and_update() classify network errors, debounce console
            # output, and decide whether this file change was processed successfully.
            raise

    def update_display(self):
        try:
            # If the source log is temporarily unavailable, keep the GUI stable
            # until a successful read provides at least one inspection row.
            if (not hasattr(self, 'compiledFrame') or
                    self.compiledFrame is None or self.compiledFrame.empty):
                return
            last_row = self.compiledFrame.iloc[-1]
            has_fluctuation = False
            fluctuation_count = 0
            for column in self.status_vars:
                if column in last_row:
                    value = last_row[column]
                    if self.logic == "USL LSL":
                        status = 1 if value > 0 else 0
                    else:
                        status = 1 if value > self.threshold else 0
                    self.status_vars[column].set(f"= {status}")
                    color = "red" if status == 1 else "green"
                    self.status_labels[column].configure(text_color=color)
                    if status == 1:
                        has_fluctuation = True
                        fluctuation_count += 1
            self.update_status_box(has_fluctuation, fluctuation_count)
            if "REFERENCE SERIAL" in last_row:
                ref_serial = last_row["REFERENCE SERIAL"]
                if self.logic == "USL LSL":
                    self.ref_serial_display.configure(text=f"REFERENCE: {ref_serial}")
                    if ref_serial == "USL/LSL DATA NOT FOUND":
                        self.status_box.configure(fg_color="red")
                        self.status_text_label.configure(text="USL/LSL DATA NOT FOUND")
                        self.counter_text_label.configure(text="Add this MODEL CODE in the USL LSL tab")
                else:
                    self.ref_serial_display.configure(text=f"REF SERIAL NO: {ref_serial}")
            if "MODEL CODE" in last_row:
                model_code = last_row["MODEL CODE"]
                self.model_display.configure(text=f"MODEL CODE: {model_code}")
            if self.logic == "DUO (SINGLE NOZZLE) W/ 2 SERIAL NUMBER":
                serial_no = last_row["SERIAL No."]
                current_time = last_row["TIME"]
                display_serial = f"{serial_no}_{current_time}"
                self.serial_display.configure(text=f"SERIAL No.: {display_serial}")
            else:
                serial_no = last_row["SERIAL No."]
                self.serial_display.configure(text=f"SERIAL No.: {serial_no}")
            self.update_bar_graph(last_row)
            self.update_line_graph()
            self.update_line_trend_tab()
            if self.logic in ["ACCU AVG (TOL 5%)", "AKH (DOUBLE NOZZLE)", "DUO (SINGLE NOZZLE) W/ 2 SERIAL NUMBER"]:
                for col in self.avg_vars:
                    key = col.replace(' ', '_')
                    self.avg_vars[col].set(self.current_avgs.get(key, "NONE"))
        except Exception as e:
            print(f"Error updating display: {e}")

    def create_section(self, title, columns):
        frame = ctk.CTkFrame(self.details_frame)
        frame.pack(fill=tk.X, pady=2)
        ctk.CTkLabel(frame, text=title, font=('Arial', 12, 'bold')).pack(anchor='w')
        for col in columns:
            self.create_status_row(frame, col)

    def create_status_row(self, parent, column_name):
        row_frame = ctk.CTkFrame(parent)
        row_frame.pack(fill=tk.X, pady=1)
        ctk.CTkLabel(row_frame, text=f"{column_name.replace(' FLUCTUATED', '')}:", 
                 width=180, anchor='w').pack(side=tk.LEFT)
        status_frame = ctk.CTkFrame(row_frame)
        status_frame.pack(side=tk.LEFT, padx=2)
        self.status_vars[column_name] = tk.StringVar()
        self.status_labels[column_name] = ctk.CTkLabel(
            status_frame, 
            textvariable=self.status_vars[column_name],
            font=('Arial', 10, 'bold'),
            width=70
        )
        self.status_labels[column_name].pack(side=tk.LEFT)
        ctk.CTkButton(
            status_frame, 
            text="Reset", 
            width=50,
            command=lambda: self.reset_fluctuation(column_name)
        ).pack(side=tk.LEFT, padx=2)

    def reset_fluctuation(self, column_name):
        try:
            self.compiledFrame.at[self.compiledFrame.index[-1], column_name] = 0
            self.status_vars[column_name].set("= 0")
            self.status_labels[column_name].configure(text_color="green")
            last_row = self.compiledFrame.iloc[-1]
            limit_for_reset = 0 if self.logic == "USL LSL" else self.threshold
            if all(last_row[col] <= limit_for_reset for col in self.status_vars if col in last_row):
                if self.logic == "AKH (DOUBLE NOZZLE)":
                    model = last_row["MODEL CODE"]
                    self.last_good_values_per_model[model] = {
                        '50Hz_WATTAGE': last_row["50Hz WATTAGE"],
                        '50Hz_AIR_VOLUME': last_row["50Hz AIR VOLUME"],
                        '50Hz_CLOSED_PRESSURE': last_row["50Hz CLOSED PRESSURE"],
                        '50Hz_AMPERAGE': last_row["50Hz AMPERAGE"],
                        '60Hz_WATTAGE': last_row["60Hz WATTAGE"],
                        '60Hz_AIR_VOLUME': last_row["60Hz AIR VOLUME"],
                        '60Hz_CLOSED_PRESSURE': last_row["60Hz CLOSED PRESSURE"],
                        '60Hz_AMPERAGE': last_row["60Hz AMPERAGE"]
                    }
                    self.last_good_serial_per_model[model] = last_row["SERIAL No."]
                    for key in self.last_good_values_per_model[model]:
                        self.previous_measurements_per_model[model][key].append(self.last_good_values_per_model[model][key])
                elif self.logic == "DUO (SINGLE NOZZLE) W/ 2 SERIAL NUMBER":
                    pass
                elif self.logic == "USL LSL":
                    pass
                else:
                    self.last_good_values = {
                        '50Hz_WATTAGE': last_row["50Hz WATTAGE"],
                        '50Hz_AIR_VOLUME': last_row["50Hz AIR VOLUME"],
                        '50Hz_CLOSED_PRESSURE': last_row["50Hz CLOSED PRESSURE"],
                        '50Hz_AMPERAGE': last_row["50Hz AMPERAGE"],
                        '60Hz_WATTAGE': last_row["60Hz WATTAGE"],
                        '60Hz_AIR_VOLUME': last_row["60Hz AIR VOLUME"],
                        '60Hz_CLOSED_PRESSURE': last_row["60Hz CLOSED PRESSURE"],
                        '60Hz_AMPERAGE': last_row["60Hz AMPERAGE"]
                    }
                    self.last_good_serial = last_row["SERIAL No."]
            self._write_compiled_output()
            self.update_display()
        except Exception as e:
            print(f"Error resetting fluctuation: {e}")

    def reset_all_fluctuations(self):
        try:
            for column in self.status_vars:
                self.compiledFrame.at[self.compiledFrame.index[-1], column] = 0
                self.status_vars[column].set("= 0")
                self.status_labels[column].configure(text_color="green")
            last_row = self.compiledFrame.iloc[-1]
            limit_for_reset = 0 if self.logic == "USL LSL" else self.threshold
            if all(last_row[col] <= limit_for_reset for col in self.status_vars if col in last_row):
                if self.logic == "AKH (DOUBLE NOZZLE)":
                    model = last_row["MODEL CODE"]
                    self.last_good_values_per_model[model] = {
                        '50Hz_WATTAGE': last_row["50Hz WATTAGE"],
                        '50Hz_AIR_VOLUME': last_row["50Hz AIR VOLUME"],
                        '50Hz_CLOSED_PRESSURE': last_row["50Hz CLOSED PRESSURE"],
                        '50Hz_AMPERAGE': last_row["50Hz AMPERAGE"],
                        '60Hz_WATTAGE': last_row["60Hz WATTAGE"],
                        '60Hz_AIR_VOLUME': last_row["60Hz AIR VOLUME"],
                        '60Hz_CLOSED_PRESSURE': last_row["60Hz CLOSED PRESSURE"],
                        '60Hz_AMPERAGE': last_row["60Hz AMPERAGE"]
                    }
                    self.last_good_serial_per_model[model] = last_row["SERIAL No."]
                    for key in self.last_good_values_per_model[model]:
                        self.previous_measurements_per_model[model][key].append(self.last_good_values_per_model[model][key])
                elif self.logic == "DUO (SINGLE NOZZLE) W/ 2 SERIAL NUMBER":
                    pass
                elif self.logic == "USL LSL":
                    pass
                else:
                    self.last_good_values = {
                        '50Hz_WATTAGE': last_row["50Hz WATTAGE"],
                        '50Hz_AIR_VOLUME': last_row["50Hz AIR VOLUME"],
                        '50Hz_CLOSED_PRESSURE': last_row["50Hz CLOSED PRESSURE"],
                        '50Hz_AMPERAGE': last_row["50Hz AMPERAGE"],
                        '60Hz_WATTAGE': last_row["60Hz WATTAGE"],
                        '60Hz_AIR_VOLUME': last_row["60Hz AIR VOLUME"],
                        '60Hz_CLOSED_PRESSURE': last_row["60Hz CLOSED PRESSURE"],
                        '60Hz_AMPERAGE': last_row["60Hz AMPERAGE"]
                    }
                    self.last_good_serial = last_row["SERIAL No."]
            self._write_compiled_output()
            self.update_status_box(False)
            self.update_display()
        except Exception as e:
            print(f"Error resetting all fluctuations: {e}")

    def open_focus_selection(self):
        focus_window = ctk.CTkToplevel(self.root)
        focus_window.title("Select Measurement to Focus")
        focus_window.geometry("350x450")
        focus_window.attributes('-topmost', True)
        ctk.CTkLabel(focus_window, text="Select measurement:", font=('Arial', 12, 'bold')).pack(pady=10)
        self.focus_var = tk.StringVar()
        measurements = [
            "50Hz WATTAGE",
            "50Hz AIR VOLUME",
            "50Hz CLOSED PRESSURE",
            "50Hz AMPERAGE",
            "60Hz WATTAGE",
            "60Hz AIR VOLUME",
            "60Hz CLOSED PRESSURE",
            "60Hz AMPERAGE"
        ]
        for meas in measurements:
            ctk.CTkRadioButton(focus_window, text=meas, variable=self.focus_var, value=meas).pack(anchor='w', padx=20, pady=3)
        ctk.CTkButton(focus_window, text="Show Graph", command=self.show_focused_graph).pack(pady=10)

    def show_focused_graph(self):
        selected = self.focus_var.get()
        if not selected:
            return
        graph_window = ctk.CTkToplevel(self.root)
        graph_window.title(f"Focused: {selected}")
        graph_window.geometry("1200x800")
        fig = Figure(figsize=(12, 8), dpi=100)
        ax = fig.add_subplot(111)
        ax.set_title(f'{selected} Trend')
        ax.set_ylabel('Value')
        ax.grid(True)
        if hasattr(self, 'compiledFrame') and not self.compiledFrame.empty:
            df = self.compiledFrame
            df = self.downsample_data(df, max_points=100)
            color_map = {
                "50Hz WATTAGE": 'blue',
                "50Hz AIR VOLUME": 'green',
                "50Hz CLOSED PRESSURE": 'red',
                "50Hz AMPERAGE": 'cyan',
                "60Hz WATTAGE": 'magenta',
                "60Hz AIR VOLUME": 'yellow',
                "60Hz CLOSED PRESSURE": 'black',
                "60Hz AMPERAGE": 'orange'
            }
            ax.plot(df['DATETIME'], df[selected], label=selected, color=color_map.get(selected, 'blue'), linewidth=2)
            ax.legend()
            ax.tick_params(axis='x', rotation=45, labelsize=10)
        fig.subplots_adjust(left=0.1, right=0.9, bottom=0.15, top=0.9)
        canvas = FigureCanvasTkAgg(fig, master=graph_window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)


    def open_display_settings(self):
        settings_window = ctk.CTkToplevel(self.root)
        settings_window.title("Display Settings")  
        settings_window.geometry("420x500+420+80")   # (WIDTHxHEIGHT+LeftRight+UpDown) # DISPLAY SETTINGS TKINTER GUI
        settings_window.attributes('-topmost', True)

        ctk.CTkLabel(settings_window, text="SPC LINE TREND WIDTH:", font=('Arial', 11, 'bold')).pack(pady=5)
        ctk.CTkRadioButton(settings_window, text="EXTRA SMALL", variable=self.line_width_var, value="Extra Small").pack(anchor='w', padx=20, pady=2)
        ctk.CTkRadioButton(settings_window, text="SMALL", variable=self.line_width_var, value="Small").pack(anchor='w', padx=20, pady=2)
        ctk.CTkRadioButton(settings_window, text="MEDIUM", variable=self.line_width_var, value="Medium").pack(anchor='w', padx=20, pady=2)

        ctk.CTkLabel(settings_window, text="X-AXIS:", font=('Arial', 11, 'bold')).pack(pady=5)
        ctk.CTkRadioButton(settings_window, text="NUMERICAL NUMBERING", variable=self.xaxis_var, value="Numerical Numbering").pack(anchor='w', padx=20, pady=2)
        ctk.CTkRadioButton(settings_window, text="MONTH/YEAR", variable=self.xaxis_var, value="Month/Year").pack(anchor='w', padx=20, pady=2)
        ctk.CTkRadioButton(settings_window, text="SERIAL NO", variable=self.xaxis_var, value="Serial No").pack(anchor='w', padx=20, pady=2)

        ctk.CTkCheckBox(settings_window, text="SHOW TITLE", variable=self.show_title_var).pack(anchor='w', padx=20, pady=5)

        ctk.CTkLabel(settings_window, text="DATAPOINTS:", font=('Arial', 11, 'bold')).pack(pady=5)
        ctk.CTkRadioButton(settings_window, text="SCATTER", variable=self.datapoints_var, value="Scatter").pack(anchor='w', padx=20, pady=2)
        ctk.CTkRadioButton(settings_window, text="NONE", variable=self.datapoints_var, value="None").pack(anchor='w', padx=20, pady=2)

        ctk.CTkLabel(settings_window, text="SCATTER COLOR:", font=('Arial', 11, 'bold')).pack(pady=5)
        ctk.CTkRadioButton(settings_window, text="NORMAL BLUE", variable=self.scatter_color_var, value="Normal Blue").pack(anchor='w', padx=20, pady=2)
        ctk.CTkRadioButton(settings_window, text="NONE", variable=self.scatter_color_var, value="None").pack(anchor='w', padx=20, pady=2)

        ctk.CTkButton(settings_window, text="Apply", command=lambda: [self.update_line_graph(), settings_window.destroy()]).pack(pady=15)

    def on_closing(self):
        self._closing = True
        self._close_line_trend_tab()
        self._close_historical_trend_tab()
        if self.after_id is not None:  # Cancel the scheduled after callback
            self.root.after_cancel(self.after_id)
        self.observer.stop()
        self.observer.join()
        _cancel_all_after(self.root)
        self.root.withdraw()
        try:
            self.root.destroy()
        except tk.TclError:
            pass

# Initialize compiledFrame with explicit dtypes
dtype_dict = {
    "DATE": str,
    "TIME": str,
    "MODEL CODE": str,
    "TYPE": str,
    "BARCODE": str,
    "SERIAL No.": str,
    "PASS/NG": str,
    "50Hz WATTAGE": float,
    "50Hz WATTAGE FLUCTUATED": float,
    "50Hz AIR VOLUME": float,
    "50Hz AIR VOLUME FLUCTUATED": float,
    "50Hz CLOSED PRESSURE": float,
    "50Hz CLOSED PRESSURE FLUCTUATED": float,
    "50Hz AMPERAGE": float,
    "50Hz AMPERAGE FLUCTUATED": float,
    "60Hz WATTAGE": float,
    "60Hz WATTAGE FLUCTUATED": float,
    "60Hz AIR VOLUME": float,
    "60Hz AIR VOLUME FLUCTUATED": float,
    "60Hz CLOSED PRESSURE": float,
    "60Hz CLOSED PRESSURE FLUCTUATED": float,
    "60Hz AMPERAGE": float,
    "60Hz AMPERAGE FLUCTUATED": float,
    "REFERENCE SERIAL": str,
    "DATETIME": "datetime64[ns]"
}
compiledFrame = pd.DataFrame(columns=[
    "DATE", "TIME", "MODEL CODE", "TYPE", "BARCODE", "SERIAL No.", "PASS/NG",
    "50Hz WATTAGE", "50Hz WATTAGE FLUCTUATED",
    "50Hz AIR VOLUME", "50Hz AIR VOLUME FLUCTUATED",
    "50Hz CLOSED PRESSURE", "50Hz CLOSED PRESSURE FLUCTUATED",
    "50Hz AMPERAGE", "50Hz AMPERAGE FLUCTUATED",
    "60Hz WATTAGE", "60Hz WATTAGE FLUCTUATED",
    "60Hz AIR VOLUME", "60Hz AIR VOLUME FLUCTUATED",
    "60Hz CLOSED PRESSURE", "60Hz CLOSED PRESSURE FLUCTUATED",
    "60Hz AMPERAGE", "60Hz AMPERAGE FLUCTUATED",
    "REFERENCE SERIAL", "DATETIME"
]).astype(dtype_dict)

if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    root = ctk.CTk()
    DatabaseSelection(root)

    # The ONLY mainloop in the program.
    root.mainloop()
