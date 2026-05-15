"""
HTTP-клиент с поддержкой:
- retry с экспоненциальной задержкой
- ротации прокси и User-Agent
- Playwright как fallback при блокировке requests
"""

import time
import random
import asyncio
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    REQUEST_TIMEOUT,
    REQUEST_DELAY_MIN,
    REQUEST_DELAY_MAX,
    MAX_RETRIES,
    RETRY_DELAY,
    USE_PLAYWRIGHT_FALLBACK,
    BROWSER_TIMEOUT,
)
from modules.utils.helpers import get_random_user_agent, get_random_proxy, get_request_headers
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class HttpClient:
    """
    Умный HTTP-клиент.
    Сначала пробует requests, при блокировке (403/429/captcha) — Playwright.
    """

    # Статус-коды, при которых переключаемся на браузер
    BROWSER_FALLBACK_CODES = {403, 429, 503}

    def __init__(self) -> None:
        self._session = self._build_session()
        self._playwright_available = self._check_playwright()

    # ── Сессия requests ───────────────────────────────────────────────────────

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=RETRY_DELAY,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _check_playwright(self) -> bool:
        try:
            import playwright  # noqa: F401
            return True
        except ImportError:
            logger.warning("Playwright не установлен — fallback на браузер недоступен")
            return False

    # ── Публичный метод ───────────────────────────────────────────────────────

    def get(
        self,
        url: str,
        params: Optional[dict] = None,
        extra_headers: Optional[dict] = None,
        use_proxy: bool = True,
    ) -> Optional[str]:
        """
        Выполняет GET-запрос.
        Возвращает HTML-текст страницы или None при ошибке.
        """
        self._polite_delay()

        html = self._get_with_requests(url, params, extra_headers, use_proxy)
        if html is not None:
            return html

        # Fallback на Playwright
        if USE_PLAYWRIGHT_FALLBACK and self._playwright_available:
            logger.info("Переключаемся на Playwright для: %s", url)
            html = self._get_with_playwright(url)

        return html

    # ── requests ──────────────────────────────────────────────────────────────

    def _get_with_requests(
        self,
        url: str,
        params: Optional[dict],
        extra_headers: Optional[dict],
        use_proxy: bool,
    ) -> Optional[str]:
        headers = get_request_headers(extra_headers)
        proxies = None

        if use_proxy:
            proxy = get_random_proxy()
            if proxy:
                proxies = {"http": proxy, "https": proxy}

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._session.get(
                    url,
                    params=params,
                    headers=headers,
                    proxies=proxies,
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=True,
                )

                if resp.status_code in self.BROWSER_FALLBACK_CODES:
                    logger.debug(
                        "Статус %d для %s — нужен браузер",
                        resp.status_code, url,
                    )
                    return None

                resp.raise_for_status()
                return resp.text

            except requests.exceptions.Timeout:
                logger.warning("Таймаут запроса [%d/%d]: %s", attempt, MAX_RETRIES, url)
            except requests.exceptions.ProxyError:
                logger.warning("Ошибка прокси [%d/%d]: %s", attempt, MAX_RETRIES, url)
                proxies = None  # Следующая попытка без прокси
            except requests.exceptions.ConnectionError:
                logger.warning("Ошибка соединения [%d/%d]: %s", attempt, MAX_RETRIES, url)
            except requests.exceptions.HTTPError as e:
                logger.warning("HTTP ошибка: %s", e)
                return None
            except Exception as e:
                logger.error("Неожиданная ошибка при запросе %s: %s", url, e)
                return None

            if attempt < MAX_RETRIES:
                sleep_time = RETRY_DELAY * (2 ** (attempt - 1))
                time.sleep(sleep_time)

        return None

    # ── Playwright ────────────────────────────────────────────────────────────

    def _get_with_playwright(self, url: str) -> Optional[str]:
        """Получает страницу через headless Chromium."""
        try:
            return asyncio.run(self._playwright_fetch(url))
        except Exception as e:
            logger.error("Playwright ошибка для %s: %s", url, e)
            return None

    async def _playwright_fetch(self, url: str) -> Optional[str]:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=get_random_user_agent(),
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            # Блокируем ненужные ресурсы для скорости
            await page.route(
                "**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}",
                lambda route: route.abort(),
            )

            try:
                await page.goto(url, timeout=BROWSER_TIMEOUT, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)  # Ждём JS-рендеринг
                content = await page.content()
                return content
            finally:
                await browser.close()

    # ── Вспомогательные ───────────────────────────────────────────────────────

    @staticmethod
    def _polite_delay() -> None:
        """Случайная задержка между запросами — уважаем сервера."""
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        time.sleep(delay)
