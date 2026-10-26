"""
================================================================
 SMART EXAM TIMETABLE GENERATOR
 ----------------------------------------------------------------
 - Mamdani Fuzzy Inference
 - FN / AN sessions with real time slots
 - Hall allocation with capacity + conflict checking
 - Export generated timetable to CSV
================================================================
"""

import csv
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta


# ================================================================
# STEP 0 — UNIVERSE + MEMBERSHIP FUNCTION
# ================================================================


def create_universe(low, high, step=1):
    return np.arange(low, high + step, step)


def triangular_mf(x, a, b, c):
    if x <= a or x >= c:
        return 0.0
    if x == b:
        return 1.0
    if x < b:
        return (x - a) / (b - a)
    return (c - x) / (c - b)


def membership_curve(universe, a, b, c):
    return np.array([triangular_mf(x, a, b, c) for x in universe])


# ================================================================
# FUZZY VARIABLE
# ================================================================


class FuzzyVariable:
    def __init__(self, name, universe):
        self.name = name
        self.universe = universe
        self.sets = {}

    def add_set(self, name, a, b, c):
        self.sets[name] = (a, b, c)

    def fuzzify(self, set_name, value):
        """STEP 1: FUZZIFICATION."""
        a, b, c = self.sets[set_name]
        return triangular_mf(value, a, b, c)

    def curve(self, set_name):
        a, b, c = self.sets[set_name]
        return membership_curve(self.universe, a, b, c)


# ================================================================
# FUZZY RULE
# ================================================================


class FuzzyRule:
    def __init__(self, antecedents, consequent):
        self.antecedents = antecedents
        self.consequent = consequent

    def firing_strength(self, inputs, variables):
        """STEP 2: AND = MIN."""
        memberships = [
            variables[var].fuzzify(set_name, inputs[var])
            for var, set_name in self.antecedents
        ]
        return min(memberships)


# ================================================================
# MAMDANI FUZZY INFERENCE SYSTEM
# ================================================================


class MamdaniFIS:
    def __init__(self, input_vars, output_var):
        self.inputs = input_vars
        self.output = output_var
        self.rules = []

    def add_rule(self, antecedents, consequent_set):
        self.rules.append(
            FuzzyRule(antecedents, (self.output.name, consequent_set))
        )

    def compute(self, input_values):
        # STEP 3: CLIPPING
        clipped = []
        for rule in self.rules:
            w = rule.firing_strength(input_values, self.inputs)
            if w == 0.0:
                continue
            _, cons_set = rule.consequent
            cons_curve = self.output.curve(cons_set)
            clipped.append(np.minimum(w, cons_curve))

        if not clipped:
            return 0.0

        # STEP 4: AGGREGATION (MAX)
        aggregated = clipped[0]
        for curve in clipped[1:]:
            aggregated = np.maximum(aggregated, curve)

        # STEP 5: DEFUZZIFICATION (CENTROID)
        denom = np.sum(aggregated)
        if denom == 0:
            return 0.0
        return float(
            np.sum(self.output.universe * aggregated) / denom
        )


# ================================================================
# BUILD THE TWO FUZZY SYSTEMS
# ================================================================


def build_difficulty_system():
    """Subject difficulty FIS."""
    credit = FuzzyVariable("credit", create_universe(1, 6, 1))
    students = FuzzyVariable("students", create_universe(0, 500, 1))
    pass_rate = FuzzyVariable("pass_rate", create_universe(0, 100, 1))
    difficulty = FuzzyVariable("difficulty", create_universe(0, 100, 1))

    credit.add_set("low", 1, 1, 3)
    credit.add_set("medium", 2, 3, 4)
    credit.add_set("high", 3, 6, 6)

    students.add_set("few", 0, 0, 70)
    students.add_set("moderate", 50, 100, 150)
    students.add_set("many", 130, 500, 500)

    pass_rate.add_set("poor", 0, 0, 50)
    pass_rate.add_set("average", 40, 65, 85)
    pass_rate.add_set("good", 75, 100, 100)

    difficulty.add_set("easy", 0, 0, 40)
    difficulty.add_set("medium", 30, 50, 70)
    difficulty.add_set("hard", 60, 100, 100)

    fis = MamdaniFIS(
        {
            "credit": credit,
            "students": students,
            "pass_rate": pass_rate,
        },
        difficulty,
    )

    fis.add_rule(
        [("credit", "high"), ("students", "many"), ("pass_rate", "poor")],
        "hard",
    )
    fis.add_rule([("credit", "high"), ("pass_rate", "poor")], "hard")
    fis.add_rule(
        [("credit", "medium"), ("students", "many"), ("pass_rate", "poor")],
        "hard",
    )
    fis.add_rule(
        [("credit", "medium"), ("pass_rate", "average")], "medium"
    )
    fis.add_rule([("credit", "low"), ("pass_rate", "good")], "easy")
    fis.add_rule([("credit", "low"), ("students", "few")], "easy")
    fis.add_rule([("credit", "high"), ("pass_rate", "good")], "medium")
    fis.add_rule([("students", "few"), ("pass_rate", "good")], "easy")
    fis.add_rule(
        [("students", "many"), ("pass_rate", "average")], "medium"
    )
    fis.add_rule(
        [("credit", "medium"), ("students", "moderate")], "medium"
    )

    return fis


