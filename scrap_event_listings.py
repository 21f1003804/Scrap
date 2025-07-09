
import asyncio
import aiohttp
import json
import time
import csv
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import random
from datetime import datetime
import ssl

# Try uvloop for performance
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    print("🚀 Using uvloop for maximum performance!")
except ImportError:
    print("⚡ Using standard asyncio")

class FastwebHubScraper:
    def __init__(self, max_workers=20, max_connections=60):
        self.max_workers = max_workers
        self.max_connections = max_connections
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0'
        ]
        
    def get_random_headers(self):
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }

    def extract_listings_from_page(self, html_content):
        """Extract listings from page HTML"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            index_data_script = soup.find('script', {'id': 'index-data'})
            
            if index_data_script and index_data_script.string:
                try:
                    data = json.loads(index_data_script.string.strip())
                    
                    if 'grid' in data and 'items' in data['grid']:
                        listings = data['grid']['items']
                        
                        grid_info = {
                            'currentPage': data['grid'].get('currentPage', 1),
                            'totalCount': data['grid'].get('totalCount', 0),
                            'pageSize': data['grid'].get('pageSize', 20),
                            'totalFilteredListings': data['grid'].get('totalFilteredListings', 0)
                        }
                        
                        return listings, grid_info
                        
                except json.JSONDecodeError as e:
                    print(f"❌ JSON parse error: {e}")
                    
        except Exception as e:
            print(f"❌ HTML parsing error: {e}")
        
        return [], {}

    async def fetch_page_async(self, session, url, page_num, semaphore):
        """Fetch single page"""
        async with semaphore:
            max_retries = 3
            
            for attempt in range(max_retries):
                try:
                    if page_num > 1:
                        await asyncio.sleep(random.uniform(0.05, 0.15))
                    
                    timeout = aiohttp.ClientTimeout(total=20, connect=8)
                    
                    async with session.get(url, headers=self.get_random_headers(), timeout=timeout, ssl=False) as response:
                        
                        if response.status == 200:
                            html_content = await response.text()
                            listings, grid_info = self.extract_listings_from_page(html_content)
                            
                            if listings:
                                print(f"✅ Page {page_num}: {len(listings)} listings")
                                return page_num, listings, grid_info
                            else:
                                print(f"⚠️  Page {page_num}: No listings found")
                                
                        elif response.status == 429:
                            wait_time = (2 ** attempt) + random.uniform(0.5, 1.5)
                            print(f"⏳ Rate limited page {page_num}, waiting {wait_time:.1f}s...")
                            await asyncio.sleep(wait_time)
                            continue
                            
                        elif response.status in [502, 503, 504]:
                            wait_time = random.uniform(1, 2)
                            print(f"🔄 Server error {response.status} on page {page_num}, retrying...")
                            await asyncio.sleep(wait_time)
                            continue
                            
                        else:
                            print(f"❌ Page {page_num}: HTTP {response.status}")
                            
                except asyncio.TimeoutError:
                    print(f"⏰ Timeout on page {page_num} (attempt {attempt + 1})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(random.uniform(0.5, 1))
                        
                except Exception as e:
                    print(f"❌ Page {page_num} error (attempt {attempt + 1}): {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(random.uniform(0.5, 1))
            
            print(f"💀 Failed page {page_num} after {max_retries} attempts")
            return page_num, [], {}

    def build_page_url(self, base_url, page_num):
        """Build URL for specific page"""
        parsed = urlparse(base_url)
        query_params = parse_qs(parsed.query)
        query_params['page'] = [str(page_num)]
        
        new_query = urlencode(query_params, doseq=True)
        new_url = urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            parsed.params, new_query, parsed.fragment
        ))
        
        return new_url

    async def scrape_all_pages_fast(self, base_url):
        """Fast async scraping"""
        print("🚀 Starting FAST webHub scraper...")
        print(f"🎯 URL: {base_url}")
        print(f"⚡ Workers: {self.max_workers}, Connections: {self.max_connections}")
        
        start_time = time.time()
        
        # SSL setup
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(
            limit=self.max_connections,
            limit_per_host=25,
            ttl_dns_cache=300,
            use_dns_cache=True,
            ssl=ssl_context
        )
        
        semaphore = asyncio.Semaphore(self.max_workers)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            # Get first page
            print("📊 Getting pagination info...")
            _, first_listings, grid_info = await self.fetch_page_async(session, base_url, 1, semaphore)
            
            if not first_listings:
                print("❌ Failed to get first page")
                return []
            
            # Calculate pagination
            total_listings = grid_info.get('totalFilteredListings', 0)
            page_size = grid_info.get('pageSize', 20)
            total_pages = (total_listings + page_size - 1) // page_size
            
            print(f"\n📊 Found {total_listings} total listings across {total_pages} pages")
            
            all_listings = first_listings.copy()
            
            if total_pages <= 1:
                print("✅ Only one page!")
                return all_listings
            
            # Create tasks for remaining pages
            page_tasks = []
            for page_num in range(2, total_pages + 1):
                page_url = self.build_page_url(base_url, page_num)
                task = self.fetch_page_async(session, page_url, page_num, semaphore)
                page_tasks.append(task)
            
            print(f"🔄 Launching {len(page_tasks)} async tasks...")
            
            # Execute in batches
            completed_pages = 0
            batch_size = min(self.max_workers * 2, len(page_tasks))
            
            for i in range(0, len(page_tasks), batch_size):
                batch = page_tasks[i:i + batch_size]
                
                print(f"🚀 Batch {i//batch_size + 1}/{(len(page_tasks) + batch_size - 1)//batch_size} ({len(batch)} pages)")
                
                results = await asyncio.gather(*batch, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        continue
                        
                    page_num, listings, _ = result
                    
                    if listings:
                        all_listings.extend(listings)
                        completed_pages += 1
                        
                        progress = (completed_pages / (total_pages - 1)) * 100
                        print(f"✅ Progress: {completed_pages}/{total_pages-1} ({progress:.1f}%) | Total: {len(all_listings)}")
                
                # Small delay between batches
                if i + batch_size < len(page_tasks):
                    await asyncio.sleep(0.1)
        
        elapsed = time.time() - start_time
        print(f"\n🎉 Scraping completed in {elapsed:.1f} seconds!")
        print(f"⚡ Rate: {len(all_listings)/elapsed:.1f} listings/second")
        
        return all_listings

    def extract_key_fields(self, listings):
        """Extract key fields from listings"""
        extracted_data = []
        
        for listing in listings:
            raw_price = listing.get('rawPrice', 0)
            price_usd = f"${raw_price / 100:.2f}" if raw_price else '$0.00'
            
            row_data = {
                'id': listing.get('id', ''),
                'section': listing.get('section', ''),
                'row': listing.get('row', ''),
                'seat': listing.get('seat', ''),
                'availableTickets': listing.get('availableTickets', 0),
                'rawPrice': raw_price,
                'priceUSD': price_usd,
                'ticketClass': listing.get('ticketClass', ''),
                'isSeatedTogether': listing.get('isSeatedTogether', False),
                'isCheapestListing': listing.get('isCheapestListing', False),
                'maxQuantity': listing.get('maxQuantity', 0),
            }
            
            # Add score info if available
            score_info = listing.get('inventoryListingScore', {})
            if score_info:
                row_data.update({
                    'discount': score_info.get('discount', 0),
                    'starRating': score_info.get('starRating', 0),
                    'dealScore': score_info.get('dealScore', 0),
                })
            
            extracted_data.append(row_data)
        
        return extracted_data

    def save_to_csv(self, listings, event_name="event"):
        """Save listings to CSV"""
        if not listings:
            print("❌ No listings to save")
            return None
        
        extracted_data = self.extract_key_fields(listings)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"webhub_{event_name}_{timestamp}.csv"
        
        if extracted_data:
            fieldnames = list(extracted_data[0].keys())
            
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(extracted_data)
                
                print(f"💾 Saved to: {filename}")
                print(f"📊 {len(fieldnames)} columns, {len(extracted_data)} rows")
                
                # Show price stats
                prices = [row['rawPrice'] for row in extracted_data if row['rawPrice'] > 0]
                if prices:
                    min_price = min(prices) / 100
                    max_price = max(prices) / 100
                    avg_price = sum(prices) / len(prices) / 100
                    print(f"💰 Price range: ${min_price:.2f} - ${max_price:.2f} (avg: ${avg_price:.2f})")
                
                return filename
                
            except Exception as e:
                print(f"❌ Error saving CSV: {e}")
                return None
        
        return None

async def main():
    """Main function"""
    print("🎵 FAST webHub Scraper")
    print("=" * 50)
    
    # Boston Celtics URL
    base_url = "https://www.webhub.com/matt-rife-new-york-tickets-7-18-2025/event/156391211/"
    
    scraper = FastwebHubScraper(max_workers=20, max_connections=60)
    
    all_listings = await scraper.scrape_all_pages_fast(base_url)
    
    if all_listings:
        print(f"\n🏆 SUCCESS! Found {len(all_listings)} listings")
        
        csv_file = scraper.save_to_csv(all_listings, "celtics")
        
        if csv_file:
            print(f"\n📄 Results saved to: {csv_file}")
            
    else:
        print(f"\n❌ No listings found")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


