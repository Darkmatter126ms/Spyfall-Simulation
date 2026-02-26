"""
Spyfall (single device) - 50 locations + per-location roles
- Fullscreen Tkinter UI: press & hold to reveal, release to hide.
- CLI fallback included.
Run: python spyfall.py
"""

import os
import sys
import time
import secrets

# 50 locations, each with a role pool
LOCATION_ROLES = {
    "Coal Mine": ["Miner", "Foreman", "Safety Inspector", "Geologist", "Equipment Mechanic", "Journalist"],
    "Library": ["Librarian", "Archivist", "Student", "Researcher", "Security Guard", "Book Club Member"],
    "Service Station": ["Attendant", "Cashier", "Mechanic", "Truck Driver", "Customer", "Manager"],
    "Bowling Alley": ["League Bowler", "Bartender", "Shoe Rental Clerk", "Manager", "Party Guest", "Maintenance Staff"],
    "Zoo": ["Zookeeper", "Veterinarian", "Ticket Seller", "Photographer", "Visitor", "Animal Researcher", "Monkey"],
    "Ocean Liner": ["Captain", "Cruise Director", "Bartender", "Tourist", "Chef", "Engineer"],

    "Theater": ["Actor", "Director", "Usher", "Stagehand", "Critic", "Ticket Clerk"],
    "Amusement Park": ["Ride Operator", "Mascot Performer", "Teen Guest", "Security Guard", "Vendor", "Manager"],
    "Restaurant": ["Chef", "Waiter", "Host", "Food Critic", "Dishwasher", "Customer"],
    "Passenger Train": ["Conductor", "Engineer", "Passenger", "Ticket Inspector", "Snack Vendor", "Rail Police"],
    "Art Gallery": ["Artist", "Curator", "Collector", "Security Guard", "Art Student", "Critic"],
    "Beach": ["Lifeguard", "Surfer", "Tourist", "Ice Cream Vendor", "Fisher", "Photographer"],

    "School": ["Teacher", "Student", "Principal", "Janitor", "School Nurse", "Parent"],
    "Space Station": ["Commander", "Engineer", "Scientist", "Doctor", "Pilot", "Tourist"],
    "Casino": ["Dealer", "Pit Boss", "Gambler", "Bartender", "Security Guard", "High Roller"],
    "Circus": ["Ringmaster", "Acrobat", "Clown", "Animal Trainer", "Ticket Taker", "Kid Visitor"],
    "Ice Hockey Stadium": ["Player", "Coach", "Referee", "Fan", "Vendor", "Security Guard"],
    "Movie Studio": ["Director", "Actor", "Camera Operator", "Producer", "Makeup Artist", "Stunt Coordinator"],

    "Vineyard": ["Winemaker", "Grape Picker", "Sommelier", "Tourist", "Owner", "Distributor"],
    "Police Station": ["Detective", "Patrol Officer", "Dispatcher", "Chief", "Journalist", "Suspect"],
    "Stadium": ["Athlete", "Coach", "Referee", "Fan", "Vendor", "Security Guard"],
    "Bank": ["Teller", "Manager", "Loan Officer", "Customer", "Security Guard", "Auditor"],
    "Supermarket": ["Cashier", "Stocker", "Manager", "Customer", "Security Guard", "Delivery Driver"],
    "Pirate Ship": ["Captain", "First Mate", "Deckhand", "Prisoner", "Navigator", "Cook"],

    "Polar Station": ["Scientist", "Engineer", "Doctor", "Cook", "Supply Officer", "Visitor"],
    "Military Base": ["Soldier", "Officer", "Mechanic", "Medic", "Cook", "Recruit", "Sergeant"],
    "Embassy": ["Ambassador", "Diplomat", "Security Guard", "Journalist", "Translator", "Visitor"],
    "Wedding": ["Bride/Groom", "Best Man", "Maid of Honor", "Officiant", "Photographer", "Guest"],
    "Hotel": ["Receptionist", "Housekeeper", "Concierge", "Guest", "Security Guard", "Chef"],
    "Submarine": ["Captain", "Sonar Operator", "Engineer", "Navigator", "Cook", "Diver"],

    "Taxi": ["Driver", "Passenger", "Dispatcher", "Tourist", "Mechanic", "Doorsman"],
    "Shopping Mall": ["Store Clerk", "Shopper", "Security Guard", "Cleaner", "Food Court Vendor", "Manager"],
    "Hospital": ["Doctor", "Nurse", "Surgeon", "Patient", "Pharmacist", "Administrator"],
    "Airplane": ["Pilot", "Flight Attendant", "Passenger", "Air Marshal", "Mechanic", "Co-pilot"],
    "University": ["Professor", "Student", "Researcher", "Librarian", "Dean", "Visitor"],
    "Spa": ["Massage Therapist", "Receptionist", "Client", "Manager", "Esthetician", "Cleaner"],
    
    "Fire Station": ["Firefighter", "Dispatcher", "Fire Chief", "EMT", "Fire Inspector", "Trainee"],
    "Prison": ["Warden", "Guard", "Inmate", "Lawyer", "Social Worker", "Parole Officer"],
    "Laboratory": ["Research Scientist", "Lab Technician", "Principal Investigator", "Safety Officer", "Intern", "Visitor"],
    "Nightclub": ["DJ", "Bouncer", "Bartender", "Clubber", "Manager", "Photographer","Bartender"],
    "Museum": ["Curator", "Tour Guide", "Security Guard", "Visitor", "Conservator", "Donor"],
    "Bakery": ["Baker", "Pastry Chef", "Cashier", "Customer", "Delivery Driver", "Owner"],
    "Construction Site": ["Site Manager", "Crane Operator", "Electrician", "Architect", "Inspector", "Laborer"],
    "Ferry Terminal": ["Ticket Agent", "Captain", "Commuter", "Dock Worker", "Security Guard", "Tourist"],
    "Ski Resort": ["Ski Instructor", "Lift Operator", "Snowboarder", "Resort Manager", "Medic", "Tourist"],
    "Mountain Cabin": ["Hiker", "Ranger", "Cabin Owner", "Lost Tourist", "Photographer", "Cook"],
    "Desert Camp": ["Guide", "Archaeologist", "Tourist", "Driver", "Camel Handler", "Medic"],
    "Aquarium": ["Aquarist", "Trainer", "Ticket Clerk", "Marine Biologist", "Visitor", "Security Guard"],
    "Gym": ["Trainer", "Member", "Receptionist", "Cleaner", "Nutrition Coach", "Manager"],
    "Courthouse": ["Judge", "Lawyer", "Defendant", "Juror", "Bailiff", "Clerk"],
}

