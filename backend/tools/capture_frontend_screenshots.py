"""Capture frontend pages as PNG screenshots for reports.

Usage examples:

    python tools/capture_frontend_screenshots.py

    python tools/capture_frontend_screenshots.py \
        --frontend-url http://127.0.0.1:3000 \
        --output-dir docs/screenshots \
        --headful

    python tools/capture_frontend_screenshots.py \
        --extra-route general_data=/floor-plans/1?step=general_data

The script:
1. Opens the login page and saves a screenshot.
2. Logs into the frontend using credentials from CLI flags or `.env`.
3. Captures the main pages available for the current role.
4. Tries to discover the first project and first floor plan automatically.
5. Saves a `manifest.md` file with ready-made figure captions for Word.

Requirements:
    python -m pip install playwright
    python -m playwright install chromium
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

DEFAULT_FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:3000")
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "docs" / "screenshots"
DEFAULT_USERNAME = os.getenv("SCREENSHOT_USERNAME") or os.getenv("BOOTSTRAP_DEVELOPER_USERNAME")
DEFAULT_PASSWORD = os.getenv("SCREENSHOT_PASSWORD") or os.getenv("BOOTSTRAP_DEVELOPER_PASSWORD")

FREEZE_UI_CSS = """
*, *::before, *::after {
  animation-duration: 0s !important;
  animation-delay: 0s !important;
  transition-duration: 0s !important;
  transition-delay: 0s !important;
  scroll-behavior: auto !important;
  caret-color: transparent !important;
}
.welcome-overlay {
  display: none !important;
}
"""


@dataclass(frozen=True)
class CaptureTarget:
    key: str
    caption: str
    path: str
    wait_for_selector: str | None = None
    full_page: bool = True


BASE_TARGETS = [
    CaptureTarget(
        key="login",
        caption="Страница авторизации",
        path="/login",
        wait_for_selector=".auth-card",
        full_page=False,
    ),
    CaptureTarget(
        key="projects",
        caption="Страница списка проектов",
        path="/",
        wait_for_selector=".project-list-container",
        full_page=True,
    ),
    CaptureTarget(
        key="create_project",
        caption="Страница создания проекта",
        path="/create-project",
        wait_for_selector=".form-container",
        full_page=True,
    ),
    CaptureTarget(
        key="equipment_catalog",
        caption="Страница каталога оборудования",
        path="/equipment",
        wait_for_selector=".equipment-page",
        full_page=True,
    ),
]

DEVELOPER_TARGETS = [
    CaptureTarget(
        key="recognition_training",
        caption="Страница дообучения распознавания",
        path="/recognition-training",
        wait_for_selector=".training-summary-grid",
        full_page=True,
    ),
    CaptureTarget(
        key="users",
        caption="Страница управления пользователями",
        path="/users",
        wait_for_selector=".users-page",
        full_page=True,
    ),
]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_").lower()
    return slug or "page"


def build_output_dir(raw_output_dir: Path, *, timestamped: bool) -> Path:
    if not timestamped:
        return raw_output_dir
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return raw_output_dir / stamp


def normalize_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    normalized_base = base_url.rstrip("/") + "/"
    return urljoin(normalized_base, path.lstrip("/"))


def caption_from_key(key: str) -> str:
    return f"Страница {key.replace('_', ' ').replace('-', ' ')}"


def parse_extra_route(raw_value: str) -> CaptureTarget:
    if "=" not in raw_value:
        raise argparse.ArgumentTypeError(
            "extra-route must have format name=/path or name=https://host/path"
        )
    key, path = raw_value.split("=", 1)
    key = slugify(key)
    if not path.strip():
        raise argparse.ArgumentTypeError("extra-route path must not be empty")
    return CaptureTarget(
        key=key,
        caption=caption_from_key(key),
        path=path.strip(),
        wait_for_selector=None,
        full_page=True,
    )


def load_routes_file(routes_file: Path | None) -> list[CaptureTarget]:
    if routes_file is None:
        return []
    resolved = routes_file if routes_file.is_absolute() else PROJECT_ROOT / routes_file
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("routes file must contain a JSON array")
    targets: list[CaptureTarget] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"routes file item #{index} must be an object")
        path = str(item.get("path", "")).strip()
        if not path:
            raise ValueError(f"routes file item #{index} must contain a non-empty 'path'")
        key = slugify(str(item.get("key") or item.get("name") or f"page_{index}"))
        caption = str(item.get("caption") or caption_from_key(key)).strip()
        wait_for_selector = item.get("wait_for_selector")
        if wait_for_selector is not None:
            wait_for_selector = str(wait_for_selector).strip() or None
        targets.append(
            CaptureTarget(
                key=key,
                caption=caption,
                path=path,
                wait_for_selector=wait_for_selector,
                full_page=bool(item.get("full_page", True)),
            )
        )
    return targets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Автоматически сохраняет PNG-скриншоты страниц фронтенда для отчета."
    )
    parser.add_argument("--frontend-url", default=DEFAULT_FRONTEND_URL, help="Base URL of the frontend.")
    parser.add_argument("--username", default=DEFAULT_USERNAME, help="Login username.")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Login password.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where screenshots will be saved.",
    )
    parser.add_argument(
        "--routes-file",
        type=Path,
        default=None,
        help="Optional JSON file with additional routes to capture.",
    )
    parser.add_argument(
        "--extra-route",
        action="append",
        default=[],
        type=parse_extra_route,
        help="Extra route in the format name=/path or name=https://host/path.",
    )
    parser.add_argument("--browser", choices=["chromium", "firefox", "webkit"], default="chromium")
    parser.add_argument("--width", type=int, default=1600, help="Viewport width.")
    parser.add_argument("--height", type=int, default=1000, help="Viewport height.")
    parser.add_argument("--device-scale-factor", type=float, default=2.0, help="Device scale factor.")
    parser.add_argument("--timeout-ms", type=int, default=20000, help="Timeout for waits and API checks.")
    parser.add_argument("--delay-ms", type=int, default=350, help="Small settle delay before screenshots.")
    parser.add_argument("--full-page-all", action="store_true", help="Force full-page screenshots for all pages.")
    parser.add_argument("--skip-login-shot", action="store_true", help="Do not save the login page screenshot.")
    parser.add_argument("--skip-dynamic", action="store_true", help="Do not auto-discover project/detail pages.")
    parser.add_argument("--headful", action="store_true", help="Run browser in headed mode.")
    parser.add_argument(
        "--no-timestamp-subdir",
        action="store_true",
        help="Save screenshots directly into output-dir without a timestamp subfolder.",
    )
    return parser.parse_args()


def ensure_credentials(username: str | None, password: str | None) -> None:
    if username and password:
        return
    raise SystemExit(
        "Не удалось найти логин и пароль для скриншотов.\n"
        "Передайте --username и --password или задайте "
        "SCREENSHOT_USERNAME/SCREENSHOT_PASSWORD либо "
        "BOOTSTRAP_DEVELOPER_USERNAME/BOOTSTRAP_DEVELOPER_PASSWORD в .env."
    )


def import_playwright() -> Any:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - helper path for local setup only
        raise SystemExit(
            "Для работы скрипта нужен Playwright.\n"
            "Установите зависимости:\n"
            "  python -m pip install playwright\n"
            "  python -m playwright install chromium"
        ) from exc
    return sync_playwright, PlaywrightTimeoutError


def wait_for_page_ready(page: Any, selector: str | None, timeout_ms: int) -> None:
    page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    try:
        page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 5000))
    except Exception:
        pass
    if selector:
        page.locator(selector).first.wait_for(state="visible", timeout=timeout_ms)


def inject_capture_styles(page: Any) -> None:
    page.add_style_tag(content=FREEZE_UI_CSS)


def wait_for_auth_me(context: Any, frontend_url: str, timeout_ms: int) -> dict[str, Any]:
    deadline = datetime.now().timestamp() + (timeout_ms / 1000)
    last_error: Exception | None = None
    me_url = normalize_url(frontend_url, "/api/auth/me")
    while datetime.now().timestamp() < deadline:
        try:
            response = context.request.get(me_url, timeout=timeout_ms)
            if response.ok:
                return response.json()
        except Exception as exc:  # pragma: no cover - local timing variation
            last_error = exc
        context.pages[0].wait_for_timeout(250)
    if last_error is not None:
        raise RuntimeError("Не удалось подтвердить авторизацию через /api/auth/me") from last_error
    raise RuntimeError("Не удалось подтвердить авторизацию через /api/auth/me")


def current_path(url: str) -> str:
    parsed = urlparse(url)
    return parsed.path or "/"


def capture_target(
    page: Any,
    frontend_url: str,
    target: CaptureTarget,
    screenshot_path: Path,
    timeout_ms: int,
    delay_ms: int,
    force_full_page: bool,
) -> None:
    page.goto(normalize_url(frontend_url, target.path), wait_until="domcontentloaded", timeout=timeout_ms)
    wait_for_page_ready(page, target.wait_for_selector, timeout_ms)
    inject_capture_styles(page)
    page.wait_for_timeout(delay_ms)
    page.screenshot(
        path=str(screenshot_path),
        full_page=force_full_page or target.full_page,
    )


def discover_dynamic_targets(page: Any, frontend_url: str, timeout_ms: int) -> list[CaptureTarget]:
    discovered: list[CaptureTarget] = []

    page.goto(normalize_url(frontend_url, "/"), wait_until="domcontentloaded", timeout=timeout_ms)
    wait_for_page_ready(page, ".project-list-container", timeout_ms)

    project_link = page.locator('.project-grid a[href^="/projects/"]').first
    if project_link.count() == 0:
        return discovered

    project_href = project_link.get_attribute("href")
    if not project_href:
        return discovered

    discovered.append(
        CaptureTarget(
            key="project_detail",
            caption="Страница карточки проекта",
            path=project_href,
            wait_for_selector=".project-detail-page",
            full_page=True,
        )
    )

    page.goto(normalize_url(frontend_url, project_href), wait_until="domcontentloaded", timeout=timeout_ms)
    wait_for_page_ready(page, ".project-detail-page", timeout_ms)

    floor_plan_link = page.locator('main a[href^="/floor-plans/"]').first
    if floor_plan_link.count() == 0:
        return discovered

    floor_plan_href = floor_plan_link.get_attribute("href")
    if not floor_plan_href:
        return discovered

    discovered.append(
        CaptureTarget(
            key="floor_plan_editor",
            caption="Страница редактора плана этажа",
            path=floor_plan_href,
            wait_for_selector=".editor-container",
            full_page=False,
        )
    )

    return discovered


def write_manifest(output_dir: Path, records: list[dict[str, str]]) -> Path:
    manifest_path = output_dir / "manifest.md"
    lines = [
        "# Скриншоты интерфейса",
        "",
        "| Файл | Подпись для отчета | Маршрут |",
        "| --- | --- | --- |",
    ]
    for record in records:
        lines.append(f"| `{record['file_name']}` | {record['caption']} | `{record['path']}` |")
    lines.append("")
    lines.append("Подписи можно вставлять в Word в формате:")
    lines.append("")
    lines.append("`Рисунок X – <подпись для отчета>`")
    manifest_path.write_text("\n".join(lines), encoding="utf-8")
    return manifest_path


def main() -> int:
    args = parse_args()
    ensure_credentials(args.username, args.password)

    output_dir = build_output_dir(
        args.output_dir,
        timestamped=not args.no_timestamp_subdir,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    custom_targets = load_routes_file(args.routes_file) + list(args.extra_route)
    sync_playwright, PlaywrightTimeoutError = import_playwright()

    with sync_playwright() as playwright:
        browser_launcher = getattr(playwright, args.browser)
        browser = browser_launcher.launch(headless=not args.headful)
        context = browser.new_context(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=args.device_scale_factor,
            locale="ru-RU",
            color_scheme="light",
        )
        page = context.new_page()

        login_target = BASE_TARGETS[0]
        if not args.skip_login_shot:
            capture_target(
                page=page,
                frontend_url=args.frontend_url,
                target=login_target,
                screenshot_path=output_dir / "01_login.png",
                timeout_ms=args.timeout_ms,
                delay_ms=args.delay_ms,
                force_full_page=args.full_page_all,
            )

        page.goto(normalize_url(args.frontend_url, "/login"), wait_until="domcontentloaded", timeout=args.timeout_ms)
        wait_for_page_ready(page, ".auth-card", args.timeout_ms)

        page.locator('input[name="username"]').fill(args.username)
        page.locator('input[name="password"]').fill(args.password)
        page.locator('button[type="submit"]').click()

        try:
            me = wait_for_auth_me(context, args.frontend_url, args.timeout_ms)
        except Exception as exc:
            error_box = ""
            if page.locator(".auth-form__error").count() > 0:
                error_box = page.locator(".auth-form__error").inner_text().strip()
            raise SystemExit(
                "Не удалось выполнить вход для съемки интерфейса."
                + (f"\nСообщение формы: {error_box}" if error_box else "")
            ) from exc

        role = str(me.get("role") or "").strip().lower()
        page.goto(normalize_url(args.frontend_url, "/"), wait_until="domcontentloaded", timeout=args.timeout_ms)
        wait_for_page_ready(page, ".project-list-container", args.timeout_ms)
        try:
            page.locator(".welcome-overlay").wait_for(state="hidden", timeout=2000)
        except PlaywrightTimeoutError:
            inject_capture_styles(page)

        targets: list[CaptureTarget] = BASE_TARGETS[1:] + custom_targets
        if role == "developer":
            targets = BASE_TARGETS[1:] + DEVELOPER_TARGETS + custom_targets

        if not args.skip_dynamic:
            targets.extend(discover_dynamic_targets(page, args.frontend_url, args.timeout_ms))

        records: list[dict[str, str]] = []
        image_index = 2 if not args.skip_login_shot else 1

        for target in targets:
            file_name = f"{image_index:02d}_{slugify(target.key)}.png"
            capture_target(
                page=page,
                frontend_url=args.frontend_url,
                target=target,
                screenshot_path=output_dir / file_name,
                timeout_ms=args.timeout_ms,
                delay_ms=args.delay_ms,
                force_full_page=args.full_page_all,
            )
            records.append(
                {
                    "file_name": file_name,
                    "caption": target.caption,
                    "path": target.path,
                }
            )
            image_index += 1

        if not args.skip_login_shot:
            records.insert(
                0,
                {
                    "file_name": "01_login.png",
                    "caption": login_target.caption,
                    "path": login_target.path,
                },
            )

        manifest_path = write_manifest(output_dir, records)
        browser.close()

    print(f"Скриншоты сохранены в: {output_dir}")
    print(f"Манифест с подписями: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
