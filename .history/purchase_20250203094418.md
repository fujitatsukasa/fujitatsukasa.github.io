---
layout: page
title: 購入ページ
permalink: /purchase/
---

# 商品購入

<div class="products-container pattern1 advanced">
  
  <div class="product-card">
    <h2>ゆっくりまとめプロセッサー</h2>
    <img src="/assets/img/product1.jpg" alt="ゆっくりまとめプロセッサー">
    <div class="description">
      <p>「ゆっくりまとめプロセッサー」は、あなたのコンテンツを効率的に整理し、魅力的な形で提供するための強力なツールです。以下の機能を備えています：</p>
      <ul>
        <li>自動整理: コンテンツを自動的にカテゴライズ</li>
        <li>カスタマイズ可能: ユーザーのニーズに合わせて調整可能</li>
        <li>高速処理: 大量のデータも迅速に処理</li>
      </ul>
    </div>
    <div class="purchase-details">
      <div class="price">¥5,000</div>
      <!-- markdownlint-disable MD033 -->
      <form class="purchase-form" action="javascript:void(0);" method="POST">
        <div class="form-group">
          <label for="user-id-1">ユーザーID:</label>
          <input type="text" id="user-id-1" name="custom" required>
        </div>
        <div class="form-group">
          <button type="button" class="btn btn-primary open-modal" data-product="1">購入する</button>
        </div>
      </form>
      <!-- markdownlint-enable MD033 -->
    </div>
  </div>

  <div class="product-card">
    <h2>ゆっくり編集ツール</h2>
    <img src="/assets/img/product2.jpg" alt="ゆっくり編集ツール">
    <div class="description">
      <p>「ゆっくり編集ツール」は、コンテンツの編集作業を簡素化し、効率化するためのツールです。以下の機能を提供します：</p>
      <ul>
        <li>直感的なインターフェース: 誰でも簡単に操作可能</li>
        <li>リアルタイムプレビュー: 編集内容を即座に確認</li>
        <li>多機能エディタ: 豊富な編集オプションを提供</li>
      </ul>
    </div>
    <div class="purchase-details">
      <div class="price">¥3,000</div>
      <!-- markdownlint-disable MD033 -->
      <form class="purchase-form" action="javascript:void(0);" method="POST">
        <div class="form-group">
          <label for="user-id-2">ユーザーID:</label>
          <input type="text" id="user-id-2" name="custom" required>
        </div>
        <div class="form-group">
          <button type="button" class="btn btn-primary open-modal" data-product="2">購入する</button>
        </div>
      </form>
      <!-- markdownlint-enable MD033 -->
    </div>
  </div>
  
</div>

<!-- エラーメッセージ表示用 -->
<div id="error-message" class="error-message">
  IDを入力してください。
</div>

<!-- モーダルウィンドウ -->
<div id="purchase-modal" class="modal">
  <div class="modal-content">
    <span class="close">&times;</span>
    <h3>購入確認</h3>
    <p id="modal-product-name"></p>
    <p>ユーザーID: <span id="modal-user-id"></span></p>
    <button id="confirm-purchase" class="btn btn-success">確定する</button>
  </div>
</div>

<!-- カスタムスクリプト -->
<script>
  // フォーム送信前のバリデーションは、モーダルを起動する前に行う
  document.querySelectorAll('.open-modal').forEach(function(button) {
    button.addEventListener('click', function() {
      var form = button.closest('.purchase-form');
      var userIdInput = form.querySelector('input[name="custom"]');
      var userId = userIdInput.value.trim();
      var errorMessage = document.getElementById('error-message');
      if (userId === "") {
        errorMessage.style.display = 'block';
        userIdInput.focus();
        return;
      } else {
        errorMessage.style.display = 'none';
      }
      
      // モーダルの内容を更新
      var productId = button.getAttribute('data-product');
      var productName = (productId === "1") ? "ゆっくりまとめプロセッサー" : "ゆっくり編集ツール";
      document.getElementById('modal-product-name').innerText = productName;
      document.getElementById('modal-user-id').innerText = userId;
      
      // モーダルを表示
      document.getElementById('purchase-modal').style.display = 'block';
    });
  });

  // モーダルのクローズ処理
  document.querySelector('.modal .close').addEventListener('click', function() {
    document.getElementById('purchase-modal').style.display = 'none';
  });

  // モーダル外クリックで閉じる
  window.addEventListener('click', function(event) {
    var modal = document.getElementById('purchase-modal');
    if (event.target == modal) {
      modal.style.display = 'none';
    }
  });

  // 確定ボタン押下時にStripeのリンクへリダイレクト
  document.getElementById('confirm-purchase').addEventListener('click', function() {
    // モーダル表示中の商品に応じたリンクへ遷移
    // ※本番ではサーバーサイドでStripe Checkout セッションを作成するなどの処理が必要
    var modalProductName = document.getElementById('modal-product-name').innerText;
    var stripeLink = (modalProductName === "ゆっくりまとめプロセッサー") 
                     ? "YOUR_STRIPE_PAYMENT_LINK_1" 
                     : "YOUR_STRIPE_PAYMENT_LINK_2";
    window.open(stripeLink, '_blank');
    document.getElementById('purchase-modal').style.display = 'none';
  });
</script>
