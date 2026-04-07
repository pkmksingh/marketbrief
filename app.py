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
    page_title="Bull & Bear | Stock Sentiment Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize sentiment analyzer
analyzer = SentimentIntensityAnalyzer()

# --- STYLING ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    * { font-family: 'Outfit', sans-serif; }
    
    .stApp {
        background: #0f172a;
    }
    
    .stMetric {
        background: rgba(30, 41, 59, 0.7);
        padding: 15px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
    }
    
    .news-card {
        background: rgba(30, 41, 59, 0.5);
        padding: 20px;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 15px;
        transition: all 0.3s ease;
    }
    
    .news-card:hover {
        transform: translateY(-2px);
        border-color: rgba(56, 189, 248, 0.5);
        background: rgba(30, 41, 59, 0.8);
    }
    
    .impact-high { color: #f87171; font-weight: 700; text-decoration: underline; }
    .impact-pos { color: #4ade80; font-weight: 700; }
    .impact-neg { color: #f87171; font-weight: 700; }
    
    .source-tag {
        background: rgba(56, 189, 248, 0.2);
        color: #38bdf8;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        margin-right: 10px;
    }
    
    .time-tag {
        color: #94a3b8;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# --- DATA CONSTANTS ---
RSS_FEEDS = [
    'https://news.google.com/rss/search?q=when:24h+stock+market+india+NSE+BSE+finance&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+stock+market+india+business&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:moneycontrol.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:financialexpress.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:business-standard.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms',
    'https://www.livemint.com/rss/markets',
    'https://news.google.com/rss/search?q=when:24h+site:thehindubusinessline.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:pulse.zerodha.com&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:in.investing.com+intitle:(stocks+OR+markets+OR+india)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:web.stockedge.com&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:groww.in&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:ndtvprofit.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:cnbctv18.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:zeebiz.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:goodreturns.in+intitle:(stocks+OR+markets+OR+shares)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:ticker.finology.in&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:moneyworks4me.com&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:trendlyne.com&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:tickertape.in&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:equitymaster.com+intitle:(stocks+OR+markets+OR+shares)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:marketsmojo.com&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:fortuneindia.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:businessworld.in+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:outlookbusiness.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:money.rediff.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:reuters.com+intitle:(india+AND+(stocks+OR+markets+OR+nse+OR+bse))&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:timesofindia.indiatimes.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
    'https://www.businesstoday.in/rss/markets',
    'https://news.google.com/rss/search?q=when:24h+site:screener.in&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:capitalmind.in&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:bseindia.com+corporate+announcements&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+site:nseindia.com+corporate+announcements&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+intitle:(dividend+OR+buyback+OR+"bonus+issue"+OR+"stock+split")+NSE+BSE&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+intitle:("quarterly+results"+OR+"earnings"+OR+"PAT+growth")+NSE+BSE&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+intitle:("FII+buying"+OR+"DII+selling"+OR+"bulk+deal"+OR+"block+deal")+NSE+BSE&hl=en-IN&gl=IN&ceid=IN:en',
    'https://news.google.com/rss/search?q=when:24h+intitle:("SEBI"+OR+"RBI+monetary+policy"+OR+"repo+rate")+India&hl=en-IN&gl=IN&ceid=IN:en'
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
def get_source_name(url, feed_title):
    if 'moneycontrol.com' in url: return 'Moneycontrol'
    if 'financialexpress.com' in url: return 'Financial Express'
    if 'business-standard.com' in url: return 'Business Standard'
    if 'economictimes' in url: return 'Economic Times'
    if 'livemint' in url: return 'LiveMint'
    if 'zerodha.com' in url: return 'Zerodha Pulse'
    if 'businesstoday.in' in url: return 'Business Today'
    if 'reuters.com' in url: return 'Reuters India'
    return feed_title.replace('Google News - ', '') if feed_title else 'Market News'

def highlight_impact(title):
    highlighted = title
    for impact_type, pattern in IMPACT_REGEX.items():
        highlighted = pattern.sub(f'<span class="impact-{impact_type}">\\1</span>', highlighted)
    return highlighted

@st.cache_data(ttl=600)  # Cache for 10 minutes
def fetch_all_news():
    all_news = []
    # Make cutoff offset-aware for comparison
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    
    def fetch_feed(url):
        try:
            feed = feedparser.parse(url)
            source = get_source_name(url, feed.feed.get('title', ''))
            items = []
            for entry in feed.entries:
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
    # Sidebar Filters
    st.sidebar.title("🔍 Filters")
    search_query = st.sidebar.text_input("Search headlines...")
    sentiment_filter = st.sidebar.multiselect(
        "Sentiment", 
        ['Positive', 'Negative', 'Neutral'], 
        default=['Positive', 'Negative', 'Neutral']
    )
    
    # Header & Indices
    st.title("🎯 Bull & Bear")
    st.markdown("### Market Sentiment Dashboard")
    
    indices = fetch_indices()
    # Sort indices for consistent layout
    sorted_names = ['NIFTY 50', 'SENSEX', 'BANK NIFTY', 'INDIA VIX']
    cols = st.columns(len(sorted_names))
    for i, name in enumerate(sorted_names):
        if name in indices:
            val = indices[name]
            cols[i].metric(
                name, 
                f"{val['price']:.2f}", 
                f"{val['pct']:.2f}%",
                delta_color="normal" if val['pct'] != 0 else "off"
            )
    
    st.divider()
    
    # Fetch News
    with st.spinner("Analyzing market pulse..."):
        df_news = fetch_all_news()
    
    if df_news.empty:
        st.warning("No news found. Check your connection or filters.")
        return

    # Filter Logic
    filtered_df = df_news[df_news['label'].isin(sentiment_filter)]
    if search_query:
        filtered_df = filtered_df[filtered_df['title'].str.contains(search_query, case=False)]
    
    # Layout: Chart and Feed
    col_chart, col_feed = st.columns([1, 2])
    
    with col_chart:
        st.subheader("Sentiment Distribution")
        if not filtered_df.empty:
            sentiment_counts = filtered_df['label'].value_counts()
            st.bar_chart(sentiment_counts)
            
            avg_score = filtered_df['score'].mean()
            st.metric("Avg Sentiment Score", f"{avg_score:.2f}", help="Range: -1 (Bearish) to +1 (Bullish)")
        else:
            st.info("No data for current filters.")

    with col_feed:
        st.subheader("Live Market Feed")
        if filtered_df.empty:
            st.info("No news matches your search/filter.")
        else:
            # Batch render cards for better performance
            for _, row in filtered_df.head(50).iterrows():
                highlighted = highlight_impact(row['title'])
                
                card_html = f"""
                <div class="news-card">
                    <div style="margin-bottom: 8px;">
                        <span class="source-tag">{row['source']}</span>
                        <span class="time-tag">{row['pubDate'].strftime('%H:%M')} UTC</span>
                    </div>
                    <a href="{row['link']}" target="_blank" style="text-decoration: none; color: inherit;">
                        <h4 style="margin: 0; line-height: 1.4;">{highlighted}</h4>
                    </a>
                    <div style="margin-top: 10px; font-size: 0.8rem; color: {'#4ade80' if row['score'] > 0 else '#f87171' if row['score'] < 0 else '#94a3b8'};">
                        Sentiment: {row['label']} ({row['score']:.2f})
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
