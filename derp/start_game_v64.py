from __future__ import annotations

import configparser
import curses
import os
import random
import string
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional

try:
    import FASEmsfx as audio
except Exception:
    audio = None

from FASEclass import Role
from FASEgg import make_immortal, unique_imrt_path, write_imrt
from FASEimm import VALID_ALIGNMENTS, VALID_DOMAINS, load_imrt_file
from FASE import (
    FEMALE_FIRST_NAMES, MALE_FIRST_NAMES, SURNAMES, TRAITS, REGION_COUNT, Simulator,
    ENDGAME_POPULATION_FLOOR, ENDGAME_INFLUENCE_LOSS_THRESHOLD,
    ENDGAME_INFLUENCE_WIN_THRESHOLD, ENDGAME_MAJORITY_CONTROL_THRESHOLD,
)
from FASEcfg import (
    PLAYER_LESSER_RELIC_LIMIT, PLAYER_GREATER_RELIC_LIMIT, LESSER_RELIC_SOUL_COST,
    HISTORIAN_ENABLED, EVENT_MEMORY_LIMIT, HISTORIAN_SUMMARY_EVENT_LIMIT,
)
from FASErg import valid_templates_for_role, BOON_DEFS as RELIC_BOON_DEFS, build_relic_payload, relic_limit_text
from FASEhelp import get_help_lines

DATA_DIR = Path(__file__).resolve().parent
BASE_DIR = DATA_DIR.parent
GODS_DIR = BASE_DIR / "MCE"
UX_SCRIPT = BASE_DIR / "FASEux.py"

STARTING_SOULS = 300
SKIP_CHAMPION_SOUL_BONUS = 100
BACK = "__BACK__"
STARTING_CHAMPION_STAT_POOL = 24
STARTING_CHAMPION_BASE_STAT = 10
STARTING_CHAMPION_MAX_STAT = 20
STARTING_CHAMPION_MIN_STAT = 6

def audio_init() -> None:
    if audio is None:
        return
    try:
        audio.init_audio()
    except Exception:
        pass

def play_intro_music() -> None:
    if audio is None:
        return
    try:
        audio.play_intro_music()
    except Exception:
        pass

def play_sfx(name: str) -> None:
    if audio is None:
        return
    try:
        audio.play_sfx(name)
    except Exception:
        pass

def stop_music() -> None:
    if audio is None:
        return
    try:
        audio.stop_music()
    except Exception:
        pass

ASCII_SPLASH = r"""
 ____________________________________________________________________________________________________________
|░█▀▀░█▀█░█▀█░▀█▀░█▀█░█▀▀░█░█░░░░█▀█░█▀█░▀█▀░█▀▀░█▀█░█▀▄░█▄█                                                 |
|░█▀▀░█▀█░█░█░░█░░█▀█░▀▀█░░█░░░░░█▀█░█░█░░█░░█▀▀░█▀█░█▀▄░█░█                                                 |
|░▀░░░▀░▀░▀░▀░░▀░░▀░▀░▀▀▀░░▀░▀▀▀░▀░▀░▀░▀░░▀░░▀░░░▀░▀░▀░▀░▀░▀ PRESENTS                                        |
|                                                                                                            |
|       ▄█    ▄▄▄▄███▄▄▄▄     ▄▄▄▄███▄▄▄▄    ▄██████▄     ▄████████     ███        ▄████████  ▄█             |
|      ███  ▄██▀▀▀███▀▀▀██▄ ▄██▀▀▀███▀▀▀██▄ ███    ███   ███    ███ ▀█████████▄   ███    ███ ███             |
|      ███▌ ███   ███   ███ ███   ███   ███ ███    ███   ███    ███    ▀███▀▀██   ███    ███ ███             |
|      ███▌ ███   ███   ███ ███   ███   ███ ███    ███  ▄███▄▄▄▄██▀     ███   ▀   ███    ███ ███             |
|      ███▌ ███   ███   ███ ███   ███   ███ ███    ███ ▀▀███▀▀▀▀▀       ███     ▀███████████ ███             |
|      ███  ███   ███   ███ ███   ███   ███ ███    ███ ▀███████████     ███       ███    ███ ███             |
|      ███  ███   ███   ███ ███   ███   ███ ███    ███   ███    ███     ███       ███    ███ ███▌    ▄       |
|      █▀    ▀█   ███   █▀   ▀█   ███   █▀   ▀██████▀    ███    ███    ▄████▀     ███    █▀  █████▄▄██       |
|                                                        ███    ███                          ▀               |
|  ▄████████    ▄█    █▄       ▄████████   ▄▄▄▄███▄▄▄▄      ▄███████▄  ▄█   ▄██████▄  ███▄▄▄▄      ▄████████ |
| ███    ███   ███    ███     ███    ███ ▄██▀▀▀███▀▀▀██▄   ███    ███ ███  ███    ███ ███▀▀▀██▄   ███    ███ |
| ███    █▀    ███    ███     ███    ███ ███   ███   ███   ███    ███ ███▌ ███    ███ ███   ███   ███    █▀  |
| ███         ▄███▄▄▄▄███▄▄   ███    ███ ███   ███   ███   ███    ███ ███▌ ███    ███ ███   ███   ███        |
| ███        ▀▀███▀▀▀▀███▀  ▀███████████ ███   ███   ███ ▀█████████▀  ███▌ ███    ███ ███   ███ ▀███████████ |
| ███    █▄    ███    ███     ███    ███ ███   ███   ███   ███        ███  ███    ███ ███   ███          ███ |
| ███    ███   ███    ███     ███    ███ ███   ███   ███   ███        ███  ███    ███ ███   ███    ▄█    ███ |
| ████████▀    ███    █▀      ███    █▀   ▀█   ███   █▀   ▄████▀      █▀    ▀██████▀   ▀█   █▀   ▄████████▀  |
|__________________________________________________________________________________________________v0.98_____|
"""

def safe_add(stdscr, y: int, x: int, text: str, attr: int = 0) -> None:
    h, w = stdscr.getmaxyx()
    if y < 0 or y >= h or x >= w:
        return
    try:
        stdscr.addstr(y, max(0, x), str(text)[: max(0, w - x - 1)], attr)
    except curses.error:
        pass