ALL_LOCATIONS_SORTED = sorted(LOCATION_ROLES.keys())

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def _assign_non_spy_roles(location: str, non_spy_count: int):
    pool = list(LOCATION_ROLES[location])
    rng = secrets.SystemRandom()

    if non_spy_count <= len(pool):
        return rng.sample(pool, non_spy_count)  # unique roles
    # Need more roles than pool size -> allow duplicates
    roles = pool[:]
    while len(roles) < non_spy_count:
        roles.append(rng.choice(pool))
    rng.shuffle(roles)
    return roles


def deal_roles(player_names):
    rng = secrets.SystemRandom()
    location = rng.choice(list(LOCATION_ROLES.keys()))
    spy_idx = rng.randrange(len(player_names))

    non_spy_needed = len(player_names) - 1
    non_spy_roles = _assign_non_spy_roles(location, non_spy_needed)
    role_iter = iter(non_spy_roles)

    roles = []
    for i, name in enumerate(player_names):
        if i == spy_idx:
            roles.append((name, "SPY", None, None))
        else:
            r = next(role_iter)
            roles.append((name, "PLAYER", location, r))
    return location, spy_idx, roles


# ----------------------- GUI VERSION (recommended) ----------------------- #
def run_gui():
    try:
        import tkinter as tk
        from tkinter import simpledialog, messagebox
    except Exception:
        return False

    class SpyfallApp:
        def __init__(self, root):
            self.root = root
            self.root.title("Spyfall (Single Device)")
            self.root.configure(bg="black")
            self.root.attributes("-fullscreen", True)
            self.root.bind("<Escape>", lambda e: self.quit())

            n = simpledialog.askinteger("Spyfall", "Number of players? (3–20)", minvalue=3, maxvalue=20)
            if not n:
                self.quit()
                return

            use_names = messagebox.askyesno("Spyfall", "Enter player names?")
            if use_names:
                names = []
                for i in range(n):
                    nm = simpledialog.askstring("Player Name", f"Player {i+1} name:")
                    names.append((nm or f"Player {i+1}").strip())
                self.player_names = names
            else:
                self.player_names = [f"Player {i+1}" for i in range(n)]

            self.round_minutes = simpledialog.askinteger("Spyfall", "Round timer (minutes)?", minvalue=1, maxvalue=30)
            if not self.round_minutes:
                self.round_minutes = 8

            self.new_round()
            
            self.locations_overlay = None

            self.title_lbl = tk.Label(root, text="", fg="white", bg="black",
                                      font=("Helvetica", 36, "bold"))
            self.title_lbl.pack(pady=30)

            self.role_lbl = tk.Label(root, text="", fg="white", bg="black",
                                     font=("Helvetica", 48, "bold"),
                                     wraplength=1200, justify="center")
            self.role_lbl.pack(pady=20)

            self.instr_lbl = tk.Label(root, text="", fg="white", bg="black",
                                      font=("Helvetica", 20),
                                      wraplength=1200, justify="center")
            self.instr_lbl.pack(pady=10)

            self.reveal_btn = tk.Button(root, text="PRESS & HOLD TO REVEAL",
                                        font=("Helvetica", 28, "bold"),
                                        width=28, height=2)
            self.reveal_btn.pack(pady=30)
            self.reveal_btn.bind("<ButtonPress-1>", self.on_press_reveal)
            self.reveal_btn.bind("<ButtonRelease-1>", self.on_release_hide)

            self.next_btn = tk.Button(root, text="Next Player →",
                                      font=("Helvetica", 24, "bold"),
                                      width=16, height=2,
                                      command=self.next_player,
                                      state="disabled")
            self.next_btn.pack(pady=20)
            
            self.prev_btn = tk.Button(
                root, text="← Previous Player",
                font=("Helvetica", 24, "bold"),
                width=16, height=2,
                command=self.prev_player,
                state="disabled"
            )
            self.prev_btn.pack(pady=5)

            self.bottom_lbl = tk.Label(root, text="Esc to quit",
                                       fg="gray", bg="black",
                                       font=("Helvetica", 14))
            self.bottom_lbl.pack(side="bottom", pady=10)

            self.show_player_screen()

        def new_round(self):
            self.location, self.spy_idx, self.roles = deal_roles(self.player_names)
            self.idx = 0
            self.seen = [False] * len(self.roles)
            self.revealed_once = False
            self.timer_running = False
            self.timer_end = None

        def show_player_screen(self):
            if not self.reveal_btn.winfo_ismapped():
                self.reveal_btn.pack(pady=30)
            if not self.next_btn.winfo_ismapped():
                self.next_btn.pack(pady=20)
            if not self.prev_btn.winfo_ismapped():
                self.prev_btn.pack(pady=5)
            name, kind, loc, role = self.roles[self.idx]
            self.title_lbl.config(text=f"{name}'s turn")
            self.role_lbl.config(text="(hidden)")
            self.instr_lbl.config(text="Hold the button to view your info.\nRelease to hide, then pass the device.")
            self.next_btn.config(state="disabled")
            self.revealed_once = False
            if self.idx > 0 and self.seen[self.idx - 1]:
                self.prev_btn.config(state="normal")
            else:
                self.prev_btn.config(state="disabled")
            
            if self.seen[self.idx]:
                self.instr_lbl.config(
                    text="You may re-check your role.\nHold to reveal, release to hide."
                )

        def on_press_reveal(self, _event=None):
            name, kind, loc, role = self.roles[self.idx]
            if kind == "SPY":
                self.role_lbl.config(text="YOU ARE THE SPY 🕵️\n\nFind the location!")
            else:
                self.role_lbl.config(text=f"LOCATION:\n{loc}\n\nROLE:\n{role}")
            self.seen[self.idx] = True
            self.revealed_once = True

        def on_release_hide(self, _event=None):
            self.role_lbl.config(text="(hidden)")
            if self.revealed_once:
                self.next_btn.config(state="normal")

        def next_player(self):
            self.idx += 1
            if self.idx >= len(self.roles):
                self.show_post_deal_screen()
            else:
                self.show_player_screen()
        def prev_player(self):
            if self.idx > 0 and self.seen[self.idx - 1]:
                self.idx -= 1
                self.show_player_screen()

        def show_post_deal_screen(self):
            self.title_lbl.config(text="All roles dealt ✅")
            self.role_lbl.config(text="Start the round when ready.")
            self.instr_lbl.config(text="Timer is optional. (Only non-spies know the location.)")
            self.reveal_btn.pack_forget()
            self.next_btn.pack_forget()
            self.prev_btn.pack_forget()

            self.timer_lbl = tk.Label(self.root, text="", fg="white", bg="black",
                                      font=("Helvetica", 48, "bold"))
            self.timer_lbl.pack(pady=20)

            btn_frame = tk.Frame(self.root, bg="black")
            btn_frame.pack(pady=20)

            self.start_btn = tk.Button(btn_frame, text="Start Timer",
                                       font=("Helvetica", 22, "bold"),
                                       width=12, height=2, command=self.start_timer)
            self.start_btn.grid(row=0, column=0, padx=10)

            self.pause_btn = tk.Button(btn_frame, text="Pause",
                                       font=("Helvetica", 22, "bold"),
                                       width=12, height=2, command=self.pause_timer,
                                       state="disabled")
            self.pause_btn.grid(row=0, column=1, padx=10)

            self.new_btn = tk.Button(btn_frame, text="New Round",
                                     font=("Helvetica", 22, "bold"),
                                     width=12, height=2, command=self.restart_round)
            self.new_btn.grid(row=0, column=2, padx=10)

            self.update_timer_label(initial=True)

            self.locations_btn = tk.Button(
                self.root,
                text="HOLD: Locations List",
                font=("Helvetica", 22, "bold"),
                width=20, height=2
            )
            self.locations_btn.pack(pady=10)

            self.locations_btn.bind("<ButtonPress-1>", lambda e: self.open_locations_overlay())
            # backup close if release happens while still on the button
            self.locations_btn.bind("<ButtonRelease-1>", lambda e: self.close_locations_overlay())

        def start_timer(self):
            if self.timer_running:
                return
            self.timer_end = time.time() + self.round_minutes * 60
            self.timer_running = True
            self.start_btn.config(state="disabled")
            self.pause_btn.config(state="normal")
            self.tick()

        def pause_timer(self):
            if not self.timer_running:
                return
            remaining = max(0, int(self.timer_end - time.time()))
            self.timer_running = False
            self.timer_end = time.time() + remaining
            self.start_btn.config(text="Resume", state="normal", command=self.resume_timer)
            self.pause_btn.config(state="disabled")

        def resume_timer(self):
            if self.timer_running:
                return
            self.timer_running = True
            self.start_btn.config(state="disabled")
            self.pause_btn.config(state="normal")
            self.start_btn.config(text="Start Timer", command=self.start_timer)
            self.tick()

        def tick(self):
            self.update_timer_label()
            if not self.timer_running:
                return
            if time.time() >= self.timer_end:
                self.timer_running = False
                self.timer_lbl.config(text="TIME'S UP!")
                self.start_btn.config(state="disabled")
                self.pause_btn.config(state="disabled")
                return
            self.root.after(250, self.tick)

        def update_timer_label(self, initial=False):
            if initial or not self.timer_running:
                if self.timer_end is None:
                    remaining = self.round_minutes * 60
                else:
                    remaining = max(0, int(self.timer_end - time.time()))
            else:
                remaining = max(0, int(self.timer_end - time.time()))

            mm = remaining // 60
            ss = remaining % 60
            self.timer_lbl.config(text=f"{mm:02d}:{ss:02d}")
        def open_locations_overlay(self):
            import tkinter as tk

            if self.locations_overlay is not None:
                return  # already open

            top = tk.Toplevel(self.root)
            self.locations_overlay = top

            top.configure(bg="black")
            top.attributes("-fullscreen", True)
            top.lift()
            top.focus_force()

            # Close on release anywhere / Esc
            top.bind("<ButtonRelease-1>", lambda e: self.close_locations_overlay())
            top.bind("<Escape>", lambda e: self.close_locations_overlay())

            title = tk.Label(
                top,
                text="All Possible Locations (does NOT reveal the real one)",
                fg="white", bg="black",
                font=("Helvetica", 28, "bold")
            )
            title.pack(pady=18)

            hint = tk.Label(
                top,
                text="Hold to view • Release to hide • Esc to close",
                fg="gray", bg="black",
                font=("Helvetica", 16)
            )
            hint.pack(pady=4)

            # Scrollable list
            frame = tk.Frame(top, bg="black")
            frame.pack(fill="both", expand=True, padx=40, pady=20)

            scrollbar = tk.Scrollbar(frame)
            scrollbar.pack(side="right", fill="y")

            listbox = tk.Listbox(
                frame,
                font=("Helvetica", 22),
                yscrollcommand=scrollbar.set,
                height=20
            )
            listbox.pack(side="left", fill="both", expand=True)
            scrollbar.config(command=listbox.yview)

            for loc in ALL_LOCATIONS_SORTED:
                listbox.insert(tk.END, loc)

        def close_locations_overlay(self):
            if self.locations_overlay is None:
                return
            try:
                self.locations_overlay.destroy()
            finally:
                self.locations_overlay = None

        def restart_round(self):
            self.root.destroy()
            main()

        def quit(self):
            try:
                self.root.destroy()
            except Exception:
                pass
            sys.exit(0)

    def main():
        root = tk.Tk()
        SpyfallApp(root)
        root.mainloop()

    main()
    return True


