from __future__ import annotations

import itertools
import json
import re
from dataclasses import dataclass
from pathlib import Path

import requests
from PIL import Image


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
CURRENT_IMAGE = ROOT / 'electricity.png'
TARGET_IMAGE = ROOT / 'solved_electricity.png'
VERIFY_URL = 'https://hub.ag3nts.org/verify'
TARGET_URL = 'https://hub.ag3nts.org/i/solved_electricity.png'


@dataclass
class AnalysisResult:
    current_grid_x: list[int]
    current_grid_y: list[int]
    target_grid_x: list[int]
    target_grid_y: list[int]
    moves: list[dict]
    solved: bool

    def to_dict(self) -> dict:
        return {
            'current_grid_x': self.current_grid_x,
            'current_grid_y': self.current_grid_y,
            'target_grid_x': self.target_grid_x,
            'target_grid_y': self.target_grid_y,
            'moves': self.moves,
            'solved': self.solved,
        }


def read_env_key(env_path: Path, var: str) -> str | None:
    if not env_path.exists():
        return None
    content = env_path.read_text(encoding='utf-8')
    match = re.search(rf'^{re.escape(var)}\s*=\s*["\']?(.*?)["\']?\s*$', content, re.M)
    return match.group(1) if match else None


def get_api_key() -> str:
    api_key = read_env_key(REPO_ROOT / '.env', 'AI_DEVS_4_API_KEY')
    if not api_key:
        raise RuntimeError('Brak AI_DEVS_4_API_KEY w pliku .env')
    return api_key


def download_current_image(reset: bool = False) -> Path:
    api_key = get_api_key()
    url = f'https://hub.ag3nts.org/data/{api_key}/electricity.png'
    if reset:
        url += '?reset=1'
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    CURRENT_IMAGE.write_bytes(response.content)
    return CURRENT_IMAGE


def ensure_target_image() -> Path:
    if not TARGET_IMAGE.exists():
        response = requests.get(TARGET_URL, timeout=30)
        response.raise_for_status()
        TARGET_IMAGE.write_bytes(response.content)
    return TARGET_IMAGE


def _profile_values(image: Image.Image, axis: str) -> list[float]:
    gray = image.convert('L')
    if axis == 'x':
        return [sum(gray.getpixel((x, y)) for y in range(gray.height)) / gray.height for x in range(gray.width)]
    return [sum(gray.getpixel((x, y)) for x in range(gray.width)) / gray.width for y in range(gray.height)]


def detect_grid_lines(image: Image.Image, axis: str) -> list[int]:
    values = _profile_values(image, axis)
    candidates = sorted(range(len(values)), key=lambda idx: values[idx])[:120]
    best: tuple[float, tuple[int, int, int, int]] | None = None
    for combo in itertools.combinations(sorted(candidates), 4):
        distances = [combo[i + 1] - combo[i] for i in range(3)]
        step = sum(distances) / 3
        spread = max(distances) - min(distances)
        if not (70 <= step <= 120):
            continue
        if spread > 8:
            continue
        score = sum(values[index] for index in combo) + spread * 10
        if best is None or score < best[0]:
            best = (score, combo)
    if best is None:
        raise RuntimeError(f'Nie udało się wykryć linii siatki dla osi {axis}')
    return list(best[1])


def crop_tiles(image: Image.Image, grid_x: list[int], grid_y: list[int], size: int = 96) -> list[list[Image.Image]]:
    tiles: list[list[Image.Image]] = []
    for row in range(3):
        tile_row = []
        for col in range(3):
            tile = image.crop((grid_x[col], grid_y[row], grid_x[col + 1], grid_y[row + 1]))
            tile_row.append(tile.resize((size, size)).convert('RGB'))
        tiles.append(tile_row)
    return tiles


def image_diff(image_a: Image.Image, image_b: Image.Image) -> int:
    total = 0
    pixels_a = list(image_a.getdata())
    pixels_b = list(image_b.getdata())
    for pixel_a, pixel_b in zip(pixels_a, pixels_b):
        total += sum((pixel_a[channel] - pixel_b[channel]) ** 2 for channel in range(3))
    return total


def analyze_board() -> AnalysisResult:
    ensure_target_image()
    if not CURRENT_IMAGE.exists():
        download_current_image()

    current_image = Image.open(CURRENT_IMAGE)
    target_image = Image.open(TARGET_IMAGE)

    current_grid_x = detect_grid_lines(current_image, 'x')
    current_grid_y = detect_grid_lines(current_image, 'y')
    target_grid_x = detect_grid_lines(target_image, 'x')
    target_grid_y = detect_grid_lines(target_image, 'y')

    current_tiles = crop_tiles(current_image, current_grid_x, current_grid_y)
    target_tiles = crop_tiles(target_image, target_grid_x, target_grid_y)

    moves: list[dict] = []
    solved = True
    for row in range(3):
        for col in range(3):
            scores = []
            for rotations in range(4):
                rotated_current = current_tiles[row][col].rotate(-90 * rotations)
                scores.append(image_diff(rotated_current, target_tiles[row][col]))
            rotate_right = min(range(4), key=lambda idx: scores[idx])
            if rotate_right != 0:
                solved = False
            moves.append(
                {
                    'tile': f'{row + 1}x{col + 1}',
                    'row': row + 1,
                    'col': col + 1,
                    'rotate_right': rotate_right,
                    'scores': scores,
                    'best_score': scores[rotate_right],
                }
            )

    return AnalysisResult(
        current_grid_x=current_grid_x,
        current_grid_y=current_grid_y,
        target_grid_x=target_grid_x,
        target_grid_y=target_grid_y,
        moves=moves,
        solved=solved,
    )


def rotate_tile(tile: str) -> dict:
    api_key = get_api_key()
    payload = {
        'apikey': api_key,
        'task': 'electricity',
        'answer': {'rotate': tile},
    }
    response = requests.post(VERIFY_URL, json=payload, timeout=30)
    response.raise_for_status()
    try:
        return response.json()
    except ValueError:
        return {'raw': response.text}


def apply_plan(moves: list[dict] | None = None) -> dict:
    if moves is None:
        analysis = analyze_board()
        moves = analysis.moves

    applied: list[dict] = []
    last_response: dict | None = None
    for move in moves:
        for _ in range(move['rotate_right']):
            last_response = rotate_tile(move['tile'])
            applied.append({'tile': move['tile']})
    download_current_image()
    analysis_after = analyze_board().to_dict()
    return {
        'applied': applied,
        'count': len(applied),
        'last_response': last_response,
        'analysis': analysis_after,
    }


def save_analysis(path: Path | None = None) -> Path:
    output_path = path or (ROOT / 'analysis.json')
    output_path.write_text(json.dumps(analyze_board().to_dict(), indent=2), encoding='utf-8')
    return output_path
