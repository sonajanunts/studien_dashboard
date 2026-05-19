import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
from statistics import mean
from enum import Enum


# ==========================================
# 1. MODEL
# Enthält die Datenklassen der Anwendung
# ==========================================

class ModulStatus(Enum):
    OFFEN = "offen"
    GEPLANT = "geplant"
    BESTANDEN = "bestanden"
    NICHT_BESTANDEN = "nicht bestanden"


class Pruefungsleistung:
    # Speichert die Modulnote
    def __init__(self, note):
        self.note = note


class Modul:
    # Repräsentiert ein Studienmodul
    def __init__(self, name, ects, status, pruefungsleistung=None):
        self.name = name
        self.ects = ects
        self.status = status
        self.pruefungsleistung = pruefungsleistung


class Semester:
    # Enthält alle Module eines Semesters
    def __init__(self, nummer):
        self.nummer = nummer
        self.module = []


class Studiengang:
    # Allgemeine Studiendaten
    def __init__(self, name, start_datum, regel_semester=6, ziel_ects=180, ziel_note=2.0):
        self.name = name
        self.start_datum = start_datum
        self.regel_semester = regel_semester
        self.ziel_ects = ziel_ects
        self.ziel_note = ziel_note

    # Enddatum wird automatisch berechnet
    @property
    def end_datum(self):
        jahre_dazu = self.regel_semester // 2

        return date(
            self.start_datum.year + jahre_dazu,
            self.start_datum.month,
            self.start_datum.day
        )


# ==========================================
# 2. REPOSITORY
# Speichert und lädt Daten aus SQLite
# ==========================================

class ModulRepository:
    def __init__(self, db_name="studium.db"):
        self.db_name = db_name
        self._db_initialisieren()

    # Erstellt Tabelle falls sie noch nicht existiert
    def _db_initialisieren(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS module (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                semester_nr INTEGER,
                name TEXT,
                ects INTEGER,
                status TEXT,
                note REAL
            )
        """)

        conn.commit()
        conn.close()

    # Speichert alle Module in die Datenbank
    def speichern(self, module_liste):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Alte Daten löschen damit nichts doppelt gespeichert wird
        cursor.execute("DELETE FROM module")

        for sem_nr, modul in module_liste:

            note = (
                modul.pruefungsleistung.note
                if modul.pruefungsleistung
                else None
            )

            cursor.execute("""
                INSERT INTO module
                (semester_nr, name, ects, status, note)
                VALUES (?, ?, ?, ?, ?)
            """, (
                sem_nr,
                modul.name,
                modul.ects,
                modul.status.value,
                note
            ))

        conn.commit()
        conn.close()

    # Lädt alle Module aus der Datenbank
    def laden(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT semester_nr, name, ects, status, note
            FROM module
        """)

        rows = cursor.fetchall()

        conn.close()

        module_liste = []

        for sem_nr, name, ects, status_text, note in rows:

            pruefungsleistung = (
                Pruefungsleistung(note)
                if note is not None
                else None
            )

            modul = Modul(
                name,
                ects,
                ModulStatus(status_text),
                pruefungsleistung
            )

            module_liste.append((sem_nr, modul))

        return module_liste


# ==========================================
# 3. SERVICE
# Fachliche Berechnungen
# ==========================================

class StudienService:

    # Berechnet bestandene ECTS
    def berechne_ects_ist(self, module_liste):
        summe = 0

        for _, modul in module_liste:

            if modul.status == ModulStatus.BESTANDEN:
                summe += modul.ects

        return summe

    # Berechnet Durchschnittsnote
    def berechne_notenschnitt(self, module_liste):
        noten = []

        for _, modul in module_liste:

            if (
                modul.status == ModulStatus.BESTANDEN
                and modul.pruefungsleistung
            ):
                noten.append(modul.pruefungsleistung.note)

        if not noten:
            return 0.0

        return round(mean(noten), 2)

    # Berechnet den Zeitfortschritt des Studiums
    def berechne_zeitfortschritt(self, studiengang):

        heute = date.today()

        gesamt_tage = (
            studiengang.end_datum
            - studiengang.start_datum
        ).days

        vergangene_tage = (
            heute
            - studiengang.start_datum
        ).days

        if vergangene_tage <= 0:
            return 0

        return min(
            round((vergangene_tage / gesamt_tage) * 100, 1),
            100
        )

    # Berechnet Studienfortschritt anhand ECTS
    def berechne_studienfortschritt(self, module_liste, ziel_ects):

        ects_ist = self.berechne_ects_ist(module_liste)

        return min(
            round((ects_ist / ziel_ects) * 100, 1),
            100
        )


