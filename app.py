import streamlit as st
import feedparser
import pandas as pd
import requests
import re
from datetime import datetime, timedelta, timezone
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import concurrent.futures
from urllib.parse import urlparse
import streamlit.components.v1 as components

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

def get_source_name(url, title=""):
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')
    mapping = {
        'moneycontrol.com': 'Moneycontrol', 'financialexpress.com': 'Financial Express',
        'business-standard.com': 'Business Standard', 'economictimes.indiatimes.com': 'Economic Times',
        'livemint.com': 'LiveMint', 'pulse.zerodha.com': 'Zerodha Pulse',
        'businesstoday.in': 'Business Today', 'reuters.com': 'Reuters India',
        'ndtvprofit.com': 'NDTV Profit', 'cnbctv18.com': 'CNBC TV18',
        'zeebiz.com': 'Zee Business', 'bloombergquint.com': 'Bloomberg Quint',
        'thehindubusinessline.com': 'BusinessLine', 'fortuneindia.com': 'Fortune India',
        'goodreturns.in': 'GoodReturns', 'ticker.finology.in': 'Finology',
        'groww.in': 'Groww', 'stockedge.com': 'StockEdge',
        'investing.com': 'Investing.com', 'money.rediff.com': 'Rediff Money',
        'timesofindia.indiatimes.com': 'Times of India', 'ndtv.com': 'NDTV Profit',
        'outlookbusiness.com': 'Outlook Business'
    }
    if domain in mapping: return mapping[domain]
    if 'news.google.com' in domain:
        for sep in [' - ', ' | ', ' : ']:
            if sep in title: return title.split(sep)[-1].strip()
    name = domain.split(':')[0]
    parts = name.split('.')
    if len(parts) >= 2:
        if parts[-2] in ['com', 'co', 'org', 'net', 'edu', 'gov']:
             name = parts[-3] if len(parts) >= 3 else parts[-2]
        else: name = parts[-2]
    return name.replace('-', ' ').capitalize()

IMPACT_KEYWORDS = {
    'high': ['crash', 'crisis', 'urgent', 'breaking', 'collapsed', 'warns', 'surge', 'plunge', 'lockdown', 'rating', 'result', 'focus'],
    'pos': ['profit', 'growth', 'record', 'dividend', 'buyback', 'partnership', 'acquired', 'expansion', 'jump', 'bullish', 'buy'],
    'neg': ['loss', 'fall', 'slump', 'down', 'decline', 'investigation', 'scam', 'penalty', 'lawsuit', 'bearish', 'sell']
}
IMPACT_REGEX = {k: re.compile(r'\b(' + '|'.join(v) + r')\b', re.IGNORECASE) for k, v in IMPACT_KEYWORDS.items()}

def highlight_impact(title):
    highlighted = title
    for k, pattern in IMPACT_REGEX.items():
        highlighted = pattern.sub(f'<span class="impact-{k}">\\1</span>', highlighted)
    return highlighted