def build_slot_system():
    """Slot suitability FIS (chooses best day + session)."""
    diff = FuzzyVariable("difficulty", create_universe(0, 100, 1))
    load = FuzzyVariable("day_load", create_universe(0, 4, 1))
    gap = FuzzyVariable("gap", create_universe(0, 10, 1))
    suitability = FuzzyVariable("suitability", create_universe(0, 100, 1))

    diff.add_set("easy", 0, 0, 40)
    diff.add_set("medium", 30, 50, 70)
    diff.add_set("hard", 60, 100, 100)

    load.add_set("empty", 0, 0, 1)
    load.add_set("light", 1, 1, 2)
    load.add_set("heavy", 2, 4, 4)

    gap.add_set("short", 0, 0, 3)
    gap.add_set("medium", 2, 5, 8)
    gap.add_set("long", 6, 10, 10)

    suitability.add_set("poor", 0, 0, 40)
    suitability.add_set("fair", 30, 50, 70)
    suitability.add_set("good", 60, 80, 100)

    fis = MamdaniFIS(
        {"difficulty": diff, "day_load": load, "gap": gap},
        suitability,
    )

    fis.add_rule(
        [("difficulty", "hard"), ("day_load", "empty"), ("gap", "long")],
        "good",
    )
    fis.add_rule(
        [("difficulty", "hard"), ("day_load", "light"), ("gap", "medium")],
        "good",
    )
    fis.add_rule(
        [("difficulty", "hard"), ("day_load", "heavy")], "poor"
    )
    fis.add_rule(
        [("difficulty", "medium"), ("day_load", "empty")], "good"
    )
    fis.add_rule(
        [("difficulty", "medium"), ("day_load", "heavy")], "fair"
    )
    fis.add_rule(
        [("difficulty", "easy"), ("day_load", "light")], "good"
    )
    fis.add_rule(
        [("difficulty", "easy"), ("day_load", "heavy")], "fair"
    )
    fis.add_rule([("gap", "short")], "poor")
    fis.add_rule(
        [("day_load", "empty"), ("gap", "long")], "good"
    )

    return fis


# ================================================================
# HALL CONFIGURATION
# ================================================================


# Each hall: (hall_number, capacity)
DEFAULT_HALLS = [
    ("H-101", 60),
    ("H-102", 60),
    ("H-201", 90),
    ("H-202", 90),
    ("H-301", 120),
    ("H-302", 120),
    ("H-401", 200),
    ("H-402", 200),
    ("AUD-1", 500),
    ("AUD-2", 500),
]


# ================================================================
# TIMETABLE GENERATOR
# ================================================================