# ==========================================
# 4. MANAGER / CONTROLLER
# Verbindet Model, Service und Datenbank
# ==========================================

class StudienManager:

    def __init__(self, studiengang, repository, service):

        self.studiengang = studiengang
        self.repository = repository
        self.service = service

        # Dictionary mit Semestern
        self.semester_liste = {}

    # Fügt ein Modul zu einem Semester hinzu
    def modul_hinzufuegen(self, semester_nr, modul):

        if semester_nr not in self.semester_liste:
            self.semester_liste[semester_nr] = Semester(semester_nr)

        self.semester_liste[semester_nr].module.append(modul)

    # Gibt alle Module sortiert zurück
    def alle_module_abrufen(self):

        liste = []

        for nr in sorted(self.semester_liste.keys()):

            for modul in self.semester_liste[nr].module:
                liste.append((nr, modul))

        return liste

    def berechne_ects_ist(self):
        return self.service.berechne_ects_ist(
            self.alle_module_abrufen()
        )

    def berechne_notenschnitt(self):
        return self.service.berechne_notenschnitt(
            self.alle_module_abrufen()
        )

    def berechne_zeitfortschritt(self):
        return self.service.berechne_zeitfortschritt(
            self.studiengang
        )

    def berechne_studienfortschritt(self):
        return self.service.berechne_studienfortschritt(
            self.alle_module_abrufen(),
            self.studiengang.ziel_ects
        )

    # Speichert Daten in SQLite
    def daten_speichern(self):
        self.repository.speichern(
            self.alle_module_abrufen()
        )

    # Lädt Daten aus SQLite
    def daten_laden(self):

        self.semester_liste.clear()

        for sem_nr, modul in self.repository.laden():
            self.modul_hinzufuegen(sem_nr, modul)


# ==========================================
# 5. VIEW
# GUI mit Tkinter
# ==========================================

