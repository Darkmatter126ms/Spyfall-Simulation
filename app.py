"""
Spyfall – Multiplayer Web Edition
Backend: Flask + Flask-SocketIO
Players join via room code on their own devices.
"""

import csv
import secrets
import string
import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates",
)
app.config["SECRET_KEY"] = secrets.token_hex(32)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ---------------------------------------------------------------------------
# Location data – loaded once from CSV
# ---------------------------------------------------------------------------
LOCATIONS_CSV = Path(__file__).parent / "locations.csv"


def load_locations(csv_path: Path) -> dict[str, list[str]]:
    """Load location→roles mapping from a CSV file."""
    location_roles: dict[str, list[str]] = {}
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            location = row["location"].strip()
            roles = [r.strip() for r in row["roles"].split(",") if r.strip()]
            # Deduplicate roles (fixes the original Nightclub duplicate)
            seen = set()
            unique_roles = []
            for r in roles:
                if r not in seen:
                    seen.add(r)
                    unique_roles.append(r)
            location_roles[location] = unique_roles
    return location_roles


LOCATION_ROLES = load_locations(LOCATIONS_CSV)
ALL_LOCATIONS_SORTED = sorted(LOCATION_ROLES.keys())
logger.info("Loaded %d locations from %s", len(LOCATION_ROLES), LOCATIONS_CSV)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
RNG = secrets.SystemRandom()


def _generate_room_code() -> str:
    """6-character uppercase room code."""
    return "".join(RNG.choices(string.ascii_uppercase + string.digits, k=6))


@dataclass
class Player:
    sid: str
    name: str
    is_host: bool = False
    role: Optional[str] = None       # "SPY" or an actual role name
    location: Optional[str] = None   # None for spy
    notes: dict = field(default_factory=dict)        # {player_name: "note text"}
    eliminated_locations: list = field(default_factory=list)  # spy's scratch-off list
    vote_target: Optional[str] = None
    connected: bool = True


@dataclass
class GameRoom:
    code: str
    host_sid: str
    players: dict = field(default_factory=dict)  # sid → Player
    phase: str = "lobby"  # lobby | playing | voting | defense | revote | spy_guess | round_end
    location: Optional[str] = None
    spy_sid: Optional[str] = None
    round_minutes: int = 8
    timer_end: Optional[float] = None
    timer_paused_remaining: Optional[int] = None
    votes: dict = field(default_factory=dict)  # voter_name → target_name
    spy_guesses_remaining: int = 2
    spy_guess_result: Optional[str] = None
    round_number: int = 0
    # Tiebreaker fields
    tied_suspects: list = field(default_factory=list)    # names of tied players
    defense_timer_end: Optional[float] = None
    defense_timer_paused_remaining: Optional[int] = None
    revote_votes: dict = field(default_factory=dict)     # voter_name → target_name (revote only)

    def player_names(self) -> list[str]:
        return [p.name for p in self.players.values() if p.connected]

    def player_by_name(self, name: str) -> Optional[Player]:
        for p in self.players.values():
            if p.name == name:
                return p
        return None

    def connected_count(self) -> int:
        return sum(1 for p in self.players.values() if p.connected)


# Active rooms: code → GameRoom
rooms: dict[str, GameRoom] = {}
# Reverse lookup: sid → room_code
sid_to_room: dict[str, str] = {}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assign_roles(location: str, non_spy_count: int) -> list[str]:
    pool = list(LOCATION_ROLES[location])
    if non_spy_count <= len(pool):
        return RNG.sample(pool, non_spy_count)
    roles = pool[:]
    while len(roles) < non_spy_count:
        roles.append(RNG.choice(pool))
    RNG.shuffle(roles)
    return roles


