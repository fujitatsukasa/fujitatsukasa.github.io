---
layout: page
title: よくある質問
subtitle: FAQ
---

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
  /* ページ見出し */
  h2.section-title {
    text-align: center;
    font-size: 2em;
    margin-bottom: 1em;
    color: #222;
    border-bottom: 2px solid #007BFF;
    padding-bottom: 0.3em;
  }
  /* カテゴリ見出し */
  h3.category-title {
    font-size: 1.6em;
    color: #0056b3;
    margin-top: 1.5em;
    margin-bottom: 0.8em;
    padding-bottom: 0.2em;
    border-bottom: 1px dashed #007BFF;
  }
  /* 目次 (TOC) */
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
    margin-top: 1em;
  }
  .toc li {
    margin: 0.5em 0;
  }
  .toc li.category {
    font-weight: bold;
    color: #0056b3;
  }
  .toc li.category + ul {
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
  /* FAQ アイテム (アコーディオン) */
  details.faq-item {
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 0.8em 1em;
    margin-bottom: 1em;
    background: #fafafa;
    transition: transform 0.3s ease, box-shadow 0.3s ease;
  }
  details.faq-item:hover {
    transform: translateY(-3px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
  }
  details.faq-item[open] {
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  }
  summary.faq-question {
    font-size: 1.3em;
    font-weight: 700;
    cursor: pointer;
    outline: none;
    padding: 0.5em;
    transition: background-color 0.3s ease, transform 0.3s ease;
  }
  summary.faq-question:hover {
    background-color: #e6f0ff;
    transform: translateY(-3px);
  }
  summary.faq-question::-webkit-details-marker {
    display: none;
  }
  .faq-answer {
    margin-top: 0.8em;
    padding-left: 1em;
    border-left: 3px solid #007BFF;
  }
</style>

<div class="page-content">
  <h2 class="section-title">よくある質問</h2>

  <!-- 目次 (TOC) -->
  <div class="toc">
    <h3>目次</h3>
    <ul>
      <li class="category">【全般】</li>
      <ul>
        <li><a href="#faq-overview">ソフトウェアの概要は？</a></li>
        <li><a href="#faq-environment">必要な動作環境は？</a></li>
        <li><a href="#faq-target">このソフトは誰向けですか？</a></li>
        <li><a href="#faq-install">インストール方法は？</a></li>
        <li><a href="#faq-update">アップデートは自動ですか？</a></li>
        <li><a href="#faq-license">ライセンスはどうなっていますか？</a></li>
        <li><a href="#faq-price">利用料金は？</a></li>
        <li><a href="#faq-support-overall">サポート体制は？</a></li>
      </ul>
      <li class="category">【動画編集関連】</li>
      <ul>
        <li><a href="#faq-basic-edit">動画編集の基本操作は？</a></li>
        <li><a href="#faq-advanced-edit">高度な編集のコツは？</a></li>
        <li><a href="#faq-template">編集用テンプレートはありますか？</a></li>
        <li><a href="#faq-format">動画フォーマットの選び方は？</a></li>
        <li><a href="#faq-effect">エフェクトの適用方法は？</a></li>
        <li><a href="#faq-audio">音声調整はどうすればよいですか？</a></li>
        <li><a href="#faq-subtitle">字幕の追加方法は？</a></li>
        <li><a href="#faq-save">保存形式の推奨は？</a></li>
      </ul>
      <li class="category">【台本取得・設定】</li>
      <ul>
        <li><a href="#faq-script-retrieval">台本取得は自動で行えますか？</a></li>
        <li><a href="#faq-script-format">台本のフォーマット調整方法は？</a></li>
        <li><a href="#faq-script-storage">取得した台本はどこに保存されますか？</a></li>
        <li><a href="#faq-script-edit">台本はどのように編集できますか？</a></li>
        <li><a href="#faq-script-effect">台本にエフェクトは適用されますか？</a></li>
        <li><a href="#faq-script-autocomplete">自動補完機能はありますか？</a></li>
        <li><a href="#faq-script-error">台本エラーの修正方法は？</a></li>
        <li><a href="#faq-script-default">デフォルト設定の変更は可能ですか？</a></li>
      </ul>
      <li class="category">【設定・カスタマイズ】</li>
      <ul>
        <li><a href="#faq-ui-custom">ユーザーインターフェースのカスタマイズは？</a></li>
        <li><a href="#faq-notification">通知設定の変更方法は？</a></li>
        <li><a href="#faq-theme">カラーテーマの選択は可能ですか？</a></li>
        <li><a href="#faq-shortcut">ショートカットキーの設定は？</a></li>
        <li><a href="#faq-reset">初期設定のリセット方法は？</a></li>
        <li><a href="#faq-account">アカウント設定はどこで行いますか？</a></li>
        <li><a href="#faq-plugin">プラグインの利用は可能ですか？</a></li>
        <li><a href="#faq-performance">動作速度向上の設定はありますか？</a></li>
      </ul>
      <li class="category">【トラブルシューティング】</li>
      <ul>
        <li><a href="#faq-error">エラー発生時の対処法は？</a></li>
        <li><a href="#faq-startup">ソフトウェアが起動しない場合は？</a></li>
        <li><a href="#faq-slow">動作が遅い場合の対策は？</a></li>
        <li><a href="#faq-display">画面が表示されない場合は？</a></li>
        <li><a href="#faq-file">ファイルが読み込めない場合は？</a></li>
        <li><a href="#faq-save-issue">設定が保存されない場合は？</a></li>
        <li><a href="#faq-update-fail">アップデートに失敗した場合は？</a></li>
        <li><a href="#faq-support-contact">サポート問い合わせ時の注意点は？</a></li>
      </ul>
    </ul>
  </div>

  <!-- 【全般】 -->
  <h3 id="general" class="category-title">【全般】</h3>
  <details id="faq-overview" class="faq-item">
    <summary class="faq-question">ソフトウェアの概要は？</summary>
    <div class="faq-answer">
      <p>
        ゆっくりまとめプロセッサーは、動画編集の半自動化を実現するツールです。運営実績を活かし、台本・画像・スレッド情報を瞬時に取得して、効率的な動画制作をサポートします。
      </p>
    </div>
  </details>
  <details id="faq-environment" class="faq-item">
    <summary class="faq-question">必要な動作環境は？</summary>
    <div class="faq-answer">
      <p>
        推奨環境は Windows 10 以上または macOS 10.15 以上です。最新のブラウザや動画編集ソフトがインストールされていることが望ましいです。
      </p>
    </div>
  </details>
  <details id="faq-target" class="faq-item">
    <summary class="faq-question">このソフトは誰向けですか？</summary>
    <div class="faq-answer">
      <p>
        主に動画配信者、動画クリエイター、未経験者、副業を検討している社会人向けに設計されています。直感的な操作で初心者にも扱いやすいのが特徴です。
      </p>
    </div>
  </details>
  <details id="faq-install" class="faq-item">
    <summary class="faq-question">インストール方法は？</summary>
    <div class="faq-answer">
      <p>
        インストールは公式サイトから最新のインストーラーをダウンロードし、ウィザードに従って簡単に行えます。
      </p>
    </div>
  </details>
  <details id="faq-update" class="faq-item">
    <summary class="faq-question">アップデートは自動ですか？</summary>
    <div class="faq-answer">
      <p>
        はい、最新バージョンは自動アップデート機能により随時更新されます。また、手動でアップデートを確認することも可能です。
      </p>
    </div>
  </details>
  <details id="faq-license" class="faq-item">
    <summary class="faq-question">ライセンスはどうなっていますか？</summary>
    <div class="faq-answer">
      <p>
        当ソフトウェアはフリーウェアとして提供されており、商用利用も可能ですが、再配布や改変に関しては公式ガイドラインに従ってください。
      </p>
    </div>
  </details>
  <details id="faq-price" class="faq-item">
    <summary class="faq-question">利用料金は？</summary>
    <div class="faq-answer">
      <p>
        基本的な機能は無料でご利用いただけます。有料のプレミアム機能も用意されており、詳細は購入ページをご参照ください。
      </p>
    </div>
  </details>
  <details id="faq-support-overall" class="faq-item">
    <summary class="faq-question">サポート体制はどうなっていますか？</summary>
    <div class="faq-answer">
      <p>
        サポートは公式サイトのお問い合わせフォームおよびメール（fujita.otm@gmail.com）で受け付けております。オンラインFAQもご利用ください。
      </p>
    </div>
  </details>

  <!-- 【動画編集関連】 -->
  <h3 id="video" class="category-title">【動画編集関連】</h3>
  <details id="faq-basic-edit" class="faq-item">
    <summary class="faq-question">動画編集の基本操作は？</summary>
    <div class="faq-answer">
      <p>
        動画のトリミング、結合、テキスト挿入などの基本操作は、直感的なUIで簡単に実行できます。各ボタン操作で迅速に編集できます。
      </p>
    </div>
  </details>
  <details id="faq-advanced-edit" class="faq-item">
    <summary class="faq-question">高度な編集のコツは？</summary>
    <div class="faq-answer">
      <p>
        エフェクトの適用、色調補正、テンプレートの利用などを駆使すると、プロフェッショナルな仕上がりになります。事前にプリセットを設定することをおすすめします。
      </p>
    </div>
  </details>
  <details id="faq-template" class="faq-item">
    <summary class="faq-question">編集用テンプレートはありますか？</summary>
    <div class="faq-answer">
      <p>
        はい、標準テンプレートがいくつか用意されています。ユーザー独自のテンプレートも作成・保存可能です。
      </p>
    </div>
  </details>
  <details id="faq-format" class="faq-item">
    <summary class="faq-question">動画フォーマットの選び方は？</summary>
    <div class="faq-answer">
      <p>
        目的に応じた解像度、フレームレート、圧縮形式を選択してください。設定画面で推奨フォーマットが表示されます。
      </p>
    </div>
  </details>
  <details id="faq-effect" class="faq-item">
    <summary class="faq-question">エフェクトの適用方法は？</summary>
    <div class="faq-answer">
      <p>
        各種エフェクトは、専用のエフェクトパネルからドラッグ＆ドロップで適用できます。効果のプレビューも可能です。
      </p>
    </div>
  </details>
  <details id="faq-audio" class="faq-item">
    <summary class="faq-question">音声調整はどうすればよいですか？</summary>
    <div class="faq-answer">
      <p>
        音声レベルの調整、ノイズ除去、エコー効果などは、音声編集ツールで簡単に行えます。基本設定を利用するか、詳細設定で微調整してください。
      </p>
    </div>
  </details>
  <details id="faq-subtitle" class="faq-item">
    <summary class="faq-question">字幕の追加方法は？</summary>
    <div class="faq-answer">
      <p>
        字幕はテキスト入力欄から直接入力するか、外部ファイルをインポートして追加できます。自動生成機能も搭載しています。
      </p>
    </div>
  </details>
  <details id="faq-save" class="faq-item">
    <summary class="faq-question">保存形式の推奨は？</summary>
    <div class="faq-answer">
      <p>
        編集後の動画は、一般的なMP4形式が推奨されます。高品質保存のため、ビットレートの調整が可能です。
      </p>
    </div>
  </details>

  <!-- 【台本取得・設定】 -->
  <h3 id="script" class="category-title">【台本取得・設定】</h3>
  <details id="faq-script-retrieval" class="faq-item">
    <summary class="faq-question">台本取得は自動で行えますか？</summary>
    <div class="faq-answer">
      <p>
        はい、サイトやまとめ掲示板から台本を自動で取得し、編集に利用できる形式に整形します。取得先は設定で変更可能です。
      </p>
    </div>
  </details>
  <details id="faq-script-format" class="faq-item">
    <summary class="faq-question">台本のフォーマット調整方法は？</summary>
    <div class="faq-answer">
      <p>
        台本の不要部分の削除や、改行・インデントの調整を自動で行い、動画編集に適した形式に整えます。
      </p>
    </div>
  </details>
  <details id="faq-script-storage" class="faq-item">
    <summary class="faq-question">取得した台本はどこに保存されますか？</summary>
    <div class="faq-answer">
      <p>
        取得した台本はローカルの指定フォルダまたはクラウドストレージに自動保存され、後から編集可能です。
      </p>
    </div>
  </details>
  <details id="faq-script-edit" class="faq-item">
    <summary class="faq-question">台本はどのように編集できますか？</summary>
    <div class="faq-answer">
      <p>
        取得した台本は、内蔵エディタで直接編集可能です。また、テンプレート適用機能で自動補正も行えます。
      </p>
    </div>
  </details>
  <details id="faq-script-effect" class="faq-item">
    <summary class="faq-question">台本にエフェクトは適用されますか？</summary>
    <div class="faq-answer">
      <p>
        基本的には台本のテキスト情報のみですが、特定のキーワードに対して自動でスタイルが適用されるオプションがあります。
      </p>
    </div>
  </details>
  <details id="faq-script-autocomplete" class="faq-item">
    <summary class="faq-question">自動補完機能はありますか？</summary>
    <div class="faq-answer">
      <p>
        はい、入力中の台本に対して、自動補完機能が搭載されています。キーワードや定型文を自動で提案します。
      </p>
    </div>
  </details>
  <details id="faq-script-default" class="faq-item">
    <summary class="faq-question">デフォルト設定の変更は可能ですか？</summary>
    <div class="faq-answer">
      <p>
        はい、台本取得と編集に関する初期設定は、専用の設定画面から変更できます。
      </p>
    </div>
  </details>

  <!-- 【設定・カスタマイズ】 -->
  <h3 id="custom" class="category-title">【設定・カスタマイズ】</h3>
  <details id="faq-ui-custom" class="faq-item">
    <summary class="faq-question">ユーザーインターフェースのカスタマイズは？</summary>
    <div class="faq-answer">
      <p>
        配色、レイアウト、フォントサイズなど、さまざまなUI要素を設定画面から自由に調整できます。
      </p>
    </div>
  </details>
  <details id="faq-notification" class="faq-item">
    <summary class="faq-question">通知設定の変更方法は？</summary>
    <div class="faq-answer">
      <p>
        通知は、アプリ内の設定画面からメールやプッシュ通知など、各種オプションをオン／オフできます。
      </p>
    </div>
  </details>
  <details id="faq-theme" class="faq-item">
    <summary class="faq-question">カラーテーマの選択は可能ですか？</summary>
    <div class="faq-answer">
      <p>
        はい、複数のカラーテーマから選択可能で、ユーザーの好みに合わせて変更できます。
      </p>
    </div>
  </details>
  <details id="faq-shortcut" class="faq-item">
    <summary class="faq-question">ショートカットキーの設定は？</summary>
    <div class="faq-answer">
      <p>
        ショートカットキーは、設定画面でカスタマイズ可能です。主要な操作のショートカットが予め用意されています。
      </p>
    </div>
  </details>
  <details id="faq-reset" class="faq-item">
    <summary class="faq-question">初期設定のリセット方法は？</summary>
    <div class="faq-answer">
      <p>
        設定画面内の「リセット」ボタンをクリックすることで、全てのカスタマイズ設定を初期状態に戻せます。
      </p>
    </div>
  </details>
  <details id="faq-account" class="faq-item">
    <summary class="faq-question">アカウント設定はどこで行いますか？</summary>
    <div class="faq-answer">
      <p>
        アカウント設定は、ユーザー情報ページから変更可能です。メールアドレスやパスワードの更新もここから行えます。
      </p>
    </div>
  </details>
  <details id="faq-plugin" class="faq-item">
    <summary class="faq-question">プラグインの利用は可能ですか？</summary>
    <div class="faq-answer">
      <p>
        一部のサードパーティ製プラグインが利用可能です。詳細は公式ドキュメントをご参照ください。
      </p>
    </div>
  </details>
  <details id="faq-performance" class="faq-item">
    <summary class="faq-question">動作速度向上の設定はありますか？</summary>
    <div class="faq-answer">
      <p>
        はい、キャッシュやグラフィック設定の最適化オプションが設定画面から利用可能です。
      </p>
    </div>
  </details>

  <!-- 【トラブルシューティング】 -->
  <h3 id="trouble" class="category-title">【トラブルシューティング】</h3>
  <details id="faq-error" class="faq-item">
    <summary class="faq-question">エラー発生時の対処法は？</summary>
    <div class="faq-answer">
      <p>
        エラーメッセージに従い、システムの再起動や設定の見直しを行ってください。解決しない場合は、サポートにお問い合わせください。
      </p>
    </div>
  </details>
  <details id="faq-startup" class="faq-item">
    <summary class="faq-question">ソフトウェアが起動しない場合は？</summary>
    <div class="faq-answer">
      <p>
        起動しない場合は、システム要件の再確認、ソフトウェアの再インストール、または最新アップデートの適用を試みてください。
      </p>
    </div>
  </details>
  <details id="faq-slow" class="faq-item">
    <summary class="faq-question">動作が遅い場合の対策は？</summary>
    <div class="faq-answer">
      <p>
        動作が遅い場合は、不要なバックグラウンドアプリケーションの停止、設定の最適化、またはシステムのアップグレードを検討してください。
      </p>
    </div>
  </details>
  <details id="faq-display" class="faq-item">
    <summary class="faq-question">画面が表示されない場合は？</summary>
    <div class="faq-answer">
      <p>
        グラフィックドライバの更新、またはソフトウェアの再起動を試してください。解決しない場合は、サポートにご相談ください。
      </p>
    </div>
  </details>
  <details id="faq-file" class="faq-item">
    <summary class="faq-question">ファイルが読み込めない場合は？</summary>
    <div class="faq-answer">
      <p>
        ファイル形式の互換性、またはファイル自体の破損が原因の場合があります。別のファイルで再試行するか、サポートへご連絡ください。
      </p>
    </div>
  </details>
  <details id="faq-save-issue" class="faq-item">
    <summary class="faq-question">設定が保存されない場合は？</summary>
    <div class="faq-answer">
      <p>
        設定保存時にエラーが発生した場合は、権限設定やディスク容量を確認してください。必要に応じて再インストールをお試しください。
      </p>
    </div>
  </details>
  <details id="faq-update-fail" class="faq-item">
    <summary class="faq-question">アップデートに失敗した場合は？</summary>
    <div class="faq-answer">
      <p>
        アップデートエラーが発生した場合、手動でのアップデートや公式サポートへの問い合わせをおすすめします。
      </p>
    </div>
  </details>
  <details id="faq-support-contact" class="faq-item">
    <summary class="faq-question">サポート問い合わせ時の注意点は？</summary>
    <div class="faq-answer">
      <p>
        問い合わせの際は、発生しているエラーの詳細、使用環境、再現手順などを明記すると、より迅速な対応が期待できます。
      </p>
    </div>
  </details>
</div>
