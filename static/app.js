async function loadMessages() {
  const r = await fetch('/api/messages');
  const xs = await r.json();

  document.querySelector('#messages').innerHTML = xs
    .map(x => {
      const reactions = x.reactions || {};

      return `
            <article class="message">
                <b>${escapeHtml(x.name)}</b>
                <p>${escapeHtml(x.message)}</p>
                <div class="meta">#${x.id}</div>

                <div class="reactions">
                    ${['👍', '❤️', '😂', '🔥']
                      .map(
                        emoji => `
                        <button class="reaction-btn"
                            onclick="toggleReaction(${x.id}, '${emoji}')">
                            ${emoji} ${reactions[emoji] || 0}
                        </button>
                    `
                      )
                      .join('')}
                </div>
            </article>
        `;
    })
    .join('');
}

// HTMLとして危険な文字を変換する
function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// リアクションの追加・取り消し
async function toggleReaction(id, emoji) {
  const r = await fetch(`/api/messages/${id}/reactions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ reaction: emoji }),
  });

  if (r.ok) {
    await loadMessages();
  }
}

const messageInput = document.querySelector('#message');
const charCount = document.querySelector('#char-count');

// 入力されるたびに文字数を更新
messageInput.addEventListener('input', () => {
  charCount.textContent = `${messageInput.value.length}/300`;
});

// 投稿処理
document.querySelector('#form').addEventListener('submit', async e => {
  e.preventDefault();

  const name = document.querySelector('#name').value;
  const message = messageInput.value;

  const r = await fetch('/api/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name, message }),
  });

  document.querySelector('#status').textContent = r.ok
    ? '投稿しました！'
    : '投稿に失敗しました';

  if (r.ok) {
    messageInput.value = '';
    charCount.textContent = '0/300'; // 送信成功時に文字数表示もリセット
    await loadMessages();
  }
});

loadMessages();

let productsById = new Map();
let selectedProductId = null;

// 商品一覧を読み込む
async function loadProducts() {
  const r = await fetch('/api/products');
  const products = await r.json();
  productsById = new Map(products.map(product => [product.id, product]));

  document.querySelector('#products').innerHTML = products
    .map(p => `
      <article class="message product">
        <img src="${escapeHtml(p.image)}" alt="商品画像">
        <h3>${escapeHtml(p.name)}</h3>
        <p class="price">${Number(p.price).toLocaleString()}円</p>
        <p>${escapeHtml(p.description)}</p>
        ${p.sold ? '<p class="sold-label">売り切れ</p>' : ''}
        <button type="button" class="detail-btn"
            onclick="openProductDetails(${p.id})">商品を見る</button>
        ${p.sold
          ? ''
          : `<button type="button" class="cancel-listing-btn"
              onclick="cancelListing(${p.id})">出品を取り消す</button>`}
      </article>
    `)
    .join('');
}

// 商品詳細とコメント欄を表示
async function openProductDetails(productId) {
  const product = productsById.get(productId);
  if (!product) {
    document.querySelector('#purchase-status').textContent =
      '商品を表示できませんでした。商品一覧を再読み込みしてください。';
    return;
  }

  selectedProductId = productId;
  document.querySelector('#products').hidden = true;
  document.querySelector('#product-detail').hidden = false;
  document.querySelector('#product-detail-content').innerHTML = `
    <img src="${escapeHtml(product.image)}" alt="商品画像">
    <h2>${escapeHtml(product.name)}</h2>
    <p class="price">${Number(product.price).toLocaleString()}円</p>
    <p>${escapeHtml(product.description)}</p>
    ${product.sold
      ? '<p class="sold-label">売り切れ</p>'
      : ''}
    ${product.sold
      ? ''
      : `<button type="button" class="cancel-listing-btn"
          onclick="cancelListing(${product.id})">出品を取り消す</button>`}
  `;
  document.querySelector('#purchase-form').hidden = product.sold;
  document.querySelector('#purchase-status').textContent = '';
  document.querySelector('#comment-status').textContent = '';
  document.querySelector('#product-comments').textContent = 'コメントを読み込み中...';
  await loadProductComments(productId);
}

document.querySelector('#purchase-form').addEventListener('submit', event => {
  event.preventDefault();
  if (selectedProductId !== null) {
    purchaseProduct(selectedProductId);
  }
});

async function cancelListing(productId) {
  if (!window.confirm('この商品の出品を取り消しますか？')) {
    return;
  }

  const r = await fetch(`/api/products/${productId}`, { method: 'DELETE' });
  if (!r.ok) {
    const result = await r.json();
    document.querySelector('#product-status').textContent =
      result.error || '出品の取り消しに失敗しました';
    await loadProducts();
    return;
  }

  selectedProductId = null;
  document.querySelector('#product-detail').hidden = true;
  document.querySelector('#products').hidden = false;
  document.querySelector('#product-status').textContent = '出品を取り消しました';
  await loadProducts();
}

async function loadProductComments(productId) {
  const r = await fetch(`/api/products/${productId}/comments`);
  const comments = await r.json();
  const section = document.querySelector('#product-comments');

  if (!r.ok) {
    document.querySelector('#comment-status').textContent =
      comments.error || 'コメントを読み込めませんでした';
    return;
  }

  section.innerHTML = comments.length
    ? comments.map(comment => `
      <article class="message">
        <b>${escapeHtml(comment.name)}</b>
        <p>${escapeHtml(comment.comment)}</p>
        <p class="meta">${escapeHtml(new Date(comment.created_at).toLocaleString('ja-JP'))}</p>
      </article>
    `).join('')
    : '<p>まだコメントはありません。</p>';
}

document.querySelector('#back-to-products').addEventListener('click', () => {
  selectedProductId = null;
  document.querySelector('#product-detail').hidden = true;
  document.querySelector('#products').hidden = false;
});

document.querySelector('#product-comment-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (selectedProductId === null) {
    return;
  }

  const status = document.querySelector('#comment-status');
  const r = await fetch(`/api/products/${selectedProductId}/comments`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      name: document.querySelector('#comment-name').value,
      comment: document.querySelector('#product-comment').value,
    }),
  });
  const result = await r.json();

  if (r.ok) {
    status.textContent = 'コメントを投稿しました';
    document.querySelector('#product-comment').value = '';
    await loadProductComments(selectedProductId);
  } else {
    status.textContent = result.error || 'コメントの投稿に失敗しました';
  }
});

// 商品を購入して注文を記録
async function purchaseProduct(productId) {
  const buyerName = document.querySelector('#buyer-name').value.trim();
  const status = document.querySelector('#purchase-status');

  if (!buyerName) {
    status.textContent = '購入者名を入力してください';
    document.querySelector('#buyer-name').focus();
    return;
  }

  const r = await fetch(`/api/products/${productId}/purchase`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ buyer_name: buyerName }),
  });
  const result = await r.json();

  if (r.ok) {
    document.querySelector('#history-buyer-name').value = buyerName;
    await loadProducts();
    if (
      selectedProductId === productId &&
      !document.querySelector('#products-panel').hidden
    ) {
      await openProductDetails(productId);
    }
    status.textContent =
      `購入しました。注文番号 #${result.id}（${result.product_name}）`;
    if (!document.querySelector('#history-panel').hidden) {
      await loadPurchaseHistory();
    }
  } else {
    if (r.status === 409) {
      await loadProducts();
      if (
        selectedProductId === productId &&
        !document.querySelector('#products-panel').hidden
      ) {
        await openProductDetails(productId);
      }
    }
    status.textContent = result.error || '購入に失敗しました';
  }
}