class DashboardApp:

    def __init__(self, fenster, manager):

        self.fenster = fenster
        self.manager = manager

        self.fenster.title("Studien Dashboard")
        self.fenster.geometry("800x600")

        self._oberflaeche_erstellen()
        self.aktualisieren()

    # Baut die Oberfläche auf
    def _oberflaeche_erstellen(self):

        ttk.Label(
            self.fenster,
            text=f"Studiengang: {self.manager.studiengang.name}",
            font=("Arial", 14, "bold")
        ).pack(pady=10)

        # KPI Bereich
        kpi_frame = ttk.LabelFrame(
            self.fenster,
            text="Status & Ziele"
        )

        kpi_frame.pack(fill="x", padx=10, pady=5)

        self.label_ects = ttk.Label(kpi_frame, text="")
        self.label_ects.pack()

        self.label_note = ttk.Label(kpi_frame, text="")
        self.label_note.pack()

        # Fortschrittsbereich
        fort_frame = ttk.LabelFrame(
            self.fenster,
            text="Fortschritt"
        )

        fort_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(
            fort_frame,
            text="Zeitfortschritt:"
        ).pack()

        self.bar_zeit = ttk.Progressbar(
            fort_frame,
            length=400
        )

        self.bar_zeit.pack()

        ttk.Label(
            fort_frame,
            text="Studienfortschritt:"
        ).pack()

        self.bar_studium = ttk.Progressbar(
            fort_frame,
            length=400
        )

        self.bar_studium.pack()

        self.label_fazit = ttk.Label(
            fort_frame,
            font=("Arial", 12, "bold")
        )

        self.label_fazit.pack(pady=5)

        # Tabelle
        tab_frame = ttk.Frame(self.fenster)

        tab_frame.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=5
        )

        spalten = (
            "Semester",
            "Modul",
            "ECTS",
            "Status",
            "Note"
        )

        self.tabelle = ttk.Treeview(
            tab_frame,
            columns=spalten,
            show="headings"
        )

        for spalte in spalten:
            self.tabelle.heading(spalte, text=spalte)

        self.tabelle.pack(fill="both", expand=True)

        # Buttons
        btn_frame = ttk.Frame(self.fenster)
        btn_frame.pack(pady=10)

        ttk.Button(
            btn_frame,
            text="Neues Modul",
            command=self.neues_modul_fenster
        ).pack(side="left", padx=5)

        ttk.Button(
            btn_frame,
            text="Speichern",
            command=self.manager.daten_speichern
        ).pack(side="left", padx=5)

    # Aktualisiert Tabelle und Kennzahlen
    def aktualisieren(self):

        self.tabelle.delete(*self.tabelle.get_children())

        for nr, modul in self.manager.alle_module_abrufen():

            note = (
                modul.pruefungsleistung.note
                if modul.pruefungsleistung
                else "-"
            )

            self.tabelle.insert(
                "",
                "end",
                values=(
                    nr,
                    modul.name,
                    modul.ects,
                    modul.status.value,
                    note
                )
            )

        # Kennzahlen
        ects_ist = self.manager.berechne_ects_ist()

        ziel = self.manager.studiengang.ziel_ects

        self.label_ects.config(
            text=f"ECTS: {ects_ist} / {ziel}"
        )

        schnitt = self.manager.berechne_notenschnitt()

        self.label_note.config(
            text=f"Schnitt: {schnitt} "
                 f"(Ziel: {self.manager.studiengang.ziel_note})"
        )

        zeit = self.manager.berechne_zeitfortschritt()

        studienfortschritt = (
            self.manager.berechne_studienfortschritt()
        )

        self.bar_zeit["value"] = zeit
        self.bar_studium["value"] = studienfortschritt

        # Einfaches Fazit
        if studienfortschritt >= zeit:

            self.label_fazit.config(
                text="Du bist im Plan!",
                foreground="green"
            )

        else:

            self.label_fazit.config(
                text="Du bist im Verzug!",
                foreground="red"
            )

    # Popup zum Hinzufügen neuer Module
    def neues_modul_fenster(self):

        popup = tk.Toplevel(self.fenster)

        popup.title("Neues Modul")
        popup.geometry("300x320")

        ttk.Label(
            popup,
            text="Semester (Zahl):"
        ).pack()

        e_sem = ttk.Entry(popup)
        e_sem.pack()

        ttk.Label(
            popup,
            text="Modulname:"
        ).pack()

        e_name = ttk.Entry(popup)
        e_name.pack()

        ttk.Label(
            popup,
            text="ECTS:"
        ).pack()

        e_ects = ttk.Entry(popup)
        e_ects.insert(0, "5")
        e_ects.pack()

        ttk.Label(
            popup,
            text="Status:"
        ).pack()

        combo = ttk.Combobox(
            popup,
            values=[s.value for s in ModulStatus],
            state="readonly"
        )

        combo.current(0)
        combo.pack()

        ttk.Label(
            popup,
            text="Note (falls bestanden):"
        ).pack()

        e_note = ttk.Entry(popup)
        e_note.pack()

        # Speichert neues Modul
        def save():

            try:
                semester_nr = int(e_sem.get())

                name = e_name.get().strip()

                ects = int(e_ects.get())

                status = ModulStatus(combo.get())

                if not name:
                    raise ValueError("Modulname fehlt")

                pruefungsleistung = None

                if (
                    e_note.get()
                    and status == ModulStatus.BESTANDEN
                ):
                    pruefungsleistung = Pruefungsleistung(
                        float(e_note.get())
                    )

                modul = Modul(
                    name,
                    ects,
                    status,
                    pruefungsleistung
                )

                self.manager.modul_hinzufuegen(
                    semester_nr,
                    modul
                )

                self.manager.daten_speichern()

                self.aktualisieren()

                popup.destroy()

            except Exception:

                messagebox.showerror(
                    "Fehler",
                    "Prüfe deine Eingaben!"
                )

        ttk.Button(
            popup,
            text="Hinzufügen",
            command=save
        ).pack(pady=20)


# ==========================================
# 6. PROGRAMMSTART
# ==========================================

def main():

    # Studiengang anlegen
    studium = Studiengang(
        "Medizinische Informatik",
        date(2025, 10, 16)
    )

    repository = ModulRepository()

    service = StudienService()

    manager = StudienManager(
        studium,
        repository,
        service
    )

    manager.daten_laden()

    # Beispielmodul wenn DB leer
    if not manager.alle_module_abrufen():

        manager.modul_hinzufuegen(
            1,
            Modul(
                "Python Basis",
                5,
                ModulStatus.BESTANDEN,
                Pruefungsleistung(1.7)
            )
        )

        manager.daten_speichern()

    # GUI starten
    root = tk.Tk()

    app = DashboardApp(root, manager)

    root.mainloop()


if __name__ == "__main__":
    main()