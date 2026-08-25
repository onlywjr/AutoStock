import re
import json
import subprocess
from datetime import datetime

def fetch_stock_data(ticker):
    result = subprocess.run(['python', 'fetch_stock.py', ticker], capture_output=True, text=True, cwd='C:/My_Project/Hermes/AutoStock')
    return json.loads(result.stdout)

def update_dashboard(ticker, data):
    """Update the HTML dashboard with fresh price/change data"""
    html_path = f'C:/My_Project/Hermes/AutoStock/{ticker}.html'
    
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    price = data['price']
    change_pct = data['changePct']
    
    # Format price with commas
    price_str = f"{price:,.2f}"
    
    # Determine change color and sign
    if change_pct > 0:
        change_color = "success"
        change_sign = "▲"
    elif change_pct < 0:
        change_color = "red-400"
        change_sign = "▼"
    else:
        change_color = "slate-400"
        change_sign = "—"
    
    change_pct_str = f"{change_sign} {abs(change_pct):.2f}%"
    
    # Update timestamp
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = re.sub(
        r'更新時間：[\d\-: ]+',
        f'更新時間：{update_time}',
        content
    )
    
    # Update price display - look for the price in the header
    def replace_price(m):
        return m.group(1) + price_str + m.group(3)
    
    content = re.sub(
        r'(<div class="text-3xl font-bold text-(success|red-400|slate-400) font-mono mt-0\.5">)[\d,]+\.?\d*(</div>)',
        replace_price,
        content
    )
    
    # Update change percentage in header
    def replace_change(m):
        return m.group(1) + '(' + change_pct_str + ')' + m.group(3)
    
    content = re.sub(
        r'(<div class="text-xl font-bold text-(success|red-400|slate-400) font-mono mt-0\.5">)[^<]*(</div>)',
        replace_change,
        content
    )
    
    # Update the change badge in the header top area
    def replace_badge(m):
        return m.group(1) + change_pct_str + m.group(3)
    
    content = re.sub(
        r'(<span class="text-xs text-(success|red-400|slate-400) font-semibold">)[^<]*(</span>)',
        replace_badge,
        content
    )
    
    # Update the price in the card (closing price in the card)
    def replace_card_price(m):
        return m.group(1) + price_str + m.group(2)
    
    content = re.sub(
        r'(收盤價: <strong class="text-slate-100 font-mono">)[\d,]+\.?\d*(</strong>)',
        replace_card_price,
        content
    )
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Updated {ticker}.html: Price={price_str}, Change={change_pct_str}")

def update_index_html(all_data):
    """Update index.html with latest prices and changes"""
    html_path = 'C:/My_Project/Hermes/AutoStock/index.html'
    
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # For each ticker, update its card
    for ticker, data in all_data.items():
        price = data['price']
        change_pct = data['changePct']
        
        price_str = f"{price:,.2f}"
        
        if change_pct > 0:
            change_color = "success"
            change_sign = "▲"
        elif change_pct < 0:
            change_color = "red-400"
            change_sign = "▼"
        else:
            change_color = "slate-400"
            change_sign = "—"
        
        change_pct_str = f"{change_sign} {abs(change_pct):.2f}%"
        
        # Update price in the card
        def replace_price(m):
            return m.group(1) + price_str + m.group(2)
        
        pattern_price = rf'(href="{ticker}\.html"[^>]*>.*?收盤價: <strong class="text-slate-100 font-mono">)[\d,]+\.?\d*(</strong>)'
        content = re.sub(
            pattern_price,
            replace_price,
            content,
            flags=re.DOTALL
        )
        
        # Update change badge in the card
        def replace_change(m):
            return m.group(1) + change_pct_str + m.group(3)
        
        pattern_change = rf'(href="{ticker}\.html"[^>]*>.*?<span class="text-xs text-(success|red-400|slate-400) font-semibold">)[^<]*(</span>)'
        content = re.sub(
            pattern_change,
            replace_change,
            content,
            flags=re.DOTALL
        )
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Updated index.html")

# Main execution
tickers = ['8299', '1434', '2327', '2330', '6139', '6213']
all_data = {}

for t in tickers:
    data = fetch_stock_data(t)
    all_data[t] = data
    update_dashboard(t, data)

update_index_html(all_data)
print("All dashboards updated!")