def _deal_round(room: GameRoom):
    """Deal a new round: pick location, pick spy, assign roles."""
    room.round_number += 1
    room.location = RNG.choice(list(LOCATION_ROLES.keys()))
    connected = [p for p in room.players.values() if p.connected]
    spy = RNG.choice(connected)
    room.spy_sid = spy.sid

    non_spies = [p for p in connected if p.sid != spy.sid]
    roles = _assign_roles(room.location, len(non_spies))

    for p in connected:
        p.vote_target = None
        p.eliminated_locations = []
        # Preserve notes across rounds if desired, or clear:
        # p.notes = {}

    spy.role = "SPY"
    spy.location = None

    for p, role in zip(non_spies, roles):
        p.role = role
        p.location = room.location

    room.phase = "playing"
    room.votes = {}
    room.spy_guesses_remaining = 2
    room.spy_guess_result = None
    room.timer_end = None
    room.timer_paused_remaining = None
    room.tied_suspects = []
    room.defense_timer_end = None
    room.defense_timer_paused_remaining = None
    room.revote_votes = {}


_broadcast_seq = 0

def _broadcast_game_state(room: GameRoom):
    """Notify all clients in the room to fetch their personalized state."""
    global _broadcast_seq
    _broadcast_seq += 1
    logger.info("Broadcasting state seq=%d phase=%s to room %s", _broadcast_seq, room.phase, room.code)

    # Send a lightweight trigger to all clients in the room
    socketio.emit("state_updated", {"seq": _broadcast_seq}, room=room.code)


def _get_player_state(room: GameRoom, p, seq: int) -> dict:
    """Build personalized state for a single player."""
    player_list = [
        {"name": pl.name, "isHost": pl.is_host, "connected": pl.connected}
        for pl in room.players.values()
    ]
    state = {
        "seq": seq,
        "roomCode": room.code,
        "phase": room.phase,
        "players": player_list,
        "roundNumber": room.round_number,
        "roundMinutes": room.round_minutes,
        "timerEnd": room.timer_end,
        "timerPausedRemaining": room.timer_paused_remaining,
        "isHost": p.is_host,
        "myName": p.name,
    }

    if room.phase in ("playing", "voting", "defense", "revote", "spy_guess", "round_end"):
        state["isSpy"] = (p.sid == room.spy_sid)
        state["allLocations"] = ALL_LOCATIONS_SORTED
        state["eliminatedLocations"] = p.eliminated_locations

        if p.sid == room.spy_sid:
            state["role"] = "SPY"
            state["location"] = None
        else:
            state["role"] = p.role
            state["location"] = p.location

        state["notes"] = p.notes

    if room.phase == "voting":
        state["votedPlayers"] = list(room.votes.keys())
        state["myVote"] = p.vote_target

    if room.phase == "defense":
        state["tiedSuspects"] = room.tied_suspects
        state["isSuspect"] = p.name in room.tied_suspects
        state["defenseTimerEnd"] = room.defense_timer_end
        state["defenseTimerPausedRemaining"] = room.defense_timer_paused_remaining
        state["firstRoundVotes"] = room.votes

    if room.phase == "revote":
        state["tiedSuspects"] = room.tied_suspects
        state["isSuspect"] = p.name in room.tied_suspects
        state["canRevote"] = p.name not in room.tied_suspects
        state["revoteVotedPlayers"] = list(room.revote_votes.keys())
        state["myRevote"] = room.revote_votes.get(p.name)

    if room.phase == "spy_guess":
        state["spyGuessesRemaining"] = room.spy_guesses_remaining
        if p.sid == room.spy_sid:
            state["canGuess"] = True
        else:
            state["canGuess"] = False

    if room.phase == "round_end":
        spy_player = room.players.get(room.spy_sid)
        state["spyName"] = spy_player.name if spy_player else "Unknown"
        state["actualLocation"] = room.location
        state["spyGuessResult"] = room.spy_guess_result
        state["votes"] = room.votes

    return state


@socketio.on("request_state")
def on_request_state():
    """Client requests its personalized state."""
    from flask import request
    sid = request.sid
    code = sid_to_room.get(sid)
    if not code or code not in rooms:
        return
    room = rooms[code]
    if sid not in room.players:
        return
    p = room.players[sid]
    state = _get_player_state(room, p, _broadcast_seq)
    emit("game_state", state)


