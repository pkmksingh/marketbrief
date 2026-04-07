import streamlit as st
import feedparser
import pandas as pd
import requests
import re
from datetime import datetime, timedelta, timezone
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import concurrent.futures
from urllib.parse import urlparse

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Market Brief",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize sentiment analyzer
analyzer = SentimentIntensityAnalyzer()

# --- HELPER FUNCTIONS ---
def format_time_ago(dt):
    if not dt: return "Now"
    now = datetime.now(timezone.utc)
    diff = now - dt
    seconds = diff.total_seconds()
    if seconds < 60: return "Now"
    if seconds < 3600: return f"{int(seconds // 60)}m ago"
    if seconds < 86400: return f"{int(seconds // 3600)}h ago"
    return f"{int(seconds // 86400)}d ago"

# --- STYLING ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Roboto+Mono:wght@400;500&display=swap');
    
    * { font-family: 'Outfit', sans-serif; }
    
    .stApp {
        background: #0f172a;
    }
    
    .stMetric {
        background: rgba(30, 41, 59, 0.7);
        padding: 10px;
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }

    /* High-Density Row Style */
    .news-row {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 6px 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        transition: background 0.2s;
        width: 100%;
        border-left: 3px solid transparent;
    }
    
    .news-row:hover {
        background: rgba(56, 189, 248, 0.05);
    }

    /* Sentiment Glow Indicators */
    .glow-pos { border-left-color: #4ade80 !important; }
    .glow-neg { border-left-color: #f87171 !important; }
    .glow-neu { border-left-color: rgba(148, 163, 184, 0.2) !important; }

    .source-tag {
        flex-shrink: 0;
        width: 120px;
        font-size: 0.75rem;
        font-weight: 600;
        color: #38bdf8;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .time-tag {
        flex-shrink: 0;
        width: 65px;
        font-family: 'Roboto Mono', monospace;
        font-size: 0.72rem;
        color: #94a3b8;
    }

    .headline-link {
        flex-grow: 1;
        text-decoration: none !important;
        color: #f8fafc !important;
        font-size: 0.95rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .sentiment-tag {
        flex-shrink: 0;
        width: 80px;
        text-align: right;
        font-size: 0.75rem;
        font-weight: 500;
    }

    .impact-high { color: #f87171; font-weight: 700; text-decoration: underline; }
    .impact-pos { color: #4ade80; font-weight: 700; }
    .impact-neg { color: #f87171; font-weight: 700; }

    /* Minimalist Top Search styling */
    .stTextInput input {
        border-radius: 4px !important;
        background: rgba(30, 41, 59, 0.8) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        color: white !important;
        font-size: 0.85rem !important;
    }

    /* Remove Streamlit elements for more space */
    #MainMenu, footer, header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- DATA CONSTANTS ---
RSS_FEEDS = [
    'https://news.google.com/rss/search?q=stock+market+india+NSE+BSE+finance&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=stock+market+india+business&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:moneycontrol.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:financialexpress.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:business-standard.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms',
    'https://www.livemint.com/rss/markets',
    'https://news.google.com/rss/search?q=site:thehindubusinessline.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:pulse.zerodha.com&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:in.investing.com+intitle:(stocks+OR+markets+OR+india)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:web.stockedge.com&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:groww.in&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:ndtvprofit.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:cnbctv18.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:zeebiz.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:goodreturns.in+intitle:(stocks+OR+markets+OR+shares)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:ticker.finology.in&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:moneyworks4me.com&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:trendlyne.com&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:tickertape.in&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:equitymaster.com+intitle:(stocks+OR+markets+OR+shares)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:marketsmojo.com&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:fortuneindia.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:businessworld.in+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:outlookbusiness.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:money.rediff.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:reuters.com+intitle:(india+AND+(stocks+OR+markets+OR+nse+OR+bse))&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:timesofindia.indiatimes.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://www.businesstoday.in/rss/markets',
    'https://news.google.com/rss/search?q=site:screener.in&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:capitalmind.in&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:bseindia.com+corporate+announcements&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=site:nseindia.com+corporate+announcements&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=intitle:(dividend+OR+buyback+OR+"bonus+issue"+OR+"stock+split")+NSE+BSE&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=intitle:("quarterly+results"+OR+"earnings"+OR+"PAT+growth")+NSE+BSE&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=intitle:("FII+buying"+OR+"DII+selling"+OR+"bulk+deal"+OR+"block+deal")+NSE+BSE&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=intitle:("SEBI"+OR+"RBI+monetary+policy"+OR+"repo+rate")+India&hl=en-IN&gl=IN&ceid=IN:en'
]

IMPACT_KEYWORDS = {
    'high': ['crash', 'crisis', 'urgent', 'breaking', 'collapsed', 'warns', 'surge', 'plunge', 'lockdown', 'rating', 'result', 'focus'],
    'pos': ['profit', 'growth', 'record', 'dividend', 'buyback', 'partnership', 'acquired', 'expansion', 'jump', 'bullish', 'buy'],
    'neg': ['loss', 'fall', 'slump', 'down', 'decline', 'investigation', 'scam', 'penalty', 'lawsuit', 'bearish', 'sell']
}

# Pre-compile Regex Patterns for speed
IMPACT_REGEX = {
    impact_type: re.compile(r'\b(' + '|'.join(words) + r')\b', re.IGNORECASE)
    for impact_type, words in IMPACT_KEYWORDS.items()
}

# --- HELPER FUNCTIONS ---
def get_source_name(url, title=""):
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')
    
    # Special Handling for Google News redirects
    if 'news.google.com' in domain and ' - ' in title:
        return title.split(' - ')[-1].strip()
    
    # Mapping for professional look
    mapping = {
        'moneycontrol.com': 'Moneycontrol',
        'financialexpress.com': 'Financial Express',
        'business-standard.com': 'Business Standard',
        'economictimes.indiatimes.com': 'Economic Times',
        'livemint.com': 'LiveMint',
        'pulse.zerodha.com': 'Zerodha Pulse',
        'businesstoday.in': 'Business Today',
        'reuters.com': 'Reuters India',
        'ndtvprofit.com': 'NDTV Profit',
        'cnbctv18.com': 'CNBC TV18',
        'zeebiz.com': 'Zee Business',
        'bloombergquint.com': 'Bloomberg Quint',
        'ndtv.com': 'NDTV Profit',
        'thehindubusinessline.com': 'BusinessLine',
        'fortuneindia.com': 'Fortune India',
        'goodreturns.in': 'GoodReturns',
        'ticker.finology.in': 'Finology',
        'groww.in': 'Groww',
        'stockedge.com': 'StockEdge'
    }
    
    if domain in mapping:
        return mapping[domain]
    
    # Better fallback for nested subdomains (e.g., in.investing.com -> Investing)
    parts = domain.split('.')
    if len(parts) >= 2:
        # Get the name before .com, .in, etc.
        name = parts[-2].capitalize()
        return name
    return domain.capitalize()

def highlight_impact(title):
    highlighted = title
    for impact_type, pattern in IMPACT_REGEX.items():
        highlighted = pattern.sub(f'<span class="impact-{impact_type}">\\1</span>', highlighted)
    return highlighted

@st.cache_data(ttl=600)  # Cache for 10 minutes
def fetch_all_news():
    all_news = []
    # Expand window to 5 days for more coverage
    cutoff = datetime.now(timezone.utc) - timedelta(hours=120)
    
    def fetch_feed(url):
        try:
            feed = feedparser.parse(url)
            items = []
            for entry in feed.entries:
                link = entry.get('link', '#')
                source = get_source_name(link, entry.get('title', ''))
                title = entry.get('title', '')
                if len(title.split()) < 5: continue
                
                # Date filtering (Last 48 Hours) - Ensure UTC
                pub_date = None
                if 'published_parsed' in entry:
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif 'published' in entry:
                    try:
                        pub_date = pd.to_datetime(entry.published).tz_convert('UTC')
                    except: pass
                
                if pub_date and pub_date < cutoff:
                    continue

                sentiment_scores = analyzer.polarity_scores(title)
                score = sentiment_scores['compound']
                label = 'Positive' if score > 0.05 else ('Negative' if score < -0.05 else 'Neutral')
                
                items.append({
                    'title': title,
                    'link': entry.get('link', '#'),
                    'source': source,
                    'pubDate': pub_date or datetime.now(timezone.utc),
                    'score': score,
                    'label': label
                })
            return items
        except:
            return []

    # Parallelize feed fetching
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        results = executor.map(fetch_feed, RSS_FEEDS)
        for res in results:
            all_news.extend(res)
            
    if not all_news:
        return pd.DataFrame()

    df = pd.DataFrame(all_news).drop_duplicates(subset=['link'])
    if not df.empty:
        # Ensure sorting by date works correctly
        df['pubDate'] = pd.to_datetime(df['pubDate'], utc=True)
        df = df.sort_values(by='pubDate', ascending=False)
    return df

@st.cache_data(ttl=60)  # Cache for 1 minute
def fetch_indices():
    tickers = {
        'NIFTY 50': '^NSEI',
        'SENSEX': '^BSESN',
        'BANK NIFTY': '^NSEBANK',
        'INDIA VIX': '^INDIAVIX'
    }
    results = {}
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    def fetch_single_index(name, ticker):
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d"
            response = requests.get(url, headers=headers, timeout=5)
            data = response.json()
            meta = data['chart']['result'][0]['meta']
            price = meta['regularMarketPrice']
            prev_close = meta['previousClose']
            change = price - prev_close
            change_pct = (change / prev_close) * 100
            return name, {'price': price, 'change': change, 'pct': change_pct}
        except:
            return name, {'price': 0.0, 'change': 0.0, 'pct': 0.0}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(fetch_single_index, name, ticker) for name, ticker in tickers.items()]
        for future in concurrent.futures.as_completed(futures):
            name, data = future.result()
            results[name] = data
            
    return results

# --- MAIN UI ---
def main():
    # 🔄 Auto-Refresh Script (Every 5 Minutes)
    st.markdown("""
    <script>
        setTimeout(function(){
            window.location.reload();
        }, 300000);
    </script>
    """, unsafe_allow_html=True)

    # --- ULTRA-COMPACT INDEXES (TOP) ---
    indices = fetch_indices()
    sorted_names = ['NIFTY 50', 'SENSEX', 'BANK NIFTY', 'INDIA VIX']
    col_idx = st.columns(4)
    
    for i, name in enumerate(sorted_names):
        if name in indices:
            val = indices[name]
            color = "#4ade80" if val['pct'] >= 0 else "#f87171"
            arrow = "▲" if val['pct'] >= 0 else "▼"
            # Ultra-compact custom HTML metric
            col_idx[i].markdown(f"""
                <div style="background: rgba(30, 41, 59, 0.7); padding: 4px 8px; border-radius: 4px; border-left: 3px solid {color}; line-height: 1;">
                    <div style="font-size: 0.65rem; color: #94a3b8; font-weight: 700;">{name}</div>
                    <div style="font-size: 1rem; font-weight: 700; color: white;">{val['price']:.0f} <span style="font-size: 0.7rem; color: {color};">{arrow} {abs(val['pct']):.2f}%</span></div>
                </div>
            """, unsafe_allow_html=True)
    
    st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)

    # 🔍 Minimalist Inline Search (Full Width)
    search_query = st.text_input("", placeholder="🔍 Search market headlines...", label_visibility="collapsed")
    
    with st.spinner("Syncing latest market news..."):
        df_news = fetch_all_news()
    
    if df_news.empty:
        st.warning("No data found.")
        return

    # Filter with Search
    if search_query:
        df_news = df_news[df_news['title'].str.contains(search_query, case=False)]

    # Header Row
    st.markdown("""
    <div style="display: flex; gap: 12px; padding: 10px 12px; border-bottom: 2px solid rgba(255,255,255,0.1); font-weight: 700; font-size: 0.75rem; color: #64748b; letter-spacing: 1px;">
        <div style="width: 120px;">SOURCE</div>
        <div style="width: 65px;">TIME</div>
        <div style="flex-grow: 1;">HEADLINE (LIVE)</div>
        <div style="width: 80px; text-align: right;">SENTIMENT</div>
    </div>
    """, unsafe_allow_html=True)

    # Render Batch 1-Line News Feed (Limit Expanded to 500)
    for _, row in df_news.head(500).iterrows():
        highlighted = highlight_impact(row['title'])
        rel_time = format_time_ago(row['pubDate'])
        
        # Determine Glow Class
        glow_class = "glow-pos" if row['score'] > 0.05 else ("glow-neg" if row['score'] < -0.05 else "glow-neu")
        sentiment_label_color = '#4ade80' if row['score'] > 0.05 else ('#f87171' if row['score'] < -0.05 else '#94a3b8')

        row_html = f"""
        <div class="news-row {glow_class}">
            <div class="source-tag">{row['source']}</div>
            <div class="time-tag">{rel_time}</div>
            <a href="{row['link']}" target="_blank" class="headline-link">{highlighted}</a>
            <div class="sentiment-tag" style="color: {sentiment_label_color};">
                {row['label']}
            </div>
        </div>
        """
        st.markdown(row_html, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
