"""Desktop app: pick a manuscript and journal, fill in what only the author knows, see what changed.

    .venv/bin/python app.py
"""
import subprocess
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from formatter import model, run
from journals import JOURNALS

NAMES = {f"{j['short']}: {j['name']}": key for key, j in JOURNALS.items()}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Manuscript Formatter")
        self.geometry("860x720")
        self.paper = tk.StringVar()
        self.journal = tk.StringVar(value=next(iter(NAMES)))
        self.out_dir = tk.StringVar()     # defaults to the manuscript's own folder
        self.boxes = {}          # (request, context) -> its text box
        self.last_out = None

        # 1. Inputs
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        top.columnconfigure(1, weight=1)
        journal = ttk.Combobox(top, textvariable=self.journal, values=list(NAMES), state="readonly")
        journal.bind("<<ComboboxSelected>>", lambda e: self.scan())
        for i, (label, widget, choose) in enumerate([
                ("Manuscript", ttk.Entry(top, textvariable=self.paper), self.choose_paper),
                ("Journal", journal, None),
                ("Save to", ttk.Entry(top, textvariable=self.out_dir), self.choose_out)]):
            ttk.Label(top, text=label).grid(row=i, column=0, sticky="w", pady=3)
            widget.grid(row=i, column=1, sticky="ew", padx=6)
            if choose:
                ttk.Button(top, text="Choose…", command=choose).grid(row=i, column=2)

        # 2. The form (scrollable) and 3. the list of changes, as two tabs
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=10)
        holder = ttk.Frame(self.tabs)
        self.tabs.add(holder, text="Fill in")
        canvas = tk.Canvas(holder, highlightthickness=0)
        bar = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        self.form = ttk.Frame(canvas, padding=10)
        self.form.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        window = canvas.create_window((0, 0), window=self.form, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        step = (lambda d: -d) if sys.platform == "darwin" else (lambda d: -d // 120)
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(step(e.delta), "units"))

        self.changes = tk.Text(self.tabs, wrap="word", padx=10, pady=10, relief="flat", font="TkDefaultFont")
        self.changes.tag_configure("status", font=("TkDefaultFont", 15, "bold"), spacing1=12, spacing3=4)
        self.changes.tag_configure("title", font=("TkDefaultFont", 12, "bold"), spacing1=6)
        self.changes.tag_configure("detail", lmargin1=18, lmargin2=30)
        self.tabs.add(self.changes, text="Changes")

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Format manuscript", command=self.format).pack(side="right")
        ttk.Button(bottom, text="Open output folder", command=self.open_output).pack(side="right", padx=6)
        self.status = ttk.Label(bottom, text="Choose a manuscript to begin.")
        self.status.pack(side="left")
        self.build_form([])

    def choose_paper(self):
        path = filedialog.askopenfilename(filetypes=[("Word document", "*.docx")])
        if path:
            self.paper.set(path)
            self.out_dir.set(self.out_dir.get() or str(Path(path).parent))
            self.scan()

    def choose_out(self):
        path = filedialog.askdirectory(initialdir=self.out_dir.get() or None)
        if path:
            self.out_dir.set(path)

    def scan(self):
        """A trial run into a throwaway folder, to learn what the author needs to supply."""
        if not self.paper.get():
            return
        try:
            with tempfile.TemporaryDirectory() as tmp:
                run(self.paper.get(), JOURNALS[NAMES[self.journal.get()]], tmp)
        except Exception as e:
            return messagebox.showerror("Could not read the manuscript", str(e))
        self.build_form(list(model.ASKED))
        self.tabs.select(0)
        self.status.config(text=f"{len(model.ASKED)} item(s) to fill in. Empty boxes stay as highlighted notes.")

    def build_form(self, asked):
        typed = {k: box.get("1.0", "end").strip() for k, box in self.boxes.items()}   # keep what was already typed
        for w in self.form.winfo_children():
            w.destroy()
        self.boxes = {}
        if not asked:
            ttk.Label(self.form, text="Nothing to fill in yet." if not self.paper.get()
                      else "Nothing to fill in: the manuscript has everything this journal asks for.").pack(anchor="w")
        for key in asked:
            request, context = key
            label = request.strip("[]").split(": ", 1)[1]
            ttk.Label(self.form, text=label[0].upper() + label[1:], font=("TkDefaultFont", 12, "bold")).pack(anchor="w", pady=(10, 0))
            if context:
                ttk.Label(self.form, text=context, foreground="gray", wraplength=760).pack(anchor="w")
            box = tk.Text(self.form, height=10 if "abstract" in request else 2, wrap="word", relief="solid", borderwidth=1, font="TkDefaultFont")
            box.insert("1.0", typed.get(key, ""))
            box.pack(fill="x", pady=(2, 0))
            self.boxes[key] = box

    def format(self):
        if not self.paper.get():
            return messagebox.showinfo("Manuscript Formatter", "Choose a manuscript first.")
        answers = {k: box.get("1.0", "end") for k, box in self.boxes.items()}
        out_dir = self.out_dir.get() or str(Path(self.paper.get()).parent)
        try:
            self.last_out, report = run(self.paper.get(), JOURNALS[NAMES[self.journal.get()]], out_dir, answers)
        except Exception as e:
            return messagebox.showerror("Formatting failed", str(e))
        self.show_changes(report)
        self.status.config(text=f"Saved to {self.last_out}")

    def show_changes(self, report):
        t = self.changes
        t.config(state="normal")
        t.delete("1.0", "end")
        for status in report.ORDER:
            items = [(title, details) for s, title, details in report.items if s == status]
            t.insert("end", f"{status} ({len(items)})\n", "status")
            for title, details in items:
                t.insert("end", title + "\n", "title")
                for line in details:
                    t.insert("end", f"• {line}\n", "detail")
        t.config(state="disabled")
        self.tabs.select(1)

    def open_output(self):
        folder = self.last_out or self.out_dir.get()
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])


if __name__ == "__main__":
    App().mainloop()