def _check_all_voted(room: GameRoom):
    """Check if all connected players have voted."""
    connected_names = {p.name for p in room.players.values() if p.connected}
    voted_names = set(room.votes.keys())
    logger.info("Vote check: connected=%s, voted=%s", connected_names, voted_names)
    return connected_names == voted_names


# ---------------------------------------------------------------------------
# Socket.IO event handlers
# ---------------------------------------------------------------------------

@socketio.on("connect")
def on_connect():
    logger.info("Client connected: %s", getattr(emit, 'sid', 'unknown'))


@socketio.on("disconnect")
def on_disconnect():
    from flask import request
    sid = request.sid
    code = sid_to_room.pop(sid, None)
    if code and code in rooms:
        room = rooms[code]
        if sid in room.players:
            room.players[sid].connected = False
            logger.info("Player %s disconnected from room %s",
                        room.players[sid].name, code)
            # If host disconnects, promote someone
            if room.host_sid == sid:
                for p in room.players.values():
                    if p.connected and p.sid != sid:
                        p.is_host = True
                        room.host_sid = p.sid
                        logger.info("Promoted %s to host in room %s", p.name, code)
                        break
            _broadcast_game_state(room)
            # Clean up empty rooms
            if room.connected_count() == 0:
                del rooms[code]
                logger.info("Room %s deleted (empty)", code)


@socketio.on("create_room")
def on_create_room(data):
    from flask import request
    sid = request.sid
    name = (data.get("name") or "").strip()
    if not name:
        emit("error", {"message": "Please enter your name."})
        return

    code = _generate_room_code()
    while code in rooms:
        code = _generate_room_code()

    player = Player(sid=sid, name=name, is_host=True)
    room = GameRoom(code=code, host_sid=sid)
    room.players[sid] = player

    rooms[code] = room
    sid_to_room[sid] = code
    join_room(code)

    logger.info("Room %s created by %s", code, name)
    _broadcast_game_state(room)


@socketio.on("join_room")
def on_join_room(data):
    from flask import request
    sid = request.sid
    name = (data.get("name") or "").strip()
    code = (data.get("code") or "").strip().upper()

    if not name:
        emit("error", {"message": "Please enter your name."})
        return
    if code not in rooms:
        emit("error", {"message": f"Room '{code}' not found."})
        return

    room = rooms[code]

    if room.phase != "lobby":
        # Allow reconnect if name matches a disconnected player
        existing = room.player_by_name(name)
        if existing and not existing.connected:
            # Reconnect
            old_sid = existing.sid
            del room.players[old_sid]
            existing.sid = sid
            existing.connected = True
            room.players[sid] = existing
            sid_to_room[sid] = code
            join_room(code)
            if old_sid == room.host_sid:
                room.host_sid = sid
            logger.info("Player %s reconnected to room %s", name, code)
            _broadcast_game_state(room)
            return
        else:
            emit("error", {"message": "Game already in progress. Cannot join."})
            return

    # Check duplicate names
    for p in room.players.values():
        if p.name.lower() == name.lower() and p.connected:
            emit("error", {"message": f"Name '{name}' is already taken."})
            return

    player = Player(sid=sid, name=name)
    room.players[sid] = player
    sid_to_room[sid] = code
    join_room(code)

    logger.info("Player %s joined room %s", name, code)
    _broadcast_game_state(room)


@socketio.on("start_game")
def on_start_game(data):
    from flask import request
    sid = request.sid
    code = sid_to_room.get(sid)
    if not code or code not in rooms:
        return

    room = rooms[code]
    if sid != room.host_sid:
        emit("error", {"message": "Only the host can start the game."})
        return

    connected = room.connected_count()
    if connected < 3:
        emit("error", {"message": "Need at least 3 players to start."})
        return

    minutes = data.get("minutes")
    if minutes and isinstance(minutes, (int, float)) and 1 <= minutes <= 30:
        room.round_minutes = int(minutes)

    _deal_round(room)
    logger.info("Round %d started in room %s (location: %s)",
                room.round_number, code, room.location)
    _broadcast_game_state(room)


