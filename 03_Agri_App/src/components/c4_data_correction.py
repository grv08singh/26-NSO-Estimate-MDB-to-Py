import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any
import pandas as pd
from src.utils.common import load_csv
from src.logger import logging


@dataclass
class DataCorrectionParams:
    rc7_preprocessed_path: Path
    output_path: Optional[Path] = None


class DataCorrectionUI:
    """Tkinter UI for filtering and correcting RC7 preprocessed data."""

    def __init__(self, params: DataCorrectionParams):
        self.params = params
        self.df: Optional[pd.DataFrame] = None
        self.filtered_df: Optional[pd.DataFrame] = None
        self.current_row_index: Optional[int] = None
        self.edit_window: Optional[tk.Toplevel] = None
        self.view_window: Optional[tk.Toplevel] = None

        # Initialize main window
        self.root = tk.Tk()
        self.root.title("RC7 Data Correction Tool")
        self.root.geometry("1400x800")
        self.root.minsize(1000, 600)

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """Set up the main UI layout."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Top panel - Filter controls
        filter_frame = ttk.LabelFrame(main_frame, text="Filters", padding="10")
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        self._create_filter_controls(filter_frame)

        # Middle panel - Results table
        table_frame = ttk.LabelFrame(main_frame, text="Filtered Rows", padding="10")
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self._create_results_table(table_frame)

        # Bottom panel - Status and actions
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT)

        ttk.Button(status_frame, text="Save Changes", command=self._save_changes).pack(side=tk.RIGHT, padx=5)
        ttk.Button(status_frame, text="Refresh", command=self._apply_filters).pack(side=tk.RIGHT, padx=5)
        ttk.Button(status_frame, text="Export Filtered", command=self._export_filtered).pack(side=tk.RIGHT, padx=5)

    def _create_filter_controls(self, parent):
        """Create filter input controls."""
        # Row 1: Text filters
        row1 = ttk.Frame(parent)
        row1.pack(fill=tk.X, pady=5)

        # UID filter
        ttk.Label(row1, text="UID:").pack(side=tk.LEFT, padx=(0, 5))
        self.uid_filter = ttk.Entry(row1, width=25)
        self.uid_filter.pack(side=tk.LEFT, padx=(0, 15))

        # EXPTID filter
        ttk.Label(row1, text="EXPTID:").pack(side=tk.LEFT, padx=(0, 5))
        self.exptid_filter = ttk.Entry(row1, width=25)
        self.exptid_filter.pack(side=tk.LEFT, padx=(0, 15))

        # STATE filter
        ttk.Label(row1, text="STATE:").pack(side=tk.LEFT, padx=(0, 5))
        self.state_filter = ttk.Combobox(row1, width=22, state="readonly")
        self.state_filter.pack(side=tk.LEFT, padx=(0, 15))

        # DIST filter
        ttk.Label(row1, text="DIST:").pack(side=tk.LEFT, padx=(0, 5))
        self.dist_filter = ttk.Combobox(row1, width=22, state="readonly")
        self.dist_filter.pack(side=tk.LEFT, padx=(0, 15))

        # Row 2: More filters
        row2 = ttk.Frame(parent)
        row2.pack(fill=tk.X, pady=5)

        # CROP filter
        ttk.Label(row2, text="CROP:").pack(side=tk.LEFT, padx=(0, 5))
        self.crop_filter = ttk.Combobox(row2, width=22, state="readonly")
        self.crop_filter.pack(side=tk.LEFT, padx=(0, 15))

        # YR filter
        ttk.Label(row2, text="YEAR:").pack(side=tk.LEFT, padx=(0, 5))
        self.year_filter = ttk.Combobox(row2, width=22, state="readonly")
        self.year_filter.pack(side=tk.LEFT, padx=(0, 15))

        # SESON filter
        ttk.Label(row2, text="SEASON:").pack(side=tk.LEFT, padx=(0, 5))
        self.season_filter = ttk.Combobox(row2, width=22, state="readonly")
        self.season_filter.pack(side=tk.LEFT, padx=(0, 15))

        # RC filter
        ttk.Label(row2, text="RC:").pack(side=tk.LEFT, padx=(0, 5))
        self.rc_filter = ttk.Combobox(row2, width=22, state="readonly")
        self.rc_filter.pack(side=tk.LEFT, padx=(0, 15))

        # Row 3: Action buttons
        row3 = ttk.Frame(parent)
        row3.pack(fill=tk.X, pady=10)

        ttk.Button(row3, text="Apply Filters", command=self._apply_filters, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(row3, text="Clear Filters", command=self._clear_filters).pack(side=tk.LEFT, padx=5)
        ttk.Button(row3, text="Show All", command=self._show_all).pack(side=tk.LEFT, padx=5)

        # Results count
        self.results_count_var = tk.StringVar(value="Rows: 0 / 0")
        ttk.Label(row3, textvariable=self.results_count_var).pack(side=tk.RIGHT, padx=10)

    def _create_results_table(self, parent):
        """Create the results table with action buttons."""
        # Create treeview with scrollbars
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # Define columns (key columns for display)
        self.display_columns = [
            "UID", "EXPTID", "SRL", "RC", "ST", "YR", "SESON", "CROP",
            "NEXP", "STAT", "DIST", "VILL", "EXPNO", "CROPCODE"
        ]

        # Treeview
        self.tree = ttk.Treeview(tree_frame, columns=self.display_columns, show="headings", selectmode="browse")

        # Configure columns
        col_widths = {
            "UID": 180, "EXPTID": 120, "SRL": 60, "RC": 50,
            "ST": 50, "YR": 60, "SESON": 60, "CROP": 60,
            "NEXP": 60, "STAT": 60, "DIST": 60, "VILL": 60,
            "EXPNO": 60, "CROPCODE": 100
        }

        for col in self.display_columns:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_tree(c))
            self.tree.column(col, width=col_widths.get(col, 100), minwidth=50, anchor=tk.CENTER)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Bind double-click to view
        self.tree.bind("<Double-1>", lambda e: self._view_selected())
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Context menu for right-click
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="View", command=self._view_selected)
        self.context_menu.add_command(label="Edit", command=self._edit_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Delete", command=self._delete_selected)
        self.tree.bind("<Button-3>", self._show_context_menu)

    def _load_data(self):
        """Load the RC7 preprocessed data."""
        try:
            path = self.params.rc7_preprocessed_path
            if not path.exists():
                messagebox.showerror("Error", f"File not found: {path}")
                return

            self.df = load_csv(path)
            self._populate_filter_dropdowns()
            self._apply_filters()
            self.status_var.set(f"Loaded {len(self.df)} rows from {path.name}")
            logging.info(f"Loaded {len(self.df)} rows for data correction from {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load data: {e}")
            logging.error(f"Failed to load data for correction: {e}")

    def _populate_filter_dropdowns(self):
        """Populate filter dropdowns with unique values from data."""
        if self.df is None:
            return

        # Get unique values for categorical columns
        categorical_cols = {
            "STATE": "STATE" if "STATE" in self.df.columns else "STAT",
            "DIST": "DIST" if "DIST" in self.df.columns else None,
            "CROP": "CROP" if "CROP" in self.df.columns else None,
            "YEAR": "YR" if "YR" in self.df.columns else None,
            "SEASON": "SESON" if "SESON" in self.df.columns else None,
            "RC": "RC" if "RC" in self.df.columns else None
        }

        for filter_name, col_name in categorical_cols.items():
            if col_name and col_name in self.df.columns:
                unique_vals = sorted(self.df[col_name].dropna().unique())
                combo = getattr(self, f"{filter_name.lower()}_filter")
                combo["values"] = [""] + [str(v) for v in unique_vals]

    def _apply_filters(self):
        """Apply filters and update the table."""
        if self.df is None:
            return

        filtered = self.df.copy()

        # Text filters
        uid_filter = self.uid_filter.get().strip()
        if uid_filter:
            filtered = filtered[filtered["UID"].astype(str).str.contains(uid_filter, case=False, na=False)]

        exptid_filter = self.exptid_filter.get().strip()
        if exptid_filter:
            filtered = filtered[filtered["EXPTID"].astype(str).str.contains(exptid_filter, case=False, na=False)]

        # Dropdown filters
        filter_map = {
            "state_filter": "STATE" if "STATE" in filtered.columns else "STAT",
            "dist_filter": "DIST",
            "crop_filter": "CROP",
            "year_filter": "YR",
            "season_filter": "SESON",
            "rc_filter": "RC"
        }

        for filter_attr, col_name in filter_map.items():
            if col_name and col_name in filtered.columns:
                value = getattr(self, filter_attr).get()
                if value:
                    filtered = filtered[filtered[col_name].astype(str) == value]

        self.filtered_df = filtered
        self._update_tree()
        self.results_count_var.set(f"Rows: {len(filtered)} / {len(self.df)}")
        self.status_var.set(f"Filtered: {len(filtered)} rows")

    def _clear_filters(self):
        """Clear all filter inputs."""
        self.uid_filter.delete(0, tk.END)
        self.exptid_filter.delete(0, tk.END)
        self.state_filter.set("")
        self.dist_filter.set("")
        self.crop_filter.set("")
        self.year_filter.set("")
        self.season_filter.set("")
        self.rc_filter.set("")
        self._apply_filters()

    def _show_all(self):
        """Show all rows (clear filters and refresh)."""
        self._clear_filters()

    def _update_tree(self):
        """Update the treeview with filtered data."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        if self.filtered_df is None or self.filtered_df.empty:
            return

        # Add rows
        for idx, row in self.filtered_df.iterrows():
            values = []
            for col in self.display_columns:
                val = row.get(col, "")
                if pd.isna(val):
                    val = ""
                values.append(str(val))

            # Use the original dataframe index as item ID
            self.tree.insert("", "end", iid=str(idx), values=values)

    def _sort_tree(self, col):
        """Sort tree by column."""
        if self.filtered_df is None:
            return

        # Get current sort direction
        try:
            current_dir = getattr(self, "_sort_dir", {})
            reverse = current_dir.get(col, False)
            current_dir[col] = not reverse
            self._sort_dir = current_dir
        except AttributeError:
            self._sort_dir = {col: True}

        # Sort
        ascending = not self._sort_dir.get(col, True)
        self.filtered_df = self.filtered_df.sort_values(by=col, ascending=ascending, na_position="last")
        self._update_tree()

    def _on_select(self, event):
        """Handle row selection."""
        selection = self.tree.selection()
        if selection:
            self.current_row_index = int(selection[0])

    def _show_context_menu(self, event):
        """Show context menu on right-click."""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.current_row_index = int(item)
            self.context_menu.tk_popup(event.x_root, event.y_root)

    def _get_selected_row(self) -> Optional[pd.Series]:
        """Get the currently selected row as a Series."""
        if self.current_row_index is None or self.filtered_df is None:
            return None
        if self.current_row_index not in self.filtered_df.index:
            return None
        return self.filtered_df.loc[self.current_row_index]

    def _view_selected(self):
        """View the selected row in a detail window."""
        row = self._get_selected_row()
        if row is None:
            messagebox.showwarning("Warning", "Please select a row to view")
            return

        self._open_detail_window(row, readonly=True)

    def _edit_selected(self):
        """Edit the selected row."""
        row = self._get_selected_row()
        if row is None:
            messagebox.showwarning("Warning", "Please select a row to edit")
            return

        self._open_detail_window(row, readonly=False)

    def _delete_selected(self):
        """Delete the selected row."""
        row = self._get_selected_row()
        if row is None:
            messagebox.showwarning("Warning", "Please select a row to delete")
            return

        uid = row.get("UID", "Unknown")
        if messagebox.askyesno("Confirm Delete", f"Delete row with UID: {uid}?\nThis cannot be undone."):
            # Remove from main dataframe
            if self.df is not None and self.current_row_index in self.df.index:
                self.df = self.df.drop(self.current_row_index).reset_index(drop=True)
                self._apply_filters()
                self.status_var.set(f"Deleted row UID: {uid}")
                logging.info(f"Deleted row with UID: {uid}")

    def _open_detail_window(self, row: pd.Series, readonly: bool = False):
        """Open a detail window for viewing/editing a row."""
        title = "View Record" if readonly else "Edit Record"

        # Close existing window if open
        if self.edit_window and self.edit_window.winfo_exists():
            self.edit_window.destroy()
        if self.view_window and self.view_window.winfo_exists():
            self.view_window.destroy()

        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("800x700")
        window.minsize(600, 500)
        window.transient(self.root)
        window.grab_set()

        if readonly:
            self.view_window = window
        else:
            self.edit_window = window

        # Create scrollable frame
        canvas = tk.Canvas(window)
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Create form fields for all columns
        self.detail_entries = {}
        row_frame = ttk.Frame(scrollable_frame, padding="10")
        row_frame.pack(fill=tk.BOTH, expand=True)

        # Get all columns from the row
        all_columns = list(row.index)

        # Group columns for better layout
        for i, col in enumerate(all_columns):
            val = row[col]
            if pd.isna(val):
                val = ""
            else:
                val = str(val)

            r = i // 2
            c = (i % 2) * 2

            ttk.Label(row_frame, text=f"{col}:").grid(row=r, column=c, sticky="w", padx=5, pady=3)

            if readonly:
                entry = ttk.Entry(row_frame, width=40)
                entry.insert(0, val)
                entry.config(state="readonly")
            else:
                entry = ttk.Entry(row_frame, width=40)
                entry.insert(0, val)

            entry.grid(row=r, column=c+1, sticky="ew", padx=5, pady=3)
            self.detail_entries[col] = entry

        row_frame.grid_columnconfigure(1, weight=1)
        row_frame.grid_columnconfigure(3, weight=1)

        # Buttons
        btn_frame = ttk.Frame(window, padding="10")
        btn_frame.pack(fill=tk.X)

        if not readonly:
            ttk.Button(btn_frame, text="Save",
                       command=lambda: self._save_detail_window(row.name, window)).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Close", command=window.destroy).pack(side=tk.RIGHT, padx=5)

    def _save_detail_window(self, row_idx: int, window: tk.Toplevel):
        """Save changes from detail window."""
        if self.df is None or row_idx not in self.df.index:
            messagebox.showerror("Error", "Row not found in dataframe")
            return

        try:
            # Update dataframe with new values
            for col, entry in self.detail_entries.items():
                if col in self.df.columns:
                    new_val = entry.get()
                    # Try to convert to appropriate type
                    if col == "EXPTID" and new_val:
                        try:
                            new_val = int(float(new_val))
                        except ValueError:
                            pass
                    elif new_val == "":
                        new_val = pd.NA
                    self.df.at[row_idx, col] = new_val

            self._apply_filters()
            window.destroy()
            self.status_var.set(f"Updated row index {row_idx}")
            logging.info(f"Updated row index {row_idx}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
            logging.error(f"Failed to save row {row_idx}: {e}")

    def _save_changes(self):
        """Save all changes to the output file."""
        if self.df is None:
            messagebox.showwarning("Warning", "No data to save")
            return

        output_path = self.params.output_path
        if output_path is None:
            output_path = self.params.rc7_preprocessed_path

        # Ask for confirmation if overwriting original
        if output_path == self.params.rc7_preprocessed_path:
            if not messagebox.askyesno("Confirm Overwrite",
                                       f"This will overwrite the original file:\n{output_path}\n\nContinue?"):
                return

        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Save
            self.df.to_csv(output_path, index=False)
            self.status_var.set(f"Saved {len(self.df)} rows to {output_path.name}")
            messagebox.showinfo("Success", f"Data saved to:\n{output_path}")
            logging.info(f"Saved corrected data to {output_path} ({len(self.df)} rows)")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
            logging.error(f"Failed to save corrected data: {e}")

    def _export_filtered(self):
        """Export filtered rows to a new CSV file."""
        if self.filtered_df is None or self.filtered_df.empty:
            messagebox.showwarning("Warning", "No filtered rows to export")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Filtered Rows"
        )

        if file_path:
            try:
                self.filtered_df.to_csv(file_path, index=False)
                self.status_var.set(f"Exported {len(self.filtered_df)} rows to {Path(file_path).name}")
                messagebox.showinfo("Success", f"Exported {len(self.filtered_df)} rows to:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {e}")

    def run(self):
        """Run the UI main loop."""
        self.root.mainloop()


def run_data_correction_ui(rc7_preprocessed_path: Path, output_path: Optional[Path] = None):
    """Entry point to run the data correction UI."""
    params = DataCorrectionParams(
        rc7_preprocessed_path=rc7_preprocessed_path,
        output_path=output_path
    )
    app = DataCorrectionUI(params)
    app.run()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        rc7_path = Path(sys.argv[1])
        out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    else:
        # Default path from config
        from src.utils.config_loader import load_config
        config = load_config("config.yaml")
        rc7_config = config.get("RC7_preprocessing", {})
        rc7_path = Path(rc7_config.get("RC7_preprocessed_path", "artifacts/a3_RC7_preprocessed/preprocessed_RC7.csv"))
        out_path = None

    run_data_correction_ui(rc7_path, out_path)