# ----------------------- CLI FALLBACK VERSION ----------------------- #
def run_cli():
    clear_screen()
    print("Spyfall (CLI fallback) - with roles\n")

    while True:
        try:
            n = int(input("Number of players (3–20): ").strip())
            if not (3 <= n <= 20):
                raise ValueError
            break
        except ValueError:
            print("Please enter an integer between 3 and 20.")

    use_names = input("Enter player names? (y/n): ").strip().lower().startswith("y")
    if use_names:
        player_names = []
        for i in range(n):
            nm = input(f"Player {i+1} name: ").strip()
            player_names.append(nm or f"Player {i+1}")
    else:
        player_names = [f"Player {i+1}" for i in range(n)]

    _, _, roles = deal_roles(player_names)

    for i, (name, kind, loc, role) in enumerate(roles, start=1):
        clear_screen()
        print(f"{name}'s turn ({i}/{n})")
        print("Pass the device to this player.")
        input("\nPress Enter to REVEAL...")
        clear_screen()

        if kind == "SPY":
            print("YOU ARE THE SPY 🕵️")
            print("Try to figure out the location!")
        else:
            print(f"LOCATION: {loc}")
            print(f"ROLE:     {role}")

        input("\nMemorize it. Press Enter to HIDE and pass device...")
        clear_screen()
        print("\n" * 60)

    clear_screen()
    print("All roles dealt ✅ Start asking questions!\n")
    input("Press Enter to exit.")


def main():
    ok = run_gui()
    if not ok:
        run_cli()


if __name__ == "__main__":
    main()