@socketio.on("start_timer")
def on_start_timer():
    from flask import request
    sid = request.sid
    code = sid_to_room.get(sid)
    if not code or code not in rooms:
        return
    room = rooms[code]
    if sid != room.host_sid:
        return

    import time
    if room.timer_paused_remaining is not None:
        room.timer_end = time.time() + room.timer_paused_remaining
        room.timer_paused_remaining = None
    else:
        room.timer_end = time.time() + room.round_minutes * 60

    _broadcast_game_state(room)


@socketio.on("pause_timer")
def on_pause_timer():
    from flask import request
    sid = request.sid
    code = sid_to_room.get(sid)
    if not code or code not in rooms:
        return
    room = rooms[code]
    if sid != room.host_sid:
        return

    import time
    if room.timer_end:
        remaining = max(0, int(room.timer_end - time.time()))
        room.timer_paused_remaining = remaining
        room.timer_end = None
    _broadcast_game_state(room)


@socketio.on("update_notes")
def on_update_notes(data):
    from flask import request
    sid = request.sid
    code = sid_to_room.get(sid)
    if not code or code not in rooms:
        return
    room = rooms[code]
    if sid not in room.players:
        return

    target_name = data.get("targetName", "")
    note_text = data.get("noteText", "")
    room.players[sid].notes[target_name] = note_text


@socketio.on("toggle_location")
def on_toggle_location(data):
    """Spy toggles a location as eliminated/not eliminated."""
    from flask import request
    sid = request.sid
    code = sid_to_room.get(sid)
    if not code or code not in rooms:
        return
    room = rooms[code]
    if sid not in room.players:
        return

    loc = data.get("location", "")
    player = room.players[sid]
    if loc in player.eliminated_locations:
        player.eliminated_locations.remove(loc)
    else:
        player.eliminated_locations.append(loc)

    # Only send back to this player (lightweight)
    emit("location_toggled", {"eliminatedLocations": player.eliminated_locations})


@socketio.on("call_vote")
def on_call_vote():
    """Host initiates a vote."""
    from flask import request
    sid = request.sid
    code = sid_to_room.get(sid)
    if not code or code not in rooms:
        return
    room = rooms[code]
    if sid != room.host_sid:
        emit("error", {"message": "Only the host can call a vote."})
        return
    if room.phase != "playing":
        return

    room.phase = "voting"
    room.votes = {}
    for p in room.players.values():
        p.vote_target = None
    _broadcast_game_state(room)


@socketio.on("cast_vote")
def on_cast_vote(data):
    from flask import request
    sid = request.sid
    code = sid_to_room.get(sid)
    if not code or code not in rooms:
        return
    room = rooms[code]
    if room.phase != "voting":
        return
    if sid not in room.players:
        return

    target = data.get("target", "")
    voter = room.players[sid]
    voter.vote_target = target
    room.votes[voter.name] = target
    logger.info("Vote cast: %s -> %s (room %s, phase %s)", voter.name, target, code, room.phase)

    # If everyone has voted, resolve immediately (do NOT broadcast voting state first,
    # as that causes a race where the client receives voting-state after defense-state)
    if _check_all_voted(room):
        _resolve_vote(room)
    else:
        _broadcast_game_state(room)


@socketio.on("cancel_vote")
def on_cancel_vote():
    """Host cancels the vote and returns to playing."""
    from flask import request
    sid = request.sid
    code = sid_to_room.get(sid)
    if not code or code not in rooms:
        return
    room = rooms[code]
    if sid != room.host_sid:
        return
    if room.phase != "voting":
        return

    room.phase = "playing"
    room.votes = {}
    for p in room.players.values():
        p.vote_target = None
    _broadcast_game_state(room)


@socketio.on("start_defense_timer")
def on_start_defense_timer():
    from flask import request
    import time
    sid = request.sid
    code = sid_to_room.get(sid)
    if not code or code not in rooms:
        return
    room = rooms[code]
    if sid != room.host_sid or room.phase != "defense":
        return

    if room.defense_timer_paused_remaining is not None:
        room.defense_timer_end = time.time() + room.defense_timer_paused_remaining
        room.defense_timer_paused_remaining = None
    else:
        room.defense_timer_end = time.time() + 30 * len(room.tied_suspects)
    _broadcast_game_state(room)


