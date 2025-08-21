"""Puppeteer client for JavaScript-rendered content scraping."""

import asyncio
import hashlib
import logging
import os
import re
import urllib.parse
from datetime import datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from pyppeteer import launch
from pyppeteer.browser import Browser
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.models.scraping import BusinessInfo, Review


class PuppeteerClient:
    """Client for scraping JavaScript-rendered content using Pyppeteer."""

    def __init__(self, max_concurrent_browsers: int = 3):
        """Initialize Puppeteer client.

        Args:
            max_concurrent_browsers: Maximum number of concurrent browser instances
        """
        self.max_concurrent_browsers = max_concurrent_browsers
        self.browsers: list[Browser] = []
        self.semaphore = asyncio.Semaphore(max_concurrent_browsers)
        self.logger = logging.getLogger(__name__)
        self.timeout = int(os.getenv("SCRAPING_TIMEOUT_SECONDS", "30")) * 1000

    async def __aenter__(self):
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup browsers."""
        await self.cleanup()

    async def cleanup(self):
        """Close all browser instances."""
        for browser in self.browsers:
            try:
                await browser.close()
            except Exception as e:
                self.logger.error(f"Error closing browser: {e}")
        self.browsers.clear()

    @retry(
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def scrape_url(self, url: str, wait_selector: str | None = None) -> str | None:
        """Scrape a URL and return HTML content.

        Args:
            url: URL to scrape
            wait_selector: CSS selector to wait for before getting content

        Returns:
            HTML content or None if failed
        """
        async with self.semaphore:
            browser = None
            try:
                browser = await launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-accelerated-2d-canvas",
                        "--no-first-run",
                        "--no-zygote",
                        "--single-process",
                        "--disable-gpu",
                    ],
                )
                self.browsers.append(browser)

                page = await browser.newPage()
                await page.setUserAgent(
                    "Mozilla/5.0 (compatible; RestaurantScraperBot/1.0; +https://example.com/bot)"
                )

                await page.goto(url, {"waitUntil": "networkidle2", "timeout": self.timeout})

                if wait_selector:
                    await page.waitForSelector(wait_selector, {"timeout": self.timeout})

                content = await page.content()
                return content

            except Exception as e:
                self.logger.error(f"Error scraping {url}: {e}")
                return None
            finally:
                if browser:
                    await browser.close()
                    if browser in self.browsers:
                        self.browsers.remove(browser)

    async def scrape_yelp_reviews(self, url: str, max_pages: int = 5) -> list[Review]:
        """Scrape reviews from Yelp.

        Args:
            url: Yelp business URL
            max_pages: Maximum number of pages to scrape

        Returns:
            List of scraped reviews
        """
        reviews = []

        for page_num in range(max_pages):
            # For Yelp, pagination is handled by start parameter
            page_url = url
            if page_num > 0:
                separator = "&" if "?" in url else "?"
                page_url = f"{url}{separator}start={page_num * 20}"

            content = await self.scrape_url(page_url, "[data-testid='reviews-section']")
            if not content:
                break

            soup = BeautifulSoup(content, "html.parser")

            # Find review containers
            review_elements = soup.find_all(
                "div", {"data-testid": re.compile(r"serp-ia-card|reviews-list-item")}
            )

            if not review_elements:
                # Fallback selectors
                review_elements = soup.find_all(
                    "li", class_=re.compile(r"review|user-passport-info")
                )

            if not review_elements:
                break

            for review_elem in review_elements:
                try:
                    # Extract review text
                    text_elem = (
                        review_elem.find("span", {"data-testid": "review-text"})
                        or review_elem.find("p", class_=re.compile(r"comment|review-content"))
                        or review_elem.find("span", class_=re.compile(r"raw__"))
                    )
                    text = self._sanitize_text(text_elem.get_text() if text_elem else "")

                    if not text or len(text) < 10:
                        continue

                    # Extract rating
                    rating_elem = review_elem.find(
                        "div", {"aria-label": re.compile(r"\d star")}
                    ) or review_elem.find("div", class_=re.compile(r"rating|stars"))
                    rating = 0.0
                    if rating_elem:
                        rating_text = rating_elem.get("aria-label", "") or rating_elem.get_text()
                        rating_match = re.search(r"(\d+(?:\.\d+)?)", rating_text)
                        if rating_match:
                            rating = float(rating_match.group(1))

                    # Extract author
                    author_elem = review_elem.find(
                        "a", class_=re.compile(r"user-name|author")
                    ) or review_elem.find("span", class_=re.compile(r"user-name|fs-block"))
                    author = self._sanitize_text(
                        author_elem.get_text() if author_elem else "Anonymous"
                    )

                    # Extract date
                    date_elem = review_elem.find(
                        "span", class_=re.compile(r"rating-qualifier|date")
                    ) or review_elem.find("time")
                    date = self._sanitize_text(
                        date_elem.get_text() if date_elem else datetime.now().strftime("%Y-%m-%d")
                    )

                    # Extract business response if available
                    response_elem = review_elem.find(
                        "div", class_=re.compile(r"biz-owner-reply|owner-response")
                    )
                    response = self._sanitize_text(
                        response_elem.get_text() if response_elem else None
                    )

                    review = Review(
                        text=text,
                        rating=rating,
                        date=date,
                        author=author,
                        platform="yelp",
                        url=page_url,
                        response=response,
                    )
                    reviews.append(review)

                except Exception as e:
                    self.logger.warning(f"Error parsing Yelp review: {e}")
                    continue

            # Break if we didn't find any reviews on this page
            if len([r for r in reviews if r.platform == "yelp"]) == len(reviews):
                break

            await asyncio.sleep(2)  # Rate limiting

        return reviews

    async def scrape_google_reviews(self, url: str, max_reviews: int = 100) -> list[Review]:
        """Scrape reviews from Google.

        Args:
            url: Google Maps/Business URL
            max_reviews: Maximum number of reviews to scrape

        Returns:
            List of scraped reviews
        """
        reviews = []

        async with self.semaphore:
            browser = None
            try:
                browser = await launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-accelerated-2d-canvas",
                        "--no-first-run",
                        "--no-zygote",
                        "--single-process",
                        "--disable-gpu",
                    ],
                )
                self.browsers.append(browser)

                page = await browser.newPage()
                await page.setUserAgent(
                    "Mozilla/5.0 (compatible; RestaurantScraperBot/1.0; +https://example.com/bot)"
                )

                await page.goto(url, {"waitUntil": "networkidle2", "timeout": self.timeout})

                # Wait for reviews section to load
                try:
                    await page.waitForSelector("[data-review-id]", {"timeout": 10000})
                except Exception:
                    # Fallback: try alternative selectors
                    try:
                        await page.waitForSelector('[jsname="fJiQFc"]', {"timeout": 5000})
                    except Exception:
                        pass

                # Scroll to load more reviews
                scroll_attempts = min(10, max_reviews // 10)
                for _ in range(scroll_attempts):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(1)

                content = await page.content()
                soup = BeautifulSoup(content, "html.parser")

                # Find review containers
                review_elements = (
                    soup.find_all("div", {"data-review-id": True})
                    or soup.find_all("div", {"jsname": "fJiQFc"})
                    or soup.find_all("div", class_=re.compile(r"review|ODSEW-ShBeI"))
                )

                for review_elem in review_elements[:max_reviews]:
                    try:
                        # Extract review text
                        text_elem = (
                            review_elem.find("span", {"data-expandable-section": True})
                            or review_elem.find("span", class_=re.compile(r"review-text|wiI7pd"))
                            or review_elem.find("div", class_=re.compile(r"MyEned"))
                        )
                        text = self._sanitize_text(text_elem.get_text() if text_elem else "")

                        if not text or len(text) < 10:
                            continue

                        # Extract rating
                        rating_elem = review_elem.find(
                            "span", class_=re.compile(r"kvMYJc")
                        ) or review_elem.find("div", {"aria-label": re.compile(r"\d stars?")})
                        rating = 0.0
                        if rating_elem:
                            rating_text = (
                                rating_elem.get("aria-label", "") or rating_elem.get_text()
                            )
                            rating_match = re.search(r"(\d+)", rating_text)
                            if rating_match:
                                rating = float(rating_match.group(1))

                        # Extract author
                        author_elem = review_elem.find(
                            "div", class_=re.compile(r"d4r55|TSUbDb")
                        ) or review_elem.find("button", class_=re.compile(r"WNxzHc"))
                        author = self._sanitize_text(
                            author_elem.get_text() if author_elem else "Anonymous"
                        )

                        # Extract date
                        date_elem = review_elem.find(
                            "span", class_=re.compile(r"rsqaWe|dehysf")
                        ) or review_elem.find("span", class_=re.compile(r"p2TkOb"))
                        date = self._sanitize_text(
                            date_elem.get_text()
                            if date_elem
                            else datetime.now().strftime("%Y-%m-%d")
                        )

                        # Extract business response if available
                        response_elem = review_elem.find("div", class_=re.compile(r"CDe7pd"))
                        response = self._sanitize_text(
                            response_elem.get_text() if response_elem else None
                        )

                        review = Review(
                            text=text,
                            rating=rating,
                            date=date,
                            author=author,
                            platform="google",
                            url=url,
                            response=response,
                        )
                        reviews.append(review)

                    except Exception as e:
                        self.logger.warning(f"Error parsing Google review: {e}")
                        continue

            except Exception as e:
                self.logger.error(f"Error scraping Google reviews from {url}: {e}")
            finally:
                if browser:
                    await browser.close()
                    if browser in self.browsers:
                        self.browsers.remove(browser)

        return reviews

    async def scrape_tripadvisor_reviews(self, url: str, max_pages: int = 5) -> list[Review]:
        """Scrape reviews from TripAdvisor.

        Args:
            url: TripAdvisor restaurant URL
            max_pages: Maximum number of pages to scrape

        Returns:
            List of scraped reviews
        """
        reviews = []

        for page_num in range(max_pages):
            # For TripAdvisor, pagination often uses -or{offset}- pattern
            page_url = url
            if page_num > 0:
                # Insert pagination into URL (TripAdvisor specific pattern)
                if "Restaurant_Review" in url:
                    base_url = url.replace(".html", "")
                    page_url = f"{base_url}-or{page_num * 10}.html"
                else:
                    separator = "&" if "?" in url else "?"
                    page_url = f"{url}{separator}offset={page_num * 10}"

            content = await self.scrape_url(page_url, '[data-test-id="review"]')
            if not content:
                break

            soup = BeautifulSoup(content, "html.parser")

            # Find review containers
            review_elements = (
                soup.find_all("div", {"data-test-id": "review"})
                or soup.find_all("div", class_=re.compile(r"reviewSelector|review-item"))
                or soup.find_all("div", class_=re.compile(r"location-review-card"))
            )

            if not review_elements:
                break

            page_reviews_count = len(reviews)

            for review_elem in review_elements:
                try:
                    # Extract review text
                    text_elem = (
                        review_elem.find("div", {"data-test-id": "review-body"})
                        or review_elem.find("span", class_=re.compile(r"partial_entry|QewHA"))
                        or review_elem.find("p", class_=re.compile(r"partial_entry"))
                    )
                    text = self._sanitize_text(text_elem.get_text() if text_elem else "")

                    if not text or len(text) < 10:
                        continue

                    # Extract rating
                    rating_elem = review_elem.find(
                        "svg", {"aria-label": re.compile(r"\d+(?:\.\d+)? of 5 bubbles")}
                    ) or review_elem.find(
                        "span", class_=re.compile(r"bubble_rating|ui_bubble_rating")
                    )
                    rating = 0.0
                    if rating_elem:
                        rating_text = (
                            rating_elem.get("aria-label", "") or rating_elem.get("class", [""])[0]
                        )
                        if "aria-label" in rating_elem.attrs:
                            rating_match = re.search(r"(\d+(?:\.\d+)?)", rating_text)
                            if rating_match:
                                rating = float(rating_match.group(1))
                        elif "bubble_" in str(rating_elem.get("class", [])):
                            # Extract from bubble class names like 'bubble_50' = 5.0 stars
                            class_str = " ".join(rating_elem.get("class", []))
                            bubble_match = re.search(r"bubble_(\d+)", class_str)
                            if bubble_match:
                                rating = float(bubble_match.group(1)) / 10

                    # Extract author
                    author_elem = (
                        review_elem.find("div", {"data-test-id": "review-username"})
                        or review_elem.find("span", class_=re.compile(r"info_text|username"))
                        or review_elem.find("a", class_=re.compile(r"ui_header_link"))
                    )
                    author = self._sanitize_text(
                        author_elem.get_text() if author_elem else "Anonymous"
                    )

                    # Extract date
                    date_elem = (
                        review_elem.find("div", {"data-test-id": "review-date"})
                        or review_elem.find("span", class_=re.compile(r"ratingDate|date"))
                        or review_elem.find(
                            "div", class_=re.compile(r"prw_rup prw_reviews_stay_date")
                        )
                    )
                    date = self._sanitize_text(
                        date_elem.get_text() if date_elem else datetime.now().strftime("%Y-%m-%d")
                    )

                    # Extract business response if available
                    response_elem = review_elem.find(
                        "div", class_=re.compile(r"management-response|owner-response")
                    )
                    response = self._sanitize_text(
                        response_elem.get_text() if response_elem else None
                    )

                    review = Review(
                        text=text,
                        rating=rating,
                        date=date,
                        author=author,
                        platform="tripadvisor",
                        url=page_url,
                        response=response,
                    )
                    reviews.append(review)

                except Exception as e:
                    self.logger.warning(f"Error parsing TripAdvisor review: {e}")
                    continue

            # Break if we didn't find any new reviews on this page
            if len(reviews) == page_reviews_count:
                break

            await asyncio.sleep(2)  # Rate limiting

        return reviews

    async def extract_business_info(self, url: str) -> BusinessInfo | None:
        """Extract business information from a URL.

        Args:
            url: Business page URL

        Returns:
            Business information or None if failed
        """
        platform = self._get_platform_from_url(url)
        if not platform:
            self.logger.warning(f"Unsupported platform for URL: {url}")
            return None

        content = await self.scrape_url(url)
        if not content:
            return None

        soup = BeautifulSoup(content, "html.parser")

        try:
            if platform == "yelp":
                return self._extract_yelp_business_info(soup, url)
            elif platform == "google":
                return self._extract_google_business_info(soup, url)
            elif platform == "tripadvisor":
                return self._extract_tripadvisor_business_info(soup, url)
            else:
                return None

        except Exception as e:
            self.logger.error(f"Error extracting business info from {url}: {e}")
            return None

    def _extract_yelp_business_info(self, soup: BeautifulSoup, url: str) -> BusinessInfo | None:
        """Extract business info from Yelp page."""
        # Business name
        name_elem = (
            soup.find("h1", {"data-testid": "business-name"})
            or soup.find("h1", class_=re.compile(r"css-.*"))
            or soup.find("title")
        )
        name = self._sanitize_text(name_elem.get_text() if name_elem else "")

        # Address
        address_elem = (
            soup.find("p", {"data-testid": "address"})
            or soup.find("address")
            or soup.find("div", class_=re.compile(r"address"))
        )
        address = self._sanitize_text(address_elem.get_text() if address_elem else None)

        # Phone
        phone_elem = soup.find("p", {"data-testid": "phone-number"}) or soup.find(
            "a", href=re.compile(r"tel:")
        )
        phone = self._sanitize_text(phone_elem.get_text() if phone_elem else None)

        # Rating
        rating_elem = soup.find("div", {"aria-label": re.compile(r"\d+(?:\.\d+)? star rating")})
        rating = None
        if rating_elem:
            rating_text = rating_elem.get("aria-label", "")
            rating_match = re.search(r"(\d+(?:\.\d+)?)", rating_text)
            if rating_match:
                rating = float(rating_match.group(1))

        # Review count
        review_count_elem = soup.find("a", {"data-testid": "reviews-link"})
        review_count = None
        if review_count_elem:
            count_text = review_count_elem.get_text()
            count_match = re.search(r"(\d+)", count_text.replace(",", ""))
            if count_match:
                review_count = int(count_match.group(1))

        # Categories
        category_elems = soup.find_all("a", {"data-testid": "business-categories"})
        categories = [self._sanitize_text(elem.get_text()) for elem in category_elems]

        if not name:
            return None

        return BusinessInfo(
            name=name,
            address=address,
            phone=phone,
            rating=rating,
            review_count=review_count,
            categories=categories,
            url=url,
        )

    def _extract_google_business_info(self, soup: BeautifulSoup, url: str) -> BusinessInfo | None:
        """Extract business info from Google Maps page."""
        # Business name
        name_elem = (
            soup.find("h1", {"data-attrid": "title"})
            or soup.find("h1", class_=re.compile(r"DUwDvf"))
            or soup.find("title")
        )
        name = self._sanitize_text(name_elem.get_text() if name_elem else "")

        # Address
        address_elem = soup.find("div", {"data-item-id": "address"}) or soup.find(
            "span", class_=re.compile(r"LrzXr")
        )
        address = self._sanitize_text(address_elem.get_text() if address_elem else None)

        # Phone
        phone_elem = soup.find("div", {"data-item-id": "phone"}) or soup.find(
            "a", href=re.compile(r"tel:")
        )
        phone = self._sanitize_text(phone_elem.get_text() if phone_elem else None)

        # Rating
        rating_elem = soup.find("div", class_=re.compile(r"F7nice"))
        rating = None
        if rating_elem:
            rating_text = rating_elem.get_text()
            rating_match = re.search(r"(\d+(?:\.\d+)?)", rating_text)
            if rating_match:
                rating = float(rating_match.group(1))

        # Review count
        review_count_elem = soup.find("a", class_=re.compile(r"HHrUdb"))
        review_count = None
        if review_count_elem:
            count_text = review_count_elem.get_text()
            count_match = re.search(r"(\d+)", count_text.replace(",", ""))
            if count_match:
                review_count = int(count_match.group(1))

        # Categories
        category_elem = soup.find("div", class_=re.compile(r"YhemCb"))
        categories = [self._sanitize_text(category_elem.get_text())] if category_elem else []

        if not name:
            return None

        return BusinessInfo(
            name=name,
            address=address,
            phone=phone,
            rating=rating,
            review_count=review_count,
            categories=categories,
            url=url,
        )

    def _extract_tripadvisor_business_info(
        self, soup: BeautifulSoup, url: str
    ) -> BusinessInfo | None:
        """Extract business info from TripAdvisor page."""
        # Business name
        name_elem = (
            soup.find("h1", {"data-test-id": "restaurant-detail-info"})
            or soup.find("h1", id="HEADING")
            or soup.find("title")
        )
        name = self._sanitize_text(name_elem.get_text() if name_elem else "")

        # Address
        address_elem = soup.find(
            "div", class_=re.compile(r"restaurants-details-card-TagCategories__address")
        )
        address = self._sanitize_text(address_elem.get_text() if address_elem else None)

        # Phone
        phone_elem = soup.find("a", href=re.compile(r"tel:"))
        phone = self._sanitize_text(phone_elem.get_text() if phone_elem else None)

        # Rating
        rating_elem = soup.find("svg", {"aria-label": re.compile(r"\d+(?:\.\d+)? of 5 bubbles")})
        rating = None
        if rating_elem:
            rating_text = rating_elem.get("aria-label", "")
            rating_match = re.search(r"(\d+(?:\.\d+)?)", rating_text)
            if rating_match:
                rating = float(rating_match.group(1))

        # Review count
        review_count_elem = soup.find("a", class_=re.compile(r"reviewsCount"))
        review_count = None
        if review_count_elem:
            count_text = review_count_elem.get_text()
            count_match = re.search(r"(\d+)", count_text.replace(",", ""))
            if count_match:
                review_count = int(count_match.group(1))

        # Categories
        category_elems = soup.find_all("a", class_=re.compile(r"cuisine"))
        categories = [self._sanitize_text(elem.get_text()) for elem in category_elems]

        if not name:
            return None

        return BusinessInfo(
            name=name,
            address=address,
            phone=phone,
            rating=rating,
            review_count=review_count,
            categories=categories,
            url=url,
        )

    async def search_business(self, business_name: str, location: str, platform: str) -> str | None:
        """Search for a business and return its URL.

        Args:
            business_name: Name of the business
            location: Location (city, state, etc.)
            platform: Platform to search on (yelp, google, tripadvisor)

        Returns:
            Business URL or None if not found
        """
        platform = platform.lower()

        # Construct search URL based on platform
        search_url = self._build_search_url(business_name, location, platform)
        if not search_url:
            self.logger.error(f"Unable to build search URL for platform: {platform}")
            return None

        content = await self.scrape_url(search_url)
        if not content:
            return None

        soup = BeautifulSoup(content, "html.parser")

        try:
            if platform == "yelp":
                return self._extract_yelp_business_url(soup)
            elif platform == "google":
                return self._extract_google_business_url(soup)
            elif platform == "tripadvisor":
                return self._extract_tripadvisor_business_url(soup)
            else:
                return None

        except Exception as e:
            self.logger.error(f"Error extracting business URL from {search_url}: {e}")
            return None

    def _build_search_url(self, business_name: str, location: str, platform: str) -> str | None:
        """Build search URL for the specified platform."""
        encoded_name = urllib.parse.quote_plus(business_name)
        encoded_location = urllib.parse.quote_plus(location)

        if platform == "yelp":
            return (
                f"https://www.yelp.com/search?find_desc={encoded_name}&find_loc={encoded_location}"
            )
        elif platform == "google":
            return f"https://www.google.com/maps/search/{encoded_name}+{encoded_location}"
        elif platform == "tripadvisor":
            return f"https://www.tripadvisor.com/Search?q={encoded_name}+{encoded_location}&searchSessionId=000&searchNearby=false&ssrc=e&geo=1"
        else:
            return None

    def _extract_yelp_business_url(self, soup: BeautifulSoup) -> str | None:
        """Extract the first business URL from Yelp search results."""
        # Look for business links in search results
        business_links = soup.find_all("a", {"data-testid": "business-name"}) or soup.find_all(
            "a", href=re.compile(r"/biz/[^/]+$")
        )

        if business_links:
            href = business_links[0].get("href")
            if href:
                if href.startswith("/biz/"):
                    return f"https://www.yelp.com{href}"
                elif href.startswith("https://www.yelp.com/biz/"):
                    return href

        return None

    def _extract_google_business_url(self, soup: BeautifulSoup) -> str | None:
        """Extract the first business URL from Google Maps search results."""
        # Google Maps URLs are complex, look for data-cid or place_id
        business_links = soup.find_all("a", {"data-cid": True})

        if business_links:
            data_cid = business_links[0].get("data-cid")
            if data_cid:
                return f"https://www.google.com/maps/place/?cid={data_cid}"

        # Alternative: look for place URLs
        place_links = soup.find_all("a", href=re.compile(r"/maps/place/"))
        if place_links:
            href = place_links[0].get("href")
            if href and href.startswith("/"):
                return f"https://www.google.com{href}"
            elif href and href.startswith("https://maps.google.com"):
                return href

        return None

    def _extract_tripadvisor_business_url(self, soup: BeautifulSoup) -> str | None:
        """Extract the first business URL from TripAdvisor search results."""
        # Look for restaurant links
        business_links = soup.find_all(
            "a", href=re.compile(r"/Restaurant_Review-")
        ) or soup.find_all("a", href=re.compile(r"/ShowUserReviews-"))

        if business_links:
            href = business_links[0].get("href")
            if href:
                if href.startswith("/Restaurant_Review-"):
                    return f"https://www.tripadvisor.com{href}"
                elif href.startswith("https://www.tripadvisor.com/Restaurant_Review-"):
                    return href

        return None

    def _get_platform_from_url(self, url: str) -> str | None:
        """Determine platform from URL.

        Args:
            url: URL to analyze

        Returns:
            Platform name or None
        """
        domain = urlparse(url).netloc.lower()
        if "yelp" in domain:
            return "yelp"
        elif "google" in domain or "maps.google" in domain:
            return "google"
        elif "tripadvisor" in domain:
            return "tripadvisor"
        return None

    def _generate_review_hash(self, review_text: str, author: str) -> str:
        """Generate hash for review deduplication.

        Args:
            review_text: Review content
            author: Review author

        Returns:
            SHA256 hash of review
        """
        content = f"{author}:{review_text}".encode()
        return hashlib.sha256(content).hexdigest()

    def _sanitize_text(self, text: str | None) -> str:
        """Sanitize text by removing extra whitespace.

        Args:
            text: Text to sanitize

        Returns:
            Sanitized text
        """
        if not text:
            return ""
        # Remove extra whitespace and newlines
        text = re.sub(r"\s+", " ", text)
        return text.strip()
