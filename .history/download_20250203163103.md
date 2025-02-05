---
layout: page
title: ダウンロード
subtitle: 最新版および各バージョンのダウンロードはこちらから
---

<!-- ページ全体のスタイル -->
<style>
  /* Google Fonts の読み込み */
  @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');

  /* 全体の基本設定 */
  .page-content {
    font-family: 'Roboto', sans-serif;
    max-width: 900px;
    margin: 0 auto;
    padding: 1em;
    color: #333;
  }
  /* セクション見出し */
  h2.section-title {
    text-align: center;
    font-size: 2.4em;
    margin-top: 1em;
    margin-bottom: 0.7em;
    color: #222;
    border-bottom: 3px solid #007BFF;
    padding-bottom: 0.3em;
  }
  /* サブセクション見出し */
  h3.subsection-title {
    text-align: center;
    font-size: 1.8em;
    margin: 1.5em 0 0.8em;
    color: #555;
  }
  /* 最新バージョン用のダウンロードボタン */
  .download-button {
    display: block;
    width: 100%;
    max-width: 300px;
    margin: 0 auto 1em;
    padding: 1em;
    background-color: #007BFF;
    color: #fff;
    text-align: center;
    text-decoration: none;
    font-size: 1.2em;
    border-radius: 8px;
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    transition: background-color 0.3s ease, transform 0.3s ease;
  }
  .download-button:hover {
    background-color: #0056b3;
    transform: translateY(-3px);
  }
  /* リリースノートの表示領域 */
  .release-notes {
    border: 1px solid #ccc;
    padding: 1em;
    border-radius: 8px;
    max-height: 200px;
    overflow-y: scroll;
    margin: 1em auto 2em;
    background-color: #f8f8f8;
  }
  /* 過去のバージョン一覧 */
  .release-list {
    max-height: 300px;
    overflow-y: scroll;
    border: 1px solid #ccc;
    padding: 1em;
    margin: 1em auto;
    background-color: #fafafa;
  }
  .release-list ul {
    list-style: none;
    padding-left: 0;
    margin: 0;
  }
  .release-list li {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: 0.8em 0;
  }
  .release-list a {
    text-decoration: none;
    color: #007BFF;
    font-weight: 500;
    transition: color 0.3s ease;
  }
  .release-list a:hover {
    color: #0056b3;
    text-decoration: underline;
  }
  .release-date {
    font-size: 0.9em;
    color: #777;
    margin-left: 1em;
    white-space: nowrap;
  }
</style>

<!-- marked.js の読み込み -->
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>

<div class="page-content">

  <!-- 最新バージョン -->
  <h2 class="section-title">最新バージョン</h2>
  <div style="text-align:center;">
    <a id="latest-release-button" class="download-button" href="#" target="_blank">
      最新バージョンをダウンロードする
    </a>
  </div>
  <h3 class="subsection-title">リリースノート</h3>
  <div id="release-notes" class="release-notes">
    ロード中...
  </div>

  <hr>

  <!-- 過去のバージョン一覧 -->
  <h2 class="section-title">過去のバージョン一覧</h2>
  <div id="release-list" class="release-list">
    ロード中...
  </div>
  
  <script>
    // GitHub のリポジトリ情報
    const owner = 'fujitatsukasa';
    const repo = 'YukkuriMatomeProcessor';
    const apiUrl = `https://api.github.com/repos/${owner}/${repo}/releases`;

    // ヘルパー関数：日付を整形（例: YYYY-MM-DD）
    function formatDate(dateString) {
      const date = new Date(dateString);
      const year = date.getFullYear();
      const month = ('0' + (date.getMonth() + 1)).slice(-2);
      const day = ('0' + date.getDate()).slice(-2);
      return `${year}-${month}-${day}`;
    }

    fetch(apiUrl)
      .then(response => response.json())
      .then(releases => {
        if (!Array.isArray(releases)) {
          document.getElementById('release-list').innerHTML = 'リリース情報を取得できませんでした。';
          return;
        }

        // 最新リリースの設定（zipball_url を利用）
        if (releases.length > 0) {
          const latest = releases[0];
          document.getElementById('latest-release-button').href = latest.zipball_url;
          // 最新リリースのリリースノートは Markdown 形式 → marked.js で変換
          const notesMarkdown = latest.body || 'リリースノートはありません。';
          const notesHTML = marked.parse(notesMarkdown);
          document.getElementById('release-notes').innerHTML = notesHTML;
        } else {
          document.getElementById('latest-release-button').innerHTML = 'リリースがありません';
          document.getElementById('release-notes').innerHTML = '';
        }

        // 過去のリリース一覧（最新リリースは除外）
        const listDiv = document.getElementById('release-list');
        listDiv.innerHTML = ''; // ロード中メッセージのクリア
        const ul = document.createElement('ul');
        releases.forEach((release, index) => {
          if (index === 0) return; // 最新はすでに表示済みなのでスキップ
          const li = document.createElement('li');
          
          // リリースリンク
          const a = document.createElement('a');
          a.href = release.zipball_url;
          a.target = '_blank';
          a.textContent = release.name || release.tag_name;
          
          // リリース日を表示するための要素
          const dateSpan = document.createElement('span');
          dateSpan.className = 'release-date';
          dateSpan.textContent = formatDate(release.published_at);
          
          li.appendChild(a);
          li.appendChild(dateSpan);
          ul.appendChild(li);
        });
        listDiv.appendChild(ul);
      })
      .catch(error => {
        document.getElementById('release-list').innerHTML = 'リリース情報の取得に失敗しました。';
        document.getElementById('release-notes').innerHTML = '';
        console.error(error);
      });
  </script>

</div>