@socketio.on("pause_defense_timer")
def on_pause_defense_timer():
    from flask import request
    import time
    sid = request.sid
    code = sid_to_room.get(sid)
    if not code or code not in rooms:
        return
    room = rooms[code]
    if sid != room.host_sid or room.phase != "defense":
        return

    if room.defense_timer_end:
        remaining = max(0, int(room.defense_timer_end - time.time()))
        room.defense_timer_paused_remaining = remaining
        room.defense_timer_end = None
    _broadcast_game_state(room)


@socketio.on("proceed_to_revote")
def on_proceed_to_revote():
    """Host moves from defense phase to revote phase."""
    from flask import request
    sid = request.sid
    code = sid_to_room.get(sid)
    if not code or code not in rooms:
        return
    room = rooms[code]
    if sid != room.host_sid:
        return
    if room.phase != "defense":
        return

    room.phase = "revote"
    room.revote_votes = {}
    _broadcast_game_state(room)


@socketio.on("cast_revote")
def on_cast_revote(data):
    from flask import request
    sid = request.sid
    code = sid_to_room.get(sid)
    if not code or code not in rooms:
        return
    room = rooms[code]
    if room.phase != "revote":
        return
    if sid not in room.players:
        return

    voter = room.players[sid]
    # Suspects cannot vote in revote
    if voter.name in room.tied_suspects:
        emit("error", {"message": "Suspects cannot vote in the revote."})
        return

    target = data.get("target", "")
    # Can only vote for suspects
    if target not in room.tied_suspects:
        emit("error", {"message": "You can only vote for the suspects."})
        return

    room.revote_votes[voter.name] = target

    # If all eligible voters have voted, resolve immediately
    eligible = {p.name for p in room.players.values()
                if p.connected and p.name not in room.tied_suspects}
    if eligible == set(room.revote_votes.keys()):
        _resolve_revote(room)
    else:
        _broadcast_game_state(room)


def _resolve_vote(room: GameRoom):
    """Tally votes and determine outcome."""
    from collections import Counter
    tally = Counter(room.votes.values())
    logger.info("Resolving vote in room %s: tally=%s", room.code, dict(tally))
    if not tally:
        room.phase = "playing"
        _broadcast_game_state(room)
        return

    top_count = tally.most_common(1)[0][1]
    tied = [name for name, count in tally.items() if count == top_count]

    if len(tied) > 1:
        # Check how many non-suspect voters would be available for a revote
        connected_names = {p.name for p in room.players.values() if p.connected}
        eligible_revoters = connected_names - set(tied)

        if len(eligible_revoters) == 0:
            # No one left to revote → back to playing
            room.phase = "playing"
            socketio.emit("vote_result", {
                "result": "tie",
                "message": "It's a tie and no one is left to break it! Back to discussion."
            }, room=room.code)
            room.votes = {}
            _broadcast_game_state(room)
            return

        # There are eligible revoters → enter defense phase
        logger.info("Tie detected in room %s: suspects=%s, eligible_revoters=%s → entering defense",
                     room.code, tied, eligible_revoters)
        room.phase = "defense"
        room.tied_suspects = tied
        room.defense_timer_end = None
        room.defense_timer_paused_remaining = None
        room.revote_votes = {}
        _broadcast_game_state(room)
        return

    # Clear winner — single player accused
    top_name = tied[0]
    _check_accusation(room, top_name)


def _resolve_revote(room: GameRoom):
    """Tally revote and determine outcome. Tie on revote = spy wins."""
    from collections import Counter
    tally = Counter(room.revote_votes.values())
    if not tally:
        room.phase = "playing"
        _broadcast_game_state(room)
        return

    top_count = tally.most_common(1)[0][1]
    tied = [name for name, count in tally.items() if count == top_count]

    if len(tied) > 1:
        # Tie on revote → spy wins
        room.phase = "round_end"
        room.spy_guess_result = "spy_wins_revote_tie"
        _broadcast_game_state(room)
        return

    # Clear winner from revote
    top_name = tied[0]
    _check_accusation(room, top_name)


