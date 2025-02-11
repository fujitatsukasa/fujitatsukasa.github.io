---
layout: page
title: 製品概要
subtitle: ゆっくりまとめプロセッサーの全貌をご紹介
---

<style>
  /* Google Fonts の読み込み */
  @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');

  /* 全体の基本設定 */
  .page-content {
    font-family: 'Roboto', sans-serif;
    line-height: 1.6;
    color: #333;
    max-width: 900px;
    margin: 0 auto;
    padding: 1em;
  }
  /* セクション見出し */
  .section-title {
    text-align: center;
    font-size: 2.4em;
    margin-top: 1em;
    margin-bottom: 0.7em;
    color: #222;
    border-bottom: 3px solid #007BFF;
    padding-bottom: 0.3em;
  }
  /* カルーセルカードスタイル */
  .carousel {
    position: relative;
    width: 100%;
    overflow: hidden;
    margin: 2em 0;
    border: 1px solid #ddd;
    border-radius: 12px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    background: #fff;
  }
  .carousel-track {
    display: flex;
    transition: transform 0.5s ease-in-out;
  }
  .carousel-slide {
    min-width: 100%;
    box-sizing: border-box;
  }
  .carousel-slide img {
    width: 100%;
    display: block;
    cursor: pointer;
    transition: transform 0.3s ease;
  }
  .carousel-slide img:hover {
    transform: scale(1.05);
  }
  /* ナビゲーション矢印 */
  .carousel-button {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    color: #fff;
    font-size: 3em;
    cursor: pointer;
    z-index: 10;
    transition: transform 0.2s ease;
  }
  .carousel-button:active {
    transform: translateY(-50%) scale(0.9);
  }
  .carousel-button--left {
    left: 10px;
  }
  .carousel-button--right {
    right: 10px;
  }
  /* インジケーターをカルーセル内に配置 */
  .carousel-indicators {
    position: absolute;
    bottom: 10px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    gap: 5px;
    z-index: 10;
  }
  .carousel-indicator {
    width: 12px;
    height: 12px;
    background: rgba(255,255,255,0.6);
    border-radius: 50%;
    cursor: pointer;
    transition: background 0.3s ease;
  }
  .carousel-indicator.active {
    background: #007BFF;
  }
  /* 全画面モーダル（拡大表示用） */
  .modal {
    display: none;
    position: fixed;
    z-index: 1000;
    left: 0;
    top: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0,0,0,0.9);
    justify-content: center;
    align-items: center;
    flex-direction: column;
  }
  .modal img {
    max-width: 60vw;
    max-height: 80vh;
  }
  .modal .modal-info {
    color: #fff;
    margin-top: 1em;
    font-size: 1.2em;
  }
  .modal .close-modal {
    position: absolute;
    top: 20px;
    right: 30px;
    font-size: 2.5em;
    color: #fff;
    cursor: pointer;
  }
  /* 既存コンテンツ（特徴、詳細機能、使い方、実績など） */
  .feature-item {
    text-align: center;
    padding: 1.2em;
    margin: 2em auto;
    border: 1px solid #eee;
    border-radius: 12px;
    background-color: #fafafa;
    max-width: 700px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.05);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
  }
  .feature-item:hover {
    transform: translateY(-5px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  }
  .feature-item h3 {
    margin-bottom: 0.7em;
    font-size: 1.6em;
  }
  .usage-list {
    max-width: 800px;
    margin: 0 auto 2em;
    font-size: 1.15em;
    line-height: 1.8;
    list-style-type: decimal;
    padding-left: 1.2em;
  }
  blockquote {
    border-left: 4px solid #ccc;
    margin: 1.8em 0;
    padding-left: 1em;
    font-style: italic;
    color: #555;
  }
  a {
    color: #007BFF;
    text-decoration: none;
    transition: color 0.3s ease;
  }
  a:hover {
    color: #0056b3;
    text-decoration: underline;
  }
  @media screen and (max-width: 768px) {
    .section-title { font-size: 2em; }
  }
</style>

<div class="page-content">
  <!-- 製品概要のイントロダクション -->
  <h2 class="section-title">製品概要</h2>
  <p style="text-align: center;">
    <strong>「ゆっくりまとめプロセッサー」</strong>は、OTM株式会社が社内で開発した<strong>自動動画編集ソフトウェア</strong>です。<br>
    サイトから台本や画像、掲示板からスレッド情報を瞬時に取得し、動画編集プロセスを半自動化。<br>
    動画配信者、動画クリエイター、未経験者、副業を模索する社会人など、幅広いユーザーに支持されています。
  </p>

  <!-- カルーセル -->
  <div class="carousel">
    <div class="carousel-track">
      <div class="carousel-slide">
        <img src="/assets/img/製品イメージ1.png" alt="製品イメージ1" title="クリックして拡大表示">
      </div>
      <div class="carousel-slide">
        <img src="/assets/img/製品イメージ2.png" alt="製品イメージ2" title="クリックして拡大表示">
      </div>
      <div class="carousel-slide">
        <img src="/assets/img/製品イメージ3.png" alt="製品イメージ3" title="クリックして拡大表示">
      </div>
    </div>
    <!-- シンプルな白い矢印 -->
    <button class="carousel-button carousel-button--left">&#10094;</button>
    <button class="carousel-button carousel-button--right">&#10095;</button>
    <!-- インジケーターをカルーセル内に配置 -->
    <div class="carousel-indicators"></div>
  </div>

  <hr>

  <!-- 既存のセクション -->
  <h2 class="section-title">特徴</h2>
  <div class="feature-item">
    <h3 style="color:#007BFF;">直感的な操作性</h3>
    <p>ゆっくりムービーメーカー4に最適化したUIで、初心者でもすぐに使いこなせます。</p>
  </div>
  <div class="feature-item">
    <h3 style="color:#28A745;">自動動画編集機能</h3>
    <p>台本、画像、掲示板のスレッド情報を瞬時に取得し、編集プロセスを自動化。手間を大幅に削減します。</p>
  </div>
  <div class="feature-item">
    <h3 style="color:#FFC107;">柔軟なデータ連携</h3>
    <p>複数のまとめサイトや掲示板から最新情報を効率的に収集。ユーザーのニーズに合わせたカスタム設定も可能です。</p>
  </div>
  <div class="feature-item">
    <h3 style="color:#DC3545;">高い信頼性と安全性</h3>
    <p>最新のセキュリティ対策と安定した動作により、個人・法人問わず安心してご利用いただけます。</p>
  </div>

  <hr>

  <h2 class="section-title">詳細機能</h2>
  <h3 class="subsection-title">自動スレッド＆画像取得</h3>
  <p style="text-align: center;">
    指定のまとめサイトから最新のスレッドと画像を自動で取得し、整理。<br>
    <em>(利点：手作業を排除し、常に最新のコンテンツを活用可能)</em>
  </p>
  <h3 class="subsection-title">ゆっくりムービーメーカー4連携</h3>
  <p style="text-align: center;">
    取得した台本と画像を、ゆっくりムービーメーカー4の編集環境に即座に反映。<br>
    <em>(利点：動画制作時間の短縮と作業効率の向上)</em>
  </p>
  <h3 class="subsection-title">カスタム編集テンプレート</h3>
  <p style="text-align: center;">
    ユーザーの好みに合わせた編集テンプレートを多数用意。<br>
    <em>(利点：ブランドイメージやコンテンツスタイルに合わせた柔軟な編集が実現)</em>
  </p>

  <hr>

  <h2 class="section-title">使い方の流れ</h2>
  <ol class="usage-list">
    <li><strong>インストール:</strong> 公式サイトからインストーラーをダウンロードし、ウィザード形式でセットアップ。</li>
    <li><strong>初期設定:</strong> ガイドに従い、各連携設定を実施。</li>
    <li><strong>自動編集開始:</strong> 台本、画像、スレッドの自動取得とテンプレート適用で、瞬時に高品質な動画を生成。</li>
  </ol>

  <hr>

  <h2 class="section-title">お客様の声</h2>
  <blockquote>
    「<strong>ゆっくりまとめプロセッサー</strong>の導入で、1日2本だった動画が半分の時間で20本に増加。<br>
    収益面でも10倍の効果を実感！」<br>
    <span style="font-size:0.9em;">*— 動画クリエイター 高橋様*</span>
  </blockquote>
  <blockquote>
    「毎日の動画編集によるストレスが軽減され、余裕を持って新たなことに挑戦できるようになりました。」<br>
    <span style="font-size:0.9em;">*— ゆっくり系配信者 S様*</span>
  </blockquote>
  <blockquote>
    「台本作成時の煩雑な作業が自動入れ替え機能で解消。作業効率が格段に向上しました！」<br>
    <span style="font-size:0.9em;">*— IT系個人事業主 A様*</span>
  </blockquote>
  <blockquote>
    「チーム全体の動画編集がシンプルになり、最終チェックのみで多数の動画が完成。売上と士気の向上に貢献！」<br>
    <span style="font-size:0.9em;">*— タブナジア合同会社様*</span>
  </blockquote>
  <p style="text-align: center;">
    弊社はお客様の声をもとに製品を進化させています。ご不明点やご要望はお気軽にお知らせください。
  </p>

  <hr>

  <h2 class="section-title">開発者情報</h2>
  <p style="text-align: center;">
    <strong>開発者</strong>: 藤田僚&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;
    <strong>所属</strong>: OTM株式会社&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;
    <strong>公式サイト</strong>: <a href="https://your-company-website.example" target="_blank">OTM株式会社</a>
  </p>

  <hr>

  <h2 class="section-title">今後の展望</h2>
  <p style="text-align: center;">
    当社は<strong>定期的なアップデート</strong>と<strong>新機能の追加</strong>を計画しております。<br>
    最新情報やアップデートは、公式サイトおよび各種SNSで随時発信いたしますのでご期待ください。
  </p>

  <hr>

  <p style="text-align: center; font-size: 0.9em;">
    本製品に関するお問い合わせは、<a href="mailto:fujita.otm@gmail.com">こちら</a>までお気軽にご連絡ください。
  </p>
</div>

<!-- 全画面モーダル（拡大表示用） -->
<div id="modal" class="modal">
  <span class="close-modal">&times;</span>
  <img id="modal-image" src="" alt="">
  <div class="modal-info" id="modal-info"></div>
</div>

<script>
  /* カルーセル処理 */
  const track = document.querySelector('.carousel-track');
  const slides = Array.from(track.children);
  let currentSlideIndex = 0;
  const slideCount = slides.length;

  const setSlidePosition = () => {
    slides.forEach((slide, index) => {
      slide.style.left = index * 100 + '%';
    });
  };
  setSlidePosition();

  // インジケーター生成：カルーセル内に配置
  const indicatorsContainer = document.querySelector('.carousel-indicators');
  for (let i = 0; i < slideCount; i++) {
    const dot = document.createElement('div');
    dot.classList.add('carousel-indicator');
    if (i === 0) dot.classList.add('active');
    dot.setAttribute('data-slide', i);
    indicatorsContainer.appendChild(dot);
  }

  const updateIndicators = (index) => {
    const dots = Array.from(document.querySelectorAll('.carousel-indicator'));
    dots.forEach(dot => dot.classList.remove('active'));
    dots[index].classList.add('active');
  };

  const moveToSlide = (index) => {
    track.style.transform = 'translateX(-' + index * 100 + '%)';
    currentSlideIndex = index;
    updateIndicators(index);
  };

  // ナビゲーション矢印
  document.querySelector('.carousel-button--left').addEventListener('click', () => {
    const prevIndex = (currentSlideIndex - 1 + slideCount) % slideCount;
    moveToSlide(prevIndex);
  });
  document.querySelector('.carousel-button--right').addEventListener('click', () => {
    const nextIndex = (currentSlideIndex + 1) % slideCount;
    moveToSlide(nextIndex);
  });

  // 自動再生（5秒ごと）
  setInterval(() => {
    const nextIndex = (currentSlideIndex + 1) % slideCount;
    moveToSlide(nextIndex);
  }, 5000);

  // インジケータークリック
  document.querySelectorAll('.carousel-indicator').forEach(dot => {
    dot.addEventListener('click', (e) => {
      const index = parseInt(e.target.getAttribute('data-slide'));
      moveToSlide(index);
    });
  });

  /* モーダル（全画面拡大表示） */
  const modal = document.getElementById('modal');
  const modalImage = document.getElementById('modal-image');
  const modalInfo = document.getElementById('modal-info');
  const closeModal = document.querySelector('.close-modal');

  document.querySelectorAll('.carousel-slide img').forEach((img, index) => {
    img.title = "クリックで拡大表示（全画面）";
    img.addEventListener('click', () => {
      modal.style.display = 'flex';
      modalImage.src = img.src;
      modalInfo.textContent = '画像 ' + (index + 1) + ' / ' + slideCount;
    });
  });

  closeModal.addEventListener('click', () => {
    modal.style.display = 'none';
  });

  window.addEventListener('click', (e) => {
    if (e.target === modal) {
      modal.style.display = 'none';
    }
  });
</script>