// 購入者名に一致する注文履歴を表示
async function loadPurchaseHistory() {
  const buyerName = document.querySelector('#history-buyer-name').value.trim();
  const status = document.querySelector('#history-status');
  const history = document.querySelector('#purchase-history');

  if (!buyerName) {
    status.textContent = '購入者名を入力してください';
    history.innerHTML = '';
    document.querySelector('#history-buyer-name').focus();
    return;
  }

  const params = new URLSearchParams({ buyer_name: buyerName });
  const r = await fetch(`/api/orders?${params}`);
  const orders = await r.json();

  if (!r.ok) {
    status.textContent = orders.error || '購入履歴を読み込めませんでした';
    return;
  }

  status.textContent = orders.length ? '' : '購入履歴はありません';
  history.innerHTML = orders
    .map(order => `
      <article class="message">
        <h3>${escapeHtml(order.product_name)}</h3>
        <p class="price">${Number(order.price).toLocaleString()}円</p>
        <p class="meta">注文番号 #${order.id} ・
          ${escapeHtml(new Date(order.created_at).toLocaleString('ja-JP'))}
        </p>
      </article>
    `)
    .join('');
}

// 商品一覧と購入履歴のタブ切り替え
function selectProductTab(selectedTab) {
  const tabs = [
    { button: document.querySelector('#products-tab'), panel: document.querySelector('#products-panel') },
    { button: document.querySelector('#history-tab'), panel: document.querySelector('#history-panel') },
  ];

  tabs.forEach(({ button, panel }) => {
    const selected = button === selectedTab;
    button.setAttribute('aria-selected', String(selected));
    panel.hidden = !selected;
  });

  if (selectedTab.id === 'history-tab') {
    loadPurchaseHistory();
  }
}

document.querySelector('#products-tab').addEventListener('click', event => {
  document.querySelector('#product-detail').hidden = true;
  document.querySelector('#products').hidden = false;
  selectedProductId = null;
  selectProductTab(event.currentTarget);
});
document.querySelector('#history-tab').addEventListener('click', event => {
  selectProductTab(event.currentTarget);
});
document.querySelector('#load-history').addEventListener('click', loadPurchaseHistory);

// 商品の出品処理
document.querySelector('#product-form').addEventListener('submit', async e => {
  e.preventDefault();

  const formData = new FormData();
  formData.append('name', document.querySelector('#product-name').value);
  formData.append('price', document.querySelector('#price').value);
  formData.append('description', document.querySelector('#description').value);
  formData.append('image', document.querySelector('#image').files[0]);

  const r = await fetch('/api/products', {
    method: 'POST',
    body: formData
  });

  const status = document.querySelector('#product-status');

  if (r.ok) {
    status.textContent = '商品を出品しました！';
    document.querySelector('#product-form').reset();
    await loadProducts();
  } else {
    const result = await r.json();
    status.textContent = result.error || '出品に失敗しました';
  }
});

// 商品一覧を最初に表示
loadProducts();