def center_add(stdscr, y: int, text: str, attr: int = 0) -> None:
    _, w = stdscr.getmaxyx()
    safe_add(stdscr, y, max(0, (w - len(str(text))) // 2), str(text), attr)


def pause_message(stdscr, lines: Iterable[str]) -> None:
    stdscr.clear()
    h, _ = stdscr.getmaxyx()
    lines = list(lines)
    start_y = max(0, h // 2 - len(lines) // 2)
    for i, line in enumerate(lines):
        center_add(stdscr, start_y + i, line, curses.A_BOLD if i == 0 else 0)
    center_add(stdscr, start_y + len(lines) + 2, "Press any key.")
    stdscr.refresh()
    stdscr.getch()
    play_sfx("ui_click")


def launcher_help_menu(stdscr) -> None:
    """Scrollable launcher copy of the UX help/reference screen."""
    scroll = 0
    old_nodelay = False
    try:
        stdscr.nodelay(False)
    except Exception:
        pass
    lines = get_help_lines(
        win_majority=ENDGAME_MAJORITY_CONTROL_THRESHOLD,
        divine_pct=ENDGAME_INFLUENCE_WIN_THRESHOLD,
        defeat_pct=ENDGAME_INFLUENCE_LOSS_THRESHOLD,
        pop_floor=ENDGAME_POPULATION_FLOOR,
    )
    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        panel_w = min(w - 4, 104) if w >= 8 else max(1, w - 1)
        panel_h = min(h - 4, 30) if h >= 8 else max(1, h - 1)
        left = max(0, (w - panel_w) // 2)
        top = max(0, (h - panel_h) // 2)
        border = "=" * max(1, panel_w - 1)
        body_top = top + 3
        body_bottom = top + panel_h - 2
        visible_rows = max(1, body_bottom - body_top)
        max_scroll = max(0, len(lines) - visible_rows)
        scroll = max(0, min(scroll, max_scroll))
        safe_add(stdscr, top, left, border, curses.A_BOLD)
        safe_add(stdscr, top + 1, left + 2, "HELP / GAMEPLAY", curses.A_BOLD)
        safe_add(stdscr, top + 2, left, "-" * max(1, panel_w - 1), curses.A_BOLD)
        y = body_top
        for line in lines[scroll:scroll + visible_rows]:
            safe_add(stdscr, y, left + 2, str(line)[:panel_w - 5])
            y += 1
        footer = "H/Esc close | Up/Down scroll | PgUp/PgDn page | Home/End"
        safe_add(stdscr, top + panel_h - 1, left, border, curses.A_BOLD)
        safe_add(stdscr, min(h - 1, top + panel_h), left + 2, footer[:max(1, panel_w - 5)])
        stdscr.refresh()
        key = stdscr.getch()
        if key != -1:
            play_sfx("ui_click")
        if key in (ord('h'), ord('H'), 27, ord('q'), ord('Q'), 10, 13, curses.KEY_ENTER):
            return
        if key in (curses.KEY_UP, ord('k')):
            scroll = max(0, scroll - 1)
        elif key in (curses.KEY_DOWN, ord('j')):
            scroll += 1
        elif key == curses.KEY_PPAGE:
            scroll = max(0, scroll - 12)
        elif key == curses.KEY_NPAGE:
            scroll += 12
        elif key == curses.KEY_HOME:
            scroll = 0
        elif key == curses.KEY_END:
            scroll = max_scroll
        elif key == curses.KEY_MOUSE:
            try:
                _id, _mx, _my, _z, bstate = curses.getmouse()
                wheel_up = bstate & getattr(curses, "BUTTON4_PRESSED", 0)
                wheel_down = bstate & getattr(curses, "BUTTON5_PRESSED", 0)
                if wheel_up or wheel_down:
                    scroll = max(0, scroll + (-3 if wheel_up else 3))
            except Exception:
                pass

def splash_screen(stdscr) -> None:
    try:
        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    except Exception:
        pass
    stdscr.nodelay(False)
    stdscr.clear()
    lines = [line.rstrip() for line in ASCII_SPLASH.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    h, w = stdscr.getmaxyx()
    block_height = len(lines) + 3
    start_y = max(0, (h - block_height) // 2)
    for i, line in enumerate(lines):
        if start_y + i >= h - 3:
            break
        safe_add(stdscr, start_y + i, max(0, (w - len(line)) // 2), line)
    center_add(stdscr, min(h - 2, start_y + len(lines) + 2), "Press any key or click to start", curses.A_BOLD)
    stdscr.refresh()
    stdscr.getch()
    play_sfx("ui_click")


def prompt_text(stdscr, prompt: str, default: str = "", allow_blank: bool = True, allow_back: bool = False):
    curses.echo()
    curses.curs_set(1)
    try:
        while True:
            stdscr.clear()
            h, w = stdscr.getmaxyx()
            box_w = min(72, max(30, w - 8))
            x = max(0, (w - box_w) // 2)
            y = max(0, h // 2 - 3)
            title = prompt + ("  (B back)" if allow_back else "")
            center_add(stdscr, y, title, curses.A_BOLD)
            if default:
                center_add(stdscr, y + 1, f"Default: {default}")
            safe_add(stdscr, y + 3, x, "> ")
            stdscr.refresh()
            raw = stdscr.getstr(y + 3, x + 2, max(1, box_w - 4)).decode(errors="ignore").strip()
            play_sfx("ui_click")
            if allow_back and raw.strip().lower() in {"b", "back"}:
                return BACK
            if raw or allow_blank:
                return raw or default
    finally:
        curses.noecho()
        curses.curs_set(0)


def choose_from_list(
    stdscr,
    title: str,
    options: Iterable[str],
    max_select: int = 1,
    allow_done: bool = False,
    allow_cancel: bool = True,
    disabled_options: Optional[Iterable[str]] = None,
    allow_back: bool = False,
) -> list[str]:
    options = [str(opt) for opt in options]
    disabled = {str(opt) for opt in (disabled_options or [])}
    if not options:
        return []
    selected: list[str] = []
    idx = 0
    top = 0

    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        controls = "Enter/Space toggle | arrows scroll | h help"
        if allow_back:
            controls += " | b back"
        if allow_cancel:
            controls += " | q cancel"
        if allow_done:
            controls += " | d done"

        center_add(stdscr, 1, title, curses.A_BOLD)
        center_add(stdscr, 2, controls)

        visible = max(1, min(len(options), h - 8))
        if idx < top:
            top = idx
        elif idx >= top + visible:
            top = idx - visible + 1

        rendered = []
        for actual, opt in enumerate(options[top: top + visible], start=top):
            cursor = ">" if actual == idx else " "
            disabled_mark = " -" if opt in disabled else "  "
            mark = "[x]" if opt in selected else "[ ]"
            rendered.append((actual, f"{cursor} {mark}{disabled_mark} {opt}"))

        menu_w = min(max((len(line) for _, line in rendered), default=20), max(20, w - 8))
        menu_x = max(0, (w - menu_w) // 2)
        start_y = max(4, (h - visible) // 2)

        for row_offset, (actual, line) in enumerate(rendered):
            opt = options[actual]
            attr = curses.A_REVERSE if actual == idx else 0
            if opt in disabled:
                attr |= curses.A_DIM
            safe_add(stdscr, start_y + row_offset, menu_x, line[:menu_w], attr)

        if top > 0:
            center_add(stdscr, start_y - 1, "↑")
        if top + visible < len(options):
            center_add(stdscr, start_y + visible, "↓")

        footer = f"Selected {len(selected)}/{max_select}: {', '.join(selected) or '-'}"
        center_add(stdscr, h - 2, footer)
        stdscr.refresh()
        key = stdscr.getch()
        if key != -1:
            play_sfx("ui_click")

        if key in (ord('h'), ord('H')):
            launcher_help_menu(stdscr)
            continue
        if key == curses.KEY_MOUSE:
            try:
                _, _mx, my, _z, _state = curses.getmouse()
                if start_y <= my < start_y + visible:
                    idx = min(len(options) - 1, top + my - start_y)
                    key = 10
            except Exception:
                continue
        if key in (curses.KEY_UP, ord('k')):
            idx = (idx - 1) % len(options)
        elif key in (curses.KEY_DOWN, ord('j')):
            idx = (idx + 1) % len(options)
        elif key in (curses.KEY_NPAGE,):
            idx = min(len(options) - 1, idx + visible)
        elif key in (curses.KEY_PPAGE,):
            idx = max(0, idx - visible)
        elif key in (10, 13, 32):
            opt = options[idx]
            if opt in disabled:
                continue
            if opt in selected:
                selected.remove(opt)
            elif len(selected) < max_select:
                selected.append(opt)
            if len(selected) == max_select and not allow_done:
                return selected
        elif key in (ord('d'), ord('D')) and allow_done and selected:
            return selected
        elif key in (ord('b'), ord('B')) and allow_back:
            return [BACK]
        elif key in (ord('q'), ord('Q'), 27) and allow_cancel:
            return selected if selected else []



def is_back(value) -> bool:
    return value == BACK or value == [BACK] or (isinstance(value, (list, tuple)) and len(value) == 1 and value[0] == BACK)

def yes_no(stdscr, prompt: str, default: bool = True, allow_cancel: bool = False, allow_back: bool = False):
    suffix = "[Y/n]" if default else "[y/N]"
    suffix += " | H help"
    if allow_back:
        suffix += " | B back"
    if allow_cancel:
        suffix += " | Esc/q cancel"
    while True:
        stdscr.clear()
        h, _ = stdscr.getmaxyx()
        center_add(stdscr, max(0, h // 2 - 1), f"{prompt} {suffix}", curses.A_BOLD)
        center_add(stdscr, max(0, h // 2 + 1), "Enter accepts default")
        stdscr.refresh()
        key = stdscr.getch()
        if key != -1:
            play_sfx("ui_click")
        if key in (ord('h'), ord('H')):
            launcher_help_menu(stdscr)
            continue
        if key in (10, 13):
            return default
        if key in (ord('y'), ord('Y')):
            return True
        if key in (ord('n'), ord('N')):
            return False
        if allow_back and key in (ord('b'), ord('B')):
            return BACK
        if allow_cancel and key in (ord('q'), ord('Q'), 27):
            return None


def random_seed_string(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(max(4, int(length))))


def _runtime_default_options() -> dict:
    seed = random_seed_string()
    return {
        "seed_mode": "random",
        "seed": seed,
        "summaries_enabled": True,
        "psum": 1,
        "csv_enabled": True,
        "historian_enabled": bool(HISTORIAN_ENABLED),
        "historian_event_limit": int(HISTORIAN_SUMMARY_EVENT_LIMIT),
        "event_memory_limit": int(EVENT_MEMORY_LIMIT),
    }


def _runtime_option_lines(opts: dict) -> list[str]:
    seed_label = f"{opts.get('seed')} ({opts.get('seed_mode', 'random')})"
    summary_label = "off" if not opts.get("summaries_enabled", True) or int(opts.get("psum", 0) or 0) <= 0 else f"every {int(opts.get('psum', 1))} year(s)"
    return [
        "Done - continue setup",
        f"Seed: {seed_label}",
        f"Periodic summaries: {summary_label}",
        f"CSV metrics/events/history: {'on' if opts.get('csv_enabled', True) else 'off'}",
        f"Historian SQLite tome: {'on' if opts.get('historian_enabled', True) else 'off'}",
        f"Historian summary event limit: {int(opts.get('historian_event_limit', 0) or 0)}",
        f"Recent event memory limit: {int(opts.get('event_memory_limit', 0) or 0)}",
        "Back",
    ]


def _prompt_int(stdscr, prompt: str, default: int, minimum: int = 0) -> int:
    while True:
        raw = prompt_text(stdscr, prompt, default=str(default), allow_blank=True)
        try:
            return max(minimum, int(str(raw).strip()))
        except Exception:
            pause_message(stdscr, ["Invalid number.", f"Enter an integer >= {minimum}."])


def configure_runtime_options(stdscr, existing: Optional[dict] = None):
    opts = dict(existing or _runtime_default_options())
    while True:
        picked = choose_from_list(
            stdscr,
            "Runtime options",
            _runtime_option_lines(opts),
            1,
            allow_cancel=False,
            allow_back=False,
        )
        if not picked:
            continue
        item = picked[0]
        if item.startswith("Done"):
            return opts
        if item == "Back":
            return BACK
        if item.startswith("Seed:"):
            choice = choose_from_list(
                stdscr,
                f"Seed setup — current random seed: {opts.get('seed')}",
                ["Use shown random seed", "Generate another random seed", "Enter seed manually", "Back"],
                1,
                allow_cancel=False,
            )
            if not choice or choice[0] == "Back":
                continue
            if choice[0].startswith("Use shown"):
                opts["seed_mode"] = "random"
            elif choice[0].startswith("Generate"):
                opts["seed"] = random_seed_string()
                opts["seed_mode"] = "random"
            else:
                manual = prompt_text(stdscr, "Enter seed", default=str(opts.get("seed") or random_seed_string()), allow_blank=False)
                opts["seed"] = manual
                opts["seed_mode"] = "manual"
        elif item.startswith("Periodic summaries"):
            enabled = yes_no(stdscr, "Enable periodic text summaries?", bool(opts.get("summaries_enabled", True)), allow_cancel=False, allow_back=True)
            if enabled == BACK:
                continue
            opts["summaries_enabled"] = bool(enabled)
            if opts["summaries_enabled"]:
                pick = choose_from_list(stdscr, "Summary interval", ["1 year", "5 years", "10 years", "Custom", "Back"], 1, allow_cancel=False)
                if not pick or pick[0] == "Back":
                    continue
                if pick[0].startswith("1"):
                    opts["psum"] = 1
                elif pick[0].startswith("5"):
                    opts["psum"] = 5
                elif pick[0].startswith("10"):
                    opts["psum"] = 10
                else:
                    opts["psum"] = _prompt_int(stdscr, "Write summary every how many years? 0 disables.", int(opts.get("psum", 1) or 1), minimum=0)
            else:
                opts["psum"] = 0
        elif item.startswith("CSV"):
            opts["csv_enabled"] = not bool(opts.get("csv_enabled", True))
        elif item.startswith("Historian SQLite"):
            opts["historian_enabled"] = not bool(opts.get("historian_enabled", True))
        elif item.startswith("Historian summary"):
            opts["historian_event_limit"] = _prompt_int(stdscr, "Historian events queried per summary", int(opts.get("historian_event_limit", HISTORIAN_SUMMARY_EVENT_LIMIT)), minimum=0)
        elif item.startswith("Recent event"):
            opts["event_memory_limit"] = _prompt_int(stdscr, "Recent RAM event buffer limit", int(opts.get("event_memory_limit", EVENT_MEMORY_LIMIT)), minimum=0)


def role_options() -> list[str]:
    return [role.value for role in Role if role is not Role.COMMONER]


def random_identity(rng: random.Random) -> tuple[str, str, str]:
    sex = rng.choice(["M", "F"])
    first = rng.choice(MALE_FIRST_NAMES if sex == "M" else FEMALE_FIRST_NAMES)
    surname = rng.choice(SURNAMES)
    return first, surname, sex


def set_imrt_field(path: Path, section: str, key: str, value: str) -> None:
    cfg = configparser.ConfigParser()
    cfg.optionxform = str
    cfg.read(path, encoding="utf-8")
    if not cfg.has_section(section):
        cfg.add_section(section)
    cfg.set(section, key, value)
    with path.open("w", encoding="utf-8") as handle:
        cfg.write(handle)
        handle.write("\n")


def force_player_imrt(path: Path) -> Path:
    set_imrt_field(path, "identity", "is_player_god", "true")
    set_imrt_field(path, "identity", "color", "magenta")
    set_imrt_field(path, "power", "starting_souls", str(STARTING_SOULS))
    # Do not overwrite generator-derived order/volatility modifiers here.
    return path




def set_imrt_active(path: Path, active: bool, *, is_player: bool = False) -> None:
    if path is None or not path.exists():
        return
    set_imrt_field(path, "identity", "active_for_run", "true" if active else "false")
    set_imrt_field(path, "identity", "is_player_god", "true" if is_player else "false")
    set_imrt_field(path, "identity", "color", "magenta" if is_player else "")


def reset_all_custom_gods_for_run() -> int:
    GODS_DIR.mkdir(exist_ok=True)
    changed = 0
    for path in sorted(GODS_DIR.glob("*.imrt")):
        set_imrt_active(path, False, is_player=False)
        changed += 1
    return changed


def configure_active_gods(stdscr, player_path: Optional[Path]) -> list[Path]:
    GODS_DIR.mkdir(exist_ok=True)
    reset_all_custom_gods_for_run()

    active: list[Path] = []
    if player_path is not None and player_path.exists():
        set_imrt_active(player_path, True, is_player=True)
        active.append(player_path)

    files = [p for p in sorted(GODS_DIR.glob("*.imrt")) if p.resolve() != player_path.resolve()] if player_path else sorted(GODS_DIR.glob("*.imrt"))
    if not files:
        return active

    choices = []
    by_choice = {}
    for path in files:
        profile = load_imrt_file(path)
        name = profile.name if profile is not None else path.stem
        domains = ",".join(getattr(profile, "domains", []) or []) if profile is not None else ""
        label = f"{name} — AI god/rival [{path.name}]"
        if domains:
            label += f" domains={domains}"
        choices.append(label)
        by_choice[label] = path

    picked = choose_from_list(
        stdscr,
        "Select additional custom gods active this run (D done, Q none)",
        choices,
        max_select=max(1, len(choices)),
        allow_done=True,
        allow_cancel=True,
        allow_back=True,
    )
    if is_back(picked):
        return BACK
    for label in picked:
        path = by_choice[label]
        set_imrt_active(path, True, is_player=False)
        active.append(path)
    return active


def set_stri_active(path: Path, active: bool, *, active_champion: bool = False) -> None:
    cfg = _read_stri(path)
    if cfg is None:
        return
    if not cfg.has_section("story"):
        cfg.add_section("story")
    if not cfg.has_section("faith"):
        cfg.add_section("faith")
    cfg.set("story", "active_for_run", "true" if active else "false")
    cfg.set("faith", "active_champion", "true" if active_champion else "false")
    cfg.set("faith", "champion", "true" if active_champion else "false")
    cfg.set("faith", "is_champion", "true" if active_champion else "false")
    with path.open("w", encoding="utf-8") as handle:
        cfg.write(handle)
        handle.write("\n")


def reset_all_custom_actors_for_run() -> int:
    changed = 0
    for path in sorted((BASE_DIR / "MCE").glob("*.stri")):
        set_stri_active(path, False, active_champion=False)
        changed += 1
    return changed


def configure_active_story_actors(stdscr, champion_path: Optional[Path]) -> list[Path]:
    reset_all_custom_actors_for_run()
    active: list[Path] = []
    if champion_path is not None and champion_path.exists():
        set_stri_active(champion_path, True, active_champion=True)
        active.append(champion_path)

    files = [p for p in _candidate_champion_files() if champion_path is None or p.resolve() != champion_path.resolve()]
    if not files:
        return active

    choices = []
    by_choice = {}
    for path in files:
        label = _stri_display_name(path)
        choices.append(label)
        by_choice[label] = path

    picked = choose_from_list(
        stdscr,
        "Select additional custom actors active this run (D done, Q none, B back)",
        choices,
        max_select=max(1, len(choices)),
        allow_done=True,
        allow_cancel=True,
        allow_back=True,
    )
    if is_back(picked):
        return BACK
    for label in picked:
        path = by_choice[label]
        set_stri_active(path, True, active_champion=False)
        active.append(path)
    return active


def load_existing_god(stdscr) -> Optional[Path]:
    GODS_DIR.mkdir(exist_ok=True)
    files = sorted(GODS_DIR.glob("*.imrt"))
    if not files:
        pause_message(stdscr, ["No .imrt files found in ./MCE."])
        return None

    labels = []
    by_label = {}
    for path in files:
        profile = load_imrt_file(path)
        if profile is None:
            label = path.name
        else:
            marker = "PLAYER" if getattr(profile, "is_player", False) else "immortal"
            domains = ",".join(getattr(profile, "domains", []) or []) or "none"
            label = f"{profile.name} [{marker}] domains={domains} file={path.name}"
        labels.append(label)
        by_label[label] = path
    picked = choose_from_list(stdscr, "Load existing god", labels, 1, allow_back=True)
    if is_back(picked):
        return BACK
    if not picked:
        return None
    return force_player_imrt(by_label[picked[0]])


def _roll_god_cfg(rng: random.Random) -> dict:
    """Return a randomly rolled set of mechanical god attributes.

    Name and description are intentionally excluded — those stay player-authored.
    """
    domain = rng.choice(list(VALID_DOMAINS))
    alignment = rng.choice(list(VALID_ALIGNMENTS))
    favored_class = rng.choice(role_options())
    favored_traits = rng.sample(list(TRAITS), 3)
    # Draw disfavored from a wider pool first, then fall back to anything not favored.
    disfavored_pool = [t for t in rng.sample(list(TRAITS), min(5, len(TRAITS))) if t not in favored_traits]
    disfavored_traits = disfavored_pool[:2]
    if len(disfavored_traits) < 2:
        disfavored_traits = [t for t in TRAITS if t not in favored_traits][:2]
    return {
        "domain": domain,
        "alignment": alignment,
        "favored_class": favored_class,
        "favored_traits": favored_traits,
        "disfavored_traits": disfavored_traits,
    }


def edit_player_god_one_screen(stdscr, cfg: dict) -> Optional[dict]:
    """Review/edit all player-god creation choices from one screen.

    Press R at the menu to randomize all mechanical attributes (domain, alignment,
    favored class, favored/disfavored traits) while keeping name and description.
    """
    while True:
        favored = ", ".join(cfg.get("favored_traits", [])) or "-"
        disfavored = ", ".join(cfg.get("disfavored_traits", [])) or "-"
        summary = (
            f"{cfg.get('name', 'Nameless God')} | domain={cfg.get('domain', '-')} | "
            f"align={cfg.get('alignment', '-')} | class={cfg.get('favored_class', '-')}"
        )
        choice = choose_from_list(
            stdscr,
            f"Player god setup: {summary}",
            [
                "Done - create god",
                f"Name: {cfg.get('name', '')}",
                f"Domain: {cfg.get('domain', '')}",
                f"Alignment: {cfg.get('alignment', '')}",
                f"Favored class: {cfg.get('favored_class', '')}",
                f"Favored traits: {favored}",
                f"Disfavored traits: {disfavored}",
                f"Description: {cfg.get('description', '')[:44]}",
                "Randomize - reroll all mechanics",
                "Cancel god creation",
            ],
            1,
            allow_cancel=True,
            allow_back=True,
        )

        # R key rerolls all mechanical attributes without going through the menu.
        # choose_from_list returns [] on q/cancel, so we only intercept non-empty returns.
        if choice == [] and hasattr(stdscr, "getch"):
            # choose_from_list consumed the key; R is not interceptable here —
            # handled via the menu item below instead.
            pass

        if is_back(choice):
            return BACK
        if not choice:
            return None
        item = choice[0]
        if item.startswith("Done"):
            if len(cfg.get("favored_traits", [])) >= 3 and len(cfg.get("disfavored_traits", [])) >= 2:
                return cfg
            pause_message(stdscr, ["God setup incomplete.", "Need 3 favored traits and 2 disfavored traits."])
            continue
        if item.startswith("Cancel"):
            return None
        if item.startswith("Randomize"):
            rolled = _roll_god_cfg(random.Random())
            cfg.update(rolled)
            # Auto-update a generic description when domain changes, same as manual domain edit.
            if not cfg.get("description") or cfg.get("description", "").startswith("An immortal power of"):
                cfg["description"] = f"An immortal power of {cfg['domain']}."
            continue
        if item.startswith("Name"):
            val = prompt_text(stdscr, "God name:", default=cfg.get("name", "Nameless God"), allow_blank=True, allow_back=True)
            if is_back(val):
                continue
            cfg["name"] = val
        elif item.startswith("Domain"):
            picked = choose_from_list(stdscr, "Choose domain", VALID_DOMAINS, 1, allow_done=True, allow_back=True)
            if is_back(picked):
                continue
            if picked:
                cfg["domain"] = picked[0]
                if not cfg.get("description") or cfg.get("description", "").startswith("An immortal power of"):
                    cfg["description"] = f"An immortal power of {cfg['domain']}."
        elif item.startswith("Alignment"):
            picked = choose_from_list(stdscr, "Choose alignment", VALID_ALIGNMENTS, 1, allow_done=True, allow_back=True)
            if is_back(picked):
                continue
            if picked:
                cfg["alignment"] = picked[0]
        elif item.startswith("Favored class"):
            picked = choose_from_list(stdscr, "Favored class", role_options(), 1, allow_done=True, allow_back=True)
            if is_back(picked):
                continue
            if picked:
                cfg["favored_class"] = picked[0]
        elif item.startswith("Favored traits"):
            picked = choose_from_list(stdscr, "Choose 3 favored traits", TRAITS, 3, allow_done=True, allow_back=True)
            if is_back(picked):
                continue
            if len(picked) >= 3:
                cfg["favored_traits"] = picked[:3]
        elif item.startswith("Disfavored traits"):
            picked = choose_from_list(stdscr, "Choose 2 disfavored traits", TRAITS, 2, allow_done=True, disabled_options=cfg.get("favored_traits", []), allow_back=True)
            if is_back(picked):
                continue
            if len(picked) >= 2:
                cfg["disfavored_traits"] = picked[:2]
        elif item.startswith("Description"):
            val = prompt_text(stdscr, "Description:", default=cfg.get("description", ""), allow_blank=True, allow_back=True)
            if is_back(val):
                continue
            cfg["description"] = val


def build_player_god(stdscr) -> Optional[Path]:
    mode = choose_from_list(
        stdscr,
        "Player god",
        ["Create new god", "Load existing .imrt", "Skip god creation"],
        1,
        allow_back=True,
    )
    if is_back(mode):
        return BACK
    if not mode or mode[0].startswith("Skip"):
        return None
    if mode[0].startswith("Load"):
        loaded = load_existing_god(stdscr)
        if is_back(loaded):
            return BACK
        if loaded is not None:
            return loaded
        retry = yes_no(stdscr, "No god loaded. Create a new god instead?", True, allow_cancel=True)
        if retry is not True:
            return None

    rng = random.Random()
    rolled = _roll_god_cfg(rng)
    cfg = {
        "name": "Nameless God",
        "description": f"An immortal power of {rolled['domain']}.",
        **rolled,
    }
    cfg = edit_player_god_one_screen(stdscr, cfg)
    if is_back(cfg):
        return BACK
    if cfg is None:
        return None

    god = make_immortal(
        rng=random.Random(),
        name=cfg["name"],
        alignment=cfg["alignment"],
        domains=[cfg["domain"]],
        favored_traits=cfg["favored_traits"],
        disfavored_traits=cfg["disfavored_traits"],
        conversion_bias=1.0,
        order_modifier=None,
        volatility_modifier=None,
        description=cfg["description"],
        is_player_god=True,
        color="magenta",
        starting_souls=STARTING_SOULS,
    )
    GODS_DIR.mkdir(exist_ok=True)
    path = unique_imrt_path(GODS_DIR, god)
    write_imrt(path, god)
    set_imrt_field(path, "champion_rules", "favored_classes", cfg["favored_class"].lower())
    return force_player_imrt(path)


def grant_skip_champion_bonus(path: Optional[Path]) -> bool:
    if path is None or not path.exists():
        return False
    cfg = configparser.ConfigParser()
    cfg.optionxform = str
    cfg.read(path, encoding="utf-8")
    if not cfg.has_section("power"):
        cfg.add_section("power")
    if not cfg.has_section("economy"):
        cfg.add_section("economy")
    current = 0
    try:
        current = int(cfg.get("power", "starting_souls", fallback=str(STARTING_SOULS)))
    except Exception:
        current = STARTING_SOULS
    new_total = current + SKIP_CHAMPION_SOUL_BONUS
    cfg.set("power", "starting_souls", str(new_total))
    cfg.set("economy", "starting_souls", str(new_total))
    with path.open("w", encoding="utf-8") as f:
        cfg.write(f)
    return True



def _starting_champion_role(path: Path) -> str:
    cfg = _read_stri(path)
    if cfg is None:
        return "Fighter"
    return cfg.get("build", "role", fallback="Fighter")


def _deduct_starting_relic_cost(god_path: Optional[Path]) -> None:
    if god_path is None or not god_path.exists():
        return
    cfg = configparser.ConfigParser()
    cfg.optionxform = str
    cfg.read(god_path, encoding="utf-8")
    for section in ("power", "economy"):
        if not cfg.has_section(section):
            cfg.add_section(section)
    current = int(cfg.get("power", "starting_souls", fallback=str(STARTING_SOULS)))
    new_total = max(0, current - int(LESSER_RELIC_SOUL_COST))
    cfg.set("power", "starting_souls", str(new_total))
    cfg.set("economy", "starting_souls", str(new_total))
    with god_path.open("w", encoding="utf-8") as handle:
        cfg.write(handle)
        handle.write("\n")


def _snapshot_relic_files(champ_path: Optional[Path], god_path: Optional[Path]) -> dict[str, Optional[str]]:
    """Capture mutable files before starting-relic creation.

    Relic creation writes a [starting_relic] section into the champion .stri and
    deducts souls from the god .imrt. The launcher wizard allows Back after that
    point, so those file mutations need to be reversible until setup is finally
    accepted.
    """
    snap: dict[str, Optional[str]] = {}
    for label, path in (("champ", champ_path), ("god", god_path)):
        if path is not None and Path(path).exists():
            snap[label] = Path(path).read_text(encoding="utf-8", errors="replace")
        else:
            snap[label] = None
    return snap


def _restore_relic_files(champ_path: Optional[Path], god_path: Optional[Path], snapshot: Optional[dict[str, Optional[str]]]) -> None:
    if not snapshot:
        return
    for label, path in (("champ", champ_path), ("god", god_path)):
        text = snapshot.get(label)
        if path is not None and text is not None:
            Path(path).write_text(text, encoding="utf-8")


def _has_additional_custom_god_choices(player_path: Optional[Path]) -> bool:
    GODS_DIR.mkdir(exist_ok=True)
    files = sorted(GODS_DIR.glob("*.imrt"))
    if player_path is None:
        return bool(files)
    try:
        player_resolved = player_path.resolve()
    except Exception:
        player_resolved = player_path
    for path in files:
        try:
            if path.resolve() == player_resolved:
                continue
        except Exception:
            pass
        return True
    return False


def choose_starting_relic(stdscr, champ_path: Optional[Path], god_path: Optional[Path], god_name: Optional[str]) -> bool:
    if champ_path is None or god_path is None or not champ_path.exists() or not god_name:
        return False
    prompt_lines = [
        "Create a LESSER relic for your starting champion?",
        relic_limit_text(),
        f"Starting relics are LESSER only and cost {LESSER_RELIC_SOUL_COST} souls.",
    ]
    relic_choice = yes_no(stdscr, "Create a LESSER relic? " + f"({relic_limit_text()})", False, allow_cancel=True, allow_back=True)
    if relic_choice == BACK:
        return BACK
    if relic_choice is not True:
        pause_message(stdscr, ["No starting relic created.", f"Relic allowance remains: {PLAYER_LESSER_RELIC_LIMIT} lesser, {PLAYER_GREATER_RELIC_LIMIT} greater."])
        return False
    role_name = _starting_champion_role(champ_path)
    templates = valid_templates_for_role(role_name)
    if not templates:
        pause_message(stdscr, [f"No valid lesser relic templates for {role_name}."])
        return False
    labels = [f"{t.label} — {t.description}" for t in templates]
    picked = choose_from_list(stdscr, "Choose starting LESSER relic type", labels, 1, allow_cancel=True, allow_back=True)
    if is_back(picked):
        return BACK
    if not picked:
        return False
    template = templates[labels.index(picked[0])]
    name = prompt_text(stdscr, "Name this LESSER relic", default=f"{template.label} of the First Champion", allow_blank=True, allow_back=True)
    if is_back(name):
        return BACK
    boon_labels = [f"{v['label']:<10} {v['description']}" for k, v in RELIC_BOON_DEFS.items()]
    boon_keys = list(RELIC_BOON_DEFS.keys())
    boon_pick = choose_from_list(stdscr, "Choose permanent relic boon", boon_labels, 1, allow_cancel=True, allow_back=True)
    if is_back(boon_pick):
        return BACK
    if not boon_pick:
        return False
    boon_key = boon_keys[boon_labels.index(boon_pick[0])]
    payload = build_relic_payload(name=name, template_key=template.key, tier="lesser", boon_key=boon_key, creator_deity=god_name, original_recipient_id=None)
    cfg = _read_stri(champ_path)
    if cfg is None:
        return False
    if not cfg.has_section("starting_relic"):
        cfg.add_section("starting_relic")
    for key, value in payload.items():
        cfg.set("starting_relic", key, str(value))
    cfg.set("starting_relic", "created_by_player", "true")
    with champ_path.open("w", encoding="utf-8") as handle:
        cfg.write(handle)
        handle.write("\n")
    _deduct_starting_relic_cost(god_path)
    pause_message(stdscr, [f"LESSER relic created: {payload['name']}", f"Boon: {RELIC_BOON_DEFS[boon_key]['label']} — {RELIC_BOON_DEFS[boon_key]['description']}", f"Cost deducted: {LESSER_RELIC_SOUL_COST} souls."])
    return True


def _randomize_starting_stats(rng: random.Random) -> tuple[dict[str, int], int]:
    names = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma", "luck"]
    stats = {name: STARTING_CHAMPION_BASE_STAT for name in names}
    pool = STARTING_CHAMPION_STAT_POOL
    guard = 0
    while pool > 0 and guard < 10000:
        guard += 1
        name = rng.choice(names)
        if stats[name] < STARTING_CHAMPION_MAX_STAT:
            stats[name] += 1
            pool -= 1
        if all(stats[n] >= STARTING_CHAMPION_MAX_STAT for n in names):
            break
    return stats, pool


def allocate_stats(stdscr) -> Optional[dict[str, int]]:
    names = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma", "luck"]
    stats = {name: STARTING_CHAMPION_BASE_STAT for name in names}
    pool = STARTING_CHAMPION_STAT_POOL
    rng = random.Random()
    idx = 0
    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        center_add(stdscr, 1, "Allocate starting champion stats", curses.A_BOLD)
        center_add(stdscr, 2, f"Pool: {pool} | h help | r randomize | left/right adjust | up/down move | Enter done | b back | q skip")
        menu_w = 20
        x = max(0, (w - menu_w) // 2)
        start_y = max(4, h // 2 - len(names) // 2)
        for i, name in enumerate(names):
            attr = curses.A_REVERSE if i == idx else 0
            safe_add(stdscr, start_y + i, x, f"{name:14s} {stats[name]:2d}", attr)
        stdscr.refresh()
        key = stdscr.getch()
        name = names[idx]
        if key in (ord('h'), ord('H')):
            launcher_help_menu(stdscr)
            continue
        if key in (curses.KEY_UP, ord('k')):
            idx = (idx - 1) % len(names)
        elif key in (curses.KEY_DOWN, ord('j')):
            idx = (idx + 1) % len(names)
        elif key in (ord('r'), ord('R')):
            stats, pool = _randomize_starting_stats(rng)
        elif key in (curses.KEY_RIGHT, ord('+'), ord('=')):
            if pool > 0 and stats[name] < STARTING_CHAMPION_MAX_STAT:
                stats[name] += 1
                pool -= 1
        elif key in (curses.KEY_LEFT, ord('-'), ord('_')):
            if stats[name] > STARTING_CHAMPION_MIN_STAT:
                stats[name] -= 1
                pool += 1
        elif key in (10, 13):
            return stats
        elif key in (ord('b'), ord('B')):
            return BACK
        elif key in (ord('q'), ord('Q'), 27):
            return None



def choose_custom_relic(stdscr, role: str) -> Optional[dict]:
    choice = choose_from_list(
        stdscr,
        "Starting relic loadout",
        ["No custom relic", "Class weapon", "Armor", "Custom named relic"],
        1,
        allow_cancel=True,
    )
    if not choice or choice[0].startswith("No"):
        return None

    role_key = str(role).strip().lower()
    class_weapons = {
        "fighter": ("Sword", "weapon", "blade", 4, 4),
        "warden": ("Bow", "weapon", "bow", 4, 4),
        "wizard": ("Staff", "weapon", "staff", 4, 4),
        "bard": ("Magic Flute", "weapon", "instrument", 4, 4),
    }

    if choice[0] == "Class weapon":
        default = class_weapons.get(role_key, ("Sword", "weapon", "blade", 4, 4))
        base_name, relic_type, slot, power, rep = default
        custom_name = prompt_text(stdscr, "Relic name", f"{base_name} of the First Champion")
        return {
            "name": custom_name or f"{base_name} of the First Champion",
            "type": relic_type,
            "slot": slot,
            "power_bonus": power,
            "reputation_bonus": rep,
            "description": f"A starting class relic: {base_name}.",
        }

    if choice[0] == "Armor":
        custom_name = prompt_text(stdscr, "Relic name", "Armor of the First Champion")
        return {
            "name": custom_name or "Armor of the First Champion",
            "type": "armor",
            "slot": "armor",
            "power_bonus": 3,
            "reputation_bonus": 5,
            "description": "Custom starting armor carried from the first day.",
        }

    custom_name = prompt_text(stdscr, "Relic name", "Unnamed Relic")
    relic_kind = choose_from_list(stdscr, "Relic type", ["Sword", "Greataxe", "Staff", "Bow", "Magic Flute", "Armor"], 1)
    kind = relic_kind[0] if relic_kind else "Relic"
    slot = "armor" if kind == "Armor" else "weapon"
    power = 3 if slot == "armor" else 4
    rep = 5 if slot == "armor" else 4
    return {
        "name": custom_name or kind,
        "type": kind.lower(),
        "slot": slot,
        "power_bonus": power,
        "reputation_bonus": rep,
        "description": f"A custom starting relic: {kind}.",
    }


def write_starting_champion(champ: dict, god_name: str) -> Path:
    cfg = configparser.ConfigParser()
    cfg.optionxform = str
    role = str(champ["role"])
    first = champ["name"]
    surname = champ["surname"]
    sex = champ["sex"]
    stats = champ["stats"]
    age = int(champ.get("age", 22))
    hp = int(champ.get("hp", max(1, 8 + stats["constitution"] * 2)))
    region = str(champ.get("preferred_region", ""))
    cfg["seed"] = {"version": "1", "source": "start_game", "locked": "true"}
    cfg["identity"] = {"id": "", "name": first, "surname": surname, "sex": sex}
    cfg["build"] = {
        "role": role,
        "alignment": champ["alignment"],
        "deity": god_name,
        "age": str(age),
        "strength": str(stats["strength"]),
        "dexterity": str(stats["dexterity"]),
        "constitution": str(stats["constitution"]),
        "intelligence": str(stats["intelligence"]),
        "wisdom": str(stats["wisdom"]),
        "charisma": str(stats["charisma"]),
        "luck": str(stats["luck"]),
        "hp": str(hp),
        "birth_year": str(1 - age),
        "birth_month": str(random.randint(1, 12)),
        "birth_day": str(random.randint(1, 30)),
        "traits": ", ".join(champ["traits"]),
    }
    cfg["faith"] = {"deity": god_name, "locked_deity": "true", "champion": "true", "is_champion": "true", "active_champion": "true"}
    cfg["spawn"] = {"preferred_region": region, "title": "First Champion", "reputation": "25", "experience": "250"}
    cfg["story"] = {
        "status": "seeded",
        "current_region": "",
        "party_id": "",
        "polity_id": "",
        "alive": "true",
        "notes": "Generated by start_game.py as the first player champion.",
    }
    cfg["visits"] = {}
    cfg["journal"] = {"entry_0001": "First champion unleashed."}

    safe_role = role.replace(" ", "")
    stem = f"pending+{first[:1].upper()}+{surname}+{safe_role}"
    GODS_DIR.mkdir(parents=True, exist_ok=True)
    path = GODS_DIR / f"{stem}.stri"
    counter = 2
    while path.exists():
        path = GODS_DIR / f"{stem}_{counter}.stri"
        counter += 1
    with path.open("w", encoding="utf-8") as handle:
        cfg.write(handle)
        handle.write("\n")
    return path


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _read_stri(path: Path) -> Optional[configparser.ConfigParser]:
    cfg = configparser.ConfigParser()
    cfg.optionxform = str
    try:
        cfg.read(path, encoding="utf-8")
    except Exception:
        return None
    if not cfg.has_section("identity") or not cfg.has_section("build"):
        return None
    return cfg


def disable_existing_champions() -> int:
    changed = 0
    for path in (BASE_DIR / "MCE").glob("*.stri"):
        cfg = _read_stri(path)
        if cfg is None:
            continue
        if not cfg.has_section("faith"):
            cfg.add_section("faith")
        was_champ = _truthy(cfg.get("faith", "champion", fallback="false")) or _truthy(cfg.get("faith", "is_champion", fallback="false")) or _truthy(cfg.get("faith", "active_champion", fallback="false"))
        if not was_champ:
            continue
        cfg.set("faith", "champion", "false")
        cfg.set("faith", "is_champion", "false")
        cfg.set("faith", "active_champion", "false")
        with path.open("w", encoding="utf-8") as handle:
            cfg.write(handle)
            handle.write("\n")
        changed += 1
    return changed


def _candidate_champion_files() -> list[Path]:
    files = []
    for path in sorted((BASE_DIR / "MCE").glob("*.stri")):
        cfg = _read_stri(path)
        if cfg is None:
            continue
        if cfg.get("build", "role", fallback="Commoner").strip().lower() != "commoner":
            files.append(path)
    return files


def _stri_display_name(path: Path) -> str:
    cfg = _read_stri(path)
    if cfg is None:
        return path.name
    first = cfg.get("identity", "name", fallback="Unknown")
    surname = cfg.get("identity", "surname", fallback="")
    role = cfg.get("build", "role", fallback="Unknown")
    xp = cfg.get("spawn", "experience", fallback=cfg.get("build", "experience", fallback=""))
    suffix = f", xp={xp}" if xp else ""
    return f"{first} {surname} — {role}{suffix} [{path.name}]"


def _reset_existing_champion_file(path: Path, god_name: str, stats: dict[str, int]) -> Optional[Path]:
    cfg = _read_stri(path)
    if cfg is None:
        return None
    for section in ("faith", "spawn", "story", "journal"):
        if not cfg.has_section(section):
            cfg.add_section(section)
    role = cfg.get("build", "role", fallback="Fighter")
    age = 22
    hp = max(1, 8 + int(stats.get("constitution", STARTING_CHAMPION_BASE_STAT)) * 2)
    cfg.set("build", "deity", god_name)
    cfg.set("build", "age", str(age))
    for key, value in stats.items():
        cfg.set("build", key, str(value))
    cfg.set("build", "hp", str(hp))
    cfg.set("build", "max_hp", str(hp))
    cfg.set("build", "birth_year", str(1 - age))
    cfg.set("build", "birth_month", str(random.randint(1, 12)))
    cfg.set("build", "birth_day", str(random.randint(1, 30)))
    cfg.set("faith", "deity", god_name)
    cfg.set("faith", "locked_deity", "true")
    cfg.set("faith", "champion", "true")
    cfg.set("faith", "is_champion", "true")
    cfg.set("faith", "active_champion", "true")
    cfg.set("story", "active_for_run", "true")
    cfg.set("spawn", "title", "First Champion")
    cfg.set("spawn", "reputation", "25")
    cfg.set("spawn", "experience", "250")
    cfg.set("story", "status", "seeded")
    cfg.set("story", "alive", "true")
    cfg.set("story", "notes", "Selected by start_game.py as first player champion; stats reset to starting values.")
    cfg.set("journal", f"entry_{random.randint(1000, 9999)}", "Chosen as first champion; old power wiped clean.")
    first = cfg.get("identity", "name", fallback="Champion").strip() or "Champion"
    surname = cfg.get("identity", "surname", fallback="Chosen").strip() or "Chosen"
    safe_role = role.replace(" ", "")
    GODS_DIR.mkdir(parents=True, exist_ok=True)
    dst = GODS_DIR / f"pending+{first[:1].upper()}+{surname}+{safe_role}.stri"
    counter = 2
    while dst.exists() and dst.resolve() != path.resolve():
        dst = GODS_DIR / f"pending+{first[:1].upper()}+{surname}+{safe_role}_{counter}.stri"
        counter += 1
    with dst.open("w", encoding="utf-8") as handle:
        cfg.write(handle)
        handle.write("\n")
    if dst.resolve() != path.resolve():
        try:
            path.unlink()
        except OSError:
            pass
    return dst


NO_PREMADE_CHAMPIONS = object()


def select_premade_champion(stdscr, god_name: str):
    files = _candidate_champion_files()
    if not files:
        pause_message(stdscr, [
            "No pre-made .stri adventurers found.",
            "Returning to champion setup.",
        ])
        return NO_PREMADE_CHAMPIONS
    choices = [_stri_display_name(path) for path in files]
    picked = choose_from_list(stdscr, "Select pre-made champion", choices, 1, allow_back=True)
    if is_back(picked):
        return BACK
    if not picked:
        return None
    path = files[choices.index(picked[0])]
    pause_message(stdscr, ["Selected pre-made champion.", "Next: wipe and reallocate starting stats."])
    stats = allocate_stats(stdscr)
    if is_back(stats):
        return BACK
    if stats is None:
        return None
    return _reset_existing_champion_file(path, god_name, stats)



DOMAIN_TRAIT_BIAS = {
    "order": ["patient", "stern", "loyal", "brave"],
    "protection": ["brave", "merciful", "loyal", "patient"],
    "domination": ["cruel", "proud", "cunning", "suspicious"],
    "decay": ["cruel", "brooding", "vengeful", "suspicious"],
    "chaos": ["rash", "curious", "cunning", "proud"],
    "fate": ["curious", "patient", "brooding", "cunning"],
    "war": ["brave", "rash", "stern", "vengeful"],
    "death": ["brooding", "stern", "patient", "suspicious"],
    "life": ["merciful", "curious", "loyal", "patient"],
    "nature": ["curious", "patient", "merciful", "stern"],
    "knowledge": ["curious", "patient", "cunning", "brooding"],
    "trickery": ["cunning", "greedy", "rash", "curious"],
    "light": ["brave", "merciful", "loyal", "proud"],
    "darkness": ["cruel", "cunning", "brooding", "suspicious"],
}


DOMAIN_CLASS_BIAS = {
    "order": ["Fighter", "Warden"],
    "protection": ["Warden", "Fighter"],
    "domination": ["Fighter", "Wizard"],
    "decay": ["Wizard", "Fighter"],
    "chaos": ["Bard", "Wizard"],
    "fate": ["Bard", "Wizard"],
    "war": ["Fighter", "Warden"],
    "death": ["Wizard", "Fighter"],
    "life": ["Warden", "Bard"],
    "nature": ["Warden", "Bard"],
    "knowledge": ["Wizard", "Bard"],
    "trickery": ["Bard", "Wizard"],
    "light": ["Warden", "Fighter"],
    "darkness": ["Wizard", "Fighter"],
}


ROLE_STAT_BIAS = {
    "Fighter": ["strength", "constitution", "dexterity"],
    "Warden": ["dexterity", "wisdom", "constitution"],
    "Wizard": ["intelligence", "wisdom", "luck"],
    "Bard": ["charisma", "luck", "dexterity"],
}


def _god_profile_from_path(path: Optional[Path]):
    if path is None:
        return None
    try:
        return load_imrt_file(path)
    except Exception:
        return None


def _weighted_choice(rng: random.Random, options: list[str], preferred: list[str], favored_weight: int = 6):
    weights = []
    preferred_l = {str(x).strip().lower() for x in preferred if str(x).strip()}
    for opt in options:
        weights.append(favored_weight if str(opt).strip().lower() in preferred_l else 1)
    return rng.choices(options, weights=weights, k=1)[0]


def _domain_trait_pool(profile) -> list[str]:
    pool: list[str] = []
    for trait in getattr(profile, "favored_traits", []) or []:
        if trait in TRAITS and trait not in pool:
            pool.append(trait)
    for domain in getattr(profile, "domains", []) or []:
        for trait in DOMAIN_TRAIT_BIAS.get(str(domain).lower(), []):
            if trait in TRAITS and trait not in pool:
                pool.append(trait)
    for trait in TRAITS:
        if trait not in pool:
            pool.append(trait)
    disfavored = {str(t).lower() for t in getattr(profile, "disfavored_traits", []) or []}
    return [trait for trait in pool if trait.lower() not in disfavored] or list(TRAITS)


def _randomize_starting_stats_for_role(rng: random.Random, role: str) -> dict[str, int]:
    names = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma", "luck"]
    stats = {name: STARTING_CHAMPION_BASE_STAT for name in names}
    pool = STARTING_CHAMPION_STAT_POOL
    preferred = ROLE_STAT_BIAS.get(role, [])
    while pool > 0:
        pick = _weighted_choice(rng, names, preferred, favored_weight=5)
        if stats[pick] < STARTING_CHAMPION_MAX_STAT:
            stats[pick] += 1
            pool -= 1
        elif all(stats[n] >= STARTING_CHAMPION_MAX_STAT for n in names):
            break
    return stats



def edit_rolled_champion(stdscr, champ: dict) -> Optional[dict]:
    """Edit a domain-guided champion roll before accepting it."""
    while True:
        stats = champ.get("stats", {})
        summary = (
            f"{champ.get('name','?')} {champ.get('surname','?')} | "
            f"{champ.get('sex','?')} | {champ.get('role','?')} | "
            f"{champ.get('alignment','?')} | traits={', '.join(champ.get('traits', []))}"
        )
        choice = choose_from_list(
            stdscr,
            f"Edit rolled champion: {summary}",
            [
                "Done editing",
                "Edit name",
                "Edit sex",
                "Edit class",
                "Edit alignment",
                "Edit traits",
                "Edit stats",
                "Edit starting region",
                "Cancel edits",
            ],
            1,
            allow_cancel=True,
            allow_back=True,
        )
        if is_back(choice):
            return BACK
        if not choice:
            return champ
        item = choice[0]

        if item == "Done editing":
            return champ

        if item == "Cancel edits":
            return None

        if item == "Edit name":
            current = f"{champ.get('name', '')} {champ.get('surname', '')}".strip()
            full_name = prompt_text(stdscr, "Champion name:", default=current or "Unnamed Champion", allow_blank=True, allow_back=True)
            if is_back(full_name):
                continue
            parts = full_name.split()
            if len(parts) >= 2:
                champ["name"] = parts[0]
                champ["surname"] = " ".join(parts[1:])
            elif len(parts) == 1 and parts[0]:
                champ["name"] = parts[0]
            continue

        if item == "Edit sex":
            picked = choose_from_list(stdscr, "Champion sex", ["M", "F"], 1, allow_back=True)
            if is_back(picked):
                continue
            if picked:
                champ["sex"] = picked[0]
            continue

        if item == "Edit class":
            picked = choose_from_list(stdscr, "Champion class", role_options(), 1, allow_back=True)
            if is_back(picked):
                continue
            if picked:
                champ["role"] = picked[0]
            continue

        if item == "Edit alignment":
            picked = choose_from_list(stdscr, "Champion alignment", VALID_ALIGNMENTS, 1, allow_back=True)
            if is_back(picked):
                continue
            if picked:
                champ["alignment"] = picked[0]
            continue

        if item == "Edit traits":
            picked = choose_from_list(stdscr, "Choose 2 traits", TRAITS, 2, allow_done=True, allow_back=True)
            if is_back(picked):
                continue
            if len(picked) >= 2:
                champ["traits"] = picked[:2]
            continue

        if item == "Edit stats":
            picked = allocate_stats(stdscr)
            if is_back(picked):
                continue
            if picked is not None:
                champ["stats"] = picked
            continue

        if item == "Edit starting region":
            picked = choose_from_list(stdscr, "Choose starting region id", ["random"] + [str(i).zfill(2) for i in range(REGION_COUNT)], 1, allow_back=True)
            if is_back(picked):
                continue
            if picked:
                champ["preferred_region"] = "" if picked[0] == "random" else str(int(picked[0]))
            continue


def roll_domain_guided_champion(stdscr, god_name: str, god_path: Optional[Path]) -> Optional[dict]:
    profile = _god_profile_from_path(god_path)
    if profile is None:
        pause_message(stdscr, ["No god profile available.", "Create or load a god first."])
        return None

    def _do_roll():
        rng = random.Random()
        classes = role_options()
        favored_classes = [c for c in getattr(profile, "favored_classes", []) or [] if c in classes]
        domain_classes: list[str] = []
        for domain in getattr(profile, "domains", []) or []:
            domain_classes.extend([c for c in DOMAIN_CLASS_BIAS.get(str(domain).lower(), []) if c in classes])
        class_prefs = favored_classes + domain_classes
        role = _weighted_choice(rng, classes, class_prefs, favored_weight=8)

        alignments = list(VALID_ALIGNMENTS)
        profile_alignment = getattr(profile, "alignment", "") or ""
        alignment = profile_alignment if profile_alignment in alignments and rng.random() < 0.80 else _weighted_choice(rng, alignments, [profile_alignment], favored_weight=5)

        trait_pool = _domain_trait_pool(profile)
        traits = []
        while len(traits) < 2 and trait_pool:
            trait = _weighted_choice(rng, trait_pool, list(getattr(profile, "favored_traits", []) or []) + sum((DOMAIN_TRAIT_BIAS.get(str(d).lower(), []) for d in getattr(profile, "domains", []) or []), []), favored_weight=8)
            if trait not in traits:
                traits.append(trait)
            else:
                trait_pool.remove(trait)
        while len(traits) < 2:
            trait = rng.choice(TRAITS)
            if trait not in traits:
                traits.append(trait)

        stats = _randomize_starting_stats_for_role(rng, role)
        first, surname, sex = random_identity(rng)
        return first, surname, sex, role, alignment, traits, stats, favored_classes

    first, surname, sex, role, alignment, traits, stats, favored_classes = _do_roll()
    preferred_region = ""

    while True:
        stdscr.clear()
        h, _w = stdscr.getmaxyx()
        lines = [
            "Domain-guided champion roll",
            f"God: {god_name}",
            f"Domains: {', '.join(getattr(profile, 'domains', []) or ['-'])}",
            f"Favored classes: {', '.join(favored_classes or ['-'])}",
            "",
            f"Name: {first} {surname} ({sex})",
            f"Class: {role}",
            f"Alignment: {alignment}",
            f"Traits: {', '.join(traits)}",
            "Stats: " + ", ".join(f"{k[:3].upper()} {v}" for k, v in stats.items()),
            "",
            "A accept | R reroll | E edit | M manual build | H help | Q cancel",
        ]
        start = max(0, h // 2 - len(lines) // 2)
        for i, line in enumerate(lines):
            center_add(stdscr, start + i, line, curses.A_BOLD if i == 0 else 0)
        stdscr.refresh()
        key = stdscr.getch()
        current_champ = {
            "name": first,
            "surname": surname,
            "sex": sex,
            "role": role,
            "alignment": alignment,
            "traits": traits,
            "stats": stats,
            "preferred_region": preferred_region,
        }

        if key in (ord("h"), ord("H")):
            launcher_help_menu(stdscr)
            continue
        if key in (ord("a"), ord("A"), 10, 13):
            return current_champ
        if key in (ord("r"), ord("R")):
            # Reroll iteratively — the original recursive call could stack unboundedly.
            first, surname, sex, role, alignment, traits, stats, favored_classes = _do_roll()
            preferred_region = ""
            continue
        if key in (ord("e"), ord("E")):
            edited = edit_rolled_champion(stdscr, dict(current_champ))
            if is_back(edited):
                continue
            if edited is None:
                continue
            first = edited.get("name", first)
            surname = edited.get("surname", surname)
            sex = edited.get("sex", sex)
            role = edited.get("role", role)
            alignment = edited.get("alignment", alignment)
            traits = edited.get("traits", traits)
            stats = edited.get("stats", stats)
            preferred_region = edited.get("preferred_region", preferred_region)
            continue
        if key in (ord("m"), ord("M")):
            return {}
        if key in (ord("q"), ord("Q"), 27):
            if yes_no(stdscr, "Cancel champion creation and return?", False, allow_cancel=True) is True:
                return None


def build_starting_champion(stdscr, god_name: Optional[str], god_path: Optional[Path] = None) -> Optional[Path]:
    while True:
        mode = choose_from_list(
            stdscr,
            "Starting champion",
            ["Create starting champion", "Random domain-guided champion", "Select pre-made champion", "Skip champion creation"],
            1,
            allow_back=True,
        )
        if is_back(mode):
            return BACK
        if not mode or mode[0].startswith("Skip"):
            build_starting_champion.skipped_by_choice = True
            return None
        if not god_name:
            pause_message(stdscr, ["No player god selected.", "Skipping champion creation."])
            return None

        if mode[0].startswith("Random"):
            champ = roll_domain_guided_champion(stdscr, god_name, god_path)
            if champ is None:
                return None
            if champ:
                return write_starting_champion(champ, god_name)
            break

        if mode[0].startswith("Select"):
            selected = select_premade_champion(stdscr, god_name)
            if is_back(selected):
                continue
            if selected is NO_PREMADE_CHAMPIONS:
                continue
            return selected
        break

    rng = random.Random()
    first, surname, sex = random_identity(rng)
    role = role_options()[0]
    champ = {
        "name": first,
        "surname": surname,
        "sex": sex,
        "role": role,
        "alignment": rng.choice(list(VALID_ALIGNMENTS)),
        "traits": rng.sample(list(TRAITS), 2),
        "stats": _randomize_starting_stats_for_role(rng, role),
        "preferred_region": "",
    }
    edited = edit_rolled_champion(stdscr, champ)
    if is_back(edited):
        return BACK
    if edited is None:
        return None
    return write_starting_champion(edited, god_name)


def god_name_from_imrt(path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None
    profile = load_imrt_file(path)
    return profile.name if profile is not None else path.stem



def choose_fics_save(stdscr) -> Optional[Path]:
    # UX saves from data/ux_curses_*.py into DATA_DIR/saves.
    # Older launcher code only checked BASE_DIR/saves, so saves made in-game
    # were invisible from Start Game. Check both locations, plus base folder
    # for legacy loose .fics files.
    save_dirs = [DATA_DIR / "saves", BASE_DIR / "saves", BASE_DIR]
    files: list[Path] = []
    seen = set()
    for save_dir in save_dirs:
        try:
            for path in sorted(save_dir.glob("*.fics"), key=lambda p: p.stat().st_mtime, reverse=True):
                key = str(path.resolve())
                if key not in seen:
                    seen.add(key)
                    files.append(path)
        except Exception:
            continue
    if not files:
        pause_message(stdscr, ["No .fics save files found.", "Expected saves in ./data/saves, ./saves, or the base folder."])
        return None

    choices = []
    by_choice = {}
    for path in files:
        try:
            stamp = path.stat().st_mtime
            label = f"{path.name} [{path.parent.name}]"
        except Exception:
            label = path.name
        choices.append(label)
        by_choice[label] = path

    picked = choose_from_list(stdscr, "Load saved .fics state", choices, 1, allow_cancel=True, allow_back=True)
    if is_back(picked):
        return BACK
    if not picked:
        return None
    return by_choice[picked[0]]



def _set_god_starting_souls(path: Optional[Path], souls: int) -> None:
    if path is None or not Path(path).exists():
        return
    cfg = configparser.ConfigParser()
    cfg.optionxform = str
    cfg.read(path, encoding="utf-8")
    for section in ("power", "economy"):
        if not cfg.has_section(section):
            cfg.add_section(section)
        cfg.set(section, "starting_souls", str(max(0, int(souls))))
    with Path(path).open("w", encoding="utf-8") as handle:
        cfg.write(handle)
        handle.write("\n")


def choose_proto_cult_from_save(stdscr, save_path: Path):
    try:
        pause_message(stdscr, ["Scanning save for proto-cults...", str(save_path.name)])
        sim = Simulator.load_state(save_path)
        cults = sim.eligible_player_cults() if hasattr(sim, "eligible_player_cults") else []
    except Exception as exc:
        pause_message(stdscr, ["Could not inspect save for cults.", str(exc)])
        return None
    if not cults:
        pause_message(stdscr, ["No eligible proto-cults found in this save."])
        return None
    labels = []
    by_label = {}
    for cult in cults[:40]:
        latent = sum(max(0, int(v)) for v in getattr(cult, "hidden_commoner_affinity_by_region", {}).values())
        label = (
            f"{cult.id}: {cult.name} | subject={getattr(cult, 'subject_name', '-')}; "
            f"pressure={float(getattr(cult, 'legend_pressure', 0.0)):.1f}; "
            f"regions={len(getattr(cult, 'known_region_ids', set()) or set())}; latent={latent}"
        )
        labels.append(label)
        by_label[label] = int(cult.id)
    picked = choose_from_list(stdscr, "Ascend existing cult as player god", labels, 1, allow_cancel=True, allow_back=True)
    if is_back(picked):
        return BACK
    if not picked:
        return None
    return by_label[picked[0]]


def configure_save_player_injection(stdscr, save_path: Path) -> dict:
    mode = choose_from_list(
        stdscr,
        "Existing save: player-god mode",
        ["Continue save as-is", "Ascend existing proto-cult", "Reveal new god from scratch"],
        1,
        allow_back=True,
    )
    if is_back(mode):
        return BACK
    if not mode or mode[0].startswith("Continue"):
        return {}
    if mode[0].startswith("Ascend"):
        cult_id = choose_proto_cult_from_save(stdscr, save_path)
        if is_back(cult_id):
            return BACK
        if cult_id is None:
            return {}
        return {"ascend_cult_id": cult_id}

    god_file = build_player_god(stdscr)
    if is_back(god_file) or god_file is None:
        return BACK
    _set_god_starting_souls(god_file, 0)
    champ_file = build_starting_champion(stdscr, god_name_from_imrt(god_file), god_file)
    if is_back(champ_file):
        return BACK
    if champ_file is not None:
        relic_choice = choose_starting_relic(stdscr, champ_file, god_file, god_name_from_imrt(god_file))
        if is_back(relic_choice):
            return BACK
    pause_message(stdscr, [
        "New god will be revealed inside the loaded save.",
        "Starting influence: zero. Assets: first champion" + (" + lesser relic." if champ_file is not None else "."),
        "Public school unlocks after the influence threshold is reached.",
    ])
    return {"inject_god": god_file, "inject_champion": champ_file}


def launch_game(load_path: Optional[Path] = None, no_autopause: bool = False, runtime_options: Optional[dict] = None, injection_options: Optional[dict] = None) -> None:
    stop_music()
    opts = dict(runtime_options or _runtime_default_options())
    injection_options = dict(injection_options or {})
    psum = int(opts.get("psum", 0) or 0) if bool(opts.get("summaries_enabled", True)) else 0
    cmd = [sys.executable, str(UX_SCRIPT), "--psum", str(max(0, psum))]
    if load_path is None and opts.get("seed"):
        cmd.extend(["--seed", str(opts.get("seed"))])
    if load_path is not None:
        cmd.extend(["--load", str(load_path)])
    if injection_options.get("inject_god"):
        cmd.extend(["--inject-god", str(injection_options.get("inject_god"))])
    if injection_options.get("inject_champion"):
        cmd.extend(["--inject-champion", str(injection_options.get("inject_champion"))])
    if injection_options.get("ascend_cult_id") is not None:
        cmd.extend(["--ascend-cult-id", str(injection_options.get("ascend_cult_id"))])
    if no_autopause:
        cmd.append("--no-autopause")
    env = os.environ.copy()
    env["FANTFARM_SUMMARIES_ENABLED"] = "1" if bool(opts.get("summaries_enabled", True)) else "0"
    env["FANTFARM_CSV_ENABLED"] = "1" if bool(opts.get("csv_enabled", True)) else "0"
    env["FANTFARM_HISTORIAN_ENABLED"] = "1" if bool(opts.get("historian_enabled", True)) else "0"
    env["FANTFARM_HISTORIAN_EVENT_LIMIT"] = str(max(0, int(opts.get("historian_event_limit", HISTORIAN_SUMMARY_EVENT_LIMIT) or 0)))
    env["FANTFARM_EVENT_MEMORY_LIMIT"] = str(max(0, int(opts.get("event_memory_limit", EVENT_MEMORY_LIMIT) or 0)))
    subprocess.run(cmd, cwd=str(BASE_DIR), env=env)


def show_summary(stdscr, god_file: Optional[Path], champ_file: Optional[Path], runtime_options: Optional[dict] = None) -> None:
    opts = dict(runtime_options or _runtime_default_options())
    stdscr.clear()
    h, _ = stdscr.getmaxyx()
    psum = int(opts.get("psum", 0) or 0) if bool(opts.get("summaries_enabled", True)) else 0
    summary_line = "Periodic summaries: off" if psum <= 0 else f"Periodic summaries: every {psum} year(s)"
    lines = [
        "Setup complete",
        f"Seed:          {opts.get('seed', '-')}",
        f"God file:      {god_file.relative_to(BASE_DIR) if god_file else 'skipped'}",
        f"Champion file: {champ_file.relative_to(BASE_DIR) if champ_file else 'skipped'}",
        summary_line,
        f"CSV exports:   {'on' if opts.get('csv_enabled', True) else 'off'}",
        f"Historian:     {'on' if opts.get('historian_enabled', True) else 'off'} | event limit {opts.get('historian_event_limit', '-')}",
        "Inactive custom gods/champions were disabled for this run.",
        "Press any key to continue.",
    ]
    start_y = max(0, h // 2 - len(lines) // 2)
    for i, line in enumerate(lines):
        center_add(stdscr, start_y + i, line, curses.A_BOLD if i == 0 else 0)
    stdscr.refresh()
    stdscr.getch()
    play_sfx("ui_click")


def main(stdscr) -> None:
    curses.curs_set(0)
    stdscr.keypad(True)
    audio_init()
    play_intro_music()
    splash_screen(stdscr)

    main.load_path = None
    main.no_autopause = False
    main.runtime_options = _runtime_default_options()
    main.injection_options = {}

    while True:
        reset_all_custom_gods_for_run()
        reset_all_custom_actors_for_run()

        setup_mode = choose_from_list(
            stdscr,
            "Game setup",
            ["Runtime options", "Create/load god and champion", "Load .fics save", "Skip setup and start simulation"],
            1,
            allow_cancel=False,
        )

        god_file: Optional[Path] = None
        champ_file: Optional[Path] = None
        active_gods: list[Path] = []
        active_actors: list[Path] = []
        champion_skipped_by_choice = False
        relic_file_snapshot = None
        starting_relic_committed = False

        if setup_mode and setup_mode[0].startswith("Runtime"):
            opts = configure_runtime_options(stdscr, getattr(main, "runtime_options", None))
            if is_back(opts):
                continue
            main.runtime_options = opts
            continue

        if setup_mode and setup_mode[0].startswith("Load"):
            save_path = choose_fics_save(stdscr)
            if is_back(save_path):
                continue
            if save_path is not None:
                main.load_path = save_path
                ap = yes_no(stdscr, "Skip notification/autopause screens for long unattended run?", False, allow_cancel=False, allow_back=True)
                if ap == BACK:
                    continue
                main.no_autopause = bool(ap)
                injection = configure_save_player_injection(stdscr, save_path)
                if injection == BACK:
                    continue
                main.injection_options = dict(injection or {})
                mode_line = "Mode: continue as-is"
                if main.injection_options.get("ascend_cult_id") is not None:
                    mode_line = f"Mode: ascend proto-cult {main.injection_options.get('ascend_cult_id')}"
                elif main.injection_options.get("inject_god"):
                    mode_line = "Mode: reveal new god"
                pause_message(stdscr, [
                    "Loading save:",
                    str(save_path.relative_to(BASE_DIR) if save_path.is_relative_to(BASE_DIR) else save_path),
                    mode_line,
                    "Press any key to continue.",
                ])
                return
            continue

        if setup_mode and setup_mode[0].startswith("Skip"):
            active_gods = configure_active_gods(stdscr, None)
            if is_back(active_gods):
                continue
            active_actors = configure_active_story_actors(stdscr, None)
            if is_back(active_actors):
                continue
            ap = yes_no(stdscr, "Skip notification/autopause screens for long unattended run?", False, allow_cancel=False, allow_back=True)
            if ap == BACK:
                continue
            main.no_autopause = bool(ap)
            show_summary(stdscr, god_file, champ_file, getattr(main, "runtime_options", None))
            return

        # Explicit setup wizard with real B=Back movement between stages.
        stage = "god"
        while True:
            if stage == "god":
                result = build_player_god(stdscr)
                if is_back(result):
                    break  # back to Game setup
                god_file = result
                champ_file = None
                champion_skipped_by_choice = False
                relic_file_snapshot = None
                starting_relic_committed = False
                stage = "champion"
                continue

            if stage == "champion":
                build_starting_champion.skipped_by_choice = False
                result = build_starting_champion(stdscr, god_name_from_imrt(god_file), god_file)
                if is_back(result):
                    stage = "god"
                    continue
                champ_file = result
                champion_skipped_by_choice = bool(getattr(build_starting_champion, "skipped_by_choice", False))
                relic_file_snapshot = None
                starting_relic_committed = False
                stage = "relic"
                continue

            if stage == "relic":
                # Re-entering relic stage means the previous relic choice is no
                # longer committed. Restore the files to their pre-relic state
                # before asking again, so Back really backs out.
                if starting_relic_committed:
                    _restore_relic_files(champ_file, god_file, relic_file_snapshot)
                    starting_relic_committed = False
                    relic_file_snapshot = None
                if champ_file is not None:
                    relic_file_snapshot = _snapshot_relic_files(champ_file, god_file)
                    result = choose_starting_relic(stdscr, champ_file, god_file, god_name_from_imrt(god_file))
                    if is_back(result):
                        _restore_relic_files(champ_file, god_file, relic_file_snapshot)
                        relic_file_snapshot = None
                        starting_relic_committed = False
                        stage = "champion"
                        continue
                    starting_relic_committed = bool(result)
                    if not starting_relic_committed:
                        relic_file_snapshot = None
                stage = "active_gods"
                continue

            if stage == "active_gods":
                result = configure_active_gods(stdscr, god_file)
                if is_back(result):
                    stage = "relic"
                    continue
                active_gods = result
                stage = "active_actors"
                continue

            if stage == "active_actors":
                result = configure_active_story_actors(stdscr, champ_file)
                if is_back(result):
                    # If there is no visible active-gods screen, stepping back
                    # to active_gods immediately returns here, which looks like
                    # Back is broken. Jump straight to relic in that case.
                    stage = "active_gods" if _has_additional_custom_god_choices(god_file) else "relic"
                    continue
                active_actors = result
                stage = "autopause"
                continue

            if stage == "autopause":
                result = yes_no(stdscr, "Skip notification/autopause screens for long unattended run?", False, allow_cancel=False, allow_back=True)
                if result == BACK:
                    stage = "active_actors"
                    continue
                main.no_autopause = bool(result)

                if champion_skipped_by_choice and grant_skip_champion_bonus(god_file):
                    pause_message(stdscr, [
                        "Champion creation skipped.",
                        f"+{SKIP_CHAMPION_SOUL_BONUS} starting souls granted to your god.",
                    ])

                show_summary(stdscr, god_file, champ_file, getattr(main, "runtime_options", None))
                return


if __name__ == "__main__":
    curses.wrapper(main)
    launch_game(getattr(main, "load_path", None), getattr(main, "no_autopause", False), getattr(main, "runtime_options", None), getattr(main, "injection_options", None))
