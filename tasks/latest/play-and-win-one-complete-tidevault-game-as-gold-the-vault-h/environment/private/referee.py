#!/usr/bin/env python3
"""Root-owned referee for one immutable live Tidevault game."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import stat
import struct
import sys
from typing import Optional

PRIVATE_DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(PRIVATE_DIRECTORY))

import core  # noqa: E402
import model as tidevault_model  # noqa: E402
import search as tidevault_search  # noqa: E402


MAXIMUM_REQUEST_BYTES = 8192
MAXIMUM_RESPONSE_BYTES = 4 * 1024 * 1024
REQUEST_DEADLINE_SECONDS = 5.0
RESPONSE_DEADLINE_SECONDS = 5.0
AGENT_UID = 65534
SUPPORTED_PROFILE = "beam-rank-lapse-v1"


class RefereeError(RuntimeError):
    """Report a startup or internal referee invariant failure."""


class OpponentTimeout(TimeoutError):
    """Stop one protected search that exceeds the frozen move ceiling."""


@dataclass(frozen=True)
class Settings:
    """Frozen public opponent tuple and protected asset identity."""

    model_path: Path
    model_id: str
    model_sha256: str
    dataset_sha256: str
    node_budget: int
    width: int
    max_depth: int
    seed: int
    selection_profile: str
    root_temperature_milli: int
    root_rank_lapse_permille: int
    move_time_limit_ms: int


@dataclass(frozen=True)
class ActionRecord:
    """One immutable accepted placement or resignation record."""

    record: int
    actor: str
    color: str
    action: Optional[str]
    placed_slot: Optional[str]
    settled_slot: Optional[str]
    state_hash_before: str
    state_hash_after: str
    tide: Optional[core.Tide]


def lowercase_sha256(value: str) -> bool:
    """Return whether value is exactly one lowercase SHA-256 digest."""

    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def file_sha256(path: Path) -> str:
    """Hash one regular protected file without following a symlink."""

    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or path.is_symlink():
        raise RefereeError("protected checkpoint is not a regular file")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(65536):
            digest.update(block)
    return digest.hexdigest()


def safe_message(message: str) -> str:
    """Return a bounded single-line ASCII public error message."""

    folded = " ".join(str(message).split())
    return folded.encode("ascii", "replace").decode("ascii")[:240] or "request failed"


def spoke_object(spoke: core.SpokeScore) -> dict[str, object]:
    """Return one exact public spoke-comparison object."""

    return {
        "sector": spoke.sector,
        "gold_weight": spoke.gold_weight,
        "violet_weight": spoke.violet_weight,
        "point_owner": spoke.point_owner,
    }


def tide_object(tide: core.Tide) -> dict[str, object]:
    """Return one exact public tide-scoring object."""

    return {
        "tide": tide.tide,
        "ply": tide.ply,
        "gold_points": tide.gold_points,
        "violet_points": tide.violet_points,
        "spokes": [spoke_object(spoke) for spoke in tide.spokes],
    }


def board_objects(state: core.State) -> list[dict[str, object]]:
    """Return all eighteen public board cells in canonical ring-major order."""

    values: list[dict[str, object]] = []
    sector_count = len(core.SECTORS)
    for index, stone in enumerate(state.board):
        ring = core.RINGS[index // sector_count]
        sector = core.SECTORS[index % sector_count]
        values.append(
            {
                "slot": f"{ring}{sector}",
                "ring": ring,
                "sector": sector,
                "occupant": None if stone is None else stone.owner,
                "power": None if stone is None else stone.power,
            }
        )
    return values


def record_object(record: ActionRecord) -> dict[str, object]:
    """Return one exact public transcript record."""

    return {
        "record": record.record,
        "actor": record.actor,
        "color": record.color,
        "action": record.action,
        "placed_slot": record.placed_slot,
        "settled_slot": record.settled_slot,
        "state_hash_before": record.state_hash_before,
        "state_hash_after": record.state_hash_after,
        "tide": tide_object(record.tide) if record.tide is not None else None,
    }


def inventory_object(values: tuple[int, int, int]) -> dict[str, int]:
    """Return a power-named inventory object in canonical order."""

    return {"P1": values[0], "P2": values[1], "P3": values[2]}


def checkpoint_identity(checkpoint: object) -> tuple[str, str]:
    """Extract the mandatory model and dataset identities from one checkpoint."""

    model_id = getattr(checkpoint, "model_id", None)
    dataset_sha256 = getattr(checkpoint, "dataset_sha256", None)
    if not isinstance(model_id, str) or not isinstance(dataset_sha256, str):
        raise RefereeError("protected checkpoint identity fields are missing")
    return model_id, dataset_sha256


def load_checkpoint(settings: Settings) -> object:
    """Load and independently attest the protected runtime checkpoint."""

    if file_sha256(settings.model_path) != settings.model_sha256:
        raise RefereeError("protected checkpoint digest differs from settings")
    loader = getattr(tidevault_model, "load_checkpoint", None)
    if loader is None:
        checkpoint_class = getattr(tidevault_model, "LinearCheckpoint", None)
        loader = getattr(checkpoint_class, "load", None)
    if loader is None:
        raise RefereeError("checkpoint loader is unavailable")
    checkpoint = loader(str(settings.model_path))
    model_id, dataset_sha256 = checkpoint_identity(checkpoint)
    if model_id != settings.model_id or dataset_sha256 != settings.dataset_sha256:
        raise RefereeError("protected checkpoint identity differs from settings")
    return checkpoint


class ArenaGame:
    """Own the native position, protected opponent, and append-only transcript."""

    def __init__(self, settings: Settings, checkpoint: object) -> None:
        self.settings = settings
        self.checkpoint = checkpoint
        self.state = core.initial_state()
        self.transcript: list[ActionRecord] = []
        self.gold_resigned = False
        self.postgame_player_requests = 0
        core.validate_state(self.state)

    @property
    def finished(self) -> bool:
        """Return whether native play or the public resignation overlay ended play."""

        return self.gold_resigned or self.state.terminal

    def observe_request(self, peer_uid: int) -> None:
        """Count every participant connection begun after a terminal result."""

        if self.finished and peer_uid == AGENT_UID:
            self.postgame_player_requests += 1

    def result_fields(self) -> tuple[str, Optional[str], Optional[str]]:
        """Return public result fields including the resignation overlay."""

        if self.gold_resigned:
            return "violet_win", "violet", "resignation"
        return self.state.result, self.state.winner, self.state.termination

    def public_state(self, include_history: bool = False) -> dict[str, object]:
        """Build the complete exact public state object."""

        result, winner, termination = self.result_fields()
        previous_action = (
            core.format_action(self.state.moves[-1].action)
            if self.state.moves
            else None
        )
        legal_actions = (
            []
            if self.finished
            else [core.format_action(action) for action in core.legal_actions(self.state)]
        )
        state: dict[str, object] = {
            "protocol": core.PROTOCOL,
            "ruleset": core.RULESET,
            "rings": list(core.RINGS),
            "sectors": list(core.SECTORS),
            "player_color": "gold",
            "opponent_model_id": self.settings.model_id,
            "opponent_model_sha256": self.settings.model_sha256,
            "opponent_dataset_sha256": self.settings.dataset_sha256,
            "opponent_node_budget": self.settings.node_budget,
            "opponent_search_width": self.settings.width,
            "opponent_max_depth": self.settings.max_depth,
            "opponent_seed": self.settings.seed,
            "opponent_selection_profile": self.settings.selection_profile,
            "opponent_root_temperature_milli": self.settings.root_temperature_milli,
            "opponent_root_rank_lapse_permille": self.settings.root_rank_lapse_permille,
            "opponent_move_time_limit_ms": self.settings.move_time_limit_ms,
            "turn": self.state.turn,
            "result": result,
            "winner": winner,
            "termination": termination,
            "ply_count": self.state.ply,
            "previous_action": previous_action,
            "gold_score": self.state.gold_score,
            "violet_score": self.state.violet_score,
            "gold_inventory": inventory_object(self.state.gold_inventory),
            "violet_inventory": inventory_object(self.state.violet_inventory),
            "board": board_objects(self.state),
            "tide_history": [tide_object(tide) for tide in self.state.tides],
            "legal_actions": legal_actions,
            "postgame_player_requests": self.postgame_player_requests,
            "state_hash": core.state_hash(self.state),
            "latest_record": (
                record_object(self.transcript[-1]) if self.transcript else None
            ),
        }
        if include_history:
            state["actions"] = [record_object(record) for record in self.transcript]
        return state

    def success(self, include_history: bool = False) -> dict[str, object]:
        """Return one successful state response with `ok` first."""

        return {"ok": True, **self.public_state(include_history)}

    def rejection(self, code: str, message: str) -> dict[str, object]:
        """Return one exact rejection envelope and unchanged snapshot."""

        return {
            "ok": False,
            "error": {"code": code, "message": safe_message(message)},
            "state": self.public_state(False),
        }

    def append_action(
        self,
        record_number: int,
        actor: str,
        color: str,
        action: core.Action,
        before_state: core.State,
        after_state: core.State,
    ) -> ActionRecord:
        """Construct one placement record from the newly appended native move."""

        move = after_state.moves[-1]
        new_tide = (
            after_state.tides[-1]
            if len(after_state.tides) == len(before_state.tides) + 1
            else None
        )
        return ActionRecord(
            record=record_number,
            actor=actor,
            color=color,
            action=core.format_action(action),
            placed_slot=move.placed_slot,
            settled_slot=move.settled_slot,
            state_hash_before=core.state_hash(before_state),
            state_hash_after=core.state_hash(after_state),
            tide=new_tide,
        )

    def choose_opponent(self, state: core.State) -> core.Action:
        """Run one deterministic protected search under the frozen wall ceiling."""

        if state.turn != "violet" or state.terminal:
            raise RefereeError("opponent search received the wrong state")

        def alarm_handler(signum: int, frame: object) -> None:
            del signum, frame
            raise OpponentTimeout("protected opponent exceeded its move ceiling")

        old_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, alarm_handler)
        signal.setitimer(signal.ITIMER_REAL, self.settings.move_time_limit_ms / 1000.0)
        try:
            chooser = getattr(tidevault_search, "choose_action", None)
            if chooser is None:
                raise RefereeError("protected search entrypoint is unavailable")
            config = tidevault_search.SearchConfig(
                node_budget=self.settings.node_budget,
                width=self.settings.width,
                max_depth=self.settings.max_depth,
                seed=self.settings.seed,
                selection_profile=self.settings.selection_profile,
                root_rank_lapse_permille=self.settings.root_rank_lapse_permille,
                root_temperature_milli=self.settings.root_temperature_milli,
            )
            selected = chooser(state, self.checkpoint, config)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            signal.signal(signal.SIGALRM, old_handler)
        if isinstance(selected, str):
            selected = core.parse_action(selected)
        if not isinstance(selected, core.Action) or not core.is_legal(state, selected):
            raise RefereeError("protected opponent returned an illegal action")
        return selected

    def move(self, fields: list[str]) -> dict[str, object]:
        """Apply one atomic Gold placement plus the required Violet reply."""

        if len(fields) != 5:
            return self.rejection(
                "bad_request",
                "move requires POWER SLOT ROTATION_RING DIRECTION",
            )
        if self.finished:
            return self.rejection("game_over", "the game has already ended")
        if self.state.turn != "gold":
            return self.rejection("wrong_turn", "the opponent reply is still pending")
        try:
            player_action = core.action_from_parts(*fields[1:])
        except (TypeError, ValueError):
            return self.rejection(
                "invalid_action",
                "use a canonical action such as P2 IA M CW",
            )
        if not core.is_legal(self.state, player_action):
            return self.rejection("illegal_action", "that placement is not legal now")

        before_state = self.state
        try:
            player_state = core.apply_action(before_state, player_action)
        except ValueError:
            return self.rejection("illegal_action", "that placement is not legal now")
        player_record = self.append_action(
            len(self.transcript) + 1,
            "player",
            "gold",
            player_action,
            before_state,
            player_state,
        )
        if player_state.terminal:
            self.state = player_state
            self.transcript.append(player_record)
            return self.success()

        try:
            opponent_action = self.choose_opponent(player_state)
            opponent_state = core.apply_action(player_state, opponent_action)
        except (Exception, KeyboardInterrupt) as error:
            if isinstance(error, KeyboardInterrupt):
                raise
            return self.rejection(
                "internal_error",
                "the opponent could not complete its reply",
            )
        opponent_record = self.append_action(
            len(self.transcript) + 2,
            "opponent",
            "violet",
            opponent_action,
            player_state,
            opponent_state,
        )
        self.state = opponent_state
        self.transcript.extend((player_record, opponent_record))
        return self.success()

    def resign(self, fields: list[str]) -> dict[str, object]:
        """Add the terminal resignation overlay without changing native state."""

        if len(fields) != 1:
            return self.rejection("bad_request", "resign takes no arguments")
        if self.finished:
            return self.rejection("game_over", "the game has already ended")
        if self.state.turn != "gold":
            return self.rejection("wrong_turn", "the opponent reply is still pending")
        digest = core.state_hash(self.state)
        self.gold_resigned = True
        self.transcript.append(
            ActionRecord(
                record=len(self.transcript) + 1,
                actor="player",
                color="gold",
                action=None,
                placed_slot=None,
                settled_slot=None,
                state_hash_before=digest,
                state_hash_after=digest,
                tide=None,
            )
        )
        return self.success()

    def handle(self, fields: list[str]) -> dict[str, object]:
        """Dispatch one parsed request without exposing mutable internals."""

        if not fields or not fields[0]:
            return self.rejection("bad_request", "request must name a command")
        command = fields[0]
        if command == "ping":
            if len(fields) != 1:
                return self.rejection("bad_request", "ping takes no arguments")
            return {"ok": True, "ready": True}
        if command in {"status", "transcript"}:
            if len(fields) != 1:
                return self.rejection("bad_request", f"{command} takes no arguments")
            return self.success(command == "transcript")
        if command == "move":
            return self.move(fields)
        if command == "resign":
            return self.resign(fields)
        return self.rejection(
            "unknown_command",
            "supported commands are status, move, transcript, resign, and ping",
        )


def parse_request(payload: bytes) -> list[str]:
    """Parse one complete bounded ASCII request or raise a public framing error."""

    if not payload or len(payload) > MAXIMUM_REQUEST_BYTES:
        raise ValueError("request must be one complete text line")
    try:
        text = payload.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("request must be ASCII") from error
    if "\x00" in text or not text.endswith("\n") or text.count("\n") != 1:
        raise ValueError("request must be one complete text line")
    line = text[:-1]
    if line.endswith("\r"):
        line = line[:-1]
    if "\r" in line or not line:
        raise ValueError("request must be one complete text line")
    if "\t" in line:
        fields = line.split("\t")
        if any(not field or field != field.strip() for field in fields):
            raise ValueError("tab-separated request fields must be nonempty")
        return fields
    return line.split()


def peer_uid(connection: socket.socket) -> int:
    """Read the Linux peer UID or return an untrusted sentinel."""

    option = getattr(socket, "SO_PEERCRED", None)
    if option is None:
        return -1
    try:
        credentials = connection.getsockopt(socket.SOL_SOCKET, option, 12)
        _, uid, _ = struct.unpack("3i", credentials)
        return uid
    except (OSError, struct.error):
        return -1


def receive_request(connection: socket.socket) -> tuple[Optional[bytes], str]:
    """Read to EOF under one deadline and classify framing failures."""

    connection.settimeout(REQUEST_DEADLINE_SECONDS)
    payload = bytearray()
    oversized = False
    try:
        while True:
            block = connection.recv(1024)
            if not block:
                break
            payload.extend(block)
            if len(payload) > MAXIMUM_REQUEST_BYTES:
                oversized = True
                break
    except TimeoutError:
        return None, "request deadline exceeded"
    except OSError:
        return None, "request transport failed"
    if oversized:
        return None, "request exceeds 8192 bytes"
    return bytes(payload), ""


def encode_response(document: dict[str, object]) -> bytes:
    """Encode one bounded deterministic ASCII JSON response."""

    payload = (
        json.dumps(document, ensure_ascii=True, separators=(",", ":")) + "\n"
    ).encode("ascii")
    if len(payload) > MAXIMUM_RESPONSE_BYTES:
        raise RefereeError("public response exceeds size limit")
    return payload


def serve(socket_path: Path, game: ArenaGame) -> None:
    """Serve one sequential immutable arena until the container exits."""

    if not socket_path.is_absolute() or len(os.fsencode(socket_path)) >= 100:
        raise RefereeError("arena socket path is invalid")
    socket_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    try:
        socket_path.unlink()
    except FileNotFoundError:
        pass
    channel = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        channel.bind(str(socket_path))
        os.chmod(socket_path, 0o666)
        channel.listen(16)
        while True:
            connection, _ = channel.accept()
            with connection:
                game.observe_request(peer_uid(connection))
                payload, transport_error = receive_request(connection)
                if payload is None:
                    code = (
                        "request_too_large"
                        if transport_error == "request exceeds 8192 bytes"
                        else "bad_request"
                    )
                    document = game.rejection(code, transport_error)
                else:
                    try:
                        fields = parse_request(payload)
                        document = game.handle(fields)
                    except ValueError as error:
                        document = game.rejection("bad_request", str(error))
                    except Exception:
                        document = game.rejection(
                            "internal_error",
                            "referee failed to complete the request",
                        )
                try:
                    connection.settimeout(RESPONSE_DEADLINE_SECONDS)
                    connection.sendall(encode_response(document))
                except (OSError, TimeoutError):
                    pass
    finally:
        channel.close()
        try:
            socket_path.unlink()
        except FileNotFoundError:
            pass


def positive_integer(value: str) -> int:
    """Parse one positive decimal command-line setting."""

    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return number


def parse_arguments() -> tuple[Path, Settings]:
    """Parse and validate the complete frozen runtime tuple."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--dataset-sha256", required=True)
    parser.add_argument("--node-budget", type=positive_integer, required=True)
    parser.add_argument("--width", type=positive_integer, required=True)
    parser.add_argument("--max-depth", type=positive_integer, required=True)
    parser.add_argument("--seed", type=positive_integer, required=True)
    parser.add_argument("--selection-profile", required=True)
    parser.add_argument("--root-temperature-milli", type=int, required=True)
    parser.add_argument("--root-rank-lapse-permille", type=int, required=True)
    parser.add_argument("--move-time-limit-ms", type=positive_integer, required=True)
    options = parser.parse_args()
    settings = Settings(
        model_path=options.model,
        model_id=options.model_id,
        model_sha256=options.model_sha256,
        dataset_sha256=options.dataset_sha256,
        node_budget=options.node_budget,
        width=options.width,
        max_depth=options.max_depth,
        seed=options.seed,
        selection_profile=options.selection_profile,
        root_temperature_milli=options.root_temperature_milli,
        root_rank_lapse_permille=options.root_rank_lapse_permille,
        move_time_limit_ms=options.move_time_limit_ms,
    )
    if (
        not options.socket.is_absolute()
        or not settings.model_path.is_absolute()
        or not settings.model_id
        or not lowercase_sha256(settings.model_sha256)
        or not lowercase_sha256(settings.dataset_sha256)
        or settings.node_budget > 1_000_000
        or settings.width > 324
        or settings.max_depth > core.PLY_LIMIT
        or settings.selection_profile != SUPPORTED_PROFILE
        or settings.root_temperature_milli != 0
        or not 0 <= settings.root_rank_lapse_permille <= 1000
        or settings.move_time_limit_ms > 20_000
    ):
        raise RefereeError("frozen opponent settings are invalid")
    return options.socket, settings


def main() -> int:
    """Start the protected opponent and serve the live arena."""

    try:
        socket_path, settings = parse_arguments()
        checkpoint = load_checkpoint(settings)
        serve(socket_path, ArenaGame(settings, checkpoint))
        return 0
    except (OSError, ValueError, RefereeError) as error:
        print(f"Tidevault referee failed: {safe_message(str(error))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