@st.cache_data(ttl=600)
def fetch_all_news():
    RSS_FEEDS = [
        'https://news.google.com/rss/search?q=stock+market+india+NSE+BSE+finance&hl=en-IN&gl=IN&ceid=IN:en',
        'https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-IN&gl=IN&ceid=IN:en',
        'https://news.google.com/rss/search?q=stock+market+india+business&hl=en-IN&gl=IN&ceid=IN:en',
        'https://news.google.com/rss/search?q=site:moneycontrol.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
        'https://news.google.com/rss/search?q=site:financialexpress.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
        'https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms',
        'https://www.livemint.com/rss/markets',
        'https://news.google.com/rss/search?q=site:thehindubusinessline.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en',
        'https://news.google.com/rss/search?q=site:pulse.zerodha.com&hl=en-IN&gl=IN&ceid=IN:en',
        'https://news.google.com/rss/search?q=site:ndtvprofit.com+intitle:(stocks+OR+markets+OR+nse+OR+bse)&hl=en-IN&gl=IN&ceid=IN:en'
    ]
    all_news = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=120)
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                link = entry.get('link', '#')
                title = entry.get('title', '')
                if len(title.split()) < 5: continue
                pub_date = None
                if 'published_parsed' in entry: pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                if pub_date and pub_date < cutoff: continue
                sentiment = analyzer.polarity_scores(title)
                score = sentiment['compound']
                all_news.append({'title': title, 'link': link, 'source': get_source_name(link, feed.feed.get('title', '')),
                                'pubDate': pub_date or datetime.now(timezone.utc), 'score': score, 
                                'label': 'Positive' if score > 0.05 else ('Negative' if score < -0.05 else 'Neutral')})
        except: continue
    if not all_news: return pd.DataFrame()
    df = pd.DataFrame(all_news).drop_duplicates(subset=['link'])
    df['pubDate'] = pd.to_datetime(df['pubDate'], utc=True)
    return df.sort_values(by='pubDate', ascending=False)

@st.cache_data(ttl=60)
def fetch_indices():
    tickers = {'NIFTY 50': '^NSEI', 'SENSEX': '^BSESN', 'BANK NIFTY': '^NSEBANK', 'INDIA VIX': '^INDIAVIX'}
    results = {}
    def fetch_single(name, ticker):
        try:
            data = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d", headers={'User-Agent': 'Mozilla/5.0'}).json()
            meta = data['chart']['result'][0]['meta']
            return name, {'price': meta['regularMarketPrice'], 'change': meta['regularMarketPrice'] - meta['previousClose'], 'pct': ((meta['regularMarketPrice'] - meta['previousClose']) / meta['previousClose']) * 100}
        except: return name, {'price': 0, 'change': 0, 'pct': 0}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(fetch_single, name, ticker) for name, ticker in tickers.items()]
        for f in concurrent.futures.as_completed(futures):
            name, d = f.result()
            results[name] = d
    return results