class ExamTimetableGenerator:
    """
    Sessions per day: FN (Forenoon) and AN (Afternoon).
    Each assigned exam gets a hall with enough capacity.
    """

    def __init__(
        self,
        start_date,
        days_available,
        sessions=None,
        max_exams_per_day=2,
        halls=None,
    ):
        self.start_date = start_date
        self.days_available = days_available
        self.max_exams_per_day = max_exams_per_day

        self.sessions = sessions or {
            "FN": {"label": "09:30 AM – 12:30 PM"},
            "AN": {"label": "02:00 PM – 05:00 PM"},
        }

        self.halls = halls or DEFAULT_HALLS[:]
        self.difficulty_fis = build_difficulty_system()
        self.slot_fis = build_slot_system()

        self.timetable = []
        self.scheduled_dates = []
        self.hall_schedule = {}

    def generate(self, subjects):
        self.timetable = []
        self.scheduled_dates = []
        self.hall_schedule = {}

        # 1. Calculate fuzzy difficulty
        for subject in subjects:
            subject["difficulty"] = self.difficulty_fis.compute({
                "credit": subject.get("credit", 3),
                "students": subject.get("enrolled", 0),
                "pass_rate": subject.get("pass_rate", 70),
            })

        # 2. Schedule hardest subjects first
        subjects_sorted = sorted(
            subjects, key=lambda item: -item["difficulty"]
        )

        # 3. Create candidate date/session slots
        candidates = []
        for day_offset in range(self.days_available):
            date = self.start_date + timedelta(days=day_offset)
            if date.weekday() == 6:  # Skip Sunday
                continue

            for session_key in self.sessions:
                candidates.append({
                    "date": date,
                    "session": session_key,
                    "day_load": 0,
                })

        # 4. Assign each subject
        for subject in subjects_sorted:
            best = None
            best_score = -1

            for candidate in candidates:
                if candidate["day_load"] >= self.max_exams_per_day:
                    continue

                gap = self._min_gap_days(candidate["date"])
                score = self.slot_fis.compute({
                    "difficulty": subject["difficulty"],
                    "day_load": candidate["day_load"],
                    "gap": gap,
                })

                days_from_start = (
                    candidate["date"] - self.start_date
                ).days

                # Prefer harder subjects earlier
                score += (
                    subject["difficulty"] / 100.0
                ) * (self.days_available - days_from_start)

                # Mild preference for FN
                if candidate["session"] == "FN":
                    score += 2

                if score > best_score:
                    best_score = score
                    best = candidate

            if best is None:
                self.timetable.append(
                    self._unscheduled_row(subject)
                )
                continue

            # Allocate a hall
            hall = self._allocate_hall(
                best["date"],
                best["session"],
                subject.get("enrolled", 0),
            )

            if hall is None:
                self.timetable.append(
                    self._unscheduled_row(subject, reason="No hall")
                )
                continue

            self.timetable.append({
                "Code": subject["code"],
                "Subject": subject["name"],
                "Date": best["date"].strftime("%a, %d %b %Y"),
                "Session": best["session"],
                "Time": self.sessions[best["session"]]["label"],
                "Hall": hall,
                "Difficulty": subject["difficulty"],
                "Students": subject.get("enrolled", 0),
            })

            best["day_load"] += 1
            self.scheduled_dates.append(best["date"])
            self.hall_schedule.setdefault(
                (best["date"], best["session"]), set()
            ).update(hall.split(", "))

        # 5. Sort by actual date, then session order
        session_order = {
            session: index
            for index, session in enumerate(self.sessions.keys())
        }

        def sort_key(row):
            if row["Date"] == "TBD":
                return (1, datetime.max.date(), 99)
            exam_date = datetime.strptime(
                row["Date"], "%a, %d %b %Y"
            ).date()
            return (
                0,
                exam_date,
                session_order.get(row["Session"], 99),
            )

        self.timetable.sort(key=sort_key)
        return self.timetable

    def _unscheduled_row(self, subject, reason="No slot"):
        return {
            "Code": subject["code"],
            "Subject": subject["name"],
            "Date": "TBD",
            "Session": "—",
            "Time": reason,
            "Hall": "—",
            "Difficulty": subject["difficulty"],
            "Students": subject.get("enrolled", 0),
        }

    def _min_gap_days(self, candidate_date):
        """Calculates minimum gap days relative to previously scheduled exams."""
        gaps = [
            (candidate_date - prev_date).days
            for prev_date in self.scheduled_dates
            if prev_date < candidate_date
        ]
        return min(gaps) if gaps else 10

    def _allocate_hall(self, date, session, enrolled):
        """Pick single hall or combine available halls to satisfy enrollment."""
        used = self.hall_schedule.get((date, session), set())

        # Option A: Single hall with sufficient capacity
        for hall_number, capacity in sorted(self.halls, key=lambda h: h[1]):
            if hall_number not in used and capacity >= enrolled:
                return hall_number

        # Option B: Combine multiple unused halls if total capacity matches enrollment
        available_halls = [
            (h_num, cap) for h_num, cap in sorted(self.halls, key=lambda h: h[1], reverse=True)
            if h_num not in used
        ]

        assigned = []
        total_cap = 0
        for h_num, cap in available_halls:
            assigned.append(h_num)
            total_cap += cap
            if total_cap >= enrolled:
                return ", ".join(assigned)

        return None


