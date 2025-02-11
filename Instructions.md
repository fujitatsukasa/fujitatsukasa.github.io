---
layout: page
title: 使い方
subtitle: ゆっくりまとめプロセッサーの操作ガイド
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
    padding: 1.5em;
    color: #333;
    line-height: 1.6;
  }
  /* 目次 (TOC) スタイル */
  .toc {
    background: #f0f8ff;
    border: 1px solid #007BFF;
    border-radius: 8px;
    padding: 1em 1.2em;
    margin-bottom: 2em;
  }
  .toc h3 {
    margin: 0;
    font-size: 1.5em;
    color: #007BFF;
    border-bottom: 1px dashed #007BFF;
    padding-bottom: 0.3em;
    text-align: center;
  }
  .toc ul {
    list-style: none;
    padding-left: 0;
    margin: 1em 0 0 0;
  }
  .toc li {
    margin: 0.5em 0;
  }
  /* 階層ごとのインデント */
  .toc li.toc-h2 {
    margin-left: 0;
  }
  .toc li.toc-h3 {
    margin-left: 1.5em;
  }
  .toc a {
    text-decoration: none;
    color: #007BFF;
    font-weight: 500;
    transition: color 0.3s ease;
  }
  .toc a:hover {
    color: #0056b3;
    text-decoration: underline;
  }
  /* セクション見出し */
  h2.section-title {
    font-size: 2em;
    margin: 1.5em 0 0.5em;
    color: #222;
    border-bottom: 2px solid #007BFF;
    padding-bottom: 0.3em;
    text-align: center;  /* 中央揃え */
  }
  /* サブセクション見出し */
  h3.subsection-title {
    font-size: 1.5em;
    margin: 1.2em 0 0.5em;
    color: #444;
    text-align: center;  /* 中央揃え */
  }
  /* セクションの本文 */
  .section-content {
    margin-bottom: 2em;
  }
  .section-content p {
    margin: 0.8em 0;
    text-align: center;
  }
  .section-content img {
    max-width: 100%;
    border-radius: 8px;
    margin: 1em 0;
    box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    cursor: pointer; /* クリックできることを示す */
    transition: transform 0.3s ease;
  }
  .section-content img:hover {
    transform: scale(1.02);
  }
  /* セクション内ナビゲーション（必要に応じて） */
  .section-nav {
    text-align: center;
    margin-top: 2em;
  }
  .section-nav a {
    margin: 0 1em;
    color: #007BFF;
    text-decoration: none;
    font-weight: 500;
  }
  .section-nav a:hover {
    text-decoration: underline;
  }

  /* モーダル（画像拡大用）のスタイル */
  .modal {
    display: none; /* 初期は非表示 */
    position: fixed;
    z-index: 1000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    overflow: auto;
    background-color: rgba(0,0,0,0.8);
  }
  .modal-content {
    margin: 5% auto;
    display: block;
    max-width: 90%;
    max-height: 80%;
    border-radius: 8px;
  }
  .modal-close {
    position: absolute;
    top: 20px;
    right: 35px;
    color: #f1f1f1;
    font-size: 40px;
    font-weight: bold;
    transition: color 0.3s ease;
    cursor: pointer;
  }
  .modal-close:hover,
  .modal-close:focus {
    color: #bbb;
    text-decoration: none;
    cursor: pointer;
  }
</style>

<!-- モーダル (ライトボックス) の HTML -->
<div id="imgModal" class="modal">
  <span class="modal-close" id="modalClose">&times;</span>
  <img class="modal-content" id="modalImg">
</div>