def main():
    if 'items_to_show' not in st.session_state: st.session_state.items_to_show = 100
    
    # ⚡ CORE TERMINAL STYLING
    st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Roboto+Mono:wght@400;500&display=swap');
    * { font-family: 'Outfit', sans-serif; }
    .stApp { background: #0f172a; }
    #MainMenu, footer, header {visibility: hidden; display: none;}
    [data-testid="stHeader"] { display: none; }
    .main .block-container { padding-top: 1rem !important; max-width: 100%; }
</style>
""", unsafe_allow_html=True)

    # UI Metrics & Hits
    indices = fetch_indices()
    cols = st.columns(4)
    for i, name in enumerate(['NIFTY 50', 'SENSEX', 'BANK NIFTY', 'INDIA VIX']):
        val = indices.get(name, {'price': 0, 'pct': 0})
        color = "#4ade80" if val['pct'] >= 0 else "#f87171"
        cols[i].markdown(f'<div style="background: rgba(30,31,59,0.7); padding: 4px 8px; border-radius: 4px; border-left: 3px solid {color};"><div style="font-size: 0.65rem; color: #94a3b8;">{name}</div><div style="font-size: 1rem; font-weight: 700; color: white;">{val["price"]:.0f} <span style="font-size: 0.7rem; color: {color};">{"▲" if val["pct"]>=0 else "▼"} {abs(val["pct"]):.2f}%</span></div></div>', unsafe_allow_html=True)
    
    st.markdown('<div style="text-align: right; margin-top: 8px;"><img src="https://hits.dwyl.com/market-brief/terminal.svg" alt="Hits"></div>', unsafe_allow_html=True)

    df_news = fetch_all_news()
    if df_news.empty:
        st.warning("No data found.")
        return

    # THE SELF-CONTAINED TERMINAL COMPONENT
    terminal_body = ""
    for _, row in df_news.head(st.session_state.items_to_show).iterrows():
        highlighted = highlight_impact(row['title'])
        rel_time = format_time_ago(row['pubDate'])
        glow = "glow-pos" if row['score'] > 0.05 else ("glow-neg" if row['score'] < -0.05 else "glow-neu")
        color = '#4ade80' if row['score'] > 0.05 else ('#f87171' if row['score'] < -0.05 else '#94a3b8')
        # SOURCE column removed from here
        terminal_body += f'<div class="news-row {glow}"><div class="time-tag">{rel_time}</div><a href="{row["link"]}" target="_blank" class="headline-link">{highlighted}</a><div class="sentiment-tag" style="color: {color};">{row["label"]}</div></div>'

    html_content = f"""
    <style>
        * {{ font-family: 'Outfit', sans-serif; box-sizing: border-box; }}
        body {{ background: #0f172a; margin: 0; overflow-x: hidden; color: white; }}
        .news-row {{ display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-bottom: 1px solid rgba(255,255,255,0.05); border-left: 3px solid transparent; width: 100%; transition: background 0.1s; }}
        .news-row:hover {{ background: rgba(56, 189, 248, 0.05); cursor: pointer; }}
        .glow-pos {{ border-left-color: #4ade80 !important; }}
        .glow-neg {{ border-left-color: #f87171 !important; }}
        .glow-neu {{ border-left-color: rgba(148, 163, 184, 0.2) !important; }}
        .time-tag {{ width: 65px; font-family: 'Roboto Mono', monospace; font-size: 0.7rem; color: #94a3b8; flex-shrink: 0; }}
        .headline-link {{ flex-grow: 1; text-decoration: none !important; color: #f8fafc !important; font-size: 0.95rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .sentiment-tag {{ width: 80px; text-align: right; font-size: 0.75rem; font-weight: 600; flex-shrink: 0; }}
        .impact-high {{ color: #f87171; font-weight: 700; text-decoration: underline; }}
        .impact-pos {{ color: #4ade80; font-weight: 700; }}
        .impact-neg {{ color: #f87171; font-weight: 700; }}
        #terminal-search {{ width: 100%; padding: 12px 15px; background: rgba(30, 41, 59, 0.8); border: 1px solid rgba(255,255,255,0.1); border-radius: 4px; color: white; outline: none; font-size: 1rem; margin-bottom: 20px; }}
        .header {{ display: flex; gap: 12px; padding: 10px 12px; border-bottom: 2px solid rgba(255,255,255,0.1); font-weight: 700; font-size: 0.75rem; color: #64748b; letter-spacing: 1px; text-transform: uppercase; }}
    </style>
    
    <input type="text" id="terminal-search" placeholder="🔍 Instant search all headlines..." autofocus>
    
    <div class="header">
        <div style="width: 65px;">TIME</div><div style="flex-grow: 1;">HEADLINE (ZERO LATENCY)</div><div style="width: 80px; text-align: right;">SENTIMENT</div>
    </div>
    
    <div id="container">
        {terminal_body}
    </div>

    <script>
        const searchInput = document.getElementById('terminal-search');
        const rows = document.querySelectorAll('.news-row');
        
        searchInput.addEventListener('input', (e) => {{
            const q = e.target.value.toLowerCase();
            rows.forEach(row => {{
                const text = row.innerText.toLowerCase();
                row.style.display = text.includes(q) ? 'flex' : 'none';
            }});
        }});
        
        // Auto-refresh communication
        setTimeout(() => {{ 
            window.parent.postMessage({{type: 'MB_REFRESH'}}, '*'); 
        }}, 120000);
    </script>
    """
    
    components.html(html_content, height=1200, scrolling=True)

    if st.session_state.items_to_show < len(df_news):
        if st.button("Load More Headlines", type="secondary", use_container_width=True):
            st.session_state.items_to_show += 100
            st.rerun()

if __name__ == "__main__":
    main()