# ================================================================
# GUI
# ================================================================


class TimetableGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart Exam Timetable Generator — Fuzzy Logic")
        self.root.geometry("1120x820")
        self.root.configure(bg="#1e1e2e")

        self.subjects = []
        self.generator = None

        self._header()
        self._form()
        self._list()
        self._controls()
        self._output()

    def _header(self):
        tk.Label(
            self.root,
            text="📅 Smart Exam Timetable Generator",
            font=("Helvetica", 20, "bold"),
            fg="#89b4fa",
            bg="#1e1e2e",
        ).pack(pady=(12, 2))

        tk.Label(
            self.root,
            text="Mamdani Fuzzy Logic · FN/AN Sessions · Hall Allocation",
            font=("Helvetica", 10, "italic"),
            fg="#a6adc8",
            bg="#1e1e2e",
        ).pack(pady=(0, 8))

    def _form(self):
        frame = tk.LabelFrame(
            self.root,
            text=" Add Subject ",
            fg="#cdd6f4",
            bg="#1e1e2e",
            font=("Helvetica", 11, "bold"),
            padx=10,
            pady=8,
        )
        frame.pack(fill="x", padx=20, pady=5)

        row1 = tk.Frame(frame, bg="#1e1e2e")
        row1.pack(fill="x", pady=3)

        tk.Label(
            row1, text="Code:", fg="#cdd6f4", bg="#1e1e2e",
            width=12, anchor="w"
        ).pack(side="left")
        self.e_code = tk.Entry(row1, width=12)
        self.e_code.pack(side="left", padx=5)

        tk.Label(
            row1, text="Name:", fg="#cdd6f4", bg="#1e1e2e",
            width=8, anchor="w"
        ).pack(side="left")
        self.e_name = tk.Entry(row1, width=28)
        self.e_name.pack(side="left", padx=5)

        row2 = tk.Frame(frame, bg="#1e1e2e")
        row2.pack(fill="x", pady=3)

        tk.Label(
            row2, text="Credits:", fg="#cdd6f4", bg="#1e1e2e",
            width=12, anchor="w"
        ).pack(side="left")
        self.e_credit = tk.Entry(row2, width=10)
        self.e_credit.insert(0, "3")
        self.e_credit.pack(side="left", padx=5)

        tk.Label(
            row2, text="Enrolled:", fg="#cdd6f4", bg="#1e1e2e",
            width=8, anchor="w"
        ).pack(side="left")
        self.e_enrolled = tk.Entry(row2, width=10)
        self.e_enrolled.insert(0, "80")
        self.e_enrolled.pack(side="left", padx=5)

        tk.Label(
            row2, text="Pass %:", fg="#cdd6f4", bg="#1e1e2e",
            width=8, anchor="w"
        ).pack(side="left")
        self.e_pass = tk.Entry(row2, width=10)
        self.e_pass.insert(0, "70")
        self.e_pass.pack(side="left", padx=5)

        tk.Button(
            frame,
            text="➕ Add Subject",
            command=self.add_subject,
            bg="#89b4fa",
            fg="#1e1e2e",
            font=("Helvetica", 10, "bold"),
            relief="flat",
            padx=10,
            pady=4,
        ).pack(pady=6)

    def _list(self):
        frame = tk.LabelFrame(
            self.root,
            text=" Subjects ",
            fg="#cdd6f4",
            bg="#1e1e2e",
            font=("Helvetica", 11, "bold"),
            padx=10,
            pady=8,
        )
        frame.pack(fill="both", expand=True, padx=20, pady=5)

        columns = (
            "Code", "Name", "Credits", "Enrolled", "Pass%"
        )
        self.tree = ttk.Treeview(
            frame, columns=columns, show="headings", height=5
        )

        for column in columns:
            self.tree.heading(column, text=column)
            self.tree.column(column, width=140, anchor="center")

        self.tree.pack(fill="both", expand=True, side="left")

        scrollbar = ttk.Scrollbar(
            frame, orient="vertical", command=self.tree.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        tk.Button(
            frame,
            text="🗑 Remove Selected",
            command=self.remove_subject,
            bg="#f38ba8",
            fg="#1e1e2e",
            relief="flat",
            font=("Helvetica", 9, "bold"),
        ).pack(side="bottom", pady=4)

    def _controls(self):
        frame = tk.Frame(self.root, bg="#1e1e2e")
        frame.pack(fill="x", padx=20, pady=5)

        tk.Label(
            frame,
            text="Start Date (YYYY-MM-DD):",
            fg="#cdd6f4",
            bg="#1e1e2e",
        ).pack(side="left")

        self.e_start = tk.Entry(frame, width=14)
        self.e_start.insert(0, "2026-10-22")
        self.e_start.pack(side="left", padx=5)

        tk.Label(
            frame, text="Days:", fg="#cdd6f4", bg="#1e1e2e"
        ).pack(side="left", padx=(15, 0))

        self.e_days = tk.Entry(frame, width=6)
        self.e_days.insert(0, "10")
        self.e_days.pack(side="left", padx=5)

        tk.Button(
            frame,
            text="⚡ Generate Timetable",
            command=self.generate,
            bg="#a6e3a1",
            fg="#1e1e2e",
            font=("Helvetica", 11, "bold"),
            relief="flat",
            padx=15,
            pady=6,
        ).pack(side="left", padx=8)

        tk.Button(
            frame,
            text="📥 Export Timetable",
            command=self.export_timetable,
            bg="#cba6f7",
            fg="#1e1e2e",
            font=("Helvetica", 10, "bold"),
            relief="flat",
            padx=12,
            pady=6,
        ).pack(side="left", padx=5)

        tk.Button(
            frame,
            text="🖨 Show Fuzzy Trace",
            command=self.show_trace,
            bg="#fab387",
            fg="#1e1e2e",
            font=("Helvetica", 10, "bold"),
            relief="flat",
            padx=10,
            pady=6,
        ).pack(side="right")

    def _output(self):
        frame = tk.LabelFrame(
            self.root,
            text=" Generated Timetable ",
            fg="#cdd6f4",
            bg="#1e1e2e",
            font=("Helvetica", 11, "bold"),
            padx=10,
            pady=8,
        )
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        columns = (
            "Code", "Subject", "Date", "Session", "Time Slot",
            "Hall", "Difficulty", "Enrolled"
        )
        self.out = ttk.Treeview(
            frame, columns=columns, show="headings", height=9
        )

        widths = (70, 180, 130, 70, 180, 80, 90, 80)
        for column, width in zip(columns, widths):
            self.out.heading(column, text=column)
            self.out.column(column, width=width, anchor="center")

        self.out.pack(fill="both", expand=True)

    def add_subject(self):
        try:
            code = self.e_code.get().strip().upper()
            name = self.e_name.get().strip()
            credit = int(self.e_credit.get())
            enrolled = int(self.e_enrolled.get())
            pass_rate = int(self.e_pass.get())

            if not code or not name:
                messagebox.showwarning(
                    "Missing", "Code and Name are required."
                )
                return

            if not 1 <= credit <= 6:
                messagebox.showerror(
                    "Invalid Input", "Credits must be between 1 and 6."
                )
                return

            if enrolled < 0:
                messagebox.showerror(
                    "Invalid Input", "Enrolled students cannot be negative."
                )
                return

            if not 0 <= pass_rate <= 100:
                messagebox.showerror(
                    "Invalid Input", "Pass percentage must be 0 to 100."
                )
                return

            if any(subject["code"] == code for subject in self.subjects):
                messagebox.showerror(
                    "Duplicate Code", "This subject code already exists."
                )
                return

            self.subjects.append({
                "code": code,
                "name": name,
                "credit": credit,
                "enrolled": enrolled,
                "pass_rate": pass_rate,
            })

            self.tree.insert(
                "", "end",
                values=(
                    code, name, credit, enrolled, pass_rate
                ),
            )

            self.e_code.delete(0, tk.END)
            self.e_name.delete(0, tk.END)

        except ValueError:
            messagebox.showerror(
                "Invalid Input", "Please enter valid numeric values."
            )

    def remove_subject(self):
        for item in self.tree.selection():
            values = self.tree.item(item, "values")
            code_to_remove = values[0]
            self.subjects = [
                subject for subject in self.subjects
                if subject["code"] != code_to_remove
            ]
            self.tree.delete(item)

        self.generator = None
        for row in self.out.get_children():
            self.out.delete(row)

    def generate(self):
        if not self.subjects:
            messagebox.showwarning(
                "No Subjects", "Please add at least one subject."
            )
            return

        try:
            start_date = datetime.strptime(
                self.e_start.get().strip(), "%Y-%m-%d"
            ).date()
            days = int(self.e_days.get())

            if days <= 0:
                messagebox.showerror(
                    "Invalid Input", "Days must be greater than zero."
                )
                return

        except ValueError:
            messagebox.showerror(
                "Invalid Input",
                "Check start date (YYYY-MM-DD) and enter a positive number of days.",
            )
            return

        self.generator = ExamTimetableGenerator(start_date, days)
        timetable = self.generator.generate(self.subjects)

        for row in self.out.get_children():
            self.out.delete(row)

        for row in timetable:
            self.out.insert(
                "", "end",
                values=(
                    row["Code"],
                    row["Subject"],
                    row["Date"],
                    row["Session"],
                    row["Time"],
                    row["Hall"],
                    f"{row['Difficulty']:.2f}",
                    row["Students"],
                ),
            )

        messagebox.showinfo(
            "Done",
            f"Timetable generated for {len(timetable)} subjects.",
        )

    def export_timetable(self):
        if self.generator is None or not self.generator.timetable:
            messagebox.showwarning(
                "No Timetable",
                "Please generate a timetable first.",
            )
            return

        file_path = filedialog.asksaveasfilename(
            title="Export Exam Timetable",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialfile="Exam_Timetable.csv",
        )

        if not file_path:
            return

        columns = [
            "Code", "Subject", "Date", "Session",
            "Time", "Hall", "Difficulty", "Students",
        ]

        try:
            with open(
                file_path, "w", newline="", encoding="utf-8-sig"
            ) as file:
                writer = csv.DictWriter(file, fieldnames=columns)
                writer.writeheader()

                for row in self.generator.timetable:
                    export_row = {
                        column: row.get(column, "")
                        for column in columns
                    }
                    export_row["Difficulty"] = (
                        f"{row['Difficulty']:.2f}"
                    )
                    writer.writerow(export_row)

            messagebox.showinfo(
                "Export Successful",
                f"Timetable exported successfully!\n\n{file_path}",
            )

        except (OSError, csv.Error) as error:
            messagebox.showerror(
                "Export Failed",
                f"Could not export timetable:\n{error}",
            )

    def show_trace(self):
        if not self.subjects:
            messagebox.showwarning(
                "No Subjects", "Add at least one subject."
            )
            return

        fis = build_difficulty_system()
        subject = self.subjects[0]
        inputs = {
            "credit": subject["credit"],
            "students": subject["enrolled"],
            "pass_rate": subject["pass_rate"],
        }

        lines = []
        lines.append("FUZZY TRACE for " + subject["code"])
        lines.append("=" * 50)
        lines.append(f"\nCrisp inputs: {inputs}")

        lines.append("\nSTEP 1 — FUZZIFICATION")
        for variable_name, value in inputs.items():
            lines.append(f"  {variable_name} = {value}")
            for set_name in fis.inputs[variable_name].sets:
                membership = fis.inputs[variable_name].fuzzify(
                    set_name, value
                )
                if membership > 0:
                    lines.append(
                        f"     μ({set_name}) = {membership:.3f}"
                    )

        lines.append("\nSTEP 2 — RULE STRENGTHS (AND = MIN)")
        for index, rule in enumerate(fis.rules, 1):
            strength = rule.firing_strength(inputs, fis.inputs)
            if strength > 0:
                antecedents = " AND ".join(
                    f"{variable}={set_name}"
                    for variable, set_name in rule.antecedents
                )
                lines.append(
                    f"  R{index}: IF {antecedents} "
                    f"THEN {rule.consequent[1]} → w={strength:.3f}"
                )

        result = fis.compute(inputs)
        lines.append("\nSTEPS 3–5 — CLIP → MAX → CENTROID")
        lines.append(f"  Difficulty score = {result:.2f}")

        messagebox.showinfo("Fuzzy Trace", "\n".join(lines))


# ================================================================
# ENTRY POINT
# ================================================================


if __name__ == "__main__":
    root = tk.Tk()
    app = TimetableGUI(root)
    root.mainloop()