def _check_accusation(room: GameRoom, accused_name: str):
    """Given a single accused player, check if they are the spy."""
    spy_player = room.players.get(room.spy_sid)
    if spy_player and accused_name == spy_player.name:
        # Players caught the spy — spy gets 2 guesses
        room.phase = "spy_guess"
        room.spy_guesses_remaining = 2
        _broadcast_game_state(room)
    else:
        # Wrong person — spy wins
        room.phase = "round_end"
        room.spy_guess_result = "spy_wins_wrong_vote"
        _broadcast_game_state(room)


@socketio.on("spy_guess")
def on_spy_guess(data):
    from flask import request
    sid = request.sid
    code = sid_to_room.get(sid)
    if not code or code not in rooms:
        return
    room = rooms[code]
    if room.phase != "spy_guess":
        return
    if sid != room.spy_sid:
        emit("error", {"message": "Only the spy can guess."})
        return

    guess = data.get("location", "")
    room.spy_guesses_remaining -= 1

    if guess == room.location:
        room.phase = "round_end"
        room.spy_guess_result = "spy_wins_correct_guess"
        _broadcast_game_state(room)
    elif room.spy_guesses_remaining <= 0:
        room.phase = "round_end"
        room.spy_guess_result = "players_win"
        _broadcast_game_state(room)
    else:
        # Wrong guess, but still has attempts
        emit("guess_result", {
            "correct": False,
            "remaining": room.spy_guesses_remaining,
            "message": f"'{guess}' is wrong! You have {room.spy_guesses_remaining} guess(es) left."
        })
        _broadcast_game_state(room)


@socketio.on("new_round")
def on_new_round():
    from flask import request
    sid = request.sid
    code = sid_to_room.get(sid)
    if not code or code not in rooms:
        return
    room = rooms[code]
    if sid != room.host_sid:
        emit("error", {"message": "Only the host can start a new round."})
        return

    _deal_round(room)
    logger.info("Round %d started in room %s", room.round_number, code)
    _broadcast_game_state(room)


@socketio.on("return_to_lobby")
def on_return_to_lobby():
    from flask import request
    sid = request.sid
    code = sid_to_room.get(sid)
    if not code or code not in rooms:
        return
    room = rooms[code]
    if sid != room.host_sid:
        return

    room.phase = "lobby"
    room.round_number = 0
    for p in room.players.values():
        p.role = None
        p.location = None
        p.notes = {}
        p.eliminated_locations = []
        p.vote_target = None
    _broadcast_game_state(room)


@socketio.on("kick_player")
def on_kick_player(data):
    """Host kicks a player from the room."""
    from flask import request
    sid = request.sid
    code = sid_to_room.get(sid)
    if not code or code not in rooms:
        return
    room = rooms[code]
    if sid != room.host_sid:
        emit("error", {"message": "Only the host can kick players."})
        return

    target_name = data.get("name", "")
    target = room.player_by_name(target_name)
    if not target:
        return
    # Host cannot kick themselves
    if target.sid == room.host_sid:
        emit("error", {"message": "You can't kick yourself."})
        return

    # Notify kicked player before removing
    socketio.emit("kicked", {
        "message": "You have been removed from the room by the host."
    }, room=target.sid)

    # Clean up
    target_sid = target.sid
    sid_to_room.pop(target_sid, None)
    del room.players[target_sid]
    leave_room(code, sid=target_sid)

    logger.info("Player %s kicked from room %s by host", target_name, code)

    # If we kicked the spy mid-game, end the round
    if room.phase in ("playing", "voting", "spy_guess") and target_sid == room.spy_sid:
        room.phase = "round_end"
        room.spy_guess_result = "spy_kicked"

    _broadcast_game_state(room)


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return {"status": "ok", "rooms": len(rooms)}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info("Starting Spyfall on port %d", port)
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)