<div class="page-content">

  <!-- 目次 (TOC) -->
  <div class="toc">
    <h3>目次</h3>
    <ul>
      <li class="toc-h2"><a href="#video-editing">動画編集</a></li>
      <li class="toc-h3"><a href="#video-editing-basics">基本操作</a></li>
      <li class="toc-h3"><a href="#video-editing-advanced">高度な編集</a></li>
      <li class="toc-h2"><a href="#script-retrieval">台本取得</a></li>
      <li class="toc-h3"><a href="#script-retrieval-flow">取得の流れ</a></li>
      <li class="toc-h2"><a href="#script-configuration">台本設定</a></li>
      <li class="toc-h3"><a href="#script-format-adjustment">フォーマット調整</a></li>
      <li class="toc-h3"><a href="#script-keyword-insertion">キーワード挿入</a></li>
      <li class="toc-h2"><a href="#overall-settings">全体設定</a></li>
      <li class="toc-h3"><a href="#ui-customization">UIカスタマイズ</a></li>
      <li class="toc-h3"><a href="#notification-settings">通知設定</a></li>
    </ul>
  </div>

  <!-- セクション: 動画編集 -->
  <div id="video-editing" class="section-content">
    <h2 class="section-title">動画編集</h2>
    <p>
      ゆっくりムービーメーカー4を使用した動画編集の手順を図解とともに解説します。
    </p>

    <!-- サブセクション: 基本操作 -->
    <div id="video-editing-basics">
      <h3 class="subsection-title">基本操作</h3>
      <p>
        クリップのトリミング、結合、再配置など、基本的な編集操作を説明します。
      </p>
      <img class="clickable-image" src="/assets/img/video-editing-basics.png" alt="基本操作の例">
    </div>

    <!-- サブセクション: 高度な編集 -->
    <div id="video-editing-advanced">
      <h3 class="subsection-title">高度な編集</h3>
      <p>
        エフェクトの適用、色調補正、テキストオーバーレイなど、より高度な編集方法を図解で紹介します。
      </p>
      <img class="clickable-image" src="/assets/img/video-editing-advanced.png" alt="高度な編集の例">
    </div>
  </div>

  <!-- セクション: 台本取得 -->
  <div id="script-retrieval" class="section-content">
    <h2 class="section-title">台本取得</h2>
    <p>
      サイトやまとめ掲示板から自動で台本を取得する方法の全体フローを解説します。
    </p>
    <!-- サブセクション: 取得の流れ -->
    <div id="script-retrieval-flow">
      <h3 class="subsection-title">取得の流れ</h3>
      <p>
        台本取得のプロセスは、データ収集、抽出、整形の３段階に分かれています。
      </p>
      <img class="clickable-image" src="/assets/img/script-retrieval-flow.png" alt="台本取得の流れ">
    </div>
  </div>

  <!-- セクション: 台本設定 -->
  <div id="script-configuration" class="section-content">
    <h2 class="section-title">台本設定</h2>
    <p>
      取得した台本を編集し、動画編集に最適な形式に整える方法を説明します。
    </p>
    <!-- サブセクション: フォーマット調整 -->
    <div id="script-format-adjustment">
      <h3 class="subsection-title">フォーマット調整</h3>
      <p>
        不要な情報の削除や改行の調整、フォーマットの統一を行います。
      </p>
      <img class="clickable-image" src="/assets/img/script-format-adjustment.png" alt="台本フォーマット調整の例">
    </div>
    <!-- サブセクション: キーワード挿入 -->
    <div id="script-keyword-insertion">
      <h3 class="subsection-title">キーワード挿入</h3>
      <p>
        台本内に効果的なキーワードを挿入して、動画のSEOや視聴率向上を狙います。
      </p>
      <img class="clickable-image" src="/assets/img/script-keyword-insertion.png" alt="キーワード挿入の例">
    </div>
  </div>

  <!-- セクション: 全体設定 -->
  <div id="overall-settings" class="section-content">
    <h2 class="section-title">全体設定</h2>
    <p>
      ユーザーインターフェースのカスタマイズ、保存先の設定、通知のオン／オフなど、ソフトウェア全体の設定方法を紹介します。
    </p>
    <!-- サブセクション: UIカスタマイズ -->
    <div id="ui-customization">
      <h3 class="subsection-title">UIカスタマイズ</h3>
      <p>
        操作性を向上させるための各種レイアウトや配色の調整方法を解説します。
      </p>
      <img class="clickable-image" src="/assets/img/ui-customization.png" alt="UIカスタマイズの例">
    </div>
    <!-- サブセクション: 通知設定 -->
    <div id="notification-settings">
      <h3 class="subsection-title">通知設定</h3>
      <p>
        動画編集や台本取得時の通知設定、アラートのカスタマイズ方法を説明します。
      </p>
      <img class="clickable-image" src="/assets/img/notification-settings.png" alt="通知設定の例">
    </div>
  </div>

  <!-- セクション内ナビゲーション（オプション） -->
  <div class="section-nav">
    <a href="#video-editing">動画編集</a>
    <a href="#script-retrieval">台本取得</a>
    <a href="#script-configuration">台本設定</a>
    <a href="#overall-settings">全体設定</a>
  </div>

</div>

<!-- 画像クリック時に拡大表示するための JavaScript -->
<script>
  // モーダル要素の取得
  const modal = document.getElementById("imgModal");
  const modalImg = document.getElementById("modalImg");
  const modalClose = document.getElementById("modalClose");

  // ページ内のすべての「clickable-image」クラスの画像にクリックイベントを付与
  document.querySelectorAll('.clickable-image').forEach(img => {
    img.addEventListener('click', () => {
      modal.style.display = "block";
      modalImg.src = img.src;
    });
  });

  // モーダルのクローズ処理
  modalClose.addEventListener('click', () => {
    modal.style.display = "none";
  });

  // モーダル外をクリックしたら閉じる
  modal.addEventListener('click', (event) => {
    if (event.target === modal) {
      modal.style.display = "none";
    }
  });
</script>
