"""Google Reviews specific scraper implementation."""

import asyncio
import re
import time
import uuid
from datetime import datetime
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from pyppeteer import launch
from pyppeteer_stealth import stealth

from app.models.scraping import BusinessInfo, Review
from app.telemetry.logger import get_logger


class GoogleReviewsScraper:
    """Scraper specifically for Google Reviews."""

    def __init__(self, headless: bool = True, timeout: int = 30000):
        """Initialize Google Reviews scraper.

        Args:
            headless: Run browser in headless mode
            timeout: Timeout in milliseconds
        """
        self.headless = headless
        self.timeout = timeout
        self.browser = None
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36 GoogleReviewsBot/1.0"
        )
        self.logger = get_logger("google_reviews_scraper")

    async def scrape_reviews(self, url: str, max_reviews: int = 100) -> list[Review]:
        """Scrape reviews from Google Maps business page.

        Args:
            url: Google Maps business URL
            max_reviews: Maximum number of reviews to scrape

        Returns:
            List of Review objects
        """
        correlation_id = str(uuid.uuid4())
        start_time = time.time()
        reviews = []
        browser = None

        self.logger.info(
            "Starting Google Reviews scraping operation",
            extra={
                "correlation_id": correlation_id,
                "url": url,
                "max_reviews": max_reviews,
                "operation": "scrape_reviews",
                "timestamp": datetime.now().isoformat(),
            },
        )

        try:
            self.logger.info(
                "Launching browser for reviews scraping",
                extra={
                    "correlation_id": correlation_id,
                    "headless": self.headless,
                    "timeout_ms": self.timeout,
                    "operation": "browser_launch",
                },
            )

            browser = await launch(
                {
                    "headless": self.headless,
                    "args": [
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                        f"--user-agent={self.user_agent}",
                    ],
                }
            )

            page = await browser.newPage()
            await stealth(page)
            await page.setUserAgent(self.user_agent)

            # Navigate to the Google Maps page
            self.logger.info(
                "Navigating to Google Maps page",
                extra={
                    "correlation_id": correlation_id,
                    "url": url,
                    "operation": "page_navigation",
                },
            )
            await page.goto(url, {"waitUntil": "networkidle2", "timeout": self.timeout})

            # Click on reviews tab if needed
            try:
                reviews_tab = await page.waitForSelector(
                    'button[aria-label*="Reviews"]', {"timeout": 5000}
                )
                if reviews_tab:
                    self.logger.info(
                        "Clicking reviews tab",
                        extra={"correlation_id": correlation_id, "operation": "reviews_tab_click"},
                    )
                    await reviews_tab.click()
                    await asyncio.sleep(2)
            except Exception as e:
                self.logger.warning(
                    "Could not find or click reviews tab, proceeding anyway",
                    extra={
                        "correlation_id": correlation_id,
                        "error": str(e),
                        "operation": "reviews_tab_click",
                    },
                )

            # Scroll to load more reviews
            scrollable_div = await page.querySelector('[role="main"]')
            if not scrollable_div:
                scrollable_div = await page.querySelector(".m6QErb.DxyBCb")

            previous_height = 0
            scroll_attempts = 0
            max_scrolls = min(20, max_reviews // 10)

            self.logger.info(
                "Starting scroll operation to load reviews",
                extra={
                    "correlation_id": correlation_id,
                    "max_scrolls": max_scrolls,
                    "target_reviews": max_reviews,
                    "operation": "scroll_start",
                },
            )

            while scroll_attempts < max_scrolls:
                if scrollable_div:
                    await page.evaluate(
                        "(element) => element.scrollTop = element.scrollHeight", scrollable_div
                    )
                else:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

                await asyncio.sleep(2)

                current_height = await page.evaluate("() => document.body.scrollHeight")

                if current_height == previous_height:
                    self.logger.info(
                        "Scroll reached end, no more content to load",
                        extra={
                            "correlation_id": correlation_id,
                            "scroll_attempts": scroll_attempts,
                            "operation": "scroll_end",
                        },
                    )
                    break

                previous_height = current_height
                scroll_attempts += 1

            # Get page content
            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")

            # Find review containers
            review_elements = soup.find_all("div", {"data-review-id": True})
            if not review_elements:
                review_elements = soup.find_all("div", class_="jftiEf")

            self.logger.info(
                "Found review elements on page",
                extra={
                    "correlation_id": correlation_id,
                    "total_elements_found": len(review_elements),
                    "max_to_process": min(len(review_elements), max_reviews),
                    "operation": "reviews_extraction",
                },
            )

            for review_elem in review_elements[:max_reviews]:
                try:
                    # Extract review text
                    text_elem = review_elem.find("span", class_="wiI7pd")
                    if not text_elem:
                        text_elem = review_elem.find("div", class_="MyEned")
                    text = text_elem.get_text().strip() if text_elem else ""

                    if not text:
                        continue

                    # Extract rating
                    rating = 0.0
                    rating_elem = review_elem.find("span", class_="kvMYJc")
                    if rating_elem:
                        aria_label = rating_elem.get("aria-label", "")
                        rating_match = re.search(r"(\d+)", aria_label)
                        if rating_match:
                            rating = float(rating_match.group(1))

                    # Extract author
                    author_elem = review_elem.find("div", class_="d4r55")
                    if not author_elem:
                        author_elem = review_elem.find("span", class_="X43Kjb")
                    author = author_elem.get_text().strip() if author_elem else "Anonymous"

                    # Extract date
                    date_elem = review_elem.find("span", class_="rsqaWe")
                    date = (
                        date_elem.get_text().strip()
                        if date_elem
                        else datetime.now().strftime("%Y-%m-%d")
                    )

                    # Extract owner response
                    response = None
                    response_elem = review_elem.find("div", class_="CDe7pd")
                    if response_elem:
                        response = response_elem.get_text().strip()

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
                    self.logger.warning(
                        "Failed to parse individual review element",
                        extra={
                            "correlation_id": correlation_id,
                            "error": str(e),
                            "operation": "review_parse_error",
                        },
                    )
                    continue

        except Exception as e:
            end_time = time.time()
            self.logger.error(
                "Google Reviews scraping operation failed",
                extra={
                    "correlation_id": correlation_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_seconds": end_time - start_time,
                    "reviews_scraped": len(reviews),
                    "operation": "scrape_reviews_error",
                },
            )
            raise

        finally:
            if browser:
                self.logger.info(
                    "Closing browser",
                    extra={"correlation_id": correlation_id, "operation": "browser_close"},
                )
                await browser.close()

        end_time = time.time()
        self.logger.info(
            "Google Reviews scraping operation completed successfully",
            extra={
                "correlation_id": correlation_id,
                "reviews_scraped": len(reviews),
                "duration_seconds": end_time - start_time,
                "reviews_per_second": len(reviews) / (end_time - start_time)
                if end_time > start_time
                else 0,
                "operation": "scrape_reviews_complete",
            },
        )

        return reviews

    async def search_business(self, business_name: str, location: str) -> str | None:
        """Search for a business on Google Maps.

        Args:
            business_name: Name of the business
            location: Location to search in

        Returns:
            Google Maps URL of the business or None
        """
        correlation_id = str(uuid.uuid4())
        start_time = time.time()
        browser = None

        self.logger.info(
            "Starting business search operation",
            extra={
                "correlation_id": correlation_id,
                "business_name": business_name,
                "location": location,
                "operation": "search_business",
                "timestamp": datetime.now().isoformat(),
            },
        )

        try:
            browser = await launch(
                {
                    "headless": self.headless,
                    "args": [
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        f"--user-agent={self.user_agent}",
                    ],
                }
            )

            page = await browser.newPage()
            await stealth(page)
            await page.setUserAgent(self.user_agent)

            # Build search URL
            query = f"{business_name} {location}"
            search_url = f"https://www.google.com/maps/search/{quote_plus(query)}"

            self.logger.info(
                "Navigating to search page",
                extra={
                    "correlation_id": correlation_id,
                    "search_url": search_url,
                    "query": query,
                    "operation": "search_navigation",
                },
            )

            # Navigate to search page
            await page.goto(search_url, {"waitUntil": "networkidle2", "timeout": self.timeout})
            await asyncio.sleep(3)

            # Click on the first result
            first_result = await page.querySelector('[role="article"] a[href*="/maps/place/"]')
            if not first_result:
                first_result = await page.querySelector('a[data-value*="0x"]')

            if first_result:
                self.logger.info(
                    "Found and clicking first search result",
                    extra={"correlation_id": correlation_id, "operation": "click_first_result"},
                )
                await first_result.click()
                await asyncio.sleep(2)

                # Get the current URL
                current_url = page.url
                if "/maps/place/" in current_url:
                    end_time = time.time()
                    self.logger.info(
                        "Business search completed successfully",
                        extra={
                            "correlation_id": correlation_id,
                            "found_url": current_url,
                            "duration_seconds": end_time - start_time,
                            "operation": "search_business_success",
                        },
                    )
                    return current_url

            end_time = time.time()
            self.logger.warning(
                "No business found in search results",
                extra={
                    "correlation_id": correlation_id,
                    "business_name": business_name,
                    "location": location,
                    "duration_seconds": end_time - start_time,
                    "operation": "search_business_not_found",
                },
            )
            return None

        except Exception as e:
            end_time = time.time()
            self.logger.error(
                "Business search operation failed",
                extra={
                    "correlation_id": correlation_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "business_name": business_name,
                    "location": location,
                    "duration_seconds": end_time - start_time,
                    "operation": "search_business_error",
                },
            )
            raise

        finally:
            if browser:
                self.logger.info(
                    "Closing browser after search",
                    extra={"correlation_id": correlation_id, "operation": "browser_close"},
                )
                await browser.close()

    async def extract_business_info(self, url: str) -> BusinessInfo | None:
        """Extract business information from Google Maps page.

        Args:
            url: Google Maps business URL

        Returns:
            BusinessInfo object or None
        """
        correlation_id = str(uuid.uuid4())
        start_time = time.time()
        browser = None

        self.logger.info(
            "Starting business info extraction",
            extra={
                "correlation_id": correlation_id,
                "url": url,
                "operation": "extract_business_info",
                "timestamp": datetime.now().isoformat(),
            },
        )

        try:
            browser = await launch(
                {
                    "headless": self.headless,
                    "args": [
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        f"--user-agent={self.user_agent}",
                    ],
                }
            )

            page = await browser.newPage()
            await stealth(page)
            await page.setUserAgent(self.user_agent)

            # Navigate to the page
            self.logger.info(
                "Navigating to business page for info extraction",
                extra={
                    "correlation_id": correlation_id,
                    "url": url,
                    "operation": "business_page_navigation",
                },
            )
            await page.goto(url, {"waitUntil": "networkidle2", "timeout": self.timeout})
            await asyncio.sleep(2)

            # Get page content
            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")

            # Extract business name
            name_elem = soup.find("h1", class_="DUwDvf")
            if not name_elem:
                name_elem = soup.find("h1", {"data-attrid": "title"})
            name = name_elem.get_text().strip() if name_elem else None

            if not name:
                end_time = time.time()
                self.logger.warning(
                    "Could not extract business name from page",
                    extra={
                        "correlation_id": correlation_id,
                        "url": url,
                        "duration_seconds": end_time - start_time,
                        "operation": "business_info_no_name",
                    },
                )
                return None

            # Extract address
            address = None
            address_elem = soup.find("button", {"data-item-id": "address"})
            if address_elem:
                address_text = address_elem.find("div", class_="fontBodyMedium")
                if address_text:
                    address = address_text.get_text().strip()

            # Extract phone
            phone = None
            phone_elem = soup.find("button", {"data-item-id": re.compile("phone:tel:")})
            if phone_elem:
                phone_text = phone_elem.find("div", class_="fontBodyMedium")
                if phone_text:
                    phone = phone_text.get_text().strip()

            # Extract rating
            rating = None
            rating_elem = soup.find("div", class_="F7nice")
            if rating_elem:
                rating_text = rating_elem.find("span")
                if rating_text:
                    try:
                        rating = float(rating_text.get_text().strip())
                    except (ValueError, AttributeError):
                        pass

            # Extract review count
            review_count = None
            review_elem = soup.find("button", {"aria-label": re.compile(r"\d+\s+reviews")})
            if review_elem:
                aria_label = review_elem.get("aria-label", "")
                count_match = re.search(r"(\d+(?:,\d+)*)\s+reviews", aria_label)
                if count_match:
                    review_count = int(count_match.group(1).replace(",", ""))

            # Extract categories
            categories = []
            category_elem = soup.find("button", {"jsaction": re.compile("category")})
            if category_elem:
                categories.append(category_elem.get_text().strip())

            business_info = BusinessInfo(
                name=name,
                address=address,
                phone=phone,
                rating=rating,
                review_count=review_count,
                categories=categories,
                url=url,
            )

            end_time = time.time()
            self.logger.info(
                "Business info extraction completed successfully",
                extra={
                    "correlation_id": correlation_id,
                    "business_name": name,
                    "has_address": address is not None,
                    "has_phone": phone is not None,
                    "rating": rating,
                    "review_count": review_count,
                    "categories_count": len(categories),
                    "duration_seconds": end_time - start_time,
                    "operation": "extract_business_info_success",
                },
            )

            return business_info

        except Exception as e:
            end_time = time.time()
            self.logger.error(
                "Business info extraction failed",
                extra={
                    "correlation_id": correlation_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "url": url,
                    "duration_seconds": end_time - start_time,
                    "operation": "extract_business_info_error",
                },
            )
            raise

        finally:
            if browser:
                self.logger.info(
                    "Closing browser after business info extraction",
                    extra={"correlation_id": correlation_id, "operation": "browser_close"},
                )
                await browser.close()
