/**
 * api/stock-update.js — Vercel Serverless Function
 * 建立 GitHub Issue 以通知自動化工具新增或移除自訂股票。
 */
export default async function handler(req, res) {
  // CORS
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { action, ticker } = req.body || {};
  if (!action || !ticker) {
    return res.status(400).json({ error: 'Missing action or ticker' });
  }

  const validActions = ['add', 'remove'];
  if (!validActions.includes(action)) {
    return res.status(400).json({ error: `Action must be one of: ${validActions.join(', ')}` });
  }

  // 驗證 4 位代號
  if (!/^\d{4}$/.test(ticker)) {
    return res.status(400).json({ error: 'Ticker must be a 4-digit number' });
  }

  const token = process.env.GITHUB_TOKEN;
  const owner = process.env.GITHUB_OWNER || 'onlywjr';
  const repo = process.env.GITHUB_REPO || 'AutoStock';

  if (!token) {
    return res.status(500).json({ error: 'GITHUB_TOKEN not configured' });
  }

  const title = action === 'add' ? `Add ${ticker}` : `Remove ${ticker}`;
  const body = action === 'add'
    ? `請新增自訂股票 ${ticker}（${ticker}.TW）至儀表板。\n\n此 Issue 由前端自動建立。`
    : `請移除自訂股票 ${ticker}（${ticker}.TW）自儀表板。\n\n此 Issue 由前端自動建立。`;

  try {
    const apiUrl = `https://api.github.com/repos/${owner}/${repo}/issues`;
    const resp = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        title,
        body,
        labels: ['bot:stock-update'],
      }),
    });

    if (resp.ok) {
      const data = await resp.json();
      return res.status(200).json({ success: true, issue: data.number, url: data.html_url });
    } else {
      const errText = await resp.text();
      console.error('GitHub API error:', resp.status, errText);
      return res.status(500).json({ error: 'Failed to create GitHub Issue' });
    }
  } catch (e) {
    console.error('Unexpected error:', e);
    return res.status(500).json({ error: 'Internal server error' });
  